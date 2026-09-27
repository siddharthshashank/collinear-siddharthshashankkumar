"""Fit hidden skills from ball-by-ball history, then simulate fixtures."""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.model import (  # noqa: E402
    MatchSimulator,
    PACE,
    SkillBook,
    load_public_model,
)
from engine.league_io import load_league  # noqa: E402


def _public_logits(model, balls):
    over_arr = balls.over.to_numpy()
    pos_arr = balls.position.to_numpy()
    wick_arr = balls.wickets_before.to_numpy()
    runs_arr = balls.runs_before.to_numpy()
    target_arr = balls.target.to_numpy().astype(float)
    innings_arr = balls.innings.to_numpy()
    ball_in_over = balls.ball.to_numpy()
    ball_num = over_arr * 6 + ball_in_over
    chasing = (innings_arr == 2).astype(float)

    cal = model.cal
    par = cal.par_rate[over_arr]
    need = np.maximum(target_arr - runs_arr, 1.0) / np.maximum((120 - ball_num) / 6.0, 1.0 / 6.0)
    press = np.where(chasing > 0, np.clip(np.log(need / par), -1.0, 1.2), 0.0)

    z_public = (
        cal.over_logits[over_arr]
        + cal.position_vectors[pos_arr]
        + (wick_arr - cal.typical_wickets[over_arr])[:, None] * cal.wickets_vector
        + chasing[:, None] * cal.second_innings_vector
        + press[:, None] * cal.pressure_vector
    )
    return z_public, chasing


class _Fitter:
    """Coordinate-Newton MAP fit of the hidden skills.

    Every ball's logits are z_public + sum_k s_ki d_k over the five fixed directions
    (bat_style, bat_quality, bowl_type, bowl_quality, conditions). Each hidden parameter
    contributes to one direction; we update one parameter group at a time and refresh
    the residual after each update so stale-gradient interactions between shared-direction
    groups do not blow up.
    """

    def __init__(self, model, history):
        self.model = model
        self.history = history
        balls = history.balls
        self.N = len(balls)
        self.n_players = len(history.players.role)
        self.n_venues = len(history.venues.pitch)
        self.n_seasons = int(history.seasons)

        self.batter = balls.batter.to_numpy()
        self.bowler = balls.bowler.to_numpy()
        self.venue = balls.venue.to_numpy()
        self.season = balls.season.to_numpy()
        self.match = balls.match.to_numpy()
        self.bat_team = balls.batting_team.to_numpy()
        self.outcome = balls.outcome.to_numpy()

        self.z_public, self.chasing = _public_logits(model, balls)

        self.bstyle = np.asarray(history.players.style[self.bowler])
        self.bhand = np.asarray(history.players.hand[self.batter])
        self.vpitch = np.asarray(history.venues.pitch[self.venue])
        self.at_home = (history.venues.home_team[self.venue] == self.bat_team).astype(float)

        self.d_bs = model.bs
        self.d_bq = model.bq
        self.d_wt = model.wt
        self.d_wq = model.wq
        self.d_c = model.c

        self.n_matches = int(self.match.max()) + 1

        self.style_p = np.zeros(self.n_players)
        self.q_pace = np.zeros(self.n_players)
        self.q_spin = np.zeros(self.n_players)
        self.kind_p = np.zeros(self.n_players)
        self.bowl_q = np.zeros(self.n_players)
        self.venue_level = np.zeros(self.n_venues)
        self.venue_dew = np.zeros(self.n_venues)
        self.affinity = np.zeros((self.n_players, self.n_venues))
        self.home_lift = 0.0
        self.era_season = np.zeros(self.n_seasons)
        self.wear = 0.0
        self.pitch_day = np.zeros(self.n_matches)
        self.type_table = np.zeros((2, 2))
        self.pitch_table = np.zeros((2, 3))

        self.pace_mask = (self.bstyle == PACE).astype(float)
        self.spin_mask = 1.0 - self.pace_mask
        self.onehot = np.zeros((self.N, 6))
        self.onehot[np.arange(self.N), self.outcome] = 1.0
        self.bv_idx = self.batter * self.n_venues + self.venue
        self.tt_idx = self.bhand * 2 + self.bstyle
        self.pt_idx = self.bstyle * 3 + self.vpitch

    def _s_c(self):
        return (
            self.venue_level[self.venue]
            + self.era_season[self.season]
            + (self.venue_dew[self.venue] - self.wear) * self.chasing
            + self.pitch_day[self.match]
            + self.affinity[self.batter, self.venue]
            + self.home_lift * self.at_home
            + self.type_table[self.bhand, self.bstyle]
            - self.pitch_table[self.bstyle, self.vpitch]
        )

    def _refresh(self):
        z = (
            self.z_public
            + self.style_p[self.batter, None] * self.d_bs
            + (self.pace_mask * self.q_pace[self.batter] + self.spin_mask * self.q_spin[self.batter])[:, None] * self.d_bq
            + self.kind_p[self.bowler, None] * self.d_wt
            + self.bowl_q[self.bowler, None] * self.d_wq
            + self._s_c()[:, None] * self.d_c
        )
        z -= z.max(axis=1, keepdims=True)
        ez = np.exp(z)
        p = ez / ez.sum(axis=1, keepdims=True)
        self.p = p
        self.r = self.onehot - p

    def _proj(self, d):
        p = self.p
        return self.r @ d, (p @ (d * d)) - (p @ d) ** 2

    def _update_indexed(self, param, idx, grad, info, prec, minlen, damping=1.0):
        num = np.bincount(idx, weights=grad, minlength=minlen)
        den = np.bincount(idx, weights=info, minlength=minlen)
        step = (num - prec * param) / (den + prec)
        return param + damping * step

    def _update_matrix(self, mat, flat_idx, grad, info, prec, shape, damping=1.0):
        num = np.bincount(flat_idx, weights=grad, minlength=shape[0] * shape[1]).reshape(shape)
        den = np.bincount(flat_idx, weights=info, minlength=shape[0] * shape[1]).reshape(shape)
        return mat + damping * (num - prec * mat) / (den + prec)

    def _update_scalar(self, x, coef, prec, damping=1.0):
        # scalar x contributes coef * d_c per ball
        g, h = self._proj(self.d_c)
        num = np.sum(g * coef)
        den = np.sum(h * (coef * coef))
        return x + damping * (num - prec * x) / (den + prec)

    def fit(self, n_sweeps, priors):
        for _ in range(n_sweeps):
            # Direction bs: only style_p uses it.
            self._refresh()
            g, h = self._proj(self.d_bs)
            self.style_p = self._update_indexed(self.style_p, self.batter, g, h, priors["style"], self.n_players)

            # Direction bq: q_pace and q_spin (disjoint per-ball via masks). One refresh is enough.
            self._refresh()
            g, h = self._proj(self.d_bq)
            self.q_pace = self._update_indexed(self.q_pace, self.batter, g * self.pace_mask, h * self.pace_mask, priors["qp"], self.n_players)
            self.q_spin = self._update_indexed(self.q_spin, self.batter, g * self.spin_mask, h * self.spin_mask, priors["qs"], self.n_players)

            # Direction wt
            self._refresh()
            g, h = self._proj(self.d_wt)
            self.kind_p = self._update_indexed(self.kind_p, self.bowler, g, h, priors["kind"], self.n_players)

            # Direction wq
            self._refresh()
            g, h = self._proj(self.d_wq)
            self.bowl_q = self._update_indexed(self.bowl_q, self.bowler, g, h, priors["bq"], self.n_players)

            # Direction c: several parameter groups, all share the same direction.
            # Refresh between each to avoid stale-gradient blow-up.
            self._refresh()
            g, h = self._proj(self.d_c)
            self.venue_level = self._update_indexed(self.venue_level, self.venue, g, h, priors["vl"], self.n_venues)

            self._refresh()
            g, h = self._proj(self.d_c)
            self.era_season = self._update_indexed(self.era_season, self.season, g, h, priors["er"], self.n_seasons)

            self._refresh()
            g, h = self._proj(self.d_c)
            num = np.sum(g * self.at_home); den = np.sum(h * self.at_home)
            self.home_lift = self.home_lift + (num - priors["hl"] * self.home_lift) / (den + priors["hl"])

            self._refresh()
            g, h = self._proj(self.d_c)
            self.venue_dew = self._update_indexed(self.venue_dew, self.venue, g * self.chasing, h * self.chasing, priors["vd"], self.n_venues)

            self._refresh()
            g, h = self._proj(self.d_c)
            num = -np.sum(g * self.chasing); den = np.sum(h * self.chasing)
            self.wear = self.wear + (num - priors["we"] * self.wear) / (den + priors["we"])

            self._refresh()
            g, h = self._proj(self.d_c)
            self.type_table = self._update_matrix(self.type_table, self.tt_idx, g, h, priors["tt"], (2, 2))

            self._refresh()
            g, h = self._proj(self.d_c)
            self.pitch_table = self._update_matrix(self.pitch_table, self.pt_idx, -g, h, priors["pt"], (2, 3))

            self._refresh()
            g, h = self._proj(self.d_c)
            self.affinity = self._update_matrix(self.affinity, self.bv_idx, g, h, priors["af"], (self.n_players, self.n_venues))

            self._refresh()
            g, h = self._proj(self.d_c)
            self.pitch_day = self._update_indexed(self.pitch_day, self.match, g, h, priors["pd"], self.n_matches)


def fit_skillbook(model, history, n_sweeps=20):
    fitter = _Fitter(model, history)
    priors = {
        "style": 1.0 / 0.35 ** 2,
        "qp": 1.0 / 0.35 ** 2,
        "qs": 1.0 / 0.35 ** 2,
        "kind": 1.0 / 0.30 ** 2,
        "bq": 1.0 / 0.40 ** 2,
        "vl": 1.0 / 0.20 ** 2,
        "vd": 1.0 / 0.12 ** 2,
        "af": 1.0 / 0.12 ** 2,
        "hl": 1.0 / 0.10 ** 2,
        "er": 1.0 / 0.15 ** 2,
        "we": 1.0 / 0.06 ** 2,
        "pd": 1.0 / 0.12 ** 2,
        "tt": 1.0 / 0.08 ** 2,
        "pt": 1.0 / 0.08 ** 2,
    }
    fitter.fit(n_sweeps, priors)

    style_out = fitter.style_p.copy()
    quality_out = (fitter.q_pace + fitter.q_spin) / 2.0
    split_out = fitter.q_pace - fitter.q_spin
    # Era drifts slowly; linearly extrapolate one season ahead from the last two observed.
    era_arr = fitter.era_season
    if len(era_arr) >= 2:
        era_forecast = float(2 * era_arr[-1] - era_arr[-2])
    else:
        era_forecast = float(era_arr[-1])
    day_sd = max(0.03, float(np.std(fitter.pitch_day)))

    return SkillBook(
        history.players, history.venues,
        style_out, quality_out, split_out, fitter.kind_p.copy(), fitter.bowl_q.copy(),
        fitter.type_table.copy(), fitter.pitch_table.copy(),
        fitter.venue_level.copy(), fitter.venue_dew.copy(), fitter.affinity.copy(),
        float(fitter.home_lift), era_forecast, day_sd, float(fitter.wear),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=20260927)
    args = parser.parse_args()

    history, fixtures = load_league(args.league)
    model = load_public_model()
    book = fit_skillbook(model, history)
    sim = MatchSimulator(model)
    gen = np.random.default_rng(args.seed)
    rows = []
    for f in fixtures:
        p = sim.win_probability(book, f, args.sims, gen)
        p = min(max(p, 0.002), 0.998)
        rows.append((int(f.match), float(p)))
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
