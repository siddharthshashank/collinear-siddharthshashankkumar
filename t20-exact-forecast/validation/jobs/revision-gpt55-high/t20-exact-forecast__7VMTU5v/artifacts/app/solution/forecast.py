import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.model import MatchSimulator, SkillBook, load_public_model  # noqa: E402
from engine.league_io import load_league  # noqa: E402


@dataclass
class Layout:
    slices: dict
    size: int
    n_players: int
    n_venues: int
    n_seasons: int
    n_matches: int


def make_layout(n_players, n_venues, n_seasons, n_matches):
    sizes = {
        "bat_style": n_players,
        "bat_q": n_players,
        "bat_dev": n_players * n_seasons,
        "split": n_players,
        "bowl_kind": n_players,
        "bowl_q": n_players,
        "bowl_dev": n_players * n_seasons,
        "type_table": 4,
        "pitch_table": 6,
        "venue_level": n_venues,
        "venue_dew": n_venues,
        "affinity": n_players * n_venues,
        "home_lift": 1,
        "era": n_seasons,
        "wear": 1,
        "match_day": n_matches,
    }
    slices = {}
    at = 0
    for name, size in sizes.items():
        slices[name] = slice(at, at + size)
        at += size
    return Layout(slices, at, n_players, n_venues, n_seasons, n_matches)


def unpack(theta, layout):
    s = layout.slices
    p, v, y = layout.n_players, layout.n_venues, layout.n_seasons
    return {
        "bat_style": theta[s["bat_style"]],
        "bat_q": theta[s["bat_q"]],
        "bat_dev": theta[s["bat_dev"]].reshape(p, y),
        "split": theta[s["split"]],
        "bowl_kind": theta[s["bowl_kind"]],
        "bowl_q": theta[s["bowl_q"]],
        "bowl_dev": theta[s["bowl_dev"]].reshape(p, y),
        "type_table": theta[s["type_table"]].reshape(2, 2),
        "pitch_table": theta[s["pitch_table"]].reshape(2, 3),
        "venue_level": theta[s["venue_level"]],
        "venue_dew": theta[s["venue_dew"]],
        "affinity": theta[s["affinity"]].reshape(p, v),
        "home_lift": theta[s["home_lift"]][0],
        "era": theta[s["era"]],
        "wear": theta[s["wear"]][0],
        "match_day": theta[s["match_day"]],
    }


def add_bincount(grad, sl, idx, values, length):
    grad[sl] += np.bincount(idx, weights=values, minlength=length)


def fit_book(league_dir):
    history, fixtures = load_league(league_dir)
    model = load_public_model()
    cal = model.cal

    balls = history.balls
    players = history.players
    venues = history.venues
    n_players = len(players.role)
    n_venues = len(venues.pitch)
    n_seasons = int(max(history.seasons, balls.season.max() + 1))
    n_matches = int(balls.match.max() + 1)
    layout = make_layout(n_players, n_venues, n_seasons, n_matches)

    season = balls.season.to_numpy(int)
    batter = balls.batter.to_numpy(int)
    bowler = balls.bowler.to_numpy(int)
    venue = balls.venue.to_numpy(int)
    match_id = balls.match.to_numpy(int)
    outcome = balls.outcome.to_numpy(int)
    over = balls.over.to_numpy(int)
    ball_no = balls.ball.to_numpy(int)
    ball_index = over * 6 + ball_no
    position = balls.position.to_numpy(int)
    wickets = balls.wickets_before.to_numpy(float)
    chasing = (balls.target.to_numpy(int) > 0).astype(float)
    pressure = np.zeros(len(balls), float)
    mask = chasing > 0
    pressure[mask] = model.pressure(
        balls.target.to_numpy(float)[mask],
        balls.runs_before.to_numpy(float)[mask],
        ball_index[mask],
    )
    base = model.situation(over, position, wickets, chasing, pressure)

    bowler_style = players.style[bowler]
    batter_hand = players.hand[batter]
    pitch = venues.pitch[venue]
    split_sign = np.where(bowler_style == 0, 0.5, -0.5)
    batting_home = (venues.home_team[venue] == balls.batting_team.to_numpy(int)).astype(float)
    dev_index = batter * n_seasons + season
    bowl_dev_index = bowler * n_seasons + season
    affinity_index = batter * n_venues + venue
    type_index = batter_hand * 2 + bowler_style
    pitch_index = bowler_style * 3 + pitch

    y_bs = cal.directions["bat_style"][outcome]
    y_bq = cal.directions["bat_quality"][outcome]
    y_wt = cal.directions["bowl_type"][outcome]
    y_wq = cal.directions["bowl_quality"][outcome]
    y_c = cal.directions["conditions"][outcome]

    weights = np.power(0.82, (n_seasons - 1) - season)

    prior_sd = {
        "bat_style": 0.55,
        "bat_q": 0.42,
        "bat_dev": 0.26,
        "split": 0.28,
        "bowl_kind": 0.50,
        "bowl_q": 0.36,
        "bowl_dev": 0.24,
        "type_table": 0.18,
        "pitch_table": 0.18,
        "venue_level": 0.30,
        "venue_dew": 0.22,
        "affinity": 0.12,
        "home_lift": 0.12,
        "era": 0.22,
        "wear": 0.14,
        "match_day": 0.20,
    }
    inv_var = np.zeros(layout.size)
    for name, sd in prior_sd.items():
        inv_var[layout.slices[name]] = 1.0 / (sd * sd)

    def objective(theta):
        prm = unpack(theta, layout)
        z = base.copy()

        bat_quality = (
            prm["bat_q"][batter]
            + prm["bat_dev"][batter, season]
            + prm["split"][batter] * split_sign
        )
        condition = (
            prm["venue_level"][venue]
            + prm["era"][season]
            + chasing * (prm["venue_dew"][venue] - prm["wear"])
            + batting_home * prm["home_lift"]
            + prm["affinity"][batter, venue]
            + prm["type_table"][batter_hand, bowler_style]
            - prm["pitch_table"][bowler_style, pitch]
            + prm["match_day"][match_id]
        )
        bowl_quality = prm["bowl_q"][bowler] + prm["bowl_dev"][bowler, season]

        z += np.outer(prm["bat_style"][batter], cal.directions["bat_style"])
        z += np.outer(bat_quality, cal.directions["bat_quality"])
        z += np.outer(prm["bowl_kind"][bowler], cal.directions["bowl_type"])
        z += np.outer(bowl_quality, cal.directions["bowl_quality"])
        z += np.outer(condition, cal.directions["conditions"])

        z -= z.max(axis=1, keepdims=True)
        ez = np.exp(z)
        prob = ez / ez.sum(axis=1, keepdims=True)
        nll = -np.sum(weights * np.log(prob[np.arange(len(outcome)), outcome] + 1e-15))

        e_bs = prob @ cal.directions["bat_style"]
        e_bq = prob @ cal.directions["bat_quality"]
        e_wt = prob @ cal.directions["bowl_type"]
        e_wq = prob @ cal.directions["bowl_quality"]
        e_c = prob @ cal.directions["conditions"]

        r_bs = weights * (e_bs - y_bs)
        r_bq = weights * (e_bq - y_bq)
        r_wt = weights * (e_wt - y_wt)
        r_wq = weights * (e_wq - y_wq)
        r_c = weights * (e_c - y_c)

        grad = theta * inv_var
        s = layout.slices
        add_bincount(grad, s["bat_style"], batter, r_bs, n_players)
        add_bincount(grad, s["bat_q"], batter, r_bq, n_players)
        add_bincount(grad, s["bat_dev"], dev_index, r_bq, n_players * n_seasons)
        add_bincount(grad, s["split"], batter, r_bq * split_sign, n_players)
        add_bincount(grad, s["bowl_kind"], bowler, r_wt, n_players)
        add_bincount(grad, s["bowl_q"], bowler, r_wq, n_players)
        add_bincount(grad, s["bowl_dev"], bowl_dev_index, r_wq, n_players * n_seasons)
        add_bincount(grad, s["type_table"], type_index, r_c, 4)
        add_bincount(grad, s["pitch_table"], pitch_index, -r_c, 6)
        add_bincount(grad, s["venue_level"], venue, r_c, n_venues)
        add_bincount(grad, s["venue_dew"], venue, r_c * chasing, n_venues)
        add_bincount(grad, s["affinity"], affinity_index, r_c, n_players * n_venues)
        grad[s["home_lift"]][0] += np.sum(r_c * batting_home)
        add_bincount(grad, s["era"], season, r_c, n_seasons)
        grad[s["wear"]][0] += -np.sum(r_c * chasing)
        add_bincount(grad, s["match_day"], match_id, r_c, n_matches)

        penalty = 0.5 * np.sum(theta * theta * inv_var)
        return nll + penalty, grad

    result = minimize(
        objective,
        np.zeros(layout.size),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 240, "ftol": 1e-7, "gtol": 1e-4, "maxls": 30},
    )
    prm = unpack(result.x, layout)

    form_keep = 0.58
    bat_quality = prm["bat_q"] + form_keep * prm["bat_dev"][:, n_seasons - 1]
    bowl_quality = prm["bowl_q"] + form_keep * prm["bowl_dev"][:, n_seasons - 1]

    era = float(prm["era"][n_seasons - 1])
    if n_seasons >= 2:
        era += 0.20 * float(prm["era"][n_seasons - 1] - prm["era"][n_seasons - 2])

    book = SkillBook(
        players=players,
        venues=venues,
        style=prm["bat_style"],
        quality=bat_quality,
        split=prm["split"],
        kind=prm["bowl_kind"],
        bowl_quality=bowl_quality,
        type_table=prm["type_table"],
        pitch_table=prm["pitch_table"],
        venue_level=prm["venue_level"],
        venue_dew=prm["venue_dew"],
        affinity=prm["affinity"],
        home_lift=float(prm["home_lift"]),
        era=era,
        day_sd=0.18,
        wear=float(prm["wear"]),
    )
    return book, fixtures, model


def forecast(league_dir, out_path):
    book, fixtures, model = fit_book(league_dir)
    sim = MatchSimulator(model)
    gen = np.random.default_rng(20260927)
    rows = []
    for fixture in fixtures:
        p_home = sim.win_probability(book, fixture, 24000, gen)
        rows.append((fixture.match, float(np.clip(p_home, 0.002, 0.998))))
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(out_path, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    forecast(Path(args.league), Path(args.out))


if __name__ == "__main__":
    main()
