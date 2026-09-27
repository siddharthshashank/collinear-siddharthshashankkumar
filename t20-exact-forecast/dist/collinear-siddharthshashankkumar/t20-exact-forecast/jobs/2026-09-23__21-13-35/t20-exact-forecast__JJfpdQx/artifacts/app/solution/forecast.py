"""Forecast home-win probability for each fixture by fitting the hidden skills
of the public ball model via regularized softmax MLE, then Monte Carlo the fixtures.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.optimize as opt

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from engine.league_io import load_league  # noqa: E402
from engine.model import (  # noqa: E402
    load_public_model, SkillBook, MatchSimulator, PACE,
)


def build_public_logits(history, model):
    balls = history.balls
    over = balls.over.to_numpy()
    position = balls.position.to_numpy()
    wickets_before = balls.wickets_before.to_numpy()
    runs_before = balls.runs_before.to_numpy()
    target = balls.target.to_numpy()
    ball_in_over = balls.ball.to_numpy()
    innings = balls.innings.to_numpy()
    chasing_bool = innings == 2
    chasing = chasing_bool.astype(np.float64)
    ball_no = over * 6 + ball_in_over

    cal = model.cal
    z_pub = (cal.over_logits[over]
             + cal.position_vectors[position]
             + np.multiply.outer(wickets_before - cal.typical_wickets[over], cal.wickets_vector)
             + np.multiply.outer(chasing, cal.second_innings_vector))
    need = np.clip(target - runs_before, 1, None).astype(np.float64)
    overs_left = (120 - ball_no) / 6
    par = cal.par_rate[over]
    pressure = np.zeros(len(balls))
    with np.errstate(invalid="ignore", divide="ignore"):
        raw = np.log((need / overs_left) / par)
    pressure[chasing_bool] = np.clip(raw[chasing_bool], -1.0, 1.2)
    z_pub = z_pub + np.multiply.outer(pressure, cal.pressure_vector)
    return z_pub, chasing


def fit_skills(history, model):
    balls = history.balls
    matches = history.matches
    N_p = len(history.players.role)
    N_v = len(history.venues.pitch)
    N_s = int(history.seasons)
    N_m = len(matches)
    N = len(balls)

    z_pub, chasing = build_public_logits(history, model)

    batter = balls.batter.to_numpy()
    bowler = balls.bowler.to_numpy()
    venue = balls.venue.to_numpy()
    ball_match = balls.match.to_numpy()
    outcome = balls.outcome.to_numpy()
    batter_team = balls.batting_team.to_numpy()

    bowler_style = history.players.style[bowler]
    batter_hand = history.players.hand[batter]
    venue_pitch = history.venues.pitch[venue]
    venue_home_team = history.venues.home_team[venue]
    at_home = (batter_team == venue_home_team).astype(np.float64)

    max_match = int(max(ball_match.max(), matches.match.max()))
    match_season = np.zeros(max_match + 1, dtype=np.int64)
    match_season[matches.match.to_numpy()] = matches.season.to_numpy()
    ball_season = match_season[ball_match]

    match_ids_sorted = matches.match.to_numpy()
    match_idx_lookup = np.zeros(max_match + 1, dtype=np.int64)
    match_idx_lookup[match_ids_sorted] = np.arange(N_m)
    ball_match_idx = match_idx_lookup[ball_match]

    sign_split = np.where(bowler_style == PACE, 0.5, -0.5)

    D = np.stack([model.bs, model.bq, model.wt, model.wq, model.c], axis=0)  # (5, 6)
    D_T = D.T  # (6, 5)

    offsets = {}
    o = 0

    def alloc(name, size):
        nonlocal o
        offsets[name] = (o, o + size)
        o += size

    alloc("style", N_p)
    alloc("quality", N_p)
    alloc("split", N_p)
    alloc("kind", N_p)
    alloc("bowl_quality", N_p)
    alloc("venue_level", N_v)
    alloc("venue_dew", N_v)
    alloc("affinity", N_p * N_v)
    alloc("type_table", 4)
    alloc("pitch_table", 6)
    alloc("wear", 1)
    alloc("home_lift", 1)
    alloc("era", N_s)
    alloc("day_effect", N_m)
    total = o

    reg = {
        "style": 4.0,
        "quality": 4.0,
        "split": 16.0,
        "kind": 4.0,
        "bowl_quality": 4.0,
        "venue_level": 4.0,
        "venue_dew": 4.0,
        "affinity": 40.0,
        "type_table": 4.0,
        "pitch_table": 4.0,
        "wear": 4.0,
        "home_lift": 4.0,
        "era": 4.0,
        "day_effect": 40.0,
    }

    aff_idx = batter * N_v + venue
    tt_idx = batter_hand * 2 + bowler_style
    pt_idx = bowler_style * 3 + venue_pitch
    idx = np.arange(N)

    wear_i = offsets["wear"][0]
    hl_i = offsets["home_lift"][0]

    def loss_and_grad(theta):
        style = theta[offsets["style"][0]:offsets["style"][1]]
        quality = theta[offsets["quality"][0]:offsets["quality"][1]]
        split = theta[offsets["split"][0]:offsets["split"][1]]
        kind = theta[offsets["kind"][0]:offsets["kind"][1]]
        bowl_quality = theta[offsets["bowl_quality"][0]:offsets["bowl_quality"][1]]
        venue_level = theta[offsets["venue_level"][0]:offsets["venue_level"][1]]
        venue_dew = theta[offsets["venue_dew"][0]:offsets["venue_dew"][1]]
        affinity = theta[offsets["affinity"][0]:offsets["affinity"][1]].reshape(N_p, N_v)
        type_table = theta[offsets["type_table"][0]:offsets["type_table"][1]].reshape(2, 2)
        pitch_table = theta[offsets["pitch_table"][0]:offsets["pitch_table"][1]].reshape(2, 3)
        wear = theta[wear_i]
        home_lift = theta[hl_i]
        era = theta[offsets["era"][0]:offsets["era"][1]]
        day_effect = theta[offsets["day_effect"][0]:offsets["day_effect"][1]]

        f_bs = style[batter]
        f_bq = quality[batter] + split[batter] * sign_split
        f_wt = kind[bowler]
        f_wq = bowl_quality[bowler]
        f_c = (venue_level[venue]
               + era[ball_season]
               + chasing * (venue_dew[venue] - wear)
               + affinity[batter, venue]
               + home_lift * at_home
               + type_table[batter_hand, bowler_style]
               - pitch_table[bowler_style, venue_pitch]
               + day_effect[ball_match_idx])
        F = np.column_stack([f_bs, f_bq, f_wt, f_wq, f_c])
        z = z_pub + F @ D
        zmax = z.max(axis=1, keepdims=True)
        ez = np.exp(z - zmax)
        s = ez.sum(axis=1, keepdims=True)
        p = ez / s
        log_norm = zmax[:, 0] + np.log(s[:, 0])
        nll = float((log_norm - z[idx, outcome]).sum())

        reg_sum = 0.0
        for name, (a, b) in offsets.items():
            reg_sum += 0.5 * reg[name] * float((theta[a:b] ** 2).sum())

        dz = p.copy()
        dz[idx, outcome] -= 1.0
        dF = dz @ D_T  # (N, 5)
        dc = dF[:, 4]

        g = np.zeros_like(theta)
        g[offsets["style"][0]:offsets["style"][1]] = np.bincount(batter, weights=dF[:, 0], minlength=N_p)
        g[offsets["quality"][0]:offsets["quality"][1]] = np.bincount(batter, weights=dF[:, 1], minlength=N_p)
        g[offsets["split"][0]:offsets["split"][1]] = np.bincount(batter, weights=dF[:, 1] * sign_split, minlength=N_p)
        g[offsets["kind"][0]:offsets["kind"][1]] = np.bincount(bowler, weights=dF[:, 2], minlength=N_p)
        g[offsets["bowl_quality"][0]:offsets["bowl_quality"][1]] = np.bincount(bowler, weights=dF[:, 3], minlength=N_p)
        g[offsets["venue_level"][0]:offsets["venue_level"][1]] = np.bincount(venue, weights=dc, minlength=N_v)
        g[offsets["venue_dew"][0]:offsets["venue_dew"][1]] = np.bincount(venue, weights=dc * chasing, minlength=N_v)
        g[offsets["affinity"][0]:offsets["affinity"][1]] = np.bincount(aff_idx, weights=dc, minlength=N_p * N_v)
        g[offsets["type_table"][0]:offsets["type_table"][1]] = np.bincount(tt_idx, weights=dc, minlength=4)
        g[offsets["pitch_table"][0]:offsets["pitch_table"][1]] = np.bincount(pt_idx, weights=-dc, minlength=6)
        g[wear_i] = -float((dc * chasing).sum())
        g[hl_i] = float((dc * at_home).sum())
        g[offsets["era"][0]:offsets["era"][1]] = np.bincount(ball_season, weights=dc, minlength=N_s)
        g[offsets["day_effect"][0]:offsets["day_effect"][1]] = np.bincount(ball_match_idx, weights=dc, minlength=N_m)

        for name, (a, b) in offsets.items():
            g[a:b] += reg[name] * theta[a:b]

        return nll + reg_sum, g

    rng = np.random.default_rng(42)
    theta0 = 0.01 * rng.standard_normal(total)
    result = opt.minimize(
        loss_and_grad, theta0, jac=True, method="L-BFGS-B",
        options={"maxiter": 600, "ftol": 1e-10, "gtol": 1e-7, "maxfun": 3000},
    )
    theta_hat = result.x

    parts = {
        "style": theta_hat[offsets["style"][0]:offsets["style"][1]].copy(),
        "quality": theta_hat[offsets["quality"][0]:offsets["quality"][1]].copy(),
        "split": theta_hat[offsets["split"][0]:offsets["split"][1]].copy(),
        "kind": theta_hat[offsets["kind"][0]:offsets["kind"][1]].copy(),
        "bowl_quality": theta_hat[offsets["bowl_quality"][0]:offsets["bowl_quality"][1]].copy(),
        "venue_level": theta_hat[offsets["venue_level"][0]:offsets["venue_level"][1]].copy(),
        "venue_dew": theta_hat[offsets["venue_dew"][0]:offsets["venue_dew"][1]].copy(),
        "affinity": theta_hat[offsets["affinity"][0]:offsets["affinity"][1]].reshape(N_p, N_v).copy(),
        "type_table": theta_hat[offsets["type_table"][0]:offsets["type_table"][1]].reshape(2, 2).copy(),
        "pitch_table": theta_hat[offsets["pitch_table"][0]:offsets["pitch_table"][1]].reshape(2, 3).copy(),
        "wear": float(theta_hat[wear_i]),
        "home_lift": float(theta_hat[hl_i]),
        "era": theta_hat[offsets["era"][0]:offsets["era"][1]].copy(),
        "day_effect": theta_hat[offsets["day_effect"][0]:offsets["day_effect"][1]].copy(),
    }
    return parts, result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    history, fixtures = load_league(args.league)
    model = load_public_model()

    parts, _ = fit_skills(history, model)

    day_sd = float(np.std(parts["day_effect"]))
    era_future = float(parts["era"][-1])

    book = SkillBook(
        history.players, history.venues,
        style=parts["style"], quality=parts["quality"], split=parts["split"],
        kind=parts["kind"], bowl_quality=parts["bowl_quality"],
        type_table=parts["type_table"], pitch_table=parts["pitch_table"],
        venue_level=parts["venue_level"], venue_dew=parts["venue_dew"],
        affinity=parts["affinity"],
        home_lift=parts["home_lift"],
        era=era_future,
        day_sd=day_sd,
        wear=parts["wear"],
    )

    sim = MatchSimulator(model)
    gen = np.random.default_rng(2026)
    N_sim = 10000
    rows = []
    for f in fixtures:
        p_home = sim.win_probability(book, f, N_sim, gen)
        rows.append((f.match, p_home))

    df = pd.DataFrame(rows, columns=["fixture", "p_home"])
    df.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
