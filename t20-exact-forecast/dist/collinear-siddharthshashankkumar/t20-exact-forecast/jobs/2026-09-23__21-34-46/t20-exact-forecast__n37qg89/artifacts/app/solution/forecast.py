import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy import sparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.league_io import load_league
from engine.model import SkillBook, MatchSimulator, load_public_model, PACE, SPIN


PACE_SPIN = 2
RECENCY_DECAY = 0.55
PROB_LOGIT_SCALE = 0.90


class Blocks:
    def __init__(self):
        self.parts = []
        self.start = {}
        self.stop = {}
        self.prior = []

    def add(self, name, size, sd):
        lo = len(self.prior)
        hi = lo + size
        self.start[name] = lo
        self.stop[name] = hi
        self.prior.extend([sd] * size)
        self.parts.append((name, lo, hi))

    @property
    def n(self):
        return len(self.prior)

    def sl(self, name):
        return slice(self.start[name], self.stop[name])

    def prior_array(self):
        return np.asarray(self.prior, float)


def _outcomes(s):
    if np.issubdtype(s.dtype, np.number):
        return s.to_numpy(int)
    return s.map({"W": 0, "0": 1, "1": 2, "2": 3, "4": 4, "6": 5}).to_numpy(int)


def _add(rows, cols, data, r, c, v=1.0):
    rows.append(r)
    cols.append(c)
    data.append(v)


def _feature_matrix(n_rows, n_cols, triples):
    if not triples[0]:
        return sparse.csr_matrix((n_rows, n_cols))
    return sparse.coo_matrix((triples[2], (triples[0], triples[1])), shape=(n_rows, n_cols)).tocsr()


def build_problem(folder):
    history, fixtures = load_league(folder)
    model = load_public_model()
    balls = history.balls.copy()
    matches = history.matches[["match", "week"]]
    balls = balls.merge(matches, on="match", how="left")

    players = history.players
    venues = history.venues
    n = len(balls)
    n_players = len(players.role)
    n_venues = len(venues.pitch)
    n_seasons = max(history.seasons, int(balls.season.max()) + 1)

    over = balls.over.to_numpy(int)
    ball_no = balls.over.to_numpy(int) * 6 + balls.ball.to_numpy(int)
    target = balls.target.to_numpy(float)
    chasing = (target > 0).astype(float)
    pressure = np.zeros(n, float)
    mask = target > 0
    if mask.any():
        pressure[mask] = model.pressure(target[mask], balls.runs_before.to_numpy(float)[mask], ball_no[mask])
    base = model.situation(
        over,
        balls.position.to_numpy(int),
        balls.wickets_before.to_numpy(float),
        chasing,
        pressure,
    )
    y = _outcomes(balls.outcome)

    blk = Blocks()
    blk.add("bat_style_role", 3, 0.45)
    blk.add("bat_style_player", n_players, 0.45)
    blk.add("bat_q_role", 3 * PACE_SPIN, 0.45)
    blk.add("bat_q_player", n_players * PACE_SPIN, 0.38)
    blk.add("bowl_type_style", PACE_SPIN, 0.85)
    blk.add("bowl_type_player", n_players, 0.35)
    blk.add("bowl_q_role", 3, 0.45)
    blk.add("bowl_q_player", n_players, 0.38)
    blk.add("venue", n_venues, 0.38)
    blk.add("season", n_seasons, 0.38)
    blk.add("chase_global", 1, 0.22)
    blk.add("chase_venue", n_venues, 0.25)
    blk.add("home_lift", 1, 0.20)
    blk.add("hand_style", 2 * PACE_SPIN, 0.16)
    blk.add("pitch_style", PACE_SPIN * 3, 0.16)
    blk.add("affinity", n_players * n_venues, 0.11)

    bat_style = ([], [], [])
    bat_q = ([], [], [])
    bowl_type = ([], [], [])
    bowl_q = ([], [], [])
    cond = ([], [], [])

    batter = balls.batter.to_numpy(int)
    bowler = balls.bowler.to_numpy(int)
    venue = balls.venue.to_numpy(int)
    season = balls.season.to_numpy(int)
    bat_team = balls.batting_team.to_numpy(int)
    bowler_style = players.style[bowler]
    batter_role = players.role[batter]
    bowler_role = players.role[bowler]
    batter_hand = players.hand[batter]
    pitch = venues.pitch[venue]

    for i in range(n):
        b = int(batter[i])
        w = int(bowler[i])
        how = int(bowler_style[i])
        v = int(venue[i])
        _add(*bat_style, i, blk.start["bat_style_role"] + int(batter_role[i]))
        _add(*bat_style, i, blk.start["bat_style_player"] + b)
        _add(*bat_q, i, blk.start["bat_q_role"] + int(batter_role[i]) * 2 + how)
        _add(*bat_q, i, blk.start["bat_q_player"] + b * 2 + how)
        _add(*bowl_type, i, blk.start["bowl_type_style"] + how)
        _add(*bowl_type, i, blk.start["bowl_type_player"] + w)
        _add(*bowl_q, i, blk.start["bowl_q_role"] + int(bowler_role[i]))
        _add(*bowl_q, i, blk.start["bowl_q_player"] + w)

        _add(*cond, i, blk.start["venue"] + v)
        _add(*cond, i, blk.start["season"] + int(season[i]))
        if chasing[i]:
            _add(*cond, i, blk.start["chase_global"])
            _add(*cond, i, blk.start["chase_venue"] + v)
        if venues.home_team[v] == bat_team[i]:
            _add(*cond, i, blk.start["home_lift"])
        _add(*cond, i, blk.start["hand_style"] + int(batter_hand[i]) * 2 + how)
        _add(*cond, i, blk.start["pitch_style"] + how * 3 + int(pitch[i]))
        _add(*cond, i, blk.start["affinity"] + b * n_venues + v)

    matrices = {
        "bat_style": _feature_matrix(n, blk.n, bat_style),
        "bat_quality": _feature_matrix(n, blk.n, bat_q),
        "bowl_type": _feature_matrix(n, blk.n, bowl_type),
        "bowl_quality": _feature_matrix(n, blk.n, bowl_q),
        "conditions": _feature_matrix(n, blk.n, cond),
    }

    age = (n_seasons - 1) - season
    weights = np.power(RECENCY_DECAY, np.maximum(age, 0))
    weights *= 0.90 + 0.10 * (balls.week.to_numpy(float) / max(1.0, balls.week.max()))

    return history, fixtures, model, blk, matrices, base, y, weights


def fit_coefficients(blk, matrices, model, base, y, weights):
    dirs = {
        "bat_style": model.bs,
        "bat_quality": model.bq,
        "bowl_type": model.wt,
        "bowl_quality": model.wq,
        "conditions": model.c,
    }
    prior = blk.prior_array()
    prior2 = prior * prior
    n = len(y)
    row = np.arange(n)

    def objective(beta):
        z = base.copy()
        for name, x in matrices.items():
            z += x.dot(beta)[:, None] * dirs[name][None, :]
        z -= z.max(axis=1, keepdims=True)
        ez = np.exp(z)
        denom = ez.sum(axis=1)
        p = ez / denom[:, None]
        logp = z[row, y] - np.log(denom)
        loss = -np.dot(weights, logp) + 0.5 * np.dot(beta / prior, beta / prior)

        grad = beta / prior2
        for name, x in matrices.items():
            d = dirs[name]
            resid = d[y] - p.dot(d)
            grad -= x.T.dot(weights * resid)
        return float(loss), np.asarray(grad, float)

    res = minimize(
        objective,
        np.zeros(blk.n, float),
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": 180, "ftol": 1e-6, "gtol": 1e-4, "maxls": 30},
    )
    return res.x


def coefficients_to_book(history, blk, beta):
    players = history.players
    venues = history.venues
    n_players = len(players.role)
    n_venues = len(venues.pitch)
    roles = players.role
    styles = players.style

    bat_style = beta[blk.sl("bat_style_role")][roles] + beta[blk.sl("bat_style_player")]

    q_role = beta[blk.sl("bat_q_role")].reshape(3, 2)
    q_player = beta[blk.sl("bat_q_player")].reshape(n_players, 2)
    q_vs = q_role[roles] + q_player
    quality = q_vs.mean(axis=1)
    split = q_vs[:, PACE] - q_vs[:, SPIN]

    kind = beta[blk.sl("bowl_type_style")][styles] + beta[blk.sl("bowl_type_player")]
    bowl_quality = beta[blk.sl("bowl_q_role")][roles] + beta[blk.sl("bowl_q_player")]

    venue_level = beta[blk.sl("venue")].copy()
    season = beta[blk.sl("season")]
    era = float(season[-1]) if len(season) else 0.0
    chase_global = float(beta[blk.sl("chase_global")][0])
    venue_dew = beta[blk.sl("chase_venue")].copy()
    wear = -chase_global
    home_lift = float(beta[blk.sl("home_lift")][0])
    type_table = beta[blk.sl("hand_style")].reshape(2, 2).copy()
    pitch_add = beta[blk.sl("pitch_style")].reshape(2, 3)
    pitch_table = -pitch_add
    affinity = beta[blk.sl("affinity")].reshape(n_players, n_venues).copy()

    day_sd = estimate_day_sd(history)
    return SkillBook(
        players,
        venues,
        bat_style,
        quality,
        split,
        kind,
        bowl_quality,
        type_table,
        pitch_table,
        venue_level,
        venue_dew,
        affinity,
        home_lift,
        era,
        day_sd,
        wear,
    )


def estimate_day_sd(history):
    totals = history.matches[["first_total", "second_total"]].to_numpy(float)
    if len(totals) < 20:
        return 0.18
    corr = np.corrcoef(totals[:, 0], totals[:, 1])[0, 1]
    if not np.isfinite(corr):
        return 0.18
    return float(np.clip(0.16 + 0.18 * max(corr, 0.0), 0.12, 0.30))


def forecast(folder, n_sims=24000):
    history, fixtures, model, blk, matrices, base, y, weights = build_problem(folder)
    beta = fit_coefficients(blk, matrices, model, base, y, weights)
    book = coefficients_to_book(history, blk, beta)
    sim = MatchSimulator(model)
    gen = np.random.default_rng(20260924)
    out = []
    for f in fixtures:
        p = sim.win_probability(book, f, n_sims, gen)
        odds = np.log(p / (1.0 - p))
        p = 1.0 / (1.0 + np.exp(-PROB_LOGIT_SCALE * odds))
        out.append((f.match, float(np.clip(p, 0.002, 0.998))))
    return pd.DataFrame(out, columns=["fixture", "p_home"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=24000)
    args = parser.parse_args()
    forecast(Path(args.league), args.sims).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
