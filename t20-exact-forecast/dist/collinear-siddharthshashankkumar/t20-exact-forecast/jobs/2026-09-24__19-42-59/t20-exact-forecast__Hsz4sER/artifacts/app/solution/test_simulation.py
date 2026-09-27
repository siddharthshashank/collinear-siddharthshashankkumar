"""Check the optimized simulator against the unmodified public engine.

Run: python solution/test_simulation.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace
import unittest
import numpy as np
from engine.model import (
    PlayerTable, VenueTable, Fixture, SkillBook, MatchSimulator, load_public_model,
)
from simulation import PredictiveSimulator


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(136)
        self.model = load_public_model()
        players = PlayerTable(np.zeros(22, int), rng.integers(2, size=22),
                              rng.integers(2, size=22))
        venues = VenueTable(np.array([0, 1]), np.array([1, 2]))
        self.book = SkillBook(
            players, venues, rng.normal(0, .3, 22), rng.normal(0, .2, 22),
            rng.normal(0, .1, 22), rng.normal(0, .2, 22),
            rng.normal(0, .2, 22), rng.normal(0, .1, (2, 2)),
            rng.normal(0, .1, (2, 3)), np.array([.2, -.1]),
            np.array([.1, .05]), rng.normal(0, .1, (22, 2)), .07, -.1, .3, 0,
        )
        self.fixture = Fixture(0, 0, 0, 1, 0, np.arange(11), np.arange(6, 11),
                               np.arange(11, 22), np.arange(17, 22))
        b = self.book
        samples = dict(
            style=b.style[None], quality=b.quality[None], split=b.split[None],
            kind=b.kind[None], bowling=b.bowl_quality[None],
            venue=b.venue_level[None], era=np.array([b.era]),
            dew=b.venue_dew[None], home=np.array([b.home_lift]),
            affinity=b.affinity[None], hand=b.type_table[None],
            pitch=-b.pitch_table[None], day_sd=b.day_sd,
        )
        fit = SimpleNamespace(h=SimpleNamespace(players=players, venues=venues),
                              model=self.model, bowlmap=np.arange(22))
        self.sim = PredictiveSimulator(fit, samples)

    def test_both_innings_match_public_engine(self):
        n, f, b = 4096, self.fixture, self.book
        day = np.random.default_rng(21).normal(0, b.day_sd, n)
        target = None
        for xi, team, five, chasing in (
            (f.home_xi, f.home, f.away_bowlers, False),
            (f.away_xi, f.away, f.home_bowlers, True),
        ):
            conditions = b.shift(f.venue, chasing) + day
            expected = MatchSimulator(self.model).innings.play(
                *b.cards(xi, team, five, f.venue), conditions, n,
                np.random.default_rng(53), target=target,
            )
            actual = self.sim.innings(
                self.sim.logits(xi, team, five, f.venue), conditions, n,
                np.random.default_rng(53), target=target,
            )
            np.testing.assert_array_equal(actual, expected)
            target = actual + 1

    def test_equal_sides_and_deterministic_simulation(self):
        self.sim.s['home'][:] = 0
        f = self.fixture
        identical = Fixture(1, 0, 0, 1, 0, f.home_xi, f.home_bowlers,
                            f.home_xi, f.home_bowlers)
        self.assertEqual(self.sim.probability(identical, 1024), .5)
        self.assertEqual(self.sim.probability(f, 1024),
                         self.sim.probability(f, 1024))


if __name__ == '__main__':
    unittest.main()
