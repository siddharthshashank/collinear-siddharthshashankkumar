"""Forecast home-win probabilities for a simulated T20 league.

Fits the engine's hidden skill/condition parameters from ball-by-ball history
by ridge-regularized multinomial-logistic maximum likelihood on the six ball
outcomes, then simulates each fixture with the engine.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.model import (
    BallModel,
    BattingCard,
    BowlingCard,
    InningsSimulator,
    MatchSimulator,
    SkillBook,
    load_public_model,
    PACE,
    SPIN,
)
from engine.league_io import load_league


# ------------------------------------------------------------------
# Fitting
# ------------------------------------------------------------------


def _per_ball_features(history, model):
    """Return per-ball numpy arrays used by the loss function."""
    balls = history.balls
    matches = history.matches
    players = history.players
    venues = history.venues

    batter = balls.batter.to_numpy(dtype=np.int64)
    bowler = balls.bowler.to_numpy(dtype=np.int64)
    venue = balls.venue.to_numpy(dtype=np.int64)
    season = balls.season.to_numpy(dtype=np.int64)
    match_id = balls.match.to_numpy(dtype=np.int64)
    over = balls.over.to_numpy(dtype=np.int64)
    ball_in_over = balls.ball.to_numpy(dtype=np.int64)
    position = balls.position.to_numpy(dtype=np.int64)
    wickets = balls.wickets_before.to_numpy(dtype=np.float64)
    runs = balls.runs_before.to_numpy(dtype=np.float64)
    target = balls.target.to_numpy(dtype=np.float64)
    innings = balls.innings.to_numpy(dtype=np.int64)
    outcome = balls.outcome.to_numpy(dtype=np.int64)
    batting_team = balls.batting_team.to_numpy(dtype=np.int64)

    chasing = (innings == 2).astype(np.float64)

    # legal-ball index used inside the engine for pressure/par_rate
    ball_idx = over * 6 + ball_in_over
    ball_idx = np.clip(ball_idx, 0, 119)

    cal = model.cal
    # public part of the logits, per ball, shape (N, 6)
    z_pub = (
        cal.over_logits[over]
        + cal.position_vectors[position]
        + np.multiply.outer(wickets - cal.typical_wickets[over], cal.wickets_vector)
        + np.multiply.outer(chasing, cal.second_innings_vector)
    )
    # pressure term (only meaningful in innings 2)
    need = np.clip(target - runs, 1.0, None) / ((120 - ball_idx) / 6.0)
    pressure = np.clip(np.log(need / cal.par_rate[ball_idx // 6]), -1.0, 1.2)
    pressure = pressure * chasing
    z_pub = z_pub + np.multiply.outer(pressure, cal.pressure_vector)

    # attributes derived from public tables
    hand_bat = players.hand[batter]
    style_bow = players.style[bowler]
    pitch_v = venues.pitch[venue]
    home_team_of_venue = venues.home_team[venue]
    home_indicator = (batting_team == home_team_of_venue).astype(np.float64)

    # remap match id to a compact contiguous index
    unique_matches, match_idx = np.unique(match_id, return_inverse=True)

    # remap seasons to a compact index (0..S-1) - already 0..seasons-1 but be safe
    unique_seasons, season_idx = np.unique(season, return_inverse=True)

    return dict(
        N=len(outcome),
        batter=batter,
        bowler=bowler,
        venue=venue,
        season_idx=season_idx.astype(np.int64),
        n_seasons=len(unique_seasons),
        match_idx=match_idx.astype(np.int64),
        n_matches=len(unique_matches),
        chasing=chasing,
        hand_bat=hand_bat.astype(np.int64),
        style_bow=style_bow.astype(np.int64),
        pitch_v=pitch_v.astype(np.int64),
        home_indicator=home_indicator,
        outcome=outcome,
        z_pub=z_pub,
    )


def _make_theta_layout(num_players, num_venues, n_seasons, n_matches):
    """Return the size and slices of each parameter block."""
    sizes = {
        "style": num_players,
        "q_bat": num_players,
        "split": num_players,
        "kind": num_players,
        "q_bowl": num_players,
        "venue_level": num_venues,
        "venue_dew": num_venues,
        "affinity": num_players * num_venues,
        "era": n_seasons,
        "home_lift": 1,
        "wear": 1,
        "type_tab": 2 * 2,
        "pitch_tab": 2 * 3,
        "day": n_matches,
    }
    slices = {}
    total = 0
    for name, sz in sizes.items():
        slices[name] = (total, total + sz)
        total += sz
    return slices, total


def _unpack(theta, slices, num_players, num_venues):
    def s(name):
        a, b = slices[name]
        return theta[a:b]

    return dict(
        style=s("style"),
        q_bat=s("q_bat"),
        split=s("split"),
        kind=s("kind"),
        q_bowl=s("q_bowl"),
        venue_level=s("venue_level"),
        venue_dew=s("venue_dew"),
        affinity=s("affinity").reshape(num_players, num_venues),
        era=s("era"),
        home_lift=s("home_lift")[0],
        wear=s("wear")[0],
        type_tab=s("type_tab").reshape(2, 2),
        pitch_tab=s("pitch_tab").reshape(2, 3),
        day=s("day"),
    )


def fit_parameters(history, model, verbose=False):
    """Ridge-regularized MAP fit of every hidden parameter, one point per player."""
    feats = _per_ball_features(history, model)

    num_players = len(history.players.role)
    num_venues = len(history.venues.pitch)
    n_seasons = feats["n_seasons"]
    n_matches = feats["n_matches"]

    slices, dim = _make_theta_layout(num_players, num_venues, n_seasons, n_matches)

    # priors: per-parameter L2 (lambda), higher => stronger shrinkage
    lam = {
        "style": 1.0,
        "q_bat": 1.0,
        "split": 20.0,
        "kind": 5.0,
        "q_bowl": 2.0,
        "venue_level": 5.0,
        "venue_dew": 20.0,
        "affinity": 20.0,
        "era": 5.0,
        "home_lift": 5.0,
        "wear": 20.0,
        "type_tab": 20.0,
        "pitch_tab": 20.0,
        "day": 10.0,
    }
    lam_vec = np.zeros(dim)
    for name, (a, b) in slices.items():
        lam_vec[a:b] = lam[name]

    bs = model.bs
    bq = model.bq
    wt = model.wt
    wq = model.wq
    cdir = model.c

    batter = feats["batter"]
    bowler = feats["bowler"]
    venue = feats["venue"]
    season_idx = feats["season_idx"]
    match_idx = feats["match_idx"]
    chasing = feats["chasing"]
    hand_bat = feats["hand_bat"]
    style_bow = feats["style_bow"]
    pitch_v = feats["pitch_v"]
    home_indicator = feats["home_indicator"]
    outcome = feats["outcome"]
    z_pub = feats["z_pub"]
    N = feats["N"]

    # sign for split: +0.5 vs pace, -0.5 vs spin
    split_sign = np.where(style_bow == PACE, 0.5, -0.5)

    row_idx = np.arange(N)

    def loss_and_grad(theta):
        p = _unpack(theta, slices, num_players, num_venues)

        a = p["style"][batter]
        b = p["q_bat"][batter] + p["split"][batter] * split_sign
        c = p["kind"][bowler]
        d = p["q_bowl"][bowler]

        aff = p["affinity"][batter, venue]
        tt = p["type_tab"][hand_bat, style_bow]
        pt = p["pitch_tab"][style_bow, pitch_v]

        e = (
            p["venue_level"][venue]
            + p["era"][season_idx]
            + aff
            + p["home_lift"] * home_indicator
            + tt
            - pt
            + p["day"][match_idx]
            + (p["venue_dew"][venue] - p["wear"]) * chasing
        )

        # z shape (N, 6); form as sum of outer products
        z = z_pub + np.outer(a, bs) + np.outer(b, bq) + np.outer(c, wt) + np.outer(d, wq) + np.outer(e, cdir)

        z_max = z.max(axis=1)
        z_shift = z - z_max[:, None]
        exp_z = np.exp(z_shift)
        sum_exp = exp_z.sum(axis=1)
        logsum = np.log(sum_exp)
        softmax = exp_z / sum_exp[:, None]

        ll = z[row_idx, outcome] - z_max - logsum
        nll = -ll.sum()

        # regularization
        reg = 0.5 * float((lam_vec * theta * theta).sum())
        loss = nll + reg

        # backprop
        grad_z = softmax
        grad_z[row_idx, outcome] -= 1.0

        ga = grad_z @ bs
        gb = grad_z @ bq
        gc = grad_z @ wt
        gd = grad_z @ wq
        ge = grad_z @ cdir

        grad = np.zeros_like(theta)

        def add(name, values):
            a_, b_ = slices[name]
            grad[a_:b_] += values

        add("style", np.bincount(batter, weights=ga, minlength=num_players))
        add("q_bat", np.bincount(batter, weights=gb, minlength=num_players))
        add("split", np.bincount(batter, weights=gb * split_sign, minlength=num_players))
        add("kind", np.bincount(bowler, weights=gc, minlength=num_players))
        add("q_bowl", np.bincount(bowler, weights=gd, minlength=num_players))
        add("venue_level", np.bincount(venue, weights=ge, minlength=num_venues))
        add("venue_dew", np.bincount(venue, weights=ge * chasing, minlength=num_venues))

        # affinity: (player, venue) flat index = batter * num_venues + venue
        pv = batter * num_venues + venue
        add(
            "affinity",
            np.bincount(pv, weights=ge, minlength=num_players * num_venues),
        )
        add("era", np.bincount(season_idx, weights=ge, minlength=n_seasons))
        grad[slices["home_lift"][0]] += float((ge * home_indicator).sum())
        grad[slices["wear"][0]] += float(-(ge * chasing).sum())

        # type_tab[hand, style] and pitch_tab[style, pitch]
        tt_idx = hand_bat * 2 + style_bow
        add("type_tab", np.bincount(tt_idx, weights=ge, minlength=4))
        pt_idx = style_bow * 3 + pitch_v
        add("pitch_tab", np.bincount(pt_idx, weights=-ge, minlength=6))
        add("day", np.bincount(match_idx, weights=ge, minlength=n_matches))

        # add L2 gradient
        grad += lam_vec * theta

        return loss, grad

    theta0 = np.zeros(dim)
    opts = dict(maxiter=400, ftol=1e-9, gtol=1e-6)
    result = minimize(
        loss_and_grad,
        theta0,
        jac=True,
        method="L-BFGS-B",
        options=opts,
    )
    if verbose:
        print("fit success:", result.success, "final loss:", result.fun)

    params = _unpack(result.x, slices, num_players, num_venues)
    # estimate day_sd from fitted day values (empirical std)
    day = np.asarray(params["day"], dtype=float)
    day_sd = float(np.std(day)) if len(day) > 1 else 0.0
    return params, day_sd


# ------------------------------------------------------------------
# Build a SkillBook that the engine can simulate with
# ------------------------------------------------------------------


class _NoPairSkillBook(SkillBook):
    pass


def build_skillbook(history, model, params, day_sd):
    players = history.players
    venues = history.venues

    num_players = len(players.role)
    num_venues = len(venues.pitch)

    style = np.asarray(params["style"], dtype=float).copy()
    q_bat = np.asarray(params["q_bat"], dtype=float).copy()
    split = np.asarray(params["split"], dtype=float).copy()
    kind = np.asarray(params["kind"], dtype=float).copy()
    q_bowl = np.asarray(params["q_bowl"], dtype=float).copy()
    venue_level = np.asarray(params["venue_level"], dtype=float).copy()
    venue_dew = np.asarray(params["venue_dew"], dtype=float).copy()
    affinity = np.asarray(params["affinity"], dtype=float).reshape(num_players, num_venues).copy()
    era_seasons = np.asarray(params["era"], dtype=float)
    home_lift = float(params["home_lift"])
    wear = float(params["wear"])
    type_tab = np.asarray(params["type_tab"], dtype=float).reshape(2, 2).copy()
    pitch_tab = np.asarray(params["pitch_tab"], dtype=float).reshape(2, 3).copy()

    # For the forecast season, use the last-observed era as the point estimate.
    era = float(era_seasons[-1]) if len(era_seasons) else 0.0

    book = SkillBook(
        players=players,
        venues=venues,
        style=style,
        quality=q_bat,
        split=split,
        kind=kind,
        bowl_quality=q_bowl,
        type_table=type_tab,
        pitch_table=pitch_tab,
        venue_level=venue_level,
        venue_dew=venue_dew,
        affinity=affinity,
        home_lift=home_lift,
        era=era,
        day_sd=day_sd,
        wear=wear,
    )
    return book


# ------------------------------------------------------------------
# Simulate each fixture
# ------------------------------------------------------------------


def forecast_fixtures(history, fixtures, book, model, n_sims=4000, seed=0):
    sim = MatchSimulator(model)
    rng = np.random.default_rng(seed)
    rows = []
    for fx in fixtures:
        p = sim.win_probability(book, fx, n=n_sims, gen=rng)
        p = float(np.clip(p, 0.002, 0.998))
        rows.append((fx.match, p))
    return pd.DataFrame(rows, columns=["fixture", "p_home"])


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--verbose", action="store_[REDACTED]")
    args = parser.parse_args()

    league_folder = Path(args.league)
    history, fixtures = load_league(league_folder)
    model = load_public_model()

    params, day_sd = fit_parameters(history, model, verbose=args.verbose)
    book = build_skillbook(history, model, params, day_sd)
    df = forecast_fixtures(history, fixtures, book, model, n_sims=args.sims, seed=args.seed)
    df.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
