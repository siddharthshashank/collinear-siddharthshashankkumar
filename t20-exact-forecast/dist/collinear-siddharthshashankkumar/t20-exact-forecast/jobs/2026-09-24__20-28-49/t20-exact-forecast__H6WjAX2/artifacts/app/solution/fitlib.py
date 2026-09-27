"""Structured multinomial-logit fit of the engine's ball model with Gaussian random effects.

Each ball contributes five scalar linear predictors (one per public direction), each a sparse linear
function of one parameter vector. Batter and bowler quality vary over time in blocks (nb blocks per season)
with a talent + AR(1)-form covariance whose scales are estimated by Laplace-EM.
"""
import sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
import scipy.linalg as sla
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.model import load_public_model, PACE  # noqa: E402

DIRS = ("bs", "bq", "wt", "wq", "c")
FIXED_SD = 3.0


class Blocks:
    def __init__(self):
        self.names, self.sizes, self.offsets, self.shapes = [], [], {}, {}
        self.total = 0

    def add(self, name, shape):
        size = int(np.prod(shape))
        self.names.append(name); self.sizes.append(size); self.offsets[name] = self.total; self.shapes[name] = tuple(shape)
        self.total += size
        return name

    def size(self, name):
        return self.sizes[self.names.index(name)]

    def idx(self, name, *multi):
        shape = self.shapes[name]
        if len(multi) == 1:
            return self.offsets[name] + np.asarray(multi[0])
        return self.offsets[name] + np.ravel_multi_index([np.asarray(m) for m in multi], shape)

    def get(self, theta, name):
        o = self.offsets[name]
        return theta[o:o + self.size(name)].reshape(self.shapes[name])


class TimeBlocks:
    """Observed (player, block) pairs for a time-varying quality, with block times."""

    def __init__(self, player, block, n_players, n_blocks, nb, W):
        key = player * n_blocks + block
        self.keys = np.unique(key)
        self.n = len(self.keys)
        self.player = self.keys // n_blocks
        self.block = self.keys % n_blocks
        self.nb, self.W = nb, W
        self.season = self.block // nb
        self.time = self.season * W + (self.block % nb + 0.5) * W / nb  # in weeks, ignoring the off-season
        self.lookup = np.full(n_players * n_blocks, -1); self.lookup[self.keys] = np.arange(self.n)
        self.starts = np.searchsorted(self.player, np.arange(n_players + 1))  # per-player slices (keys sorted by player)

    def index(self, player, block):
        return self.lookup[player * self.lookup.shape[0] // self.lookup.shape[0] * 0 + player * (self.lookup.shape[0] // max(1, self.n_players_guess())) + block] if False else self.lookup[player * self._nblk + block]

    @property
    def _nblk(self):
        return self.lookup.shape[0] // (self.starts.shape[0] - 1)

    def n_players_guess(self):
        return self.starts.shape[0] - 1

    def slice(self, p):
        return slice(self.starts[p], self.starts[p + 1])


def time_cov(hp, t1, s1, t2, s2):
    """Talent + AR(1) form covariance between block times: st^2 + sf^2 * rho_w^|dt| * rho_off^|ds|."""
    st, sf, rho_w, rho_off = hp
    dt = np.abs(t1[:, None] - t2[None, :]); ds = np.abs(s1[:, None] - s2[None, :])
    return st ** 2 + sf ** 2 * rho_w ** dt * rho_off ** ds


def prep(history):
    m = load_public_model()
    b = history.balls
    over = b.over.to_numpy(); ballno = over * 6 + b.ball.to_numpy()
    chasing = (b.innings.to_numpy() == 2).astype(float)
    target = b.target.to_numpy(); runs = b.runs_before.to_numpy()
    pressure = np.where(chasing > 0, m.pressure(np.maximum(target, 1), runs, ballno), 0.0)
    S = m.situation(over, b.position.to_numpy(), b.wickets_before.to_numpy(), chasing, pressure)
    D = np.stack([m.bs, m.bq, m.wt, m.wq, m.c])
    return m, S, D


class Design:
    def __init__(self, history, n_seasons, nb=1):
        self.m, self.S, self.D = prep(history)
        b = history.balls
        P, V = history.players, history.venues
        self.n = len(b); self.y = b.outcome.to_numpy()
        self.n_players, self.n_venues = len(P.role), len(V.pitch)
        self.n_seasons, self.nb = n_seasons, nb
        bat = b.batter.to_numpy(); bowl = b.bowler.to_numpy(); season = b.season.to_numpy()
        venue = b.venue.to_numpy(); match = b.match.to_numpy(); chasing = (b.innings.to_numpy() == 2).astype(float)
        hand = P.hand[bat]; bstyle = P.style[bowl]; pitch = V.pitch[venue]
        at_home = (b.batting_team.to_numpy() == V.home_team[venue]).astype(float)
        sign = np.where(bstyle == PACE, 0.5, -0.5)
        mt = history.matches
        week_of = dict(zip(mt.match.to_numpy(), mt.week.to_numpy()))
        self.W = int(mt.week.max()) + 1
        week = np.array([week_of[mm] for mm in match])
        block = season * nb + (week * nb) // self.W
        self.n_blocks = n_seasons * nb
        self.matches = np.unique(match)
        midx = np.searchsorted(self.matches, match)
        self.bowlers = np.unique(bowl)
        self.bowler_index = np.full(self.n_players, -1); self.bowler_index[self.bowlers] = np.arange(len(self.bowlers))
        widx = self.bowler_index[bowl]
        pair_key = bat * self.n_venues + venue
        self.pairs = np.unique(pair_key); pidx = np.searchsorted(self.pairs, pair_key)
        self.qblk = TimeBlocks(bat, block, self.n_players, self.n_blocks, nb, self.W)
        self.wblk = TimeBlocks(bowl, block, self.n_players, self.n_blocks, nb, self.W)
        qidx = self.qblk.lookup[bat * self.n_blocks + block]
        bqidx = self.wblk.lookup[bowl * self.n_blocks + block]

        B = self.B = Blocks()
        B.add("style_role", (3,)); B.add("q_role", (3,)); B.add("kind_style", (2,)); B.add("wq_cell", (2, 2))
        B.add("era", (n_seasons,)); B.add("home_lift", (1,)); B.add("wear", (1,)); B.add("type_table", (2, 2)); B.add("pitch_table", (2, 3))
        B.add("style", (self.n_players,)); B.add("quality", (self.qblk.n,)); B.add("split", (self.n_players,))
        B.add("kind", (len(self.bowlers),)); B.add("bowl_quality", (self.wblk.n,))
        B.add("venue", (self.n_venues,)); B.add("dew", (self.n_venues,)); B.add("affinity", (len(self.pairs),)); B.add("day", (len(self.matches),))
        self.fixed = ["style_role", "q_role", "kind_style", "wq_cell", "era", "home_lift", "wear", "type_table", "pitch_table"]
        self.random = ["style", "split", "kind", "venue", "dew", "affinity", "day"]
        self.seasonal = {"quality": self.qblk, "bowl_quality": self.wblk}

        rows = np.arange(self.n); ones = np.ones(self.n)
        role_b = P.role[bat]; wrole = np.where(P.role[bowl] == 1, 0, 1)
        cols = {
            "bs": [(B.idx("style_role", role_b), ones), (B.idx("style", bat), ones)],
            "bq": [(B.idx("q_role", role_b), ones), (B.idx("quality", qidx), ones), (B.idx("split", bat), sign)],
            "wt": [(B.idx("kind_style", bstyle), ones), (B.idx("kind", widx), ones)],
            "wq": [(B.idx("wq_cell", wrole, bstyle), ones), (B.idx("bowl_quality", bqidx), ones)],
            "c": [(B.idx("era", season), ones), (B.idx("home_lift", np.zeros(self.n, int)), at_home), (B.idx("wear", np.zeros(self.n, int)), chasing),
                  (B.idx("type_table", hand, bstyle), ones), (B.idx("pitch_table", bstyle, pitch), -ones),
                  (B.idx("venue", venue), ones), (B.idx("dew", venue), chasing), (B.idx("affinity", pidx), ones), (B.idx("day", midx), ones)],
        }
        self.X = {}
        for d in DIRS:
            r = np.concatenate([rows] * len(cols[d])); c = np.concatenate([ci for ci, _ in cols[d]]); v = np.concatenate([vi for _, vi in cols[d]])
            self.X[d] = sp.csr_matrix((v, (r, c)), shape=(self.n, B.total))
        self.XT = {d: self.X[d].T.tocsr() for d in DIRS}
        self.Y = np.zeros((self.n, 6)); self.Y[rows, self.y] = 1.0

    # ---- prior
    def player_cov(self, name, hp, p):
        tb = self.seasonal[name]; sl = tb.slice(p)
        return time_cov(hp[name], tb.time[sl], tb.season[sl], tb.time[sl], tb.season[sl])

    def prior_precision(self, hp):
        B = self.B
        diag = np.zeros(B.total)
        for name in self.fixed:
            o = B.offsets[name]; diag[o:o + B.size(name)] = 1.0 / FIXED_SD ** 2
        for name in self.random:
            o = B.offsets[name]; diag[o:o + B.size(name)] = 1.0 / hp[name] ** 2
        rows, cols, vals = [np.arange(B.total)], [np.arange(B.total)], [diag]
        for name, tb in self.seasonal.items():
            o = B.offsets[name]
            for p in range(self.n_players):
                sl = tb.slice(p)
                if sl.stop == sl.start:
                    continue
                prec = np.linalg.inv(self.player_cov(name, hp, p))
                ii = np.arange(o + sl.start, o + sl.stop)
                rows.append(np.repeat(ii, len(ii))); cols.append(np.tile(ii, len(ii))); vals.append(prec.ravel())
        return sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(B.total, B.total))

    # ---- objective
    def logits(self, theta):
        z = self.S.copy()
        for j, d in enumerate(DIRS):
            z += np.outer(self.X[d] @ theta, self.D[j])
        return z

    def nll_grad(self, theta, P):
        z = self.logits(theta)
        z -= z.max(axis=1, keepdims=True)
        lse = np.log(np.exp(z).sum(axis=1))
        nll = -(z[np.arange(self.n), self.y] - lse).sum()
        p = np.exp(z - lse[:, None])
        R = p - self.Y
        g = np.zeros_like(theta)
        for j, d in enumerate(DIRS):
            g += self.XT[d] @ (R @ self.D[j])
        Pt = P @ theta
        return nll + 0.5 * theta @ Pt, g + Pt, p

    def hessian(self, p, P, chunk=40000):
        DP = p @ self.D.T
        G = np.einsum("nk,dk,ek->nde", p, self.D, self.D) - DP[:, :, None] * DP[:, None, :]
        G += 1e-12 * np.eye(5)[None]
        M = np.linalg.cholesky(G)  # (n, 5, 5): G_i = M_i M_i^T so that H = Z^T Z
        H = P.toarray()
        for start in range(0, self.n, chunk):
            sl = slice(start, min(start + chunk, self.n))
            for kcol in range(5):
                Zk = None
                for a, d in enumerate(DIRS):
                    term = sp.diags(M[sl, a, kcol]) @ self.X[d][sl]
                    Zk = term if Zk is None else Zk + term
                Zk = Zk.tocsr()
                H += (Zk.T @ Zk).toarray()
        return H

    def fit(self, hp, theta0=None, newton_iters=12, tol=1e-6, verbose=False):
        P = self.prior_precision(hp)
        theta = np.zeros(self.B.total) if theta0 is None else theta0.copy()
        f, g, p = self.nll_grad(theta, P)
        for it in range(newton_iters):
            H = self.hessian(p, P)
            L = sla.cho_factor(H, lower=True)
            step = sla.cho_solve(L, g)
            t = 1.0
            while True:
                th = theta - t * step
                f2, g2, p2 = self.nll_grad(th, P)
                if f2 <= f - 1e-4 * t * (g @ step) or t < 1e-4:
                    break
                t *= 0.5
            dec = g @ step
            theta, f, g, p = th, f2, g2, p2
            if verbose:
                print(f"  newton {it}: f={f:.3f} t={t} dec={dec:.4g}", flush=True)
            if dec < tol:
                break
        H = self.hessian(p, P)
        return theta, f, H

    def posterior_cov(self, H):
        """Inverse of the (SPD) Hessian, computed in place from its Cholesky factor."""
        c, info = sla.lapack.dpotrf(H, lower=1, overwrite_a=0)
        if info != 0:
            raise np.linalg.LinAlgError("Hessian not positive definite")
        inv, info = sla.lapack.dpotri(c, lower=1, overwrite_c=1)
        inv = np.tril(inv) + np.tril(inv, -1).T
        return inv

    # ---- EM
    def em_update(self, theta, C, hp, floor=0.01):
        B = self.B
        new = dict(hp)
        for name in self.random:
            o = B.offsets[name]; s = B.size(name)
            th = theta[o:o + s]
            new[name] = max(float(np.sqrt((th @ th + np.trace(C[o:o + s, o:o + s])) / s)), floor)
        for name, tb in self.seasonal.items():
            o = B.offsets[name]
            mats = []
            for p in range(self.n_players):
                sl = tb.slice(p)
                if sl.stop == sl.start:
                    continue
                ii = slice(o + sl.start, o + sl.stop)
                th = theta[ii]
                mats.append((tb.time[sl], tb.season[sl], np.outer(th, th) + C[ii, ii]))
            new[name] = self._fit_time_cov(mats, hp[name])
        return new

    def _fit_time_cov(self, mats, hp0):
        fix_rho_w = self.nb == 1

        def unpack(x):
            st, sf = np.exp(x[0]), np.exp(x[1])
            rho_w = 1.0 if fix_rho_w else 1 / (1 + np.exp(-x[2]))
            rho_off = 1 / (1 + np.exp(-x[3]))
            return (st, sf, rho_w, rho_off)

        def nl(x):
            hp = unpack(x)
            tot = 0.0
            for t, s, Sm in mats:
                cov = time_cov(hp, t, s, t, s)
                try:
                    Lc = np.linalg.cholesky(cov)
                except np.linalg.LinAlgError:
                    return 1e12
                tot += np.log(np.diag(Lc)).sum() + 0.5 * np.trace(sla.cho_solve((Lc, True), Sm))
            return tot

        def logit(r):
            r = min(max(r, 1e-3), 1 - 1e-3); return np.log(r / (1 - r))
        st0, sf0, rw0, ro0 = hp0
        x0 = np.array([np.log(max(st0, 1e-3)), np.log(max(sf0, 1e-3)), logit(rw0), logit(ro0)])
        r = minimize(nl, x0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-4, "maxiter": 600})
        return unpack(r.x)

    def forecast_weights(self, name, hp, p, t_fix, s_fix):
        """Conditional mean weights and sd of the quality at time (t_fix, s_fix) given the player's observed blocks."""
        tb = self.seasonal[name]; sl = tb.slice(p)
        prior_var = hp[name][0] ** 2 + hp[name][1] ** 2
        if sl.stop == sl.start:
            return None, np.sqrt(prior_var)
        A = self.player_cov(name, hp, p)
        c = time_cov(hp[name], np.array([t_fix]), np.array([s_fix]), tb.time[sl], tb.season[sl])[0]
        w = np.linalg.solve(A, c)
        var = prior_var - c @ w
        return w, np.sqrt(max(var, 0.0))
