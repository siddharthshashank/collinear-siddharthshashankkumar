import json
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import pandas as pd

# runs scored by each of the six outcomes, in the order W, 0, 1, 2, 4, 6; a wicket scores nothing
RUN = np.array([0, 0, 1, 2, 4, 6])
# the two bowling styles, as integers so they can index tables
PACE, SPIN = 0, 1

@dataclass
class PlayerTable:
    # one entry per player in the league, indexed by player id; these are public facts about a player
    role: np.ndarray
    hand: np.ndarray # 0 right, 1 left
    style: np.ndarray # PACE or SPIN; meaningful only for players who bowl

@dataclass
class VenueTable:
    # one entry per ground, indexed by venue id; also public
    home_team: np.ndarray
    pitch: np.ndarray # 0 neutral, 1 helps pace, 2 helps spin

@dataclass
class Fixture:
    # one match's line-ups: the eleven and the five bowlers for each side, plus where and when it is played
    match: int
    season: int
    home: int
    away: int
    venue: int
    home_xi: np.ndarray
    home_bowlers: np.ndarray
    away_xi: np.ndarray
    away_bowlers: np.ndarray

@dataclass
class History:
    # everything an AI agent is allowed to see about the past: every ball, every match, the players, the grounds, the line-ups
    balls: pd.DataFrame
    matches: pd.DataFrame
    players: PlayerTable
    venues: VenueTable
    played: list = field(default_factory = list) # the Fixture of every past match (who played, who bowled)
    seasons: int = 0

@dataclass
class BowlingCard:
    # the same for the five bowlers of the other side
    kind: np.ndarray
    quality: np.ndarray

class BallModel:
    # Public part of a ball. Holds the measured constants and the five directions; adds up the situation. Nothing hidden lives here.
    def __init__(self, cal):
        self.cal = cal
        d = cal.directions
        # short names for the five unit vectors: batter style, batter quality, bowler type, bowler quality, conditions
        self.bs = d["bat_style"]
        self.bq = d["bat_quality"]
        self.wt = d["bowl_type"]
        self.wq = d["bowl_quality"]
        self.c = d["conditions"]

    def pressure(self, target, runs, ball):
        # chase pressure, the same formula as in the fit: log of the rate still needed over the rate sides usually maange from here.
        # `ball` counts legal balls from 0 to 119, so (120 - ball) / 6 is the overs left. Clipped so freak situations do not dominate.
        need = np.clip(target - runs, 1, None) / ((120 - ball) / 6)
        return np.clip(np.log(need / self.cal.par_rate[ball // 6]), -1.0, 1.2)

    def situation(self, over, position, wickets, chasing, pressure):
        """
        The public part of the logits: the over, the batting position and the match situation. Works for one ball or a table of balls.
        """
        # each term is one effect from the fitted model
        # np.multiply.outer scales a six-vector by one number per ball
        cal = self.cal
        z = cal.over_logits[over] + cal.position_vectors[position] + np.multiply.outer(wickets - cal.typical_wickets[over], cal.wickets_vector)
        return z + np.multiply.outer(chasing, cal.second_innings_vector) + np.multiply.outer(pressure, cal.pressure_vector)

    @staticmethod
    def shares(z):
        # six scores become six probabilities; subtracting the row maximum changes nothing and stops exp() overflowing
        p = np.exp(z - z.max(axis=1, keepdims=True))
        return p / p.sum(axis=1, keepdims=True)