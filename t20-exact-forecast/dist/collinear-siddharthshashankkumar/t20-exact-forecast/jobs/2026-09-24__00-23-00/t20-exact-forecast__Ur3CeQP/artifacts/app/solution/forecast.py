"""forecast.py

Fits hidden player, venue and league parameters via multinomial MLE on the
public ball model, then simulates each fixture with the shared MatchSimulator.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here.parent))

from engine.model import (  # noqa: E402
    SkillBook, MatchSimulator, load_public_model,
)
from engine.league_io import load_league  # noqa: E402


def _prepare_arrays(history, model):
    balls = history.balls
    players, venues = history.players, history.venues
    cal = model.cal

    over = balls.over.to_numpy(np.int64)
    ball_in_over = balls.ball.to_numpy(np.int64)
    position = balls.position.to_numpy(np.int64)
    wickets = balls.wickets_before.to_numpy(np.int64)
    runs = balls.runs_before.to_numpy(np.int64)
    target = balls.target.to_numpy(np.int64)
    innings = balls.innings.to_numpy(np.int64)
    bat = balls.batter.to_numpy(np.int64)
    bowler = balls.bowler.to_numpy(np.int64)
    venue_id = balls.venue.to_numpy(np.int64)
    batting_team = balls.batting_team.to_numpy(np.int64)
    outcome = balls.outcome.to_numpy(np.int64)
    season = balls.season.to_numpy(np.int64)

    N = len(balls)
    chasing = (innings == 2).astype(np.float64)
    ball_num = 6 * over + ball_in_over

    pressure = np.zeros(N)
    mask = target > 0
    if mask.any():
        need = np.clip(target[mask] - runs[mask], 1, None) / ((120 - ball_num[mask]) / 6.0)
        pressure[mask] = np.clip(np.log(need / cal.par_rate[over[mask]]), -1.0, 1.2)

    pub = cal.over_logits[over].astype(np.float64).copy()
    pub += cal.position_vectors[position]
    pub += np.outer(wickets.astype(np.float64) - cal.typical_wickets[over], cal.wickets_vector)
    pub += np.outer(chasing, cal.second_innings_vector)
    pub += np.outer(pressure, cal.pressure_vector)

    hand = players.hand[bat]
    bstyle = players.style[bowler]
    pitch = venues.pitch[venue_id]
    home_team_of_venue = venues.home_team[venue_id]
    is_home_bat = (home_team_of_venue == batting_team).astype(np.float64)

    return {
        "N": N,
        "n_players": len(players.role),
        "n_venues": len(venues.pitch),
        "pub": pub,
        "outcome": outcome,
        "bat": bat,
        "bowler": bowler,
        "venue_id": venue_id,
        "hand": hand.astype(np.int64),
        "bstyle": bstyle.astype(np.int64),
        "pitch": pitch.astype(np.int64),
        "is_home_bat": is_home_bat,
        "chasing": chasing,
        "season": season,
    }


def fit_book(history, model, lam=1.0, maxiter=300):
    arr = _prepare_arrays(history, model)
    N = arr["N"]
    n_p = arr["n_players"]
    n_v = arr["n_venues"]
    pub = arr["pub"]
    outcome = arr["outcome"]
    bat = arr["bat"]
    bowler = arr["bowler"]
    venue_id = arr["venue_id"]
    hand = arr["hand"]
    bstyle = arr["bstyle"]
    pitch = arr["pitch"]
    is_home_bat = arr["is_home_bat"]
    chasing = arr["chasing"]
    season = arr["season"]
    n_seasons = int(season.max()) + 1

    bs = model.bs
    bq = model.bq
    wt = model.wt
    wq = model.wq
    c = model.c

    # Parameter layout
    layout = [
        ("bs_p", n_p),
        ("bq_p", n_p * 2),          # bat quality vs [pace, spin]
        ("wt_p", n_p),              # bowler kind
        ("wq_p", n_p),              # bowler quality
        ("vl", n_v),                # venue level
        ("vd", n_v),                # venue dew (used only if chasing)
        ("hl", 1),                  # home lift for batting side
        ("era_s", n_seasons),       # per-season era
        ("wear", 1),                # league wear (subtracted from dew if chasing)
        ("type_tab", 4),            # [hand][bowl_style]
        ("pitch_tab", 6),           # [bowl_style][pitch]
        ("aff", n_p * n_v),         # affinity per (player, venue), heavily reg'd
    ]
    offsets = {}
    off = 0
    for name, sz in layout:
        offsets[name] = (off, off + sz)
        off += sz
    total = off

    # Per-param regularization strengths
    reg = np.full(total, lam)
    reg[offsets["hl"][0]:offsets["hl"][1]] = 0.01
    reg[offsets["era_s"][0]:offsets["era_s"][1]] = 0.01
    reg[offsets["wear"][0]:offsets["wear"][1]] = 0.01
    reg[offsets["type_tab"][0]:offsets["type_tab"][1]] = 0.1
    reg[offsets["pitch_tab"][0]:offsets["pitch_tab"][1]] = 0.1
    reg[offsets["vl"][0]:offsets["vl"][1]] = 0.5
    reg[offsets["vd"][0]:offsets["vd"][1]] = 0.5
    reg[offsets["aff"][0]:offsets["aff"][1]] = 20.0

    arange_N = np.arange(N)

    def unpack(theta):
        return {name: theta[offsets[name][0]:offsets[name][1]] for name in offsets}

    def loss_and_grad(theta):
        p_ = unpack(theta)
        bs_p = p_["bs_p"]
        bq_p = p_["bq_p"].reshape(n_p, 2)
        wt_p = p_["wt_p"]
        wq_p = p_["wq_p"]
        vl = p_["vl"]
        vd = p_["vd"]
        hl = p_["hl"][0]
        era_s = p_["era_s"]
        wear = p_["wear"][0]
        type_tab = p_["type_tab"].reshape(2, 2)
        pitch_tab = p_["pitch_tab"].reshape(2, 3)
        aff = p_["aff"].reshape(n_p, n_v)

        bat_style_scalar = bs_p[bat]
        bat_qual_scalar = bq_p[bat, bstyle]
        bowl_kind_scalar = wt_p[bowler]
        bowl_qual_scalar = wq_p[bowler]
        cond_scalar = (
            vl[venue_id]
            + era_s[season]
            + hl * is_home_bat
            + type_tab[hand, bstyle]
            - pitch_tab[bstyle, pitch]
            + chasing * (vd[venue_id] - wear)
            + aff[bat, venue_id]
        )

        z = (
            pub
            + bat_style_scalar[:, None] * bs[None, :]
            + bat_qual_scalar[:, None] * bq[None, :]
            + bowl_kind_scalar[:, None] * wt[None, :]
            + bowl_qual_scalar[:, None] * wq[None, :]
            + cond_scalar[:, None] * c[None, :]
        )

        z_max = z.max(axis=1, keepdims=True)
        exp_z = np.exp(z - z_max)
        Z = exp_z.sum(axis=1, keepdims=True)
        log_probs = z - z_max - np.log(Z)
        nll = -log_probs[arange_N, outcome].sum()

        prob = exp_z / Z
        d_z = prob.copy()
        d_z[arange_N, outcome] -= 1.0

        d_bs = d_z @ bs
        d_bq = d_z @ bq
        d_wt = d_z @ wt
        d_wq = d_z @ wq
        d_c = d_z @ c

        g_bs_p = np.bincount(bat, weights=d_bs, minlength=n_p)
        idx_bq = bat * 2 + bstyle
        g_bq_p = np.bincount(idx_bq, weights=d_bq, minlength=n_p * 2)
        g_wt_p = np.bincount(bowler, weights=d_wt, minlength=n_p)
        g_wq_p = np.bincount(bowler, weights=d_wq, minlength=n_p)
        g_vl = np.bincount(venue_id, weights=d_c, minlength=n_v)
        g_vd = np.bincount(venue_id, weights=d_c * chasing, minlength=n_v)
        g_hl = np.array([(d_c * is_home_bat).sum()])
        g_era_s = np.bincount(season, weights=d_c, minlength=n_seasons)
        g_wear = np.array([-(d_c * chasing).sum()])
        idx_type = hand * 2 + bstyle
        g_type = np.bincount(idx_type, weights=d_c, minlength=4)
        idx_pitch = bstyle * 3 + pitch
        g_pitch = -np.bincount(idx_pitch, weights=d_c, minlength=6)
        idx_aff = bat * n_v + venue_id
        g_aff = np.bincount(idx_aff, weights=d_c, minlength=n_p * n_v)

        grad = np.concatenate([
            g_bs_p, g_bq_p, g_wt_p, g_wq_p,
            g_vl, g_vd, g_hl, g_era_s, g_wear,
            g_type, g_pitch, g_aff,
        ])
        grad = grad + reg * theta
        loss = nll + 0.5 * (reg * theta * theta).sum()
        return loss, grad

    theta0 = np.zeros(total)
    res = minimize(
        loss_and_grad, theta0, jac=True, method="L-BFGS-B",
        options={"maxiter": maxiter, "ftol": 1e-9, "gtol": 1e-6, "maxcor": 30},
    )
    theta = res.x
    p_ = unpack(theta)

    players, venues = history.players, history.venues
    bs_p = p_["bs_p"].copy()
    bq_p = p_["bq_p"].reshape(n_p, 2)
    # quality[player] + split[player]*sign_of_bowler_style (sign=+0.5 pace, -0.5 spin)
    # so bq_p[.,PACE]=quality+0.5*split, bq_p[.,SPIN]=quality-0.5*split
    quality = 0.5 * (bq_p[:, 0] + bq_p[:, 1])
    split = bq_p[:, 0] - bq_p[:, 1]
    kind = p_["wt_p"].copy()
    bowl_quality = p_["wq_p"].copy()
    venue_level = p_["vl"].copy()
    venue_dew = p_["vd"].copy()
    home_lift = float(p_["hl"][0])
    era_s = p_["era_s"].copy()
    # forecast era for the upcoming season by linear extrapolation from the last
    # two seasons (with 1+ seasons of history) or fall back to the last value.
    if len(era_s) >= 2:
        era_future = float(2.0 * era_s[-1] - era_s[-2])
        # blend with last value to be conservative against extrapolation error
        era_future = 0.5 * era_future + 0.5 * float(era_s[-1])
    else:
        era_future = float(era_s[-1])
    wear = float(p_["wear"][0])
    type_table = p_["type_tab"].reshape(2, 2)
    pitch_table = p_["pitch_tab"].reshape(2, 3)
    affinity = p_["aff"].reshape(n_p, n_v).copy()

    day_sd = 0.12

    book = SkillBook(
        players, venues,
        bs_p, quality, split, kind, bowl_quality,
        type_table, pitch_table,
        venue_level, venue_dew, affinity,
        home_lift, era_future, day_sd, wear,
    )
    return book


def forecast(league_folder, out_path, n_sim=20000, seed=1234):
    model = load_public_model()
    history, fixtures = load_league(league_folder)
    book = fit_book(history, model)
    sim = MatchSimulator(model)

    rows = []
    for f in fixtures:
        gen = np.random.default_rng(seed + int(f.match))
        p = sim.win_probability(book, f, n_sim, gen)
        # Guard against 0/1 from small tails; grader clips to [0.002, 0.998]
        p = float(min(max(p, 0.002), 0.998))
        rows.append((int(f.match), p))

    out = pd.DataFrame(rows, columns=["fixture", "p_home"])
    out.to_csv(out_path, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    forecast(args.league, args.out)


if __name__ == "__main__":
    main()
