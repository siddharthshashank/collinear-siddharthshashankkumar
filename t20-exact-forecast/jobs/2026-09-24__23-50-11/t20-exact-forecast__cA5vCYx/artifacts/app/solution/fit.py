"""Hierarchical fit of the engine's ball model to a league's history.

Every hidden number in engine.model.SkillBook is a scalar that moves the six outcome logits along a fixed public
direction, so the whole thing is a multinomial logistic regression with a sparse design matrix per direction and
Gaussian (ridge) priors on every block. Prior variances are estimated by Laplace-EM. The result is a MAP estimate with
a Gaussian (Laplace) posterior, from which forecasts draw skill books.
"""
import numpy as np
import scipy.sparse as sp
from scipy.optimize import minimize
from scipy.linalg import cho_factor, cho_solve

try:
    from engine.model import PACE, SPIN, load_public_model
except ImportError:  # the engine may also live inside a `league` package
    from league.engine.model import PACE, SPIN, load_public_model


class Blocks:
    """Registers named parameter blocks and the sparse design entries that connect balls to them."""

    def __init__(self, n_balls):
        self.n = n_balls
        self.size = 0
        self.blocks = {}
        self.entries = {}  # direction name -> (rows, cols, vals)

    def add(self, name, size):
        self.blocks[name] = (self.size, size)
        self.size += size
        return self.blocks[name]

    def index(self, name, offset):
        start, size = self.blocks[name]
        return start + np.asarray(offset)

    def design(self, direction, rows, cols, vals=None):
        if vals is None:
            vals = np.ones(len(rows))
        r, c, v = self.entries.setdefault(direction, ([], [], []))
        r.append(np.asarray(rows)); c.append(np.asarray(cols)); v.append(np.asarray(vals, float))

    def matrices(self):
        out = {}
        for d, (r, c, v) in self.entries.items():
            X = sp.coo_matrix((np.concatenate(v), (np.concatenate(r), np.concatenate(c))), shape=(self.n, self.size)).tocsr()
            X.sum_duplicates()
            out[d] = X
        return out


class LeagueFit:
    def __init__(self, history, seasons=None, model=None):
        self.model = model or load_public_model()
        self.h = history
        self.S = int(history.seasons if seasons is None else seasons)
        self.P = len(history.players.role)
        self.V = len(history.venues.pitch)
        self._build()

    # ------------------------------------------------------------------ design
    def _build(self):
        h, m = self.h, self.model
        b = h.balls
        n = len(b)
        over = b.over.to_numpy(); ballno = over * 6 + b.ball.to_numpy()
        pos = b.position.to_numpy(); wk = b.wickets_before.to_numpy(); runs = b.runs_before.to_numpy()
        chasing = (b.innings.to_numpy() == 2).astype(float)
        target = b.target.to_numpy()
        need = np.clip(target - runs, 1, None) / ((120 - ballno) / 6)
        pressure = np.where(chasing > 0, np.clip(np.log(need / m.cal.par_rate[over]), -1.0, 1.2), 0.0)
        self.base = m.situation(over, pos, wk, chasing, pressure)  # (n, 6) public part
        self.y = b.outcome.to_numpy()
        bat = b.batter.to_numpy(); bowl = b.bowler.to_numpy(); ven = b.venue.to_numpy()
        season = b.season.to_numpy(); match = b.match.to_numpy()
        self.match_ids = np.unique(match)
        match_idx = np.searchsorted(self.match_ids, match)
        self.M = len(self.match_ids)
        team = b.batting_team.to_numpy()
        home = (h.venues.home_team[ven] == team).astype(float)
        hand = h.players.hand[bat]; how = h.players.style[bowl]; pitch = h.venues.pitch[ven]
        P, V, S = self.P, self.V, self.S
        self.bowlers = np.unique(bowl)
        self.n_bowl = len(self.bowlers)
        bowl_idx = np.searchsorted(self.bowlers, bowl)
        self.match_season = np.zeros(self.M, int); self.match_season[match_idx] = season

        B = Blocks(n)
        B.add("style", P);           B.design("bat_style", np.arange(n), B.index("style", bat))
        B.add("q", P * S);           B.design("bat_quality", np.arange(n), B.index("q", bat * S + season))
        B.add("split", P);           B.design("bat_quality", np.arange(n), B.index("split", bat), np.where(how == PACE, 0.5, -0.5))
        B.add("kind", self.n_bowl);  B.design("bowl_type", np.arange(n), B.index("kind", bowl_idx))
        B.add("bq", self.n_bowl * S); B.design("bowl_quality", np.arange(n), B.index("bq", bowl_idx * S + season))
        B.add("level", V);           B.design("conditions", np.arange(n), B.index("level", ven))
        B.add("era", S);             B.design("conditions", np.arange(n), B.index("era", season))
        B.add("day", self.M);        B.design("conditions", np.arange(n), B.index("day", match_idx))
        B.add("chase", V);           B.design("conditions", np.arange(n), B.index("chase", ven), chasing)
        B.add("wear", 1);            B.design("conditions", np.arange(n), B.index("wear", np.zeros(n, int)), -chasing)
        B.add("aff", P * V);         B.design("conditions", np.arange(n), B.index("aff", bat * V + ven))
        B.add("home", 1);            B.design("conditions", np.arange(n), B.index("home", np.zeros(n, int)), home)
        B.add("type", 4);            B.design("conditions", np.arange(n), B.index("type", hand * 2 + how))
        B.add("pitch", 6);           B.design("conditions", np.arange(n), B.index("pitch", how * 3 + pitch), -np.ones(n))
        self.B = B
        self.X = B.matrices()
        self.dirs = {k: m.cal.directions[k] for k in self.X}
        self.K = B.size
        self.onehot = np.zeros((n, 6)); self.onehot[np.arange(n), self.y] = 1.0
        # starting prior variances, refined by EM; these are the converged values on the league shipped with the task
        self.hyper = dict(style=0.142, split=0.03, kind=0.022, level=0.002, era=0.007, day=0.08, chase=0.002, wear=1.0,
                          aff=0.01, home=1.0, type=0.001, pitch=0.001)
        # talent + AR(1) form structure of season-level quality, shared drift rate for batters and bowlers
        self.ar = dict(tau_q=0.005, f_q=0.039, tau_b=0.011, f_b=0.025, rho=0.56)
        self.prior_moments = None  # optional (C_q, n_q, C_b, n_b) from another league of the same kind, pooled in the M step
        self.prior_weight = 1.0
        self.kind_mean = np.array([-0.2, 0.12])  # prior mean of bowler kind by public style, refined by EM
        self.bowler_style = h.players.style[self.bowlers]

    @property
    def Sigma_q(self):
        return season_cov(self.ar["tau_q"], self.ar["f_q"], self.ar["rho"], self.S)

    @property
    def Sigma_bq(self):
        return season_cov(self.ar["tau_b"], self.ar["f_b"], self.ar["rho"], self.S)

    # ------------------------------------------------------------------ prior
    def _prior(self):
        """Sparse precision matrix and prior mean for the current hyperparameters."""
        B, S = self.B, self.S
        diag = np.zeros(self.K)
        for name, var in self.hyper.items():
            start, size = B.blocks[name]
            diag[start:start + size] = 1.0 / var
        Lam = sp.diags(diag).tolil()
        for name, Sig, count in (("q", self.Sigma_q, self.P), ("bq", self.Sigma_bq, self.n_bowl)):
            start, size = B.blocks[name]
            inv = np.linalg.inv(Sig)
            rows = start + np.repeat(np.arange(count) * S, S * S) + np.tile(np.repeat(np.arange(S), S), count)
            cols = start + np.repeat(np.arange(count) * S, S * S) + np.tile(np.tile(np.arange(S), S), count)
            blk = sp.coo_matrix((np.tile(inv.ravel(), count), (rows, cols)), shape=(self.K, self.K))
            Lam = Lam + blk.tolil()
        mean = np.zeros(self.K)
        start, size = B.blocks["kind"]
        mean[start:start + size] = self.kind_mean[self.bowler_style]
        return Lam.tocsr(), mean

    # ------------------------------------------------------------------ likelihood
    def logits(self, theta):
        z = self.base.copy()
        for d, X in self.X.items():
            z += np.outer(X @ theta, self.dirs[d])
        return z

    def probs(self, theta):
        z = self.logits(theta)
        p = np.exp(z - z.max(axis=1, keepdims=True))
        return p / p.sum(axis=1, keepdims=True)

    def objective(self, theta, Lam, mean):
        p = self.probs(theta)
        nll = -np.log(p[np.arange(len(self.y)), self.y] + 1e-300).sum()
        R = self.onehot - p
        g = np.zeros(self.K)
        for d, X in self.X.items():
            g -= X.T @ (R @ self.dirs[d])
        dtheta = theta - mean
        Lt = Lam @ dtheta
        return nll + 0.5 * dtheta @ Lt, g + Lt

    def fit(self, theta0=None, maxiter=500):
        Lam, mean = self._prior()
        x0 = mean.copy() if theta0 is None else theta0
        res = minimize(self.objective, x0, args=(Lam, mean), jac=True, method="L-BFGS-B", options=dict(maxiter=maxiter, maxcor=30))
        self.theta = res.x
        self.Lam, self.mean = Lam, mean
        return res

    def hessian(self, theta=None):
        theta = self.theta if theta is None else theta
        p = self.probs(theta)
        names = list(self.X)
        H = self.Lam.toarray()
        pd_ = {d: p @ self.dirs[d] for d in names}
        for i, a in enumerate(names):
            for b_ in names[i:]:
                w = p @ (self.dirs[a] * self.dirs[b_]) - pd_[a] * pd_[b_]
                blk = (self.X[a].T @ sp.diags(w) @ self.X[b_]).toarray()
                H += blk if a == b_ else blk + blk.T
        return H

    def laplace(self):
        H = self.hessian()
        c, low = cho_factor(H, lower=True, overwrite_a=True)
        del H
        self.cov = cho_solve((c, low), np.eye(self.K))
        del c
        return self.cov

    # ------------------------------------------------------------------ accessors
    def block(self, name, arr=None):
        arr = self.theta if arr is None else arr
        start, size = self.B.blocks[name]
        return arr[start:start + size]

    def block_cov(self, name):
        start, size = self.B.blocks[name]
        return self.cov[start:start + size, start:start + size]

    # ------------------------------------------------------------------ EM
    def em_step(self):
        """Update prior variances from posterior second moments (one M step of Laplace-EM)."""
        B, S = self.B, self.S
        var = np.diag(self.cov)
        new = {}
        for name in self.hyper:
            if name in ("wear", "home"):
                continue  # single free parameters keep a broad prior
            start, size = B.blocks[name]
            th = self.theta[start:start + size] - self.mean[start:start + size]
            new[name] = float(np.mean(th ** 2 + var[start:start + size]))
        self.hyper.update(new)
        moments = {}
        for name, count in (("q", self.P), ("bq", self.n_bowl)):
            start, size = B.blocks[name]
            th = self.theta[start:start + size].reshape(count, S)
            C = self.cov[start:start + size, start:start + size]
            Cb = np.array([C[i * S:(i + 1) * S, i * S:(i + 1) * S] for i in range(count)])
            moments[name] = (np.einsum("is,it->st", th, th) + Cb.sum(0)) / count
        self.moments = moments
        terms = [(moments["q"], self.P, "q"), (moments["bq"], self.n_bowl, "b")]
        if self.prior_moments is not None:
            Cq, nq, Cb, nb = self.prior_moments
            terms += [(Cq, nq * self.prior_weight, "q"), (Cb, nb * self.prior_weight, "b")]
        self.ar = fit_ar(terms, self.S, self.ar)
        k = self.block("kind")
        for s in (PACE, SPIN):
            sel = self.bowler_style == s
            self.kind_mean[s] = k[sel].mean() if sel.any() else 0.0
        start, size = B.blocks["kind"]
        th = k - self.kind_mean[self.bowler_style]
        self.hyper["kind"] = float(np.mean(th ** 2 + var[start:start + size]))
        return dict(self.hyper, ar=dict(self.ar), kind_mean=self.kind_mean.copy())


def season_cov(tau2, f2, rho, S):
    lag = np.abs(np.arange(S)[:, None] - np.arange(S)[None, :])
    return tau2 + f2 * rho ** lag


def fit_ar(terms, S, start):
    """Maximum likelihood fit of (talent variance, form variance, drift) to posterior second-moment matrices.

    terms: list of (C, n, group) where C is a mean second-moment matrix over n players and group is "q" or "b".
    The drift rho is shared by both groups. Minimises n * (log det Sigma + tr(Sigma^-1 C)) summed over terms.
    """
    def unpack(x):
        x = np.clip(x, -12, 12)
        return dict(tau_q=np.exp(x[0]), f_q=np.exp(x[1]), tau_b=np.exp(x[2]), f_b=np.exp(x[3]), rho=0.995 / (1 + np.exp(-x[4])))

    def obj(x):
        a = unpack(x)
        tot = 0.0
        for C, n, g in terms:
            Sig = season_cov(a["tau_q" if g == "q" else "tau_b"], a["f_q" if g == "q" else "f_b"], a["rho"], S) + 1e-7 * np.eye(S)
            sign, logdet = np.linalg.slogdet(Sig)
            tot += n * (logdet + np.trace(np.linalg.solve(Sig, C)))
        return tot

    x0 = np.array([np.log(start["tau_q"]), np.log(start["f_q"]), np.log(start["tau_b"]), np.log(start["f_b"]), np.log(start["rho"] / (1 - start["rho"]))])
    best = None
    for init in (x0, x0 + np.array([0, 0, 0, 0, 2.0]), x0 + np.array([0, 0, 0, 0, -2.0])):
        res = minimize(obj, init, method="Nelder-Mead", options=dict(maxiter=4000, xatol=1e-6, fatol=1e-8))
        if best is None or res.fun < best.fun:
            best = res
    a = unpack(best.x)
    a["rho"] = float(np.clip(a["rho"], 1e-4, 0.999))
    return a
