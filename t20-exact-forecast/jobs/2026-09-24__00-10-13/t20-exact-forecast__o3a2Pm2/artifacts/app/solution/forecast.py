import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from engine.league_io import load_league
from engine.model import MatchSimulator, SkillBook, load_public_model


OUTCOME = {"W": 0, "0": 1, "1": 2, "2": 3, "4": 4, "6": 5}
HAND = {"right": 0, "left": 1}
STYLE = {"pace": 0, "spin": 1}
PITCH = {"neutral": 0, "pace": 1, "spin": 2}


def _read_tables(folder):
    folder = Path(folder)
    return {
        "balls": pd.read_csv(folder / "balls.csv", dtype={"outcome": str}),
        "players": pd.read_csv(folder / "players.csv"),
        "venues": pd.read_csv(folder / "venues.csv"),
    }


def _fit_book(folder):
    tables = _read_tables(folder)
    balls, players, venues = tables["balls"], tables["players"], tables["venues"]
    model = load_public_model()
    cal = model.cal

    y = balls.outcome.map(OUTCOME).to_numpy(np.int64)
    n_obs = len(balls)
    n_players = len(players)
    n_venues = len(venues)
    n_seasons = int(balls.season.max()) + 1

    ball_no = balls.over.to_numpy(np.int64) * 6 + balls.ball.to_numpy(np.int64)
    chasing = (balls.target.to_numpy(np.int64) > 0).astype(float)
    pressure = np.zeros(n_obs)
    chase_mask = chasing.astype(bool)
    pressure[chase_mask] = model.pressure(
        balls.target.to_numpy(np.int64)[chase_mask],
        balls.runs_before.to_numpy(np.int64)[chase_mask],
        ball_no[chase_mask],
    )
    base = model.situation(
        balls.over.to_numpy(np.int64),
        balls.position.to_numpy(np.int64),
        balls.wickets_before.to_numpy(np.int64),
        chasing,
        pressure,
    )

    p_style = players.bowling_style.map(STYLE).to_numpy(np.int64)
    p_hand = players.hand.map(HAND).to_numpy(np.int64)
    v_home = venues.home_team.to_numpy(np.int64)
    v_pitch = venues.pitch.map(PITCH).to_numpy(np.int64)

    batter = balls.batter.to_numpy(np.int64)
    bowler = balls.bowler.to_numpy(np.int64)
    venue = balls.venue.to_numpy(np.int64)
    season = balls.season.to_numpy(np.int64)
    bow_style = p_style[bowler]
    hand = p_hand[batter]
    pitch = v_pitch[venue]
    home_ball = (v_home[venue] == balls.batting_team.to_numpy(np.int64)).astype(float)

    # Recent form is real in the simulator, but talent is persistent. These mild
    # weights let the last season speak a little louder without throwing away data.
    if n_seasons <= 1:
        weights = np.ones(n_obs)
    else:
        weights = 0.65 + 0.35 * season / (n_seasons - 1)

    pos = 0
    slices = {}

    def add(name, size, ridge):
        nonlocal pos
        slices[name] = (pos, pos + size, ridge)
        pos += size

    add("bat_style", n_players, 6.0)
    add("bat_quality", n_players * 2, 5.0)
    add("bowl_kind", n_players, 8.0)
    add("bowl_quality", n_players, 5.0)
    add("venue", n_venues, 8.0)
    add("chase_venue", n_venues, 10.0)
    add("era", n_seasons, 8.0)
    add("home", 1, 8.0)
    add("hand_style", 4, 12.0)
    add("pitch", 6, 12.0)
    add("affinity", n_players * n_venues, 22.0)

    indexes = {
        "bat_style": batter,
        "bat_quality": batter * 2 + bow_style,
        "bowl_kind": bowler,
        "bowl_quality": bowler,
        "venue": venue,
        "chase_venue": venue,
        "era": season,
        "home": np.zeros(n_obs, dtype=np.int64),
        "hand_style": hand * 2 + bow_style,
        "pitch": bow_style * 3 + pitch,
        "affinity": batter * n_venues + venue,
    }
    coefs = {"chase_venue": chasing, "home": home_ball}
    directions = {
        "bat_style": cal.directions["bat_style"],
        "bat_quality": cal.directions["bat_quality"],
        "bowl_kind": cal.directions["bowl_type"],
        "bowl_quality": cal.directions["bowl_quality"],
        "venue": cal.directions["conditions"],
        "chase_venue": cal.directions["conditions"],
        "era": cal.directions["conditions"],
        "home": cal.directions["conditions"],
        "hand_style": cal.directions["conditions"],
        "pitch": cal.directions["conditions"],
        "affinity": cal.directions["conditions"],
    }

    def part(x, name):
        start, stop, _ = slices[name]
        return x[start:stop]

    def objective_and_grad(x):
        z = base.copy()
        for name, idx in indexes.items():
            effect = part(x, name)[idx]
            if name in coefs:
                effect = effect * coefs[name]
            z += effect[:, None] * directions[name]

        row_max = z.max(axis=1)
        exp_z = np.exp(z - row_max[:, None])
        denom = exp_z.sum(axis=1)
        probs = exp_z / denom[:, None]
        value = np.sum(weights * (-(z[np.arange(n_obs), y] - row_max - np.log(denom))))

        resid = probs
        resid[np.arange(n_obs), y] -= 1.0
        resid *= weights[:, None]

        grad = np.zeros_like(x)
        for name, idx in indexes.items():
            obs_grad = resid @ directions[name]
            if name in coefs:
                obs_grad = obs_grad * coefs[name]
            start, stop, _ = slices[name]
            np.add.at(grad[start:stop], idx, obs_grad)

        for start, stop, ridge in slices.values():
            block = x[start:stop]
            value += 0.5 * ridge * float(block @ block)
            grad[start:stop] += ridge * block
        return value, grad

    result = minimize(
        objective_and_grad,
        np.zeros(pos),
        jac=True,
        method="L-BFGS-B",
        options={"maxiter": 85, "ftol": 1e-7, "gtol": 1e-4, "maxls": 20},
    )
    x = result.x

    bat_style = part(x, "bat_style")
    bat_vs_style = part(x, "bat_quality").reshape(n_players, 2)
    quality = bat_vs_style.mean(axis=1)
    split = bat_vs_style[:, 0] - bat_vs_style[:, 1]

    bowl_kind = part(x, "bowl_kind")
    bowl_quality = part(x, "bowl_quality")
    venue_level = part(x, "venue")
    chase_venue = part(x, "chase_venue")
    era = float(part(x, "era")[-1])
    home_lift = float(part(x, "home")[0])
    type_table = part(x, "hand_style").reshape(2, 2)
    pitch_effect = part(x, "pitch").reshape(2, 3)
    affinity = part(x, "affinity").reshape(n_players, n_venues)

    history, _ = load_league(folder)
    return SkillBook(
        history.players,
        history.venues,
        bat_style,
        quality,
        split,
        bowl_kind,
        bowl_quality,
        type_table,
        -pitch_effect,
        venue_level,
        chase_venue,
        affinity,
        home_lift,
        era,
        0.16,
        0.0,
    )


def forecast(league_folder, out_file, sims=24000):
    history, fixtures = load_league(league_folder)
    model = load_public_model()
    book = _fit_book(league_folder)
    simulator = MatchSimulator(model)
    rng = np.random.default_rng(20260924)

    rows = []
    for fixture in fixtures:
        p_home = simulator.win_probability(book, fixture, sims, rng)
        rows.append((fixture.match, min(0.998, max(0.002, p_home))))
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(out_file, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--sims", type=int, default=24000)
    args = parser.parse_args()
    forecast(args.league, args.out, args.sims)


if __name__ == "__main__":
    main()
