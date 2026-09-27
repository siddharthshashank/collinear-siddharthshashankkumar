import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from engine.model import (
    BallModel, InningsSimulator, MatchSimulator, PublicConstants, SkillBook,
)
from engine.league_io import load_league


def compute_z_public(model, balls):
    over = balls.over.to_numpy().astype(int)
    position = balls.position.to_numpy().astype(int)
    wickets = balls.wickets_before.to_numpy().astype(int)
    innings = balls.innings.to_numpy().astype(int)
    chasing = (innings == 2).astype(float)
    target = balls.target.to_numpy().astype(int)
    runs_before = balls.runs_before.to_numpy().astype(int)
    ball_num = over * 6 + balls.ball.to_numpy().astype(int)

    overs_left = np.maximum((120 - ball_num) / 6.0, 1e-6)
    need_rate = np.clip(target - runs_before, 1, None) / overs_left
    par = model.cal.par_rate[over]
    pressure_val = np.where(chasing > 0, np.clip(np.log(need_rate / par), -1.0, 1.2), 0.0)

    z_pub = model.situation(over, position, wickets, chasing, pressure_val)
    return z_pub, chasing


def fit_skills(model, history, lam=1.0, maxiter=250, verbose=False):
    from scipy.optimize import minimize

    balls = history.balls
    N = len(balls)
    z_pub, chasing = compute_z_public(model, balls)

    batter = balls.batter.to_numpy().astype(int)
    bowler = balls.bowler.to_numpy().astype(int)
    venue = balls.venue.to_numpy().astype(int)
    batting_team = balls.batting_team.to_numpy().astype(int)
    season = balls.season.to_numpy().astype(int)
    match_arr = balls.match.to_numpy().astype(int)
    outcome = balls.outcome.to_numpy().astype(int)

    match_ids, match_inv = np.unique(match_arr, return_inverse=True)

    P = len(history.players.role)
    V = len(history.venues.pitch)
    S = int(season.max()) + 1
    M = len(match_ids)

    hand_all = history.players.hand.astype(int)
    style_all = history.players.style.astype(int)
    pitch_all = history.venues.pitch.astype(int)
    home_of_venue = history.venues.home_team.astype(int)

    batter_hand = hand_all[batter]
    bowler_style = style_all[bowler]
    ball_pitch = pitch_all[venue]
    at_home_bat = (home_of_venue[venue] == batting_team).astype(float)
    sign = np.where(bowler_style == 0, 0.5, -0.5)

    bs, bq, wt, wq, c_dir = model.bs, model.bq, model.wt, model.wq, model.c

    layout = [
        ("bat_style", P), ("bat_quality", P), ("bat_split", P),
        ("bowl_kind", P), ("bowl_quality", P),
        ("venue_level", V), ("venue_chase", V),
        ("home_lift", 1), ("era", S), ("day", M),
        ("type_table", 4), ("pitch_table", 6),
    ]
    idx = {}
    off = 0
    for name, sz in layout:
        idx[name] = (off, off + sz)
        off += sz
    n_params = off

    tt_flat = batter_hand * 2 + bowler_style
    pt_flat = bowler_style * 3 + ball_pitch
    N_range = np.arange(N)

    def loss_and_grad(theta):
        bat_style_p = theta[idx["bat_style"][0]:idx["bat_style"][1]]
        bat_quality_p = theta[idx["bat_quality"][0]:idx["bat_quality"][1]]
        bat_split_p = theta[idx["bat_split"][0]:idx["bat_split"][1]]
        bowl_kind_p = theta[idx["bowl_kind"][0]:idx["bowl_kind"][1]]
        bowl_quality_p = theta[idx["bowl_quality"][0]:idx["bowl_quality"][1]]
        venue_level_p = theta[idx["venue_level"][0]:idx["venue_level"][1]]
        venue_chase_p = theta[idx["venue_chase"][0]:idx["venue_chase"][1]]
        home_lift_p = theta[idx["home_lift"][0]]
        era_p = theta[idx["era"][0]:idx["era"][1]]
        day_p = theta[idx["day"][0]:idx["day"][1]]
        type_tbl_p = theta[idx["type_table"][0]:idx["type_table"][1]].reshape(2, 2)
        pitch_tbl_p = theta[idx["pitch_table"][0]:idx["pitch_table"][1]].reshape(2, 3)

        a = bat_style_p[batter]
        b_ = bat_quality_p[batter] + bat_split_p[batter] * sign
        k = bowl_kind_p[bowler]
        q = bowl_quality_p[bowler]
        c_scalar = (venue_level_p[venue] + venue_chase_p[venue] * chasing
                    + home_lift_p * at_home_bat + era_p[season] + day_p[match_inv]
                    + type_tbl_p[batter_hand, bowler_style]
                    - pitch_tbl_p[bowler_style, ball_pitch])

        z = (z_pub
             + a[:, None] * bs
             + b_[:, None] * bq
             + k[:, None] * wt
             + q[:, None] * wq
             + c_scalar[:, None] * c_dir)

        z_max = z.max(axis=1, keepdims=True)
        exp_z = np.exp(z - z_max)
        sum_exp = exp_z.sum(axis=1, keepdims=True)
        log_softmax = (z - z_max) - np.log(sum_exp)
        nll = -log_softmax[N_range, outcome].sum()

        soft = exp_z / sum_exp
        dz = soft.copy()
        dz[N_range, outcome] -= 1.0

        d_a = dz @ bs
        d_b = dz @ bq
        d_k = dz @ wt
        d_q = dz @ wq
        d_c = dz @ c_dir

        grad = np.zeros_like(theta)
        grad[idx["bat_style"][0]:idx["bat_style"][1]] = np.bincount(batter, weights=d_a, minlength=P)
        grad[idx["bat_quality"][0]:idx["bat_quality"][1]] = np.bincount(batter, weights=d_b, minlength=P)
        grad[idx["bat_split"][0]:idx["bat_split"][1]] = np.bincount(batter, weights=d_b * sign, minlength=P)
        grad[idx["bowl_kind"][0]:idx["bowl_kind"][1]] = np.bincount(bowler, weights=d_k, minlength=P)
        grad[idx["bowl_quality"][0]:idx["bowl_quality"][1]] = np.bincount(bowler, weights=d_q, minlength=P)
        grad[idx["venue_level"][0]:idx["venue_level"][1]] = np.bincount(venue, weights=d_c, minlength=V)
        grad[idx["venue_chase"][0]:idx["venue_chase"][1]] = np.bincount(venue, weights=d_c * chasing, minlength=V)
        grad[idx["home_lift"][0]] = (d_c * at_home_bat).sum()
        grad[idx["era"][0]:idx["era"][1]] = np.bincount(season, weights=d_c, minlength=S)
        grad[idx["day"][0]:idx["day"][1]] = np.bincount(match_inv, weights=d_c, minlength=M)
        grad[idx["type_table"][0]:idx["type_table"][1]] = np.bincount(tt_flat, weights=d_c, minlength=4)
        grad[idx["pitch_table"][0]:idx["pitch_table"][1]] = -np.bincount(pt_flat, weights=d_c, minlength=6)

        # L2 regularization
        nll = nll + 0.5 * lam * float(np.dot(theta, theta))
        grad = grad + lam * theta

        return nll, grad

    theta0 = np.zeros(n_params)
    result = minimize(loss_and_grad, theta0, jac=True, method="L-BFGS-B",
                      options={"maxiter": maxiter, "ftol": 1e-9, "gtol": 1e-6})
    if verbose:
        print(f"optim: success={result.success} fun={result.fun:.2f} nit={result.nit}")
    return result.x, idx


def build_skillbook(theta, idx, history):
    P = len(history.players.role)
    V = len(history.venues.pitch)

    bat_style = theta[idx["bat_style"][0]:idx["bat_style"][1]].copy()
    bat_quality = theta[idx["bat_quality"][0]:idx["bat_quality"][1]].copy()
    bat_split = theta[idx["bat_split"][0]:idx["bat_split"][1]].copy()
    bowl_kind = theta[idx["bowl_kind"][0]:idx["bowl_kind"][1]].copy()
    bowl_quality = theta[idx["bowl_quality"][0]:idx["bowl_quality"][1]].copy()
    venue_level = theta[idx["venue_level"][0]:idx["venue_level"][1]].copy()
    venue_chase = theta[idx["venue_chase"][0]:idx["venue_chase"][1]].copy()
    home_lift = float(theta[idx["home_lift"][0]])
    era_arr = theta[idx["era"][0]:idx["era"][1]].copy()
    day_arr = theta[idx["day"][0]:idx["day"][1]].copy()
    type_tbl = theta[idx["type_table"][0]:idx["type_table"][1]].reshape(2, 2).copy()
    pitch_tbl = theta[idx["pitch_table"][0]:idx["pitch_table"][1]].reshape(2, 3).copy()

    # For the next season, use last observed era (random-walk one-step forecast).
    era_next = float(era_arr[-1])

    # day pitch is drawn afresh each match: estimate its spread from fitted per-match values.
    day_sd = float(np.std(day_arr))

    # venue_chase = venue_dew - wear; fold into venue_dew and set wear=0.
    venue_dew = venue_chase
    wear = 0.0

    # No batter-by-venue affinity in our fit; keep at zero.
    affinity = np.zeros((P, V))

    return SkillBook(
        history.players, history.venues,
        style=bat_style, quality=bat_quality, split=bat_split,
        kind=bowl_kind, bowl_quality=bowl_quality,
        type_table=type_tbl, pitch_table=pitch_tbl,
        venue_level=venue_level, venue_dew=venue_dew, affinity=affinity,
        home_lift=home_lift, era=era_next, day_sd=day_sd, wear=wear,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=6000)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--verbose", action="store_[REDACTED]")
    args = parser.parse_args()

    np.random.seed(args.seed)

    history, fixtures = load_league(args.league)
    pub_path = _HERE.parent / "engine" / "public.json"
    model = BallModel(PublicConstants(json.loads(pub_path.read_text())))

    theta, idx = fit_skills(model, history, verbose=args.verbose)
    book = build_skillbook(theta, idx, history)

    sim = MatchSimulator(model)
    rng = np.random.default_rng(args.seed)

    rows = []
    for fx in fixtures:
        p = sim.win_probability(book, fx, args.sims, rng)
        p = float(np.clip(p, 0.002, 0.998))
        rows.append((fx.match, p))
        if args.verbose:
            print(f"fixture {fx.match}: p_home={p:.4f}")

    df = pd.DataFrame(rows, columns=["fixture", "p_home"])
    df.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
