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
        self._build_players()
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

    def _build_venues(self):
        d, rng, per = self.d, self.rng, self.cal.runs_per_condition_unit
        # one ground per team; the pitch type is public, the level, the dew and each batter's liking for it are hidden
        # `per` converts runs per ball into units along the conditions direction
        self.venues = VenueTable(np.arange(d.teams), rng.integers(0, 3, d.teams))
        self.venue_level = rng.normal(0, self.cal.venue_sd_runs / per, d.teams)
        self.venue_dew = np.where(rng.random(d.teams) < d.dew_share, d.dew_runs / per, 0.0)
        self.affinity = rng.normal(0, self.cal.batter_venue_sd_runs * np.sqrt(d.affinity_share) / per, (len(self.team_of), d.teams))

    # Hidden State
    def skillbook(self):
        # the true skill book at this moment: talent plus current form, plus every hidden condition, in engine units
        d, per = self.d, self.cal.runs_per_condition_unit
        now = {k: self.talent[k] + self.form[k] for k in self.spread}
        return SkillBook(self.players, self.venues, self.style, now["quality"], self.split, self.kind, now["bowl_quality"],
                         np.array(d.type_table_runs) / per, np.array(d.pitch_table_runs) / per, self.venue_level, self.venue_dew, self.affinity,
                         d.home_runs / per, self.cal.era_step * (self.season - (d.seasons - 1) / 2) + d.level_runs / per, d.day_sd_runs / per, d.wear_runs / per)

    def _drift(self, weeks):
        # form decays toward zero with the measured memory and picks up fresh noise, so its spread stays constant over time
        keep = np.exp(-weeks / (self.d.form_memory_years * 52))
        for k, sd in self.spread.items():
            fresh = self.rng.normal(0, sd * np.sqrt((1 - self.d.talent_share) * (1 - keep ** 2)), len(self.team_of))
            self.form[k] = keep * self.form[k] + fresh

    def _transfers(self):
        # between seasons a share of players change teams; swaps happen within a role so every squad keeps its shape
        for r in (BATTER, ALLROUNDER, BOWLER):                  # swaps stay inside a role, so every squad keeps its shape
            pool = np.flatnonzero(self.players.role == r)
            movers = self.rng.choice(pool, int(len(pool) * self.d.transfer_share), replace=False)
            self.team_of[movers] = self.team_of[self.rng.permutation(movers)]

    def pick_xi(self, team):
        # a fresh eleven every match: 5 batters, 2 allrounders, 4 bowlers drawn from the squad; the bowlers plus one allrounder bowl
        squad = np.flatnonzero(self.team_of == team)
        role = self.players.role[squad]
        chosen = [self.rng.choice(squad[role == r], k, replace=False) for r, k in zip((BATTER, ALLROUNDER, BOWLER), self.d.xi_roles)]
        xi = np.concatenate(chosen)
        return xi, np.concatenate([chosen[2], chosen[1][:1]])  # four bowlers and one allrounder bowl four overs each

    def _fixture(self, match, home, away):
        (hx, hb), (ax, ab) = self.pick_xi(home), self.pick_xi(away)
        return Fixture(match, self.season, home, away, home, hx, hb, ax, ab)