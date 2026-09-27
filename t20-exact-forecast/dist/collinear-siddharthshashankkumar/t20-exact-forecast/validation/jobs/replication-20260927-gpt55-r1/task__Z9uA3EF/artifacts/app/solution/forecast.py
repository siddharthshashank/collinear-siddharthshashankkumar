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

from engine.league_io import load_league
from engine.model import PlayerTable, VenueTable, SkillBook, MatchSimulator, load_public_model


OUTCOME = {"W": 0, "0": 1, "1": 2, "2": 3, "4": 4, "6": 5}
ROLE = {"batter": 0, "allrounder": 1, "bowler": 2}
HAND = {"right": 0, "left": 1}
STYLE = {"pace": 0, "spin": 1}
PITCH = {"neutral": 0, "pace": 1, "spin": 2}


@dataclass(frozen=True)
class FitSpec:
    decay: float
    prior_scale: float
    shrink: float
    day_sd: float
    weight: float
    seed: int


class LeagueFitter:
    def __init__(self, folder: Path):
        self.folder = folder
        self.model = load_public_model()
        self.cal = self.model.cal

        players = pd.read_csv(folder / "players.csv")
        venues = pd.read_csv(folder / "venues.csv")
        balls = pd.read_csv(folder / "balls.csv", dtype={"outcome": str})

        self.players_df = players
        self.venues_df = venues
        self.balls = balls
        self.n_players = len(players)
        self.n_venues = len(venues)
        self.role = players.role.map(ROLE).to_numpy(np.int64)
        self.hand = players.hand.map(HAND).to_numpy(np.int64)
        self.player_style = players.bowling_style.map(STYLE).to_numpy(np.int64)
        self.pitch = venues.pitch.map(PITCH).to_numpy(np.int64)
        self.home_team = venues.home_team.to_numpy(np.int64)

        self._prepare_ball_arrays()

    def _prepare_ball_arrays(self):
        b = self.balls
        self.y = b.outcome.map(OUTCOME).to_numpy(np.int64)
        self.n_balls = len(b)
        self.batter = b.batter.to_numpy(np.int64)
        self.bowler = b.bowler.to_numpy(np.int64)
        self.season = b.season.to_numpy(np.int64)
        self.venue = b.venue.to_numpy(np.int64)
        self.n_seasons = int(self.season.max()) + 1

        ball_index = b.over.to_numpy(np.int64) * 6 + b.ball.to_numpy(np.int64)
        chasing = (b.target.to_numpy() > 0).astype(float)
        pressure = np.zeros(self.n_balls)
        mask = chasing.astype(bool)
        if mask.any():
            needed = np.clip(
                b.target.to_numpy()[mask] - b.runs_before.to_numpy()[mask],
                1,
                None,
            )
            needed = needed / ((120 - ball_index[mask]) / 6)
            pressure[mask] = np.clip(
                np.log(needed / self.cal.par_rate[ball_index[mask] // 6]),
                -1.0,
                1.2,
            )

        self.chasing = chasing
        self.base_logits = self.model.situation(
            b.over.to_numpy(np.int64),
            b.position.to_numpy(np.int64),
            b.wickets_before.to_numpy(np.int64),
            chasing,
            pressure,
        )
        self.bowler_style = self.player_style[self.bowler]
        self.batter_hand = self.hand[self.batter]
        self.row_pitch = self.pitch[self.venue]
        self.at_home = (
            self.home_team[self.venue] == b.batting_team.to_numpy(np.int64)
        ).astype(float)

    def fit(self, spec: FitSpec):
        slices = {}
        pos = 0

        def add(name, size):
            nonlocal pos
            slices[name] = slice(pos, pos + size)
            pos += size

        p, v, s = self.n_players, self.n_venues, self.n_seasons
        add("bat_style", p)
        add("bat_quality", p)
        add("split", p)
        add("bowl_kind", p)
        add("bowl_quality", p)
        add("bat_role", 3)
        add("bowl_role", 3)
        add("kind_style", 2)
        add("venue_level", v)
        add("chase_delta", v)
        add("era", s)
        add("home_lift", 1)
        add("type_table", 4)
        add("pitch_table", 6)

        n_params = pos
        scales = np.ones(n_params)
        base_scales = {
            "bat_style": 0.55,
            "bat_quality": 0.48,
            "split": 0.26,
            "bowl_kind": 0.35,
            "bowl_quality": 0.42,
            "bat_role": 0.22,
            "bowl_role": 0.28,
            "kind_style": 0.55,
            "venue_level": 0.32,
            "chase_delta": 0.22,
            "era": 0.24,
            "home_lift": 0.16,
            "type_table": 0.12,
            "pitch_table": 0.12,
        }
        for name, scale in base_scales.items():
            scales[slices[name]] = scale * spec.prior_scale

        max_season = self.season.max()
        weights = np.power(spec.decay, max_season - self.season)

        dirs = self.cal.directions
        bat_style_dir = dirs["bat_style"]
        bat_quality_dir = dirs["bat_quality"]
        bowl_type_dir = dirs["bowl_type"]
        bowl_quality_dir = dirs["bowl_quality"]
        conditions_dir = dirs["conditions"]

        rows = np.arange(self.n_balls)
        pace_sign = np.where(self.bowler_style == 0, 0.5, -0.5)
        role_batter = self.role[self.batter]
        role_bowler = self.role[self.bowler]
        type_index = self.batter_hand * 2 + self.bowler_style
        pitch_index = self.bowler_style * 3 + self.row_pitch

        def unpack(x):
            return {name: x[sl] for name, sl in slices.items()}

        def objective_and_grad(x):
            u = unpack(x)
            bat_quality = (
                u["bat_quality"][self.batter]
                + u["bat_role"][role_batter]
                + u["split"][self.batter] * pace_sign
            )
            bowl_kind = u["bowl_kind"][self.bowler] + u["kind_style"][self.bowler_style]
            bowl_quality = (
                u["bowl_quality"][self.bowler] + u["bowl_role"][role_bowler]
            )
            conditions = (
                u["venue_level"][self.venue]
                + u["era"][self.season]
                + u["chase_delta"][self.venue] * self.chasing
                + u["home_lift"][0] * self.at_home
                + u["type_table"][type_index]
                - u["pitch_table"][pitch_index]
            )

            z = self.base_logits.copy()
            z += u["bat_style"][self.batter, None] * bat_style_dir
            z += bat_quality[:, None] * bat_quality_dir
            z += bowl_kind[:, None] * bowl_type_dir
            z += bowl_quality[:, None] * bowl_quality_dir
            z += conditions[:, None] * conditions_dir

            zmax = z.max(axis=1, keepdims=True)
            ez = np.exp(z - zmax)
            probs = ez / ez.sum(axis=1, keepdims=True)
            logp = z[rows, self.y] - zmax[:, 0] - np.log(ez.sum(axis=1))
            value = -(weights * logp).sum() + 0.5 * np.sum((x / scales) ** 2)

            grad = x / (scales**2)

            svec = (probs @ bat_style_dir - bat_style_dir[self.y]) * weights
            np.add.at(grad[slices["bat_style"]], self.batter, svec)

            svec = (probs @ bat_quality_dir - bat_quality_dir[self.y]) * weights
            np.add.at(grad[slices["bat_quality"]], self.batter, svec)
            np.add.at(grad[slices["bat_role"]], role_batter, svec)
            np.add.at(grad[slices["split"]], self.batter, svec * pace_sign)

            svec = (probs @ bowl_type_dir - bowl_type_dir[self.y]) * weights
            np.add.at(grad[slices["bowl_kind"]], self.bowler, svec)
            np.add.at(grad[slices["kind_style"]], self.bowler_style, svec)

            svec = (probs @ bowl_quality_dir - bowl_quality_dir[self.y]) * weights
            np.add.at(grad[slices["bowl_quality"]], self.bowler, svec)
            np.add.at(grad[slices["bowl_role"]], role_bowler, svec)

            svec = (probs @ conditions_dir - conditions_dir[self.y]) * weights
            np.add.at(grad[slices["venue_level"]], self.venue, svec)
            np.add.at(grad[slices["era"]], self.season, svec)
            np.add.at(grad[slices["chase_delta"]], self.venue, svec * self.chasing)
            grad[slices["home_lift"].start] += np.sum(svec * self.at_home)
            np.add.at(grad[slices["type_table"]], type_index, svec)
            np.add.at(grad[slices["pitch_table"]], pitch_index, -svec)

            return value, grad

        result = minimize(
            objective_and_grad,
            np.zeros(n_params),
            jac=True,
            method="L-BFGS-B",
            options={"maxiter": 140, "ftol": 1e-5, "gtol": 1e-3, "maxls": 30},
        )
        return self._book_from_params(result.x, slices, spec)

    def _book_from_params(self, x, slices, spec: FitSpec):
        def part(name):
            return x[slices[name]]

        role = self.role
        player_style = self.player_style
        eras = part("era")
        if len(eras) >= 2:
            era = eras[-1] + 0.25 * (eras[-1] - eras[-2])
        else:
            era = eras[-1]
        era = float(np.clip(era, -0.6, 0.6))

        shrink = spec.shrink
        players = PlayerTable(self.role, self.hand, self.player_style)
        venues = VenueTable(self.home_team, self.pitch)
        affinity = np.zeros((self.n_players, self.n_venues))

        return SkillBook(
            players=players,
            venues=venues,
            style=part("bat_style") * shrink,
            quality=(part("bat_quality") + part("bat_role")[role]) * shrink,
            split=part("split") * shrink,
            kind=(part("bowl_kind") + part("kind_style")[player_style]) * shrink,
            bowl_quality=(part("bowl_quality") + part("bowl_role")[role]) * shrink,
            type_table=part("type_table").reshape(2, 2),
            pitch_table=part("pitch_table").reshape(2, 3),
            venue_level=part("venue_level"),
            venue_dew=part("chase_delta"),
            affinity=affinity,
            home_lift=float(part("home_lift")[0]),
            era=era,
            day_sd=spec.day_sd,
            wear=0.0,
        )


def forecast(folder: Path):
    fitter = LeagueFitter(folder)
    _, fixtures = load_league(folder)
    simulator = MatchSimulator(fitter.model)

    specs = [
        FitSpec(0.78, 1.00, 0.96, 0.18, 0.45, 91817),
        FitSpec(0.88, 0.95, 0.92, 0.20, 0.35, 34031),
        FitSpec(1.00, 0.90, 0.88, 0.16, 0.20, 73129),
    ]

    probs = np.zeros(len(fixtures))
    total_weight = 0.0
    sims_per_order = 12000
    for spec in specs:
        book = fitter.fit(spec)
        gen = np.random.default_rng(spec.seed)
        this = np.array(
            [
                simulator.win_probability(book, fixture, sims_per_order, gen)
                for fixture in fixtures
            ]
        )
        probs += spec.weight * this
        total_weight += spec.weight

    probs = np.clip(probs / total_weight, 0.002, 0.998)
    return pd.DataFrame({"fixture": [f.match for f in fixtures], "p_home": probs})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    out = forecast(Path(args.league))
    out.to_csv(args.out, index=False)


if __name__ == "__main__":
    main()
