#!/usr/bin/env python3
"""Learn hidden league state from history then simulate each fixture."""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine.model import (  # noqa: E402
    PACE,
    SPIN,
    MatchSimulator,
    SkillBook,
    load_public_model,
)
from engine.league_io import load_league  # noqa: E402


def _public_logits(balls, model):
    over = balls["over"].to_numpy()
    position = balls["position"].to_numpy()
    wickets = balls["wickets_before"].to_numpy()
    runs = balls["runs_before"].to_numpy()
    target = balls["target"].to_numpy()
    ball_idx = over * 6 + balls["ball"].to_numpy()
    innings = balls["innings"].to_numpy()
    chasing = (innings == 2).astype(float)

    pressure = np.zeros_like(chasing)
    mask = chasing > 0
    if mask.any():
        pressure[mask] = model.pressure(target[mask], runs[mask], ball_idx[mask])

    z = model.situation(over, position, wickets, chasing, pressure)
    return z, chasing


def fit_book(history, model, n_iters=12, verbose=False):
    balls = history.balls
    N = len(balls)
    n_players = len(history.players.role)
    n_venues = len(history.venues.pitch)
    n_seasons = int(history.seasons)

    outcome = balls["outcome"].to_numpy()
    batter = balls["batter"].to_numpy()
    bowler = balls["bowler"].to_numpy()
    venue_of = balls["venue"].to_numpy()
    season_of = balls["season"].to_numpy()
    match_of = balls["match"].to_numpy()
    bat_team = balls["batting_team"].to_numpy()

    bowl_style = history.players.style
    bat_hand = history.players.hand
    pitch_of_venue = history.venues.pitch
    home_of_venue = history.venues.home_team

    bwl_style_of_ball = bowl_style[bowler].astype(int)
    bat_hand_of_ball = bat_hand[batter].astype(int)
    pitch_of_ball = pitch_of_venue[venue_of].astype(int)
    at_home_of_ball = (home_of_venue[venue_of] == bat_team).astype(float)

    z_pub, chasing = _public_logits(balls, model)

    bs, bq, wt, wq, cvec = model.bs, model.bq, model.wt, model.wq, model.c

    n_matches = int(match_of.max()) + 1
    n_seasons = max(n_seasons, 1)

    style = np.zeros(n_players)
    quality = np.zeros(n_players)
    split = np.zeros(n_players)
    kind_p = np.zeros(n_players)
    bowlq = np.zeros(n_players)
    venue_level = np.zeros(n_venues)
    era = np.zeros(n_seasons)
    home_lift = 0.0
    wear = 0.0
    dew = np.zeros(n_venues)
    type_table = np.zeros((2, 2))
    pitch_table = np.zeros((2, 3))
    match_effect = np.zeros(n_matches)
    affinity_pv = np.zeros((n_players, n_venues))

    lam_style = 4.0
    lam_quality = 4.0
    lam_split = 20.0
    lam_kind = 4.0
    lam_bowlq = 4.0
    lam_venue = 15.0
    lam_era = 15.0
    lam_home = 30.0
    lam_wear = 30.0
    lam_dew = 30.0
    lam_tt = 30.0
    lam_pt = 30.0
    lam_match = 20.0
    lam_aff = 50.0

    mp = bwl_style_of_ball == PACE
    ms = bwl_style_of_ball == SPIN

    aff_flat_idx = batter * n_venues + venue_of
    n_aff = n_players * n_venues

    idx_arange = np.arange(N)

    def compute_conditions_per_ball():
        return (
            venue_level[venue_of]
            + era[season_of]
            + home_lift * at_home_of_ball
            + chasing * (dew[venue_of] - wear)
            + type_table[bat_hand_of_ball, bwl_style_of_ball]
            - pitch_table[bwl_style_of_ball, pitch_of_ball]
            + affinity_pv[batter, venue_of]
            + match_effect[match_of]
        )

    sign_ps = np.where(mp, 0.5, -0.5)  # 0.5 for pace, -0.5 for spin

    def compute_z():
        s = style[batter]
        q_bat = quality[batter] + split[batter] * sign_ps
        k = kind_p[bowler]
        bqb = bowlq[bowler]
        conditions = compute_conditions_per_ball()
        z = z_pub + (
            s[:, None] * bs
            + q_bat[:, None] * bq
            + k[:, None] * wt
            + bqb[:, None] * wq
            + conditions[:, None] * cvec
        )
        return z

    def softmax_p(z):
        zm = z - z.max(axis=1, keepdims=True)
        ez = np.exp(zm)
        return ez / ez.sum(axis=1, keepdims=True)

    def residual_and_p(z):
        p = softmax_p(z)
        r = -p.copy()
        r[idx_arange, outcome] += 1.0
        return r, p

    def grad_hess_along(r, p, direction):
        g = r @ direction
        h = (direction * direction * p).sum(axis=1) - (p @ direction) ** 2
        return g, h

    step = 0.9

    for it in range(n_iters):
        z = compute_z()
        r, p = residual_and_p(z)

        g_bs, h_bs = grad_hess_along(r, p, bs)
        g_bq, h_bq = grad_hess_along(r, p, bq)
        g_wt, h_wt = grad_hess_along(r, p, wt)
        g_wq, h_wq = grad_hess_along(r, p, wq)

        gs = np.bincount(batter, weights=g_bs, minlength=n_players) - lam_style * style
        hs = np.bincount(batter, weights=h_bs, minlength=n_players) + lam_style
        style = style + step * gs / np.maximum(hs, 1e-8)

        # quality: direction bq, contribution quality[b] * bq per ball
        gq = np.bincount(batter, weights=g_bq, minlength=n_players) - lam_quality * quality
        hq = np.bincount(batter, weights=h_bq, minlength=n_players) + lam_quality
        quality = quality + step * gq / np.maximum(hq, 1e-8)
        # split: direction sign_ps * bq (magnitude 0.5), so grad = sign_ps * g_bq, hess = 0.25 * h_bq
        gsp = np.bincount(batter, weights=sign_ps * g_bq, minlength=n_players) - lam_split * split
        hsp = np.bincount(batter, weights=0.25 * h_bq, minlength=n_players) + lam_split
        split = split + step * gsp / np.maximum(hsp, 1e-8)

        gk = np.bincount(bowler, weights=g_wt, minlength=n_players) - lam_kind * kind_p
        hk = np.bincount(bowler, weights=h_wt, minlength=n_players) + lam_kind
        kind_p = kind_p + step * gk / np.maximum(hk, 1e-8)

        gbq = np.bincount(bowler, weights=g_wq, minlength=n_players) - lam_bowlq * bowlq
        hbq = np.bincount(bowler, weights=h_wq, minlength=n_players) + lam_bowlq
        bowlq = bowlq + step * gbq / np.maximum(hbq, 1e-8)

        # cvec-direction params: sequential Gauss-Seidel updates so they don't overshoot
        # Recompute z/p/r before each so competing terms don't stack.
        z = compute_z()
        r, p = residual_and_p(z)
        g_c, h_c = grad_hess_along(r, p, cvec)

        gvl = np.bincount(venue_of, weights=g_c, minlength=n_venues) - lam_venue * venue_level
        hvl = np.bincount(venue_of, weights=h_c, minlength=n_venues) + lam_venue
        venue_level = venue_level + step * gvl / np.maximum(hvl, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        ge = np.bincount(season_of, weights=g_c, minlength=n_seasons) - lam_era * era
        he = np.bincount(season_of, weights=h_c, minlength=n_seasons) + lam_era
        era = era + step * ge / np.maximum(he, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        gh = (g_c * at_home_of_ball).sum() - lam_home * home_lift
        hh = (h_c * at_home_of_ball ** 2).sum() + lam_home
        home_lift = home_lift + step * gh / max(hh, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        gw = -(g_c * chasing).sum() - lam_wear * wear
        hw = (h_c * chasing ** 2).sum() + lam_wear
        wear = wear + step * gw / max(hw, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        gd = np.bincount(venue_of, weights=g_c * chasing, minlength=n_venues) - lam_dew * dew
        hd = np.bincount(venue_of, weights=h_c * chasing ** 2, minlength=n_venues) + lam_dew
        dew = dew + step * gd / np.maximum(hd, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        for h_v in range(2):
            for s_v in range(2):
                m = (bat_hand_of_ball == h_v) & (bwl_style_of_ball == s_v)
                if not m.any():
                    continue
                gt = g_c[m].sum() - lam_tt * type_table[h_v, s_v]
                ht = h_c[m].sum() + lam_tt
                type_table[h_v, s_v] = type_table[h_v, s_v] + step * gt / max(ht, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        for s_v in range(2):
            for p_v in range(3):
                m = (bwl_style_of_ball == s_v) & (pitch_of_ball == p_v)
                if not m.any():
                    continue
                gpt = -g_c[m].sum() - lam_pt * pitch_table[s_v, p_v]
                hpt = h_c[m].sum() + lam_pt
                pitch_table[s_v, p_v] = pitch_table[s_v, p_v] + step * gpt / max(hpt, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        gme = np.bincount(match_of, weights=g_c, minlength=n_matches) - lam_match * match_effect
        hme = np.bincount(match_of, weights=h_c, minlength=n_matches) + lam_match
        match_effect = match_effect + step * gme / np.maximum(hme, 1e-8)

        z = compute_z(); r, p = residual_and_p(z); g_c, h_c = grad_hess_along(r, p, cvec)
        aff_flat = affinity_pv.reshape(-1)
        ga = np.bincount(aff_flat_idx, weights=g_c, minlength=n_aff) - lam_aff * aff_flat
        ha = np.bincount(aff_flat_idx, weights=h_c, minlength=n_aff) + lam_aff
        aff_flat = aff_flat + step * ga / np.maximum(ha, 1e-8)
        affinity_pv = aff_flat.reshape(n_players, n_venues)

        if verbose:
            z = compute_z()
            zm = z - z.max(axis=1, keepdims=True)
            ez = np.exp(zm)
            logZ = np.log(ez.sum(axis=1)) + z.max(axis=1)
            ll = (z[idx_arange, outcome] - logZ).mean()
            print(f"iter {it}: LL/ball={ll:.4f}", file=sys.stderr)

    z = compute_z()
    zm = z - z.max(axis=1, keepdims=True)
    ez = np.exp(zm)
    logZ = np.log(ez.sum(axis=1)) + z.max(axis=1)
    ll = (z[idx_arange, outcome] - logZ).mean()
    print(f"fit done, LL/ball={ll:.4f}", file=sys.stderr)

    era_val = float(era[-1])
    day_sd = float(np.std(match_effect))

    return SkillBook(
        players=history.players,
        venues=history.venues,
        style=style,
        quality=quality,
        split=split,
        kind=kind_p,
        bowl_quality=bowlq,
        type_table=type_table,
        pitch_table=pitch_table,
        venue_level=venue_level,
        venue_dew=dew,
        affinity=affinity_pv,
        home_lift=float(home_lift),
        era=era_val,
        day_sd=day_sd,
        wear=float(wear),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    history, fixtures = load_league(args.league)
    model = load_public_model()
    book = fit_book(history, model, verbose=False)

    sim = MatchSimulator(model)
    gen = np.random.default_rng(20260924)

    rows = []
    for f in fixtures:
        p = sim.win_probability(book, f, n=12000, gen=gen)
        p = float(np.clip(p, 0.002, 0.998))
        rows.append({"fixture": f.match, "p_home": p})

    pd.DataFrame(rows).to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
