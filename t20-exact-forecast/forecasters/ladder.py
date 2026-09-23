import numpy as np
from scipy.optimize import minimize
from league.engine import PACE, MatchSimulator, SkillBook

class Forecaster:
    # the interface every tier shares: fit on a History, predict one home-win probability per Fixture
    name = "forecaster"
    def fit(self, history):
        return self
    def predict(self, fixtures):
        raise NotImplementedError

class CoinFlip(Forecaster):
    # says 0.5 for everything; the yardstick for skill, and what the task's starter program does
    name = "coin flip"
    def predict(self, fixtures):
        return np.full(len(fixtures), 0.5)

class TeamRatings(Forecaster):
    """
    Team strengths and one home advantage, from results only.
    """
    # Bradley-Terry model fitted by gradient ascent on match results
    # P (home wins) = sigmoid(s_home - s_away + h)
    name = "team ratings from results"
    def fit(self, history):
        m, teams = history.matches, int(history.matches[["home", "away"]].max().max()) + 1
        home, away, won = m.home.to_numpy(), m.away.to_numpy(), (m.winner == m.home).to_numpy(float)
        self.s, self.h = np.zeros(teams), 0.0
        for _ in range(400):
            p = 1 / (1 + np.exp(-(self.s[home] - self.s[away] + self.h)))
            g = won - p
            # each team's strength moves with the results it was involved in, with a light pull toward zero
            self.s += 0.05 * (np.bincount(home, g, teams) - np.bincount(away, g, teams) - 0.5 * self.s)
            self.h += 0.01 * g.sum()
        return self

    def predict(self, fixtures):
        return np.array([1 / (1 + np.exp(-(self.s[f.home] - self.s[f.away] + self.h))) for f in fixtures])

class EstimatedBook(SkillBook):
    """
    A forecaster's own picture of the league. It may also hold effects for specific batter-bowler pairs.
    """

    def __init__(self, *args, pairs=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pairs = pairs or {}

    def pair_effect(self, xi, bowlers):
        # the one hook where a head-to-head belief enters the engine; empty for every tier except the raw head-to-head one
        if not self.pairs:
            return 0.0
        return np.array([[self.pairs.get((int(b), int(w)), 0.0) for w in bowlers] for b in xi])


class BallModelForecaster(Forecaster):
    """
    Fits the documented ball model to the history by penalised likelihood, then plays each fixture many times.
    """

    # ridge strengths per block: lambda = 1 / sigma^2 for a prior spread sigma, so bat_quality at 44 is a spread of 0.15
    PRIOR = {"bat_style": 11.0, "bat_quality": 44.0, "bowl_type": 44.0, "bowl_quality": 31.0, "venue": 156.0, "dew": 400.0, "home": 400.0, "day": 16.0,
             "split": 100.0, "type": 400.0, "pitch": 400.0, "affinity": 100.0, "pair": 0.05}

    def __init__(self, name, model, shrink=True, matchups=False, affinity=False, head_to_head=False, season_weights=None, copies=2500, seed=400_000, uncertainty=0):
        # the switches that turn the reference into each careless or richer tier
        self.name, self.model, self.shrink = name, model, shrink
        self.matchups, self.use_affinity, self.head_to_head = matchups, affinity, head_to_head
        self.season_weights, self.copies, self.seed, self.uncertainty = season_weights, copies, seed, uncertainty

    # one row per ball
    def _design(self, history):
        # everything the likelihood needs, as flat arrays with one entry per ball
        b, pl, vn, m = history.balls, history.players, history.venues, self.model
        d = {k: b[k].to_numpy() for k in ("batter", "bowler", "venue", "season", "match", "outcome")}
        d["chasing"] = (b.innings.to_numpy() == 2).astype(float)
        ball = (b.over * 6 + b.ball).to_numpy()
        pressure = np.where(d["chasing"] > 0, m.pressure(b.target.to_numpy(), b.runs_before.to_numpy(), ball), 0.0)
        # the public part of every ball's six scores, computed once and fixed; the fit only learns what is added to it
        d["offset"] = m.situation(b.over.to_numpy(), b.position.to_numpy(), b.wickets_before.to_numpy(), d["chasing"], pressure)   # the public part
        d["home"] = (vn.home_team[d["venue"]] == b.batting_team.to_numpy()).astype(float)
        d["how"] = pl.style[d["bowler"]]
        d["sign"] = np.where(d["how"] == PACE, 0.5, -0.5)
        d["cell"] = pl.hand[d["batter"]] * 2 + d["how"]
        d["pitch_cell"] = d["how"] * 3 + vn.pitch[d["venue"]]
        d["bv"] = d["batter"] * len(vn.pitch) + d["venue"]
        # every batter-bowler pair that ever met gets an index, used only by the head-to-head tier
        self.pair_keys, d["pair"] = np.unique(d["batter"].astype(np.int64) * 100_000 + d["bowler"], return_inverse=True)
        self.shape = {"players": len(pl.role), "venues": len(vn.pitch), "seasons": history.seasons, "matches": int(d["match"].max()) + 1}
        return d