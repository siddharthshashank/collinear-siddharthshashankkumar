import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.append(str(Path(__file__).resolve().parents[1]))

from engine.league_io import load_league
from engine.model import SkillBook, MatchSimulator, load_public_model


CLIP = (0.002, 0.998)


@dataclass
class Layout:
    n_players: int
    n_venues: int
    n_seasons: int
    n_matches: int

    def __post_init__(self):
        p, v, s, m = self.n_players, self.n_venues, self.n_seasons, self.n_matches
        start = 0
        self.bs = slice(start, start + p); start += p
        self.bq = slice(start, start + p); start += p
        self.bq_form = slice(start, start + p * s); start += p * s
        self.split = slice(start, start + p); start += p
        self.wt = slice(start, start + p); start += p
        self.wq = slice(start, start + p); start += p
        self.wq_form = slice(start, start + p * s); start += p * s
        self.venue = slice(start, start + v); start += v
        self.season = slice(start, start + s); start += s
        self.chase_venue = slice(start, start + v); start += v
        self.home = slice(start, start + 1); start += 1
        self.chase = slice(start, start + 1); start += 1
        self.hand_style = slice(start, start + 4); start += 4
        self.pitch_style = slice(start, start + 6); start += 6
        self.affinity = slice(start, start + p * v); start += p * v
        self.day = slice(start, start + m); start += m
        self.n = start


def _prepare_arrays(history, model):
    balls = history.balls
    players, venues = history.players, history.venues
    ball_no = balls["over"].to_numpy(np.int16) * 6 + balls["ball"].to_numpy(np.int16)
    chasing = (balls["target"].to_numpy(np.int16) > 0).astype(float)
    pressure = np.zeros(len(balls), dtype=float)
    mask = chasing > 0
    if mask.any():
        pressure[mask] = model.pressure(
            balls.loc[mask, "target"].to_numpy(float),
            balls.loc[mask, "runs_before"].to_numpy(float),
            ball_no[mask],
        )

    base = model.situation(
        balls["over"].to_numpy(np.int16),
        balls["position"].to_numpy(np.int16),
        balls["wickets_before"].to_numpy(float),
        chasing,
        pressure,
    )
    outcome = balls["outcome"].to_numpy(np.int8)

    match_ids, match_index = np.unique(balls["match"].to_numpy(int), return_inverse=True)
    season = balls["season"].to_numpy(np.int16)
    batter = balls["batter"].to_numpy(np.int16)
    bowler = balls["bowler"].to_numpy(np.int16)
    venue = balls["venue"].to_numpy(np.int16)
    bowl_style = players.style[bowler].astype(np.int16)
    hand = players.hand[batter].astype(np.int16)
    pitch = venues.pitch[venue].astype(np.int16)
    split_sign = np.where(bowl_style == 0, 0.5, -0.5)
    home_ball = (venues.home_team[venue] == balls["batting_team"].to_numpy(int)).astype(float)

    max_season = max(int(history.seasons) - 1, 0)
    recency = 0.72 ** (max_season - season)
    recency = recency / recency.mean()

    return {
        "base": base,
        "y": outcome,
        "w": recency.astype(float),
        "season": season,
        "batter_season": (batter * history.seasons + season).astype(np.int32),
        "bowler_season": (bowler * history.seasons + season).astype(np.int32),
        "batter": batter,
        "bowler": bowler,
        "venue": venue,
        "split_sign": split_sign.astype(float),
        "chasing": chasing,
        "home": home_ball,
        "hand_style": (hand * 2 + bowl_style).astype(np.int16),
        "pitch_style": (bowl_style * 3 + pitch).astype(np.int16),
        "affinity": (batter * len(venues.pitch) + venue).astype(np.int32),
        "match_index": match_index.astype(np.int16),
        "match_ids": match_ids,
    }


def _penalty(layout):
    lam = np.zeros(layout.n)
    lam[layout.bs] = 2.0
    lam[layout.bq] = 1.2
    lam[layout.bq_form] = 8.0
    lam[layout.split] = 5.0
    lam[layout.wt] = 3.0
    lam[layout.wq] = 1.5
    lam[layout.wq_form] = 8.0
    lam[layout.venue] = 5.0
    lam[layout.season] = 4.0
    lam[layout.chase_venue] = 8.0
    lam[layout.home] = 10.0
    lam[layout.chase] = 6.0
    lam[layout.hand_style] = 12.0
    lam[layout.pitch_style] = 12.0
    lam[layout.affinity] = 24.0
    lam[layout.day] = 9.0
    return lam


def _fit(history, model):
    arrays = _prepare_arrays(history, model)
    layout = Layout(
        len(history.players.role),
        len(history.venues.pitch),
        int(history.seasons),
        len(arrays["match_ids"]),
    )
    lam = _penalty(layout)
    dirs = model.cal.directions
    D = np.vstack([
        dirs["bat_style"],
        dirs["bat_quality"],
        dirs["bowl_type"],
        dirs["bowl_quality"],
        dirs["conditions"],
    ])

    base = arrays["base"]
    y = arrays["y"]
    w = arrays["w"]
    n = len(y)
    rows = np.arange(n)

    def unpack_eta(x):
        eta_bs = x[layout.bs][arrays["batter"]]
        eta_bq = (
            x[layout.bq][arrays["batter"]]
            + x[layout.bq_form][arrays["batter_season"]]
            + x[layout.split][arrays["batter"]] * arrays["split_sign"]
        )
        eta_wt = x[layout.wt][arrays["bowler"]]
        eta_wq = x[layout.wq][arrays["bowler"]] + x[layout.wq_form][arrays["bowler_season"]]
        eta_c = (
            x[layout.venue][arrays["venue"]]
            + x[layout.season][arrays["season"]]
            + arrays["chasing"] * (x[layout.chase][0] + x[layout.chase_venue][arrays["venue"]])
            + arrays["home"] * x[layout.home][0]
            + x[layout.hand_style][arrays["hand_style"]]
            + x[layout.pitch_style][arrays["pitch_style"]]
            + x[layout.affinity][arrays["affinity"]]
            + x[layout.day][arrays["match_index"]]
        )
        return eta_bs, eta_bq, eta_wt, eta_wq, eta_c

    def objective(x):
        etas = np.vstack(unpack_eta(x)).T
        z = base + etas @ D
        z -= z.max(axis=1, keepdims=True)
        expz = np.exp(z)
        p = expz / expz.sum(axis=1, keepdims=True)
        nll = -np.sum(w * np.log(p[rows, y] + 1e-15))
        diff = p
        diff[rows, y] -= 1.0
        diff *= w[:, None]
        scores = diff @ D.T

        g = lam * x
        np.add.at(g[layout.bs], arrays["batter"], scores[:, 0])
        np.add.at(g[layout.bq], arrays["batter"], scores[:, 1])
        np.add.at(g[layout.bq_form], arrays["batter_season"], scores[:, 1])
        np.add.at(g[layout.split], arrays["batter"], scores[:, 1] * arrays["split_sign"])
        np.add.at(g[layout.wt], arrays["bowler"], scores[:, 2])
        np.add.at(g[layout.wq], arrays["bowler"], scores[:, 3])
        np.add.at(g[layout.wq_form], arrays["bowler_season"], scores[:, 3])
        np.add.at(g[layout.venue], arrays["venue"], scores[:, 4])
        np.add.at(g[layout.season], arrays["season"], scores[:, 4])
        chase_score = scores[:, 4] * arrays["chasing"]
        np.add.at(g[layout.chase_venue], arrays["venue"], chase_score)
        g[layout.chase][0] += chase_score.sum()
        g[layout.home][0] += np.sum(scores[:, 4] * arrays["home"])
        np.add.at(g[layout.hand_style], arrays["hand_style"], scores[:, 4])
        np.add.at(g[layout.pitch_style], arrays["pitch_style"], scores[:, 4])
        np.add.at(g[layout.affinity], arrays["affinity"], scores[:, 4])
        np.add.at(g[layout.day], arrays["match_index"], scores[:, 4])
        val = nll + 0.5 * np.sum(lam * x * x)
        return val, g

    result = minimize(
        objective,
        np.zeros(layout.n, dtype=float),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 170, "ftol": 1e-6, "gtol": 1e-4, "maxls": 30},
    )
    return result.x, layout


def _book_from_fit(history, x, layout):
    n_players, n_venues = layout.n_players, layout.n_venues
    season_effect = x[layout.season].copy()
    era = float(season_effect[-1]) if len(season_effect) else 0.0
    day_sd = float(np.clip(np.std(x[layout.day]), 0.03, 0.65))
    form_keep = 0.58
    bq_form = x[layout.bq_form].reshape(n_players, layout.n_seasons)
    wq_form = x[layout.wq_form].reshape(n_players, layout.n_seasons)

    return SkillBook(
        history.players,
        history.venues,
        style=x[layout.bs].copy(),
        quality=x[layout.bq].copy() + form_keep * bq_form[:, -1],
        split=x[layout.split].copy(),
        kind=x[layout.wt].copy(),
        bowl_quality=x[layout.wq].copy() + form_keep * wq_form[:, -1],
        type_table=x[layout.hand_style].reshape(2, 2).copy(),
        pitch_table=-x[layout.pitch_style].reshape(2, 3).copy(),
        venue_level=x[layout.venue].copy(),
        venue_dew=x[layout.chase_venue].copy(),
        affinity=x[layout.affinity].reshape(n_players, n_venues).copy(),
        home_lift=float(x[layout.home][0]),
        era=era,
        day_sd=day_sd,
        wear=-float(x[layout.chase][0]),
    )


def forecast(league_folder, n_sims=24000):
    history, fixtures = load_league(league_folder)
    model = load_public_model()
    x, layout = _fit(history, model)
    book = _book_from_fit(history, x, layout)
    simulator = MatchSimulator(model)
    gen = np.random.default_rng(20260924)
    rows = []
    for fixture in fixtures:
        p_home = simulator.win_probability(book, fixture, n_sims, gen)
        rows.append((fixture.match, float(np.clip(p_home, *CLIP))))
    return pd.DataFrame(rows, columns=["fixture", "p_home"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    forecast(Path(args.league)).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
