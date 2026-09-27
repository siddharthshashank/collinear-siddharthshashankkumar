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


OUTCOME = {"W": 0, "0": 1, "1": 2, "2": 3, "4": 4, "6": 5}
PROB_SHRINK = 0.82
DAY_SD = 0.25


def _indexed(values, ids):
    out = np.empty(int(ids.max()) + 1, dtype=values.dtype)
    out[ids.to_numpy(int)] = values
    return out


def _tables(folder):
    players = pd.read_csv(folder / "players.csv")
    venues = pd.read_csv(folder / "venues.csv")
    role = _indexed(players.role.map({"batter": 0, "allrounder": 1, "bowler": 2}).to_numpy(int), players.player)
    hand = _indexed(players.hand.map({"right": 0, "left": 1}).to_numpy(int), players.player)
    style = _indexed(players.bowling_style.map({"pace": 0, "spin": 1}).to_numpy(int), players.player)
    home = _indexed(venues.home_team.to_numpy(int), venues.venue)
    pitch = _indexed(venues.pitch.map({"neutral": 0, "pace": 1, "spin": 2}).to_numpy(int), venues.venue)
    return players, venues, role, hand, style, home, pitch


def fit_book(folder, history):
    balls = pd.read_csv(folder / "balls.csv", dtype={"outcome": str})
    players, venues, _role, hand, public_style, venue_home, venue_pitch = _tables(folder)
    model = load_public_model()

    y = balls.outcome.map(OUTCOME).to_numpy(np.int64)
    n = len(balls)
    over = balls.over.to_numpy(np.int64)
    abs_ball = over * 6 + balls.ball.to_numpy(np.int64)
    position = balls.position.to_numpy(np.int64)
    wickets = balls.wickets_before.to_numpy(float)
    target = balls.target.to_numpy(float)
    runs = balls.runs_before.to_numpy(float)
    chasing = target > 0

    pressure = np.zeros(n)
    chase_ix = chasing
    need = np.clip(target[chase_ix] - runs[chase_ix], 1, None) / ((120 - abs_ball[chase_ix]) / 6)
    pressure[chase_ix] = np.clip(np.log(need / model.cal.par_rate[over[chase_ix]]), -1.0, 1.2)
    base = model.situation(over, position, wickets, chasing.astype(float), pressure)

    batter = balls.batter.to_numpy(np.int64)
    bowler = balls.bowler.to_numpy(np.int64)
    season = balls.season.to_numpy(np.int64)
    venue = balls.venue.to_numpy(np.int64)
    batting_team = balls.batting_team.to_numpy(np.int64)

    bowl_style = public_style[bowler]
    split_sign = np.where(bowl_style == 0, 0.5, -0.5)
    home_ball = (venue_home[venue] == batting_team).astype(float)
    hand_style = hand[batter] * 2 + bowl_style
    pitch_style = bowl_style * 3 + venue_pitch[venue]

    max_season = int(season.max()) + 1
    if max_season <= 1:
        weights = np.ones(n)
    else:
        # Recent form is more predictive, but talent is persistent; keep all seasons in play.
        season_weights = np.linspace(0.58, 1.0, max_season)
        weights = season_weights[season]

    dirs = (model.bs, model.bq, model.wt, model.wq, model.c)
    ymat = np.zeros((n, 6))
    ymat[np.arange(n), y] = 1.0

    n_players = int(players.player.max()) + 1
    n_venues = int(venues.venue.max()) + 1
    slices = {}
    offset = 0
    for name, size in (
        ("bat_style", n_players),
        ("bat_quality", n_players),
        ("bat_split", n_players),
        ("bowl_kind", n_players),
        ("bowl_quality", n_players),
        ("venue", n_venues),
        ("season", max_season),
        ("chase_venue", n_venues),
        ("home_lift", 1),
        ("hand_style", 4),
        ("pitch_style", 6),
    ):
        slices[name] = slice(offset, offset + size)
        offset += size

    prior_sd = np.ones(offset)
    scales = {
        "bat_style": 0.55,
        "bat_quality": 0.55,
        "bat_split": 0.30,
        "bowl_kind": 0.45,
        "bowl_quality": 0.50,
        "venue": 0.35,
        "season": 0.30,
        "chase_venue": 0.25,
        "home_lift": 0.20,
        "hand_style": 0.15,
        "pitch_style": 0.15,
    }
    for name, scale in scales.items():
        prior_sd[slices[name]] = scale

    def objective(x):
        bat_style = x[slices["bat_style"]][batter]
        bat_quality = x[slices["bat_quality"]][batter] + x[slices["bat_split"]][batter] * split_sign
        bowl_kind = x[slices["bowl_kind"]][bowler]
        bowl_quality = x[slices["bowl_quality"]][bowler]
        condition = (
            x[slices["venue"]][venue]
            + x[slices["season"]][season]
            + x[slices["chase_venue"]][venue] * chasing
            + x[slices["home_lift"]][0] * home_ball
            + x[slices["hand_style"]][hand_style]
            + x[slices["pitch_style"]][pitch_style]
        )

        logits = (
            base
            + np.outer(bat_style, dirs[0])
            + np.outer(bat_quality, dirs[1])
            + np.outer(bowl_kind, dirs[2])
            + np.outer(bowl_quality, dirs[3])
            + np.outer(condition, dirs[4])
        )
        zmax = logits.max(axis=1)
        exp_z = np.exp(logits - zmax[:, None])
        probs = exp_z / exp_z.sum(axis=1)[:, None]
        nll = np.sum(weights * (-logits[np.arange(n), y] + zmax + np.log(exp_z.sum(axis=1))))
        nll += 0.5 * np.sum((x / prior_sd) ** 2)

        err = (probs - ymat) * weights[:, None]
        grad = np.zeros_like(x)

        g = err @ dirs[0]
        np.add.at(grad[slices["bat_style"]], batter, g)
        g = err @ dirs[1]
        np.add.at(grad[slices["bat_quality"]], batter, g)
        np.add.at(grad[slices["bat_split"]], batter, g * split_sign)
        g = err @ dirs[2]
        np.add.at(grad[slices["bowl_kind"]], bowler, g)
        g = err @ dirs[3]
        np.add.at(grad[slices["bowl_quality"]], bowler, g)
        g = err @ dirs[4]
        np.add.at(grad[slices["venue"]], venue, g)
        np.add.at(grad[slices["season"]], season, g)
        np.add.at(grad[slices["chase_venue"]], venue, g * chasing)
        grad[slices["home_lift"]][0] += np.sum(g * home_ball)
        np.add.at(grad[slices["hand_style"]], hand_style, g)
        np.add.at(grad[slices["pitch_style"]], pitch_style, g)

        grad += x / (prior_sd**2)
        return nll, grad

    result = minimize(
        lambda x: objective(x),
        np.zeros(offset),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 160, "ftol": 1e-7, "maxls": 30},
    )
    x = result.x

    pitch_add = x[slices["pitch_style"]].reshape(2, 3)
    era = float(x[slices["season"]][-1])
    return SkillBook(
        history.players,
        history.venues,
        x[slices["bat_style"]],
        x[slices["bat_quality"]],
        x[slices["bat_split"]],
        x[slices["bowl_kind"]],
        x[slices["bowl_quality"]],
        x[slices["hand_style"]].reshape(2, 2),
        -pitch_add,
        x[slices["venue"]],
        x[slices["chase_venue"]],
        np.zeros((n_players, n_venues)),
        float(x[slices["home_lift"]][0]),
        era,
        DAY_SD,
        0.0,
    )


def forecast(folder, out_file):
    folder = Path(folder)
    history, fixtures = load_league(folder)
    book = fit_book(folder, history)
    simulator = MatchSimulator(load_public_model())
    gen = np.random.default_rng(20260927)

    rows = []
    for fixture in fixtures:
        p = simulator.win_probability(book, fixture, 20000, gen)
        p = 0.5 + PROB_SHRINK * (p - 0.5)
        rows.append((fixture.match, float(np.clip(p, 0.002, 0.998))))
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(out_file, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    forecast(args.league, args.out)


if __name__ == "__main__":
    main()
