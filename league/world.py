from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from league.calibration import Calibration, Design
from league.engine import PACE, SPIN, BallModel, Fixture, History, MatchSimulator, PlayerTable, SkillBook, VenueTable

BATTER, ALLROUNDER, BOWLER = 0, 1, 2

class League:
    def __init__(self, seed, calibration = None, design = None):
        # one random stream drives everything, so a seed fixes the whole world: players, skills, matches, fixtures
        self.cal, self.d = calibration or Calibration.load(), design or Design()
        self.rng = np.random.default_rng(seed)
        self.simulator = MatchSimulator(BallModel(self.cal))
        self.season = 0
        self._build_player()
        self._build_venues()

    # League Construction
    def _build_players(self):
        d, rng, sd = self.d, self.rng, self.cal.spreads
        # every squad has the same shape: 7 batters, 4 all rounders, 7 bowlers, so 180 players for ten teams
        squad = np.repeat([BATTER, ALLROUNDER, BOWLER], d.squad_roles)
        role = np.tile(squad, d.teams)
        n = len(role)
        # public facts: handedness and bowling style are printed in players.csv
        spin_share = np.where(role == ALLROUNDER, 0.5, 0.4)
        self.players = PlayerTable(role, (rng.random(n) < d.left_handed).astype(int), np.where(rng.random(n) < spin_share, SPIN, PACE))
        self.team_of = np.repeat(np.arange(d.teams), len(squad))
        # hidden facts, drawn from the measured spreads
        self.style = rng.normal(0, sd["bat_style"], n)
        # bowler type: half the measured spread comes from the public style (pace or spin), the rest is hidden and personal
        within = np.sqrt(max(sd["bowl_type"] ** 2 - (d.type_gap / 2) ** 2, 1e-6))
        self.kind = np.where(self.players.style == SPIN, 0.5, -0.5) * d.type_gap + rng.normal(0, within, n)
        # the two qualities are talent (fixed) plus form (drifts); the shares split the measured spread between them
        self.spread = {"quality": sd["bat_quality"], "bowl_quality": sd["bowl_quality"]}  # these two have talent plus form
        self.talent = {k: rng.normal(0, v * np.sqrt(d.talent_share), n) for k, v in self.spread.items()}
        self.form = {k: rng.normal(0, v * np.sqrt(1 - d.talent_share), n) for k, v in self.spread.items()}
        # a batter's pace-versus-spin gap in quality, small
        self.split = rng.normal(0, d.split_sd, n)