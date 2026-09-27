import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.league_io import load_league
from engine.model import MatchSimulator, SkillBook, load_public_model


OUTCOME_MAP = {"W": 0, "0": 1, "1": 2, "2": 3, "4": 4, "6": 5}


class Packed:
    def __init__(self, n_players, n_venues, n_seasons):
        self.n_players = n_players
        self.n_venues = n_venues
        self.n_seasons = n_seasons
        self.parts = []
        self.size = 0

    def add(self, name, shape, sigma):
        shape = tuple(shape)
        n = int(np.prod(shape))
        self.parts.append((name, self.size, self.size + n, shape, float(sigma)))
        self.size += n

    def zeros(self):
        return np.zeros(self.size)

    def unpack(self, x):
        out = {}
        for name, lo, hi, shape, _ in self.parts:
            out[name] = x[lo:hi].reshape(shape)
        return out

    def regularize(self, x, grad):
        loss = 0.0
        for _, lo, hi, _, sigma in self.parts:
            if sigma <= 0:
                continue
            block = x[lo:hi]
            inv = 1.0 / (sigma * sigma)
            loss += 0.5 * inv * float(np.dot(block, block))
            grad[lo:hi] += inv * block
        return loss

    def add_grad(self, grad, name, value):
        for part_name, lo, hi, shape, _ in self.parts:
            if part_name == name:
                grad[lo:hi] += value.reshape(shape).ravel()
                return
        raise KeyError(name)


def _league_arrays(folder):
    folder = Path(folder)
    hist, fixtures = load_league(folder)
    balls = pd.read_csv(folder / "balls.csv", dtype={"outcome": str})
    balls["y"] = balls.outcome.map(OUTCOME_MAP).astype(int)
    return hist, fixtures, balls


def _public_logits(model, balls):
    ball_no = balls["over"].to_numpy(int) * 6 + balls["ball"].to_numpy(int)
    target = balls["target"].to_numpy(float)
    runs = balls["runs_before"].to_numpy(float)
    chasing = (target > 0).astype(float)
    pressure = np.zeros(len(balls))
    mask = chasing.astype(bool)
    if mask.any():
        pressure[mask] = model.pressure(target[mask], runs[mask], ball_no[mask])
    return model.situation(
        balls["over"].to_numpy(int),
        balls["position"].to_numpy(int),
        balls["wickets_before"].to_numpy(int),
        chasing,
        pressure,
    )


def fit_book(folder):
    hist, fixtures, balls = _league_arrays(folder)
    model = load_public_model()
    players, venues = hist.players, hist.venues
    n_players = len(players.role)
    n_venues = len(venues.pitch)
    n_seasons = max(hist.seasons, int(balls.season.max()) + 1)

    batter = balls.batter.to_numpy(int)
    bowler = balls.bowler.to_numpy(int)
    season = balls.season.to_numpy(int)
    venue = balls.venue.to_numpy(int)
    y = balls.y.to_numpy(int)
    bowler_style = players.style[bowler].astype(int)
    batter_hand = players.hand[batter].astype(int)
    pitch = venues.pitch[venue].astype(int)
    chase = balls.target.to_numpy(int) > 0
    at_home = venues.home_team[venue] == balls.batting_team.to_numpy(int)
    sign = np.where(bowler_style == 0, 0.5, -0.5)

    z_public = _public_logits(model, balls)
    dirs = model.cal.directions
    dir_stack = np.vstack(
        [
            dirs["bat_style"],
            dirs["bat_quality"],
            dirs["bowl_type"],
            dirs["bowl_quality"],
            dirs["conditions"],
        ]
    )

    pack = Packed(n_players, n_venues, n_seasons)
    pack.add("bat_style", (n_players,), 0.85)
    pack.add("bat_base", (n_players,), 0.75)
    pack.add("bat_form", (n_players, n_seasons), 0.32)
    pack.add("split", (n_players,), 0.35)
    pack.add("kind_style", (2,), 0.95)
    pack.add("kind_dev", (n_players,), 0.45)
    pack.add("bowl_base", (n_players,), 0.75)
    pack.add("bowl_form", (n_players, n_seasons), 0.34)
    pack.add("venue_level", (n_venues,), 0.50)
    pack.add("venue_chase", (n_venues,), 0.42)
    pack.add("home_lift", (1,), 0.32)
    pack.add("era", (n_seasons,), 0.42)
    pack.add("type_table", (2, 2), 0.24)
    pack.add("pitch_table", (2, 3), 0.24)

    x0 = pack.zeros()
    u0 = pack.unpack(x0)
    u0["kind_style"][:] = [-0.25, 0.25]

    age = (n_seasons - 1) - season
    weights = np.power(0.82, age).astype(float)

    idx_player_season_bat = batter * n_seasons + season
    idx_player_season_bowl = bowler * n_seasons + season
    idx_type = batter_hand * 2 + bowler_style
    idx_pitch = bowler_style * 3 + pitch

    def objective(x):
        u = pack.unpack(x)
        bat_q = u["bat_base"][batter] + u["bat_form"].reshape(-1)[idx_player_season_bat]
        bat_q = bat_q + u["split"][batter] * sign
        bowl_q = u["bowl_base"][bowler] + u["bowl_form"].reshape(-1)[idx_player_season_bowl]
        kind = u["kind_style"][bowler_style] + u["kind_dev"][bowler]
        cond = (
            u["venue_level"][venue]
            + u["era"][season]
            + u["type_table"].reshape(-1)[idx_type]
            - u["pitch_table"].reshape(-1)[idx_pitch]
        )
        cond = cond + at_home * u["home_lift"][0] + chase * u["venue_chase"][venue]

        scalars = np.column_stack(
            [u["bat_style"][batter], bat_q, kind, bowl_q, cond]
        )
        z = z_public + scalars @ dir_stack
        z -= z.max(axis=1, keepdims=True)
        ez = np.exp(z)
        p = ez / ez.sum(axis=1, keepdims=True)
        nll_rows = -np.log(np.clip(p[np.arange(len(y)), y], 1e-15, None))
        loss = float(np.dot(weights, nll_rows))

        residual = p
        residual[np.arange(len(y)), y] -= 1.0
        residual *= weights[:, None]
        g_bs, g_bq, g_wt, g_wq, g_c = (residual @ dir_stack.T).T

        grad = np.zeros_like(x)
        pack.add_grad(
            grad,
            "bat_style",
            np.bincount(batter, weights=g_bs, minlength=n_players),
        )
        pack.add_grad(
            grad,
            "bat_base",
            np.bincount(batter, weights=g_bq, minlength=n_players),
        )
        pack.add_grad(
            grad,
            "bat_form",
            np.bincount(
                idx_player_season_bat,
                weights=g_bq,
                minlength=n_players * n_seasons,
            ).reshape(n_players, n_seasons),
        )
        pack.add_grad(
            grad,
            "split",
            np.bincount(batter, weights=g_bq * sign, minlength=n_players),
        )
        pack.add_grad(
            grad,
            "kind_style",
            np.bincount(bowler_style, weights=g_wt, minlength=2),
        )
        pack.add_grad(
            grad,
            "kind_dev",
            np.bincount(bowler, weights=g_wt, minlength=n_players),
        )
        pack.add_grad(
            grad,
            "bowl_base",
            np.bincount(bowler, weights=g_wq, minlength=n_players),
        )
        pack.add_grad(
            grad,
            "bowl_form",
            np.bincount(
                idx_player_season_bowl,
                weights=g_wq,
                minlength=n_players * n_seasons,
            ).reshape(n_players, n_seasons),
        )
        pack.add_grad(
            grad,
            "venue_level",
            np.bincount(venue, weights=g_c, minlength=n_venues),
        )
        pack.add_grad(
            grad,
            "venue_chase",
            np.bincount(venue, weights=g_c * chase, minlength=n_venues),
        )
        pack.add_grad(grad, "home_lift", np.array([float(np.dot(g_c, at_home))]))
        pack.add_grad(
            grad,
            "era",
            np.bincount(season, weights=g_c, minlength=n_seasons),
        )
        pack.add_grad(
            grad,
            "type_table",
            np.bincount(idx_type, weights=g_c, minlength=4).reshape(2, 2),
        )
        pack.add_grad(
            grad,
            "pitch_table",
            -np.bincount(idx_pitch, weights=g_c, minlength=6).reshape(2, 3),
        )

        loss += pack.regularize(x, grad)
        return loss, grad

    res = minimize(
        objective,
        x0,
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": 180, "ftol": 1e-7, "gtol": 1e-4, "maxls": 30},
    )
    u = pack.unpack(res.x)

    rho = 0.58
    last = n_seasons - 1
    style = u["bat_style"].copy()
    quality = u["bat_base"] + rho * u["bat_form"][:, last]
    split = u["split"].copy()
    kind = u["kind_style"][players.style] + u["kind_dev"]
    bowl_quality = u["bowl_base"] + rho * u["bowl_form"][:, last]

    era = float(u["era"][last])
    if n_seasons >= 3:
        era += 0.25 * float(u["era"][last] - u["era"][last - 1])

    return model, SkillBook(
        players=players,
        venues=venues,
        style=style,
        quality=quality,
        split=split,
        kind=kind,
        bowl_quality=bowl_quality,
        type_table=u["type_table"],
        pitch_table=u["pitch_table"],
        venue_level=u["venue_level"],
        venue_dew=u["venue_chase"],
        affinity=np.zeros((n_players, n_venues)),
        home_lift=float(u["home_lift"][0]),
        era=era,
        day_sd=0.28,
        wear=0.0,
    ), fixtures


def forecast(league_folder, out_file):
    model, book, fixtures = fit_book(league_folder)
    sim = MatchSimulator(model)
    gen = np.random.default_rng(20260924)
    rows = []
    for fixture in fixtures:
        p_home = sim.win_probability(book, fixture, 40000, gen)
        rows.append((fixture.match, float(np.clip(p_home, 0.002, 0.998))))
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(out_file, index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    forecast(args.league, args.out)


if __name__ == "__main__":
    main()
