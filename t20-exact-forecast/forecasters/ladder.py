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

    def _blocks(self, d):
        # each block is one family of hidden numbers: which row of the table each ball points to, what multiplies the number
        # on that ball, which public direction it moves the outcomes along, which ridge strength shrinks it, and how many there are
        n, m, zero = self.shape, self.model, np.zeros(len(d["venue"]), int)
        blocks = [("level", zero, 1.0, m.c, None, 1), ("bat_style", d["batter"], 1.0, m.bs, "bat_style", n["players"]),
                  ("bat_quality", d["batter"], 1.0, m.bq, "bat_quality", n["players"]), ("type_mean", d["how"], 1.0, m.wt, None, 2),
                  ("bowl_type", d["bowler"], 1.0, m.wt, "bowl_type", n["players"]), ("bowl_quality", d["bowler"], 1.0, m.wq, "bowl_quality", n["players"]),
                  ("venue", d["venue"], 1.0, m.c, "venue", n["venues"]), ("dew", d["venue"], d["chasing"], m.c, "dew", n["venues"]), ("wear", zero, -d["chasing"], m.c, None, 1),
                  ("era", np.maximum(d["season"] - 1, 0), (d["season"] > 0).astype(float), m.c, None, max(n["seasons"] - 1, 1)), ("home", zero, d["home"], m.c, "home", 1)]
        # the per-match pitch effect is fitted only by the shrunk tiers, because unshrunk it would absorb everything
        if self.shrink:
            blocks.append(("day", d["match"], 1.0, m.c, "day", n["matches"]))
        # the richer tiers: a pace-versus-spin split per batter, the hand-by-style and pitch-by-style tables, a personal venue liking
        if self.matchups:
            blocks += [("split", d["batter"], d["sign"], m.bq, "split", n["players"]), ("type", d["cell"], 1.0, m.c, "type", 4), ("pitch", d["pitch_cell"], -1.0, m.c, "pitch", 6)]
        if self.use_affinity:
            blocks.append(("affinity", d["bv"], 1.0, m.c, "affinity", n["players"] * n["venues"]))
        # the raw head-to-head tier: one number for every pair that ever met, barely shrunk
        if self.head_to_head:
            blocks.append(("pair", d["pair"], 1.0, m.c, "pair", len(self.pair_keys)))
        return blocks

    def _empty(self):
        # a zero for every possible hidden number, so a tier that does not fit a block still has it (as zeros) when it builds its book
        n = self.shape
        sizes = {"level": 1, "bat_style": n["players"], "bat_quality": n["players"], "type_mean": 2, "bowl_type": n["players"], "bowl_quality": n["players"],
                 "venue": n["venues"], "dew": n["venues"], "wear": 1, "era": n["seasons"], "home": 1, "day": n["matches"], "split": n["players"], "type": 4,
                 "pitch": 6, "affinity": n["players"] * n["venues"], "pair": len(self.pair_keys)}
        return {k: np.zeros(v) for k, v in sizes.items()}

    def _logits(self, d, blocks, theta, cuts):
        # the six scores of every ball: the fixed public part plus each block's number for that ball, times its coefficient, along its direction
        z = d["offset"].copy()
        for (_, index, coef, direction, _, _), lo, hi in zip(blocks, cuts[:-1], cuts[1:]):
            z += np.multiply.outer(theta[lo:hi][index] * coef, direction)
        return z

    def _fit(self, d, keep, scale, iterations):
        """Maximises the penalised likelihood with L-BFGS and exact gradients."""
        # ridge strengths: the PRIOR table times the chosen scale for a shrunk tier, or almost nothing for the unshrunk tier
        lam = {k: (v * scale if self.shrink else 0.05) for k, v in self.PRIOR.items()}
        lam["pair"] = self.PRIOR["pair"] # a raw head-to-head table is, by definition, barely shrunk
        # which balls count, and how much: a mask for held-out validation, and optional season weights
        w = keep.astype(float)
        if self.season_weights is not None:
            w = w * np.asarray(self.season_weights, float)[d["season"]]
        blocks = self._blocks(d)
        cuts = np.concatenate([[0], np.cumsum([b[5] for b in blocks])])
        # one ridge strength per parameter; blocks with no ridge key get a token 1e-3 so the optimum stays unique
        ridge = np.concatenate([np.full(b[5], lam[b[4]] if b[4] else 1e-3) for b in blocks])
        Y, rows = np.eye(6)[d["outcome"]], np.arange(len(w))

        def objective(theta):
            # negative log-likelihood of what happened, plus half the ridge penalty
            p = self.model.shares(self._logits(d, blocks, theta, cuts))
            loss = -(w * np.log(np.clip(p[rows, d["outcome"]], 1e-12, None))).sum() + 0.5 * (ridge * theta ** 2).sum()
            # exact gradient: (Y - p) projected on each block's direction, summed into each block's rows
            R = (Y - p) * w[:, None]
            grad = np.empty_like(theta)
            for (_, index, coef, direction, _, size), lo, hi in zip(blocks, cuts[:-1], cuts[1:]):
                grad[lo:hi] = -np.bincount(index, (R @ direction) * coef, size)
            return loss, grad + ridge * theta

        best = minimize(objective, np.zeros(cuts[-1]), jac=True, method="L-BFGS-B", options={"maxiter": iterations, "maxfun": iterations * 2})
        t = self._empty()
        p = self.model.shares(self._logits(d, blocks, best.x, cuts))
        # how uncertain each fitted number is, from the curvature of the loss at the optimum (a diagonal Laplace approximation)
        self.sd = {k: np.zeros_like(v) for k, v in t.items()} # how uncertain each fitted number is (diagonal Laplace approximation)
        for (name, index, coef, direction, _, size), lo, hi in zip(blocks, cuts[:-1], cuts[1:]):
            curvature = ((p @ direction ** 2) - (p @ direction) ** 2) * w
            spread = 1.0 / np.sqrt(np.bincount(index, curvature * np.square(coef), size) + ridge[lo:hi])
            # the era block has no entry for the first season (it is the baseline), so pad it with a zero
            if name == "era":
                t[name], self.sd[name] = np.concatenate([[0.0], best.x[lo:hi]])[:self.shape["seasons"]], np.concatenate([[0.0], spread])[:self.shape["seasons"]]
            else:
                t[name], self.sd[name] = best.x[lo:hi], spread
        return t

    def _held_out(self, d, t, rows):
        # mean log-likelihood per ball on the held-out rows, scored without the per-match day effects (a new match does not have one)
        keep, self.shrink = self.shrink, False # score without the per-match day effects, which a new match does not have
        blocks = [b for b in self._blocks(d) if b[0] != "day"]
        self.shrink = keep
        theta = np.concatenate([t[b[0]][1:] if b[0] == "era" else t[b[0]] for b in blocks])
        cuts = np.concatenate([[0], np.cumsum([b[5] for b in blocks])])
        p = self.model.shares(self._logits(d, blocks, theta, cuts))
        return float(np.log(np.clip(p[np.arange(len(p)), d["outcome"]], 1e-12, None))[rows].mean())

    def fit(self, history):
        self.history = history
        d = self._design(history)
        seasons = history.seasons
        self.scale = 1.0
        # choose how much to shrink by validation: fit on the earlier seasons, score the last season, keep the best multiplier
        if self.shrink:                                   # choose the amount of shrinkage on the last season, as of the season before
            train = d["season"] < seasons - 1
            scores = {}
            for s in (0.3, 1.0, 3.0):
                t = self._fit(d, train, s, 150)
                # the held-out season's level is not fitted, so extrapolate it from the earlier seasons' trend
                t["era"][-1] = t["era"][-2] + (t["era"][-2] - t["era"][0]) / max(seasons - 2, 1)
                scores[s] = self._held_out(d, t, ~train)
            self.scale = max(scores, key=scores.get)
        # then fit on everything with the chosen scale
        self.t = self._fit(d, np.ones(len(d["season"]), bool), self.scale, 350)
        return self

    def _book(self, t):
        # turn fitted numbers into an EstimatedBook the engine can play, with next season's level extrapolated one step further
        h, n = self.history, self.shape
        era_next = float(t["level"][0] + t["era"][-1] + (t["era"][-1] - t["era"][0]) / max(n["seasons"] - 1, 1))
        day_sd = float(np.std(self.t["day"]) * 1.25) if self.shrink else 0.0   # fitted day effects are shrunk, so their spread understates the truth
        pairs = {}
        if self.head_to_head:
            pairs = {(int(k // 100_000), int(k % 100_000)): float(v) for k, v in zip(self.pair_keys, t["pair"]) if abs(v) > 1e-6}
        return EstimatedBook(h.players, h.venues, t["bat_style"], t["bat_quality"], t["split"], t["type_mean"][h.players.style] + t["bowl_type"], t["bowl_quality"],
                             t["type"].reshape(2, 2), t["pitch"].reshape(2, 3), t["venue"], t["dew"], t["affinity"].reshape(n["players"], n["venues"]),
                             float(t["home"][0]), era_next, day_sd, float(t["wear"][0]), pairs=pairs)

    def predict(self, fixtures):
        sim = MatchSimulator(self.model)
        if not self.uncertainty:
            # the plug-in forecast: play each fixture with the point estimates, a fixed seed per fixture so the output is deterministic
            book = self._book(self.t)
            return np.array([sim.win_probability(book, fx, self.copies, np.random.default_rng(self.seed + fx.match)) for fx in fixtures])
        # carry the uncertainty about every fitted number into the forecast: draw plausible leagues, forecast each, average
        draws, each = self.uncertainty, max(self.copies // self.uncertainty, 50)
        total = np.zeros(len(fixtures))
        for k in range(draws):
            gen = np.random.default_rng([self.seed, 77, k])
            t = {name: (value + gen.normal(0.0, 1.0, value.shape) * self.sd[name] if name not in ("day", "pair") else value) for name, value in self.t.items()}
            book = self._book(t)
            total += np.array([sim.win_probability(book, fx, each, np.random.default_rng([self.seed + fx.match, k])) for fx in fixtures])
        return total / draws