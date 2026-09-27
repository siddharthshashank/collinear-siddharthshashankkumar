import json
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import pandas as pd

# runs scored by each of the six outcomes, in the order W, 0, 1, 2, 4, 6; a wicket scores nothing
RUNS = np.array([0, 0, 1, 2, 4, 6])
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
class BattingCard:
    # what the innings simulator needs about the eleven batters of one side in one match; built by SkillBook.cards
    style: np.ndarray        
    quality: np.ndarray      
    conditions: np.ndarray   # (11, 5): venue affinity, home lift, hand-by-style and pitch effects for each batter-bowler meeting

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

# Innings Simulator
class InningsSimulator:
    # Plays many copies of one innings at once. Every array below would have one entry per copy, so a ball is one vectorized step.
    def __init__(self, model):
        self.model = model

    def play(self, batting, bowling, conditions, n, gen, target = None, log = None):
        """
        Plays n copies of one innings and returns the n totals.
        `conditions` is a number of one value per copy.
        """
        m, rows = self.model, np.arange(n)
        # who is on strike, who is at the other end, and who comes in next, as positions 0 to 10 in batting order
        striker, partner, next_in = np.zeros(n, int), np.ones(n, int), np.full(n, 2)
        # wickets lost, runs scored, and whether this copy's innings is still going
        wickets = np.zeros(n, int)
        runs = np.zeros(n, int)
        live = np.ones(n, bool)
        chasing = 0.0 if target is None else 1.0
        for ball in range(120):
            over = ball // 6
            # five bowlers rotate over by over; a bowler never bowls two overs in a row
            who = over % 5
            pressure = 0.0 if target is None else m.pressure(target, runs, ball)
            # the public part of the six scores, then the hidden numbers of the striker, the bowler and the conditions, each along its direction
            z = m.situation(over, striker, wickets, np.full(n, chasing), pressure)
            z = z + np.outer(batting.style[striker], m.bs) + np.outer(batting.quality[striker, who], m.bq)
            z = z + bowling.kind[who] * m.wt + bowling.quality[who] * m.wq + np.outer(conditions + batting.conditions[striker, who], m.c)
            p = m.shares(z)
            # one uniform draw per copy picks the outcome from the cumulative probabilities; the minimum guards against rounding
            kind = np.minimum((gen.random(n)[:, None] > p.cumsum(axis=1)).sum(axis=1), 5)
            # an extra run with the measured probability, independent of the bat outcome
            extra = (gen.random(n) < m.cal.extras_per_ball) & live
            # optional ball-by-ball record of copy 0, used by the league to write the history files
            if log is not None and live[0]:
                log.append((ball, int(striker[0]), who, int(kind[0]), int(extra[0]), int(wickets[0]), int(runs[0])))
            out = (kind == 0) & live
            scored = np.where(live & ~out, RUNS[kind], 0)
            runs += scored + extra
            wickets += out
            # the next batter replaces a dismissed striker
            striker = np.where(out, next_in, striker)
            next_in = next_in + out
            # the batters cross on an odd number of runs and at the end of an over, but not both
            swap = (scored % 2 == 1) ^ (ball % 6 == 5)
            striker, partner = np.where(swap, partner, striker), np.where(swap, striker, partner)
            # after the tenth wicket the indices would run past the eleven; clamp them, the innings is over anyway
            striker, partner = np.minimum(striker, 10), np.minimum(partner, 10)
            # an innings ends at ten wickets, or when a chase reaches its target
            live &= wickets < 10
            if target is not None:
                live &= runs < target
        return runs

class SkillBook:
    """Everything the engine needs to know about players and venues. 
    The league owns the [REDACTED] one. A forecaster builds its own.
    """
    # Per player: style, quality, split (pace-versus-spin gap in quality), kind (bowler type), bowl_quality.
    # Per venue: level and dew. Per player-venue: affinity. Whole league: home lift, era (season level), day spread, wear.
    # Two small public-structure tables: type_table [hand][bowling style] and pitch_table [bowling style][pitch type].

    def __init__(self, players, venues, style, quality, split, kind, bowl_quality, type_table, pitch_table, venue_level, venue_dew, affinity, home_lift, era, day_sd, wear):
        self.players, self.venues = players, venues
        self.style, self.quality, self.split, self.kind, self.bowl_quality = style, quality, split, kind, bowl_quality
        self.type_table, self.pitch_table = np.asarray(type_table), np.asarray(pitch_table)
        self.venue_level, self.venue_dew, self.affinity = venue_level, venue_dew, affinity
        self.home_lift, self.era, self.day_sd, self.wear = home_lift, era, day_sd, wear

    def cards(self, xi, team, bowlers, venue):
        # builds the two cards for one side batting against five named bowlers at one ground
        hand, how = self.players.hand[xi], self.players.style[bowlers]
        # a batter's quality against pace is quality + split/2, against spin quality - split/2
        sign = np.where(how == PACE, 0.5, -0.5)
        at_home = self.home_lift if self.venues.home_team[venue] == team else 0.0
        # the conditions each batter meets against each bowler: liking for the ground, home lift, hand-versus-style, and the pitch's help to that style
        meeting = (self.affinity[xi, venue] + at_home)[:, None] + self.type_table[hand][:, how] - self.pitch_table[how, self.venues.pitch[venue]][None, :]
        batting = BattingCard(self.style[xi], self.quality[xi][:, None] + self.split[xi][:, None] * sign[None, :], meeting + self.pair_effect(xi, bowlers))
        return batting, BowlingCard(self.kind[bowlers], self.bowl_quality[bowlers])

    def pair_effect(self, xi, bowlers):
        # a forecaster that believes in head-to-head records can override this; the [REDACTED] league has none
        return 0.0                       # the [REDACTED] league has no effect tied to one specific batter-bowler pair

    def shift(self, venue, chasing):
        # the conditions shared by every ball of an innings: the ground's level, the season level, and in a chase the dew minus the wear
        return self.venue_level[venue] + self.era + ((self.venue_dew[venue] - self.wear) if chasing else 0.0)


class MatchSimulator:
    def __init__(self, model):
        self.innings = InningsSimulator(model)

    def win_probability(self, book, fixture, n, gen):
        """
        P(home side wins). 
        The toss is a coin flip and the winner always chases. 
        A tie is settled by a coin flip.
        """
        f = fixture
        xi, five = {f.home: f.home_xi, f.away: f.away_xi}, {f.home: f.home_bowlers, f.away: f.away_bowlers}
        total = 0.0
        # both orders of batting are played, each with weight one half, because the toss decides who chases
        for first, second in ((f.home, f.away), (f.away, f.home)):
            day = gen.normal(0.0, book.day_sd, n) if book.day_sd > 0 else np.zeros(n)       # the same pitch for both innings of a copy
            set_ = self.innings.play(*book.cards(xi[first], first, five[second], f.venue), book.shift(f.venue, False) + day, n, gen)
            chase = self.innings.play(*book.cards(xi[second], second, five[first], f.venue), book.shift(f.venue, True) + day, n, gen, target=set_ + 1)
            # the chasing side wins if it passes the total; a tie is worth half
            second_wins = (chase > set_).mean() + 0.5 * (chase == set_).mean()
            total += 0.5 * (second_wins if second == f.home else 1 - second_wins)
        return float(total)


class PublicConstants:
    """
    The documented structure of a ball: 
        everything in the engine that is not a hidden skill or a hidden condition.
    """
    # This is what ships to the agent as public.json: the profiles, the situation responses, the directions and the extras rate.
    # The spreads, the venue spread and the real targets from calibration.json are deliberately not in it.
    FIELDS = ("over_logits", "position_vectors", "wickets_vector", "pressure_vector", "second_innings_vector", "typical_wickets", "par_rate")

    def __init__(self, raw):
        for name in self.FIELDS:
            setattr(self, name, np.array(raw[name]))
        self.directions = {k: np.array(v) for k, v in raw["directions"].items()}
        self.extras_per_ball = raw["extras_per_ball"]

    @classmethod
    def from_calibration(cls, cal):
        raw = {name: getattr(cal, name).tolist() for name in cls.FIELDS}
        raw.update(directions={k: v.tolist() for k, v in cal.directions.items()}, extras_per_ball=cal.extras_per_ball)
        return raw


def load_public_model(path=None):
    # what the AI agent's copy of the engine does: build a BallModel from public.json beside it
    raw = json.loads(Path(path or Path(__file__).with_name("public.json")).read_text())
    return BallModel(PublicConstants(raw))