import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.league_io import load_league
from engine.model import MatchSimulator, SkillBook, load_public_model


CLIP = (0.002, 0.998)


def _outcome_codes(s):
    if np.issubdtype(s.dtype, np.number):
        return s.astype(int).to_numpy()
    return s.map({"W": 0, "0": 1, "1": 2, "2": 3, "4": 4, "6": 5}).astype(int).to_numpy()


class EffectFit:
    def __init__(self, league_folder):
        self.folder = Path(league_folder)
        self.history, self.fixtures = load_league(self.folder)
        self.model = load_public_model()
        self.players = self.history.players
        self.venues = self.history.venues
        self.balls = self.history.balls.copy()

        b = self.balls
        self.n_players = len(self.players.role)
        self.n_venues = len(self.venues.pitch)
        self.n_seasons = int(max(self.history.seasons, int(b.season.max()) + 1))
        match_ids = np.sort(b.match.unique())
        self.match_index = {int(m): i for i, m in enumerate(match_ids)}
        self.n_matches = len(match_ids)

        self.y = _outcome_codes(b.outcome)
        self.batter = b.batter.astype(int).to_numpy()
        self.bowler = b.bowler.astype(int).to_numpy()
        self.venue = b.venue.astype(int).to_numpy()
        self.season = b.season.astype(int).to_numpy()
        self.match = b.match.map(self.match_index).astype(int).to_numpy()
        self.over = b.over.astype(int).to_numpy()
        self.ball_no = (b.over.astype(int) * 6 + b.ball.astype(int)).to_numpy()
        self.position = b.position.astype(int).to_numpy()
        self.wickets = b.wickets_before.astype(int).to_numpy()
        self.chasing = (b.target.astype(int).to_numpy() > 0).astype(float)
        self.hand = self.players.hand[self.batter]
        self.bowler_style = self.players.style[self.bowler]
        self.pitch = self.venues.pitch[self.venue]
        self.pace_sign = np.where(self.bowler_style == 0, 0.5, -0.5)
        self.is_home = (self.venues.home_team[self.venue] == b.batting_team.astype(int).to_numpy()).astype(float)

        pressure = np.zeros(len(b), dtype=float)
        chase_rows = self.chasing > 0
        pressure[chase_rows] = self.model.pressure(
            b.target.astype(float).to_numpy()[chase_rows],
            b.runs_before.astype(float).to_numpy()[chase_rows],
            self.ball_no[chase_rows],
        )
        self.base = self.model.situation(
            self.over,
            self.position,
            self.wickets,
            self.chasing,
            pressure,
        )

        # A light recency tilt helps with drifting form while still using all seasons.
        if self.n_seasons > 1:
            age = self.n_seasons - 1 - self.season
            self.weights = 0.86 ** age
            self.weights *= len(self.weights) / self.weights.sum()
        else:
            self.weights = np.ones(len(b))

        self._make_layout()

    def _make_layout(self):
        n, v, s, m = self.n_players, self.n_venues, self.n_seasons, self.n_matches
        fields = [
            ("bat_style", n, 0.55),
            ("bat_quality", n, 0.55),
            ("bat_split", n, 0.32),
            ("kind_mean", 2, 0.85),
            ("kind_dev", n, 0.28),
            ("bowl_quality", n, 0.50),
            ("venue_level", v, 0.35),
            ("era", s, 0.28),
            ("chase_venue", v, 0.28),
            ("chase_global", 1, 0.22),
            ("home_lift", 1, 0.18),
            ("type_table", 4, 0.20),
            ("pitch_table", 6, 0.20),
            ("affinity", n * v, 0.14),
            ("day", m, 0.30),
        ]
        self.sl = {}
        self.sigma = []
        pos = 0
        for name, size, sig in fields:
            self.sl[name] = slice(pos, pos + size)
            self.sigma.append(np.full(size, sig, dtype=float))
            pos += size
        self.n_params = pos
        self.sigma = np.concatenate(self.sigma)
        self.prior_mean = np.zeros(self.n_params, dtype=float)

        # Pitch effects are used as "conditions minus help-to-bowler"; anchor
        # neutral pitch weakly at zero and let pace/spin surfaces move if the
        # balls support it.
        pt = self.sl["pitch_table"].start
        self.sigma[pt + 0] = 0.08
        self.sigma[pt + 3] = 0.08

    def _arrays(self, x):
        a = lambda name: x[self.sl[name]]
        kind = a("kind_mean")[self.players.style] + a("kind_dev")
        return {
            "bat_style": a("bat_style"),
            "bat_quality": a("bat_quality"),
            "bat_split": a("bat_split"),
            "kind": kind,
            "bowl_quality": a("bowl_quality"),
            "venue_level": a("venue_level"),
            "era": a("era"),
            "chase_venue": a("chase_venue"),
            "chase_global": float(a("chase_global")[0]),
            "home_lift": float(a("home_lift")[0]),
            "type_table": a("type_table").reshape(2, 2),
            "pitch_table": a("pitch_table").reshape(2, 3),
            "affinity": a("affinity").reshape(self.n_players, self.n_venues),
            "day": a("day"),
        }

    def objective(self, x):
        arr = self._arrays(x)
        bs = arr["bat_style"][self.batter]
        bq = arr["bat_quality"][self.batter] + arr["bat_split"][self.batter] * self.pace_sign
        wt = arr["kind"][self.bowler]
        wq = arr["bowl_quality"][self.bowler]
        cond = (
            arr["venue_level"][self.venue]
            + arr["era"][self.season]
            + self.chasing * (arr["chase_venue"][self.venue] + arr["chase_global"])
            + arr["home_lift"] * self.is_home
            + arr["type_table"][self.hand, self.bowler_style]
            - arr["pitch_table"][self.bowler_style, self.pitch]
            + arr["affinity"][self.batter, self.venue]
            + arr["day"][self.match]
        )

        m = self.model
        z = (
            self.base
            + bs[:, None] * m.bs
            + bq[:, None] * m.bq
            + wt[:, None] * m.wt
            + wq[:, None] * m.wq
            + cond[:, None] * m.c
        )
        z -= z.max(axis=1, keepdims=True)
        ez = np.exp(z)
        p = ez / ez.sum(axis=1, keepdims=True)
        rows = np.arange(len(self.y))
        nll = -np.sum(self.weights * np.log(np.clip(p[rows, self.y], 1e-15, 1.0)))

        r = p
        r[rows, self.y] -= 1.0
        r *= self.weights[:, None]
        g_bs = r @ m.bs
        g_bq = r @ m.bq
        g_wt = r @ m.wt
        g_wq = r @ m.wq
        g_c = r @ m.c

        grad = np.zeros_like(x)
        n, v = self.n_players, self.n_venues
        grad[self.sl["bat_style"]] += np.bincount(self.batter, weights=g_bs, minlength=n)
        grad[self.sl["bat_quality"]] += np.bincount(self.batter, weights=g_bq, minlength=n)
        grad[self.sl["bat_split"]] += np.bincount(self.batter, weights=g_bq * self.pace_sign, minlength=n)
        grad[self.sl["kind_mean"]] += np.bincount(self.bowler_style, weights=g_wt, minlength=2)
        grad[self.sl["kind_dev"]] += np.bincount(self.bowler, weights=g_wt, minlength=n)
        grad[self.sl["bowl_quality"]] += np.bincount(self.bowler, weights=g_wq, minlength=n)
        grad[self.sl["venue_level"]] += np.bincount(self.venue, weights=g_c, minlength=v)
        grad[self.sl["era"]] += np.bincount(self.season, weights=g_c, minlength=self.n_seasons)
        grad[self.sl["chase_venue"]] += np.bincount(self.venue, weights=g_c * self.chasing, minlength=v)
        grad[self.sl["chase_global"]] += np.array([np.sum(g_c * self.chasing)])
        grad[self.sl["home_lift"]] += np.array([np.sum(g_c * self.is_home)])
        grad[self.sl["type_table"]] += np.bincount(self.hand * 2 + self.bowler_style, weights=g_c, minlength=4)
        grad[self.sl["pitch_table"]] += -np.bincount(self.bowler_style * 3 + self.pitch, weights=g_c, minlength=6)
        grad[self.sl["affinity"]] += np.bincount(self.batter * v + self.venue, weights=g_c, minlength=n * v)
        grad[self.sl["day"]] += np.bincount(self.match, weights=g_c, minlength=self.n_matches)

        diff = (x - self.prior_mean) / self.sigma
        nll += 0.5 * float(diff @ diff)
        grad += diff / self.sigma
        return nll, grad

    def fit(self):
        x0 = self.prior_mean.copy()
        res = minimize(
            self.objective,
            x0,
            method="L-BFGS-B",
            jac=True,
            options={"maxiter": 170, "ftol": 1e-5, "gtol": 1e-3, "maxls": 30},
        )
        self.x = res.x
        self.result = res
        return self

    def skill_book(self):
        arr = self._arrays(self.x)
        era = float(arr["era"][-1])

        # Day estimates are posterior-shrunk. Inflate them a little to recover
        # the latent match-to-match pitch spread used by the simulator.
        day = arr["day"]
        day_sd = float(np.sqrt(max(0.0, np.var(day) - 0.04)))
        day_sd = float(np.clip(day_sd * 1.25, 0.0, 0.45))

        return SkillBook(
            self.players,
            self.venues,
            arr["bat_style"].copy(),
            arr["bat_quality"].copy(),
            arr["bat_split"].copy(),
            arr["kind"].copy(),
            arr["bowl_quality"].copy(),
            arr["type_table"].copy(),
            arr["pitch_table"].copy(),
            arr["venue_level"].copy(),
            arr["chase_venue"].copy(),
            arr["affinity"].copy(),
            arr["home_lift"],
            era,
            day_sd,
            -arr["chase_global"],
        )


def forecast(league_folder, out_file, sims=50000):
    fit = EffectFit(league_folder).fit()
    book = fit.skill_book()
    sim = MatchSimulator(fit.model)
    rng = np.random.default_rng(20260924)
    rows = []
    for fixture in fit.fixtures:
        p = sim.win_probability(book, fixture, sims, rng)
        rows.append((fixture.match, float(np.clip(p, *CLIP))))
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(out_file, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=50000)
    args = parser.parse_args()
    forecast(args.league, args.out, args.sims)


if __name__ == "__main__":
    main()
