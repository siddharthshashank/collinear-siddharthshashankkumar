"""Load a league folder and turn every recorded ball into the public part of its logits plus the indices needed for the fit."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from engine.model import load_public_model, PACE, SPIN  # noqa: E402
from engine.league_io import load_league  # noqa: E402


def period_of(season, week, halves=2, weeks_per_season=8):
    # split each season into `halves` equal blocks of weeks
    return season * halves + np.minimum((week * halves) // max(int(weeks_per_season), 1), halves - 1)


class LeagueData:
    def __init__(self, folder, halves=2):
        self.folder = Path(folder)
        self.model = load_public_model()
        self.history, self.fixtures = load_league(folder)
        h = self.history
        self.players, self.venues = h.players, h.venues
        self.n_players = len(self.players.role)
        self.n_venues = len(self.venues.pitch)
        self.n_teams = int(max(h.matches.home.max(), h.matches.away.max())) + 1
        self.matches = h.matches.copy()
        self.n_seasons = int(self.matches.season.max()) + 1
        self.halves = halves
        weeks = int(self.matches.week.max()) + 1
        self.matches["period"] = period_of(self.matches.season.to_numpy(), self.matches.week.to_numpy(), halves, weeks)
        self.n_periods = self.n_seasons * halves   # observed periods; the fixture period is n_periods
        b = h.balls
        m = self.matches.set_index("match")
        b = b.join(m[["period", "week"]], on="match")
        self.balls = b
        self.public = self.public_logits(b)
        self.y = b.outcome.to_numpy()

    def public_logits(self, b):
        model = self.model
        ballidx = (b.over * 6 + b.ball).to_numpy()
        chasing = (b.innings.to_numpy() == 2).astype(float)
        target = b.target.to_numpy()
        pressure = np.where(chasing > 0, model.pressure(np.maximum(target, 1), b.runs_before.to_numpy(), ballidx), 0.0)
        return model.situation(b.over.to_numpy(), b.position.to_numpy(), b.wickets_before.to_numpy(), chasing, pressure)
