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

    # Public Products
    def play_history(self):
        # plays the seasons of history one ball at a time (one copy each) and records everything an agent may see
        balls, matches, played = [], [], []
        for season in range(self.d.seasons):
            self.season = season
            if season:
                # the off-season: form drifts for the weeks the league is not playing, then transfers
                self._drift(52 - self.d.weeks_per_season)
                self._transfers()
            # a double round robin, in random order, spread over the season's weeks
            pairs = [(h, a) for h in range(self.d.teams) for a in range(self.d.teams) if h != a]
            order = self.rng.permutation(len(pairs))
            per_week = int(np.ceil(len(pairs) / self.d.weeks_per_season))
            for slot, j in enumerate(order):
                if slot and slot % per_week == 0:
                    self._drift(1)
                fx = self._fixture(len(matches), *pairs[j])
                book = self.skillbook()
                toss = fx.home if self.rng.random() < 0.5 else fx.away
                first, second = (fx.away, fx.home) if toss == fx.home else (fx.home, fx.away)      # the toss winner chases
                xi = {fx.home: fx.home_xi, fx.away: fx.away_xi}
                bowlers = {fx.home: fx.home_bowlers, fx.away: fx.away_bowlers}
                # one pitch-on-the-day value shared by both innings
                totals, day = [], self.rng.normal(0.0, book.day_sd)
                for inn, (bat, bowl) in enumerate(((first, second), (second, first))):
                    log = []
                    total = self.simulator.innings.play(*book.cards(xi[bat], bat, bowlers[bowl], fx.venue), book.shift(fx.venue, inn == 1) + day,
                                                        1, self.rng, totals[0] + 1 if inn else None, log)[0]
                    totals.append(int(total))
                    # one row per ball from the log: who faced whom, the outcome, and the scoreboard before the ball
                    balls += [(season, fx.match, inn + 1, b // 6, b % 6, bat, bowl, fx.venue, int(xi[bat][pos]), int(bowlers[bowl][who]), kind, extra, pos, wk, before, totals[0] + 1 if inn else 0)
                              for b, pos, who, kind, extra, wk, before in log]
                if totals[0] != totals[1]:
                    winner = first if totals[0] > totals[1] else second
                else:
                    winner = first if self.rng.random() < 0.5 else second
                matches.append((season, fx.match, slot // per_week, fx.home, fx.away, fx.venue, toss, first, totals[0], totals[1], winner))
                played.append(fx)
        self.season = self.d.seasons
        # the off-season before the fixtures to be forecast: this is the drift no history can show
        self._drift(52 - self.d.weeks_per_season)                # the off-season before the fixtures to be forecast
        self._transfers()
        ball_cols = ["season", "match", "innings", "over", "ball", "batting_team", "bowling_team", "venue", "batter", "bowler", "outcome", "extra", "position", "wickets_before", "runs_before", "target"]
        match_cols = ["season", "match", "week", "home", "away", "venue", "toss_winner", "batted_first", "first_total", "second_total", "winner"]
        return History(pd.DataFrame(balls, columns=ball_cols), pd.DataFrame(matches, columns=match_cols), self.players, self.venues, played, self.d.seasons)

    def draw_fixtures(self, count):
        # next season's fixtures: a random sample of pairings with fresh elevens, numbered from 10,000 so they cannot collide with history
        pairs = [(h, a) for h in range(self.d.teams) for a in range(self.d.teams) if h != a]
        order = self.rng.permutation(len(pairs))[:count]
        return [self._fixture(10_000 + i, *pairs[j]) for i, j in enumerate(order)]


class TruthEngine:
    """The only door to the hidden skills: the true probability that the home side wins each fixture."""

    def __init__(self, league, copies=20_000, chunk=20_000):
        self.league, self.copies, self.chunk = league, copies, chunk

    def probabilities(self, fixtures):
        # plays each fixture `copies` times with the true skill book, in chunks so memory stays bounded; one seed per fixture and chunk
        book, sim = self.league.skillbook(), self.league.simulator
        parts = max(1, int(np.ceil(self.copies / self.chunk)))
        size = int(np.ceil(self.copies / parts))
        return np.array([np.mean([sim.win_probability(book, fx, size, np.random.default_rng([900_000 + fx.match, part])) for part in range(parts)]) for fx in fixtures])