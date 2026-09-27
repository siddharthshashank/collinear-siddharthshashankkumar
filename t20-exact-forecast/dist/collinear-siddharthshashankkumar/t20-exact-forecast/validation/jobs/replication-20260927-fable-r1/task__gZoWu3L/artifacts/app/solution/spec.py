"""Builds the design and the priors for one league, and turns a parameter vector into the cards the simulator needs."""
import numpy as np
from fitter import Design, Fitter, ar_covariance

PACE, SPIN = 0, 1

DEFAULT_HYPER = dict(
    sd_style=0.3, sd_talent=0.3, sd_form=0.15, rho_w=0.9, rho_o=0.7,
    sd_split=0.1, sd_kind=0.3, sd_btalent=0.3, sd_bform=0.15, rho_bw=0.9, rho_bo=0.7,
    sd_venue=0.3, sd_era=0.2, sd_chase=0.1, sd_day=0.15, sd_aff=0.1, sd_type=0.1, sd_pitch=0.1,
    sd_fixed=3.0,
)


class Spec:
    def __init__(self, L, hyper=None, halves=None):
        self.L = L
        self.h = dict(DEFAULT_HYPER, **(hyper or {}))
        b = L.balls
        pl, ve = L.players, L.venues
        self.K = L.n_periods                        # observed periods; the fixture period is index K
        self.n_seasons = L.n_seasons
        # bowlers: anyone who has a bowling slot in history or in the fixtures
        hist_bowlers = set()
        for f in L.fixtures:
            hist_bowlers |= set(map(int, f.home_bowlers)) | set(map(int, f.away_bowlers))
        hist_bowlers |= set(map(int, b.bowler.unique()))
        self.bowlers = np.array(sorted(hist_bowlers))
        self.bowler_index = np.full(L.n_players, -1); self.bowler_index[self.bowlers] = np.arange(len(self.bowlers))
        # batter-venue pairs seen in history or needed for fixtures
        pairs = set(zip(b.batter.to_numpy().tolist(), b.venue.to_numpy().tolist()))
        for f in L.fixtures:
            for p in list(f.home_xi) + list(f.away_xi):
                pairs.add((int(p), int(f.venue)))
        self.pairs = np.array(sorted(pairs))
        self.pair_index = {tuple(x): i for i, x in enumerate(self.pairs.tolist())}
        self.build_design()

    def build_design(self):
        L, b = self.L, self.L.balls
        pl, ve = L.players, L.venues
        N = len(b)
        n = np.arange(N)
        batter, bowler, venue = b.batter.to_numpy(), b.bowler.to_numpy(), b.venue.to_numpy()
        period = b.period.to_numpy(); season = b.season.to_numpy(); match = b.match.to_numpy()
        chasing = (b.innings.to_numpy() == 2).astype(float)
        bat_team = b.batting_team.to_numpy()
        K1 = self.K + 1
        des = Design()
        # direction 0: batter style
        blk = des.add_block("style_mean", 3, 0); des.add_entries(blk, n, pl.role[batter])
        blk = des.add_block("style", L.n_players, 0); des.add_entries(blk, n, batter)
        # direction 1: batter quality
        blk = des.add_block("tal_mean", 3, 1); des.add_entries(blk, n, pl.role[batter])
        blk = des.add_block("q", L.n_players * K1, 1); des.add_entries(blk, n, batter * K1 + period)
        sign = np.where(pl.style[bowler] == PACE, 0.5, -0.5)
        blk = des.add_block("split", L.n_players, 1); des.add_entries(blk, n, batter, sign)
        # direction 2: bowler type
        bi = self.bowler_index[bowler]
        blk = des.add_block("kind_mean", 2, 2); des.add_entries(blk, n, pl.style[bowler])
        blk = des.add_block("kind", len(self.bowlers), 2); des.add_entries(blk, n, bi)
        # direction 3: bowler quality
        blk = des.add_block("bq_mean", 3, 3); des.add_entries(blk, n, pl.role[bowler])
        blk = des.add_block("r", len(self.bowlers) * K1, 3); des.add_entries(blk, n, bi * K1 + period)
        # direction 4: conditions
        blk = des.add_block("venue", L.n_venues, 4); des.add_entries(blk, n, venue)
        blk = des.add_block("era", self.n_seasons + 1, 4); des.add_entries(blk, n, season)
        blk = des.add_block("chase_mean", 1, 4); des.add_entries(blk, n, np.zeros(N, int), chasing)
        blk = des.add_block("chase", L.n_venues, 4); des.add_entries(blk, n, venue, chasing)
        blk = des.add_block("day", len(L.matches), 4); des.add_entries(blk, n, match)
        pair_idx = np.array([self.pair_index[(int(x), int(v))] for x, v in zip(batter, venue)])
        blk = des.add_block("aff", len(self.pairs), 4); des.add_entries(blk, n, pair_idx)
        at_home = (ve.home_team[venue] == bat_team).astype(float)
        blk = des.add_block("home", 1, 4); des.add_entries(blk, n, np.zeros(N, int), at_home)
        blk = des.add_block("type", 4, 4); des.add_entries(blk, n, pl.hand[batter] * 2 + pl.style[bowler])
        blk = des.add_block("pitch", 6, 4); des.add_entries(blk, n, pl.style[bowler] * 3 + ve.pitch[venue], -np.ones(N))
        des.build(N)
        self.des = des
        self.fitter = Fitter(des, L.public, L.y, L.model.cal.directions)
        self.set_hyper(self.h)

    def transitions(self, rho_w, rho_o):
        # rho for each transition between consecutive periods 0..K (K transitions); an off-season sits between seasons
        halves = self.L.halves
        return [rho_o if (k + 1) % halves == 0 else rho_w for k in range(self.K)]

    def set_hyper(self, h):
        self.h = h = dict(self.h, **h)
        K1 = self.K + 1
        prec = {}
        fixed = 1.0 / h["sd_fixed"] ** 2
        for name in ("style_mean", "tal_mean", "kind_mean", "bq_mean", "chase_mean", "home"):
            prec[name] = fixed
        prec["style"] = 1 / h["sd_style"] ** 2
        prec["split"] = 1 / h["sd_split"] ** 2
        prec["kind"] = 1 / h["sd_kind"] ** 2
        prec["venue"] = 1 / h["sd_venue"] ** 2
        prec["chase"] = 1 / h["sd_chase"] ** 2
        prec["day"] = 1 / h["sd_day"] ** 2
        prec["aff"] = 1 / h["sd_aff"] ** 2
        prec["type"] = 1 / h["sd_type"] ** 2
        prec["pitch"] = 1 / h["sd_pitch"] ** 2
        Cq = ar_covariance(self.transitions(h["rho_w"], h["rho_o"]), h["sd_talent"], h["sd_form"])
        prec["q"] = (np.linalg.inv(Cq), self.L.n_players)
        Cr = ar_covariance(self.transitions(h["rho_bw"], h["rho_bo"]), h["sd_btalent"], h["sd_bform"])
        prec["r"] = (np.linalg.inv(Cr), len(self.bowlers))
        # era: random walk across seasons (including the fixture season), start N(0, sd_era^2) -- use a walk with step sd_era
        S1 = self.n_seasons + 1
        Ce = np.array([[min(i, j) + 1 for j in range(S1)] for i in range(S1)], float) * h["sd_era"] ** 2
        prec["era"] = (np.linalg.inv(Ce), 1)
        self.fitter.set_prior(prec)

    # ---- extracting cards for fixtures ----
    def block(self, theta, name):
        b = self.des.blocks[name]
        return theta[..., b.start:b.stop]

    def cards(self, theta, fixture, period=None):
        """Returns per-side dicts of arrays for the simulator. theta may be (P,) or (S, P): outputs get a leading S axis."""
        L, pl, ve = self.L, self.L.players, self.L.venues
        K1 = self.K + 1
        period = self.K if period is None else period
        f = fixture
        th = np.atleast_2d(theta)
        S = th.shape[0]
        style_mean, style = self.block(th, "style_mean"), self.block(th, "style")
        tal_mean, q, split = self.block(th, "tal_mean"), self.block(th, "q").reshape(S, L.n_players, K1), self.block(th, "split")
        kind_mean, kind = self.block(th, "kind_mean"), self.block(th, "kind")
        bq_mean, r = self.block(th, "bq_mean"), self.block(th, "r").reshape(S, len(self.bowlers), K1)
        venue, era = self.block(th, "venue"), self.block(th, "era")
        chase_mean, chase = self.block(th, "chase_mean"), self.block(th, "chase")
        aff, home, typ, pitch = self.block(th, "aff"), self.block(th, "home"), self.block(th, "type"), self.block(th, "pitch")
        v = f.venue
        season = f.season if f.season <= self.n_seasons else self.n_seasons
        out = {}
        for team, xi, five in ((f.home, f.home_xi, f.home_bowlers), (f.away, f.away_xi, f.away_bowlers)):
            xi = np.asarray(xi, int); five = np.asarray(five, int)
            bi = self.bowler_index[five]
            how = pl.style[five]
            sign = np.where(how == PACE, 0.5, -0.5)
            st = style_mean[:, pl.role[xi]] + style[:, xi]
            qual = (tal_mean[:, pl.role[xi]] + q[:, xi, period])[:, :, None] + split[:, xi][:, :, None] * sign[None, None, :]
            at_home = home[:, 0] if ve.home_team[v] == team else np.zeros(S)
            pair = np.array([self.pair_index.get((int(p), int(v)), -1) for p in xi])
            a = np.where(pair[None, :] >= 0, aff[:, np.maximum(pair, 0)], 0.0)
            cond = (a + at_home[:, None])[:, :, None] + typ[:, pl.hand[xi][:, None] * 2 + how[None, :]] - pitch[:, how * 3 + ve.pitch[v]][:, None, :]
            out[team] = dict(style=st, quality=qual, conditions=cond,
                             kind=kind_mean[:, how] + kind[:, bi], bowl_quality=bq_mean[:, pl.role[five]] + r[:, bi, period])
        shift_first = venue[:, v] + era[:, season]
        shift_chase = shift_first + chase_mean[:, 0] + chase[:, v]
        return out, shift_first, shift_chase
