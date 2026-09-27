"""Forecast home-win probabilities for the fixtures of a simulated T20 league.

We do MAP inference on the hidden per-player and per-venue values that enter
the engine's ball-by-ball logistic model, then Monte-Carlo simulate each
fixture with the fitted SkillBook.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve()
sys.path.insert(0, str(_HERE.parent.parent))

from engine.league_io import load_league  # noqa: E402
from engine.model import (  # noqa: E402
    MatchSimulator,
    PACE,
    SkillBook,
    load_public_model,
)


def _public_logits(model, over, position, wickets_before, chasing, pressure):
    cal = model.cal
    z = cal.over_logits[over] + cal.position_vectors[position]
    z = z + np.multiply.outer(wickets_before - cal.typical_wickets[over], cal.wickets_vector)
    z = z + np.multiply.outer(chasing, cal.second_innings_vector)
    z = z + np.multiply.outer(pressure, cal.pressure_vector)
    return z


def fit_hidden(history, model, n_iter=40, verbose=False):
    balls = history.balls
    players = history.players
    venues = history.venues
    cal = model.cal
    N = len(balls)

    outcome = balls.outcome.to_numpy().astype(np.int64)
    over = balls.over.to_numpy().astype(np.int64)
    position = balls.position.to_numpy().astype(np.int64)
    wickets_before = balls.wickets_before.to_numpy().astype(float)
    runs_before = balls.runs_before.to_numpy().astype(np.int64)
    target_arr = balls.target.to_numpy().astype(np.int64)
    chasing = (target_arr > 0).astype(float)
    ball_in_over = balls.ball.to_numpy().astype(np.int64)
    ball_total = over * 6 + ball_in_over

    # pressure only in chase
    overs_remaining = np.maximum((120 - ball_total) / 6.0, 1e-6)
    need_rate = np.maximum(target_arr - runs_before, 1).astype(float) / overs_remaining
    par = cal.par_rate[over]
    press = np.clip(np.log(need_rate / par), -1.0, 1.2)
    pressure = np.where(chasing > 0, press, 0.0)

    z_pub = _public_logits(model, over, position, wickets_before, chasing, pressure)

    batter = balls.batter.to_numpy().astype(np.int64)
    bowler = balls.bowler.to_numpy().astype(np.int64)
    venue = balls.venue.to_numpy().astype(np.int64)
    batting_team = balls.batting_team.to_numpy().astype(np.int64)
    match_id = balls.match.to_numpy().astype(np.int64)
    season = balls.season.to_numpy().astype(np.int64)

    hand = players.hand[batter]
    bowl_style_ball = players.style[bowler]
    pitch = venues.pitch[venue]
    home_of_venue = venues.home_team[venue]
    at_home = (batting_team == home_of_venue).astype(float)

    sign_ps = np.where(bowl_style_ball == PACE, 0.5, -0.5)

    n_players = len(players.role)
    n_venues = len(venues.pitch)
    n_seasons = int(history.seasons)

    matches_unique = np.unique(match_id)
    m2i = {int(m): i for i, m in enumerate(matches_unique)}
    match_idx = np.array([m2i[int(m)] for m in match_id])
    n_matches = len(matches_unique)

    bowled = np.zeros(n_players, dtype=bool)
    bowled[np.unique(bowler)] = True

    style = np.zeros(n_players)
    quality = np.zeros(n_players)
    split = np.zeros(n_players)
    kind = np.zeros(n_players)
    bowl_quality = np.zeros(n_players)
    venue_level = np.zeros(n_venues)
    venue_dew = np.zeros(n_venues)
    affinity = np.zeros((n_players, n_venues))
    era = np.zeros(n_seasons)
    home_lift = 0.0
    wear = 0.0
    type_table = np.zeros((2, 2))
    pitch_table = np.zeros((2, 3))
    day = np.zeros(n_matches)

    bs = np.asarray(cal.directions["bat_style"])
    bq = np.asarray(cal.directions["bat_quality"])
    wt = np.asarray(cal.directions["bowl_type"])
    wq = np.asarray(cal.directions["bowl_quality"])
    cc = np.asarray(cal.directions["conditions"])
    bs2, bq2, wt2, wq2, cc2 = bs**2, bq**2, wt**2, wq**2, cc**2

    # Prior variances (informed guesses).
    var_style = 0.6**2
    var_quality = 0.8**2
    var_split = 0.3**2
    var_kind = 1.0**2
    var_bwlq = 0.8**2
    var_vlevel = 0.3**2
    var_vdew = 0.25**2
    var_aff = 0.15**2
    var_era = 0.3**2
    var_home = 0.25**2
    var_wear = 0.2**2
    var_typet = 0.15**2
    var_pitcht = 0.25**2
    var_day = 0.25**2

    hand_style_ix = hand * 2 + bowl_style_ball
    style_pitch_ix = bowl_style_ball * 3 + pitch
    bv_idx = batter * n_venues + venue
    sign2 = sign_ps * sign_ps  # constantly 0.25

    idxN = np.arange(N)

    def newton(x, num, den, var):
        return (num - x / var) / (den + 1.0 / var)

    def compute_p():
        h_style = style[batter]
        h_bq = quality[batter] + split[batter] * sign_ps
        h_kind = kind[bowler]
        h_bwlq = bowl_quality[bowler]
        h_cond = (
            venue_level[venue]
            + era[season]
            + affinity[batter, venue]
            + at_home * home_lift
            + type_table[hand, bowl_style_ball]
            - pitch_table[bowl_style_ball, pitch]
            + chasing * (venue_dew[venue] - wear)
            + day[match_idx]
        )
        z = (
            z_pub
            + np.multiply.outer(h_style, bs)
            + np.multiply.outer(h_bq, bq)
            + np.multiply.outer(h_kind, wt)
            + np.multiply.outer(h_bwlq, wq)
            + np.multiply.outer(h_cond, cc)
        )
        z = z - z.max(axis=1, keepdims=True)
        p = np.exp(z)
        p = p / p.sum(axis=1, keepdims=True)
        return p

    def residual_and_info(p, d, d2):
        r = -p.copy()
        r[idxN, outcome] += 1.0
        g = r @ d
        info = p @ d2 - (p @ d) ** 2
        return g, info

    for it in range(n_iter):
        # --- Block A: batter params (bs and bq directions) ---
        p = compute_p()
        g_bs, pd_bs = residual_and_info(p, bs, bs2)
        g_bq, pd_bq = residual_and_info(p, bq, bq2)
        num = np.bincount(batter, weights=g_bs, minlength=n_players)
        den = np.bincount(batter, weights=pd_bs, minlength=n_players)
        style = style + newton(style, num, den, var_style)
        num = np.bincount(batter, weights=g_bq, minlength=n_players)
        den = np.bincount(batter, weights=pd_bq, minlength=n_players)
        quality = quality + newton(quality, num, den, var_quality)
        num = np.bincount(batter, weights=sign_ps * g_bq, minlength=n_players)
        den = np.bincount(batter, weights=sign2 * pd_bq, minlength=n_players)
        split = split + newton(split, num, den, var_split)

        # --- Block B: bowler params (wt and wq directions) ---
        p = compute_p()
        g_wt, pd_wt = residual_and_info(p, wt, wt2)
        g_wq, pd_wq = residual_and_info(p, wq, wq2)
        num = np.bincount(bowler, weights=g_wt, minlength=n_players)
        den = np.bincount(bowler, weights=pd_wt, minlength=n_players)
        kind = kind + newton(kind, num, den, var_kind)
        kind[~bowled] = 0.0
        num = np.bincount(bowler, weights=g_wq, minlength=n_players)
        den = np.bincount(bowler, weights=pd_wq, minlength=n_players)
        bowl_quality = bowl_quality + newton(bowl_quality, num, den, var_bwlq)
        bowl_quality[~bowled] = 0.0

        # --- Block C: conditions (cc direction) — many params share it, so
        # update them one sub-block at a time with p recomputed each time.
        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        num = np.bincount(venue, weights=g_c, minlength=n_venues)
        den = np.bincount(venue, weights=pd_c, minlength=n_venues)
        venue_level = venue_level + newton(venue_level, num, den, var_vlevel)

        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        num = np.bincount(season, weights=g_c, minlength=n_seasons)
        den = np.bincount(season, weights=pd_c, minlength=n_seasons)
        era = era + newton(era, num, den, var_era)

        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        g_home = float(np.sum(at_home * g_c))
        h_home = float(np.sum(at_home * pd_c))
        home_lift = home_lift + (g_home - home_lift / var_home) / (h_home + 1.0 / var_home)
        g_wear = float(np.sum(-chasing * g_c))
        h_wear = float(np.sum(chasing * pd_c))
        wear = wear + (g_wear - wear / var_wear) / (h_wear + 1.0 / var_wear)

        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        num = np.bincount(hand_style_ix, weights=g_c, minlength=4).reshape(2, 2)
        den = np.bincount(hand_style_ix, weights=pd_c, minlength=4).reshape(2, 2)
        type_table = type_table + newton(type_table, num, den, var_typet)

        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        num = np.bincount(style_pitch_ix, weights=-g_c, minlength=6).reshape(2, 3)
        den = np.bincount(style_pitch_ix, weights=pd_c, minlength=6).reshape(2, 3)
        pitch_table = pitch_table + newton(pitch_table, num, den, var_pitcht)

        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        num = np.bincount(venue, weights=chasing * g_c, minlength=n_venues)
        den = np.bincount(venue, weights=chasing * pd_c, minlength=n_venues)
        venue_dew = venue_dew + newton(venue_dew, num, den, var_vdew)

        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        num = np.bincount(bv_idx, weights=g_c, minlength=n_players * n_venues).reshape(n_players, n_venues)
        den = np.bincount(bv_idx, weights=pd_c, minlength=n_players * n_venues).reshape(n_players, n_venues)
        affinity = affinity + newton(affinity, num, den, var_aff)

        p = compute_p()
        g_c, pd_c = residual_and_info(p, cc, cc2)
        num = np.bincount(match_idx, weights=g_c, minlength=n_matches)
        den = np.bincount(match_idx, weights=pd_c, minlength=n_matches)
        day = day + newton(day, num, den, var_day)

        if verbose:
            p = compute_p()
            ll = float(np.log(np.maximum(p[idxN, outcome], 1e-30)).sum())
            print(f"iter {it}: ll = {ll:.2f}")

    # Estimate day_sd from spread of fitted per-match day effects.
    # Fitted day is shrunk toward 0 by the prior; empirical std is a reasonable
    # rough estimate (the pitch spread is what the simulator draws from).
    if n_matches > 1:
        day_sd = float(np.std(day))
    else:
        day_sd = 0.0

    # Extrapolate era to the next season by linear fit on observed seasons.
    if n_seasons >= 2:
        s = np.arange(n_seasons)
        a, b = np.polyfit(s, era, 1)
        era_future = float(a * n_seasons + b)
    else:
        era_future = float(era[-1])

    book = SkillBook(
        players,
        venues,
        style,
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
        era_future,
        day_sd,
        wear,
    )
    return book


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=12000)
    parser.add_argument("--iters", type=int, default=50)
    parser.add_argument("--seed", type=int, default=0xC0FFEE)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    np.random.seed(args.seed)
    history, fixtures = load_league(args.league)
    model = load_public_model()
    book = fit_hidden(history, model, n_iter=args.iters, verbose=args.verbose)

    simulator = MatchSimulator(model)
    gen = np.random.default_rng(args.seed)
    rows = []
    for f in fixtures:
        p = simulator.win_probability(book, f, args.sims, gen)
        p = float(np.clip(p, 0.002, 0.998))
        rows.append((f.match, p))
    df = pd.DataFrame(rows, columns=["fixture", "p_home"])
    df.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
