"""Regularised multinomial-logit fit of the hidden skill book from ball-by-ball history."""
import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.optimize import minimize
from scipy.linalg import cho_factor, cho_solve, solve_triangular

DIRS = ["bat_style", "bat_quality", "bowl_type", "bowl_quality", "conditions"]


class Design:
    """Sparse design: every hidden number is a scalar along one of the five public directions."""

    def __init__(self, model, hist, periods_per_season=1, drop_matches=None):
        self.model = model
        b = hist.balls
        if drop_matches is not None:
            b = b[~b.match.isin(drop_matches)]
        self.balls = b = b.reset_index(drop=True)
        self.n = n = len(b)
        self.np_ = P = len(hist.players.role)
        self.nv = V = len(hist.venues.pitch)
        self.ns = S = hist.seasons
        self.pps = K = periods_per_season
        self.T = T = S * K + 1                     # + one period for the fixtures
        m = model
        ballidx = b.over.to_numpy() * 6 + b.ball.to_numpy()
        chasing = (b.innings.to_numpy() == 2).astype(float)
        pressure = np.where(chasing > 0, m.pressure(b.target.to_numpy(), b.runs_before.to_numpy(), ballidx), 0.0)
        self.pub = m.situation(b.over.to_numpy(), b.position.to_numpy(), b.wickets_before.to_numpy(), chasing, pressure)
        self.y = b.outcome.to_numpy()
        self.Y = np.eye(6)[self.y]
        self.D = np.array([m.cal.directions[k] for k in DIRS])
        # match -> week within season, to place a ball in its period
        matches = hist.matches.set_index("match")
        week = matches.loc[b.match.to_numpy(), "week"].to_numpy()
        season = b.season.to_numpy()
        weeks_per_season = int(hist.matches.week.max()) + 1
        self.weeks_per_season = weeks_per_season
        period = season * K + np.minimum((week * K) // weeks_per_season, K - 1)
        self.period = period
        bat, bowl, venue, match = b.batter.to_numpy(), b.bowler.to_numpy(), b.venue.to_numpy(), b.match.to_numpy()
        hand, style, pitch = hist.players.hand, hist.players.style, hist.venues.pitch
        self.home_team = hist.venues.home_team
        at_home = (self.home_team[venue] == b.batting_team.to_numpy()).astype(float)
        bstyle = style[bowl]
        sign = np.where(bstyle == 0, 0.5, -0.5)
        n_matches = int(hist.matches.match.max()) + 1
        self.n_matches = n_matches
        # blocks: name -> (size, direction)
        self.blocks = {}
        cols, vals, rows = [], [], []
        ar = np.arange(n)

        self.ball_idx, self.ball_coef, self.ball_dir = [], [], []

        def add(name, size, d, idx=None, coef=None):
            start = sum(s for s, _ in self.blocks.values())
            self.blocks[name] = (size, d)
            if idx is not None:
                c = np.ones(n) if coef is None else np.asarray(coef, float)
                rows.append(ar); cols.append(start + idx); vals.append(c)
                self.ball_idx.append(start + idx); self.ball_coef.append(c); self.ball_dir.append(d)

        add("style", P, 0, bat)
        add("qual", P * T, 1, bat * T + period)
        add("split", P, 1, bat, sign)
        add("kindmean", 2, 2, bstyle)
        add("kind", P, 2, bowl)
        add("bowlq", P * T, 3, bowl * T + period)
        add("venue", V, 4, venue)
        add("era", S + 1, 4, season)
        add("day", n_matches, 4, match)
        add("dew", V, 4, venue, chasing)
        add("wear", 1, 4, np.zeros(n, int), -chasing)
        add("home", 1, 4, np.zeros(n, int), at_home)
        add("aff", P * V, 4, bat * V + venue)
        add("type", 4, 4, hand[bat] * 2 + bstyle)
        add("pitch", 6, 4, bstyle * 3 + pitch[venue], -np.ones(n))
        self.nparam = sum(s for s, _ in self.blocks.values())
        self.X = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(n, self.nparam))
        self.XT = self.X.T.tocsr()
        self.dir_of = np.concatenate([np.full(s, d) for s, d in self.blocks.values()])
        self.onehot = np.eye(5)[self.dir_of]            # nparam x 5
        self.offsets = {}
        start = 0
        for k, (s, d) in self.blocks.items():
            self.offsets[k] = start; start += s
        self.is_bowler = np.zeros(P, bool); self.is_bowler[np.unique(bowl)] = True

    def block(self, theta, name):
        s, _ = self.blocks[name]
        o = self.offsets[name]
        return theta[o:o + s]

    def logits(self, theta):
        S = self.X @ (theta[:, None] * self.onehot)          # n x 5
        return self.pub + S @ self.D

    def nll_grad(self, theta):
        z = self.logits(theta)
        z = z - z.max(axis=1, keepdims=True)
        p = np.exp(z); p /= p.sum(axis=1, keepdims=True)
        nll = -np.log(p[np.arange(self.n), self.y]).sum()
        G = (p - self.Y) @ self.D.T                           # n x 5
        g = (self.XT @ G)                                     # nparam x 5
        return nll, g[np.arange(self.nparam), self.dir_of]


class Prior:
    """Gaussian prior. iid blocks with sd; skill blocks with a per-player T x T covariance (talent + OU form)."""

    def __init__(self, design, hyper):
        self.d = design
        self.h = hyper
        T, K = design.T, design.pps
        self.prec = np.zeros(design.nparam)   # diagonal precision for iid blocks (0 = flat)
        h = hyper
        for name, sd in [("style", h["sd_style"]), ("split", h["sd_split"]), ("kind", h["sd_kind"]), ("venue", h["sd_venue"]),
                         ("day", h["sd_day"]), ("dew", h["sd_dew"]), ("aff", h["sd_aff"]), ("type", h["sd_type"]), ("pitch", h["sd_type"]),
                         ("era", h["sd_era"]), ("wear", h["sd_wear"]), ("home", h["sd_home"])]:
            o, (s, _) = design.offsets[name], design.blocks[name]
            self.prec[o:o + s] = 1.0 / sd ** 2
        # kindmean flat. skill blocks
        self.Q = {}
        for name, tal, frm, rw, rb in [("qual", h["sd_talent"], h["sd_form"], h["rho_within"], h["rho_between"]),
                                       ("bowlq", h["sd_btalent"], h["sd_bform"], h["rho_bwithin"], h["rho_bbetween"])]:
            cov = self.skill_cov(T, K, tal, frm, rw, rb)
            self.Q[name] = np.linalg.inv(cov)

    @staticmethod
    def skill_cov(T, K, tal, frm, rw, rb):
        # correlation between period i and j: product of step correlations along the chain
        step = np.array([rb if (t + 1) % K == 0 else rw for t in range(T - 1)])
        logstep = np.log(np.maximum(step, 1e-12))
        cum = np.concatenate([[0.0], np.cumsum(logstep)])
        corr = np.exp(-np.abs(cum[:, None] - cum[None, :]))
        return tal ** 2 + frm ** 2 * corr

    def value_grad(self, theta):
        v = 0.5 * np.sum(self.prec * theta ** 2)
        g = self.prec * theta
        for name, Q in self.Q.items():
            o, (s, _) = self.d.offsets[name], self.d.blocks[name]
            th = theta[o:o + s].reshape(-1, self.d.T)
            gq = th @ Q
            v += 0.5 * np.sum(gq * th)
            g[o:o + s] = gq.ravel()
        return v, g


def fit_map(design, prior, theta0=None, maxiter=500, tol=1e-6):
    def f(th):
        a, ga = design.nll_grad(th)
        b, gb = prior.value_grad(th)
        return a + b, ga + gb
    x0 = np.zeros(design.nparam) if theta0 is None else theta0
    res = minimize(f, x0, jac=True, method="L-BFGS-B", options={"maxiter": maxiter, "maxcor": 30, "ftol": tol * 1e-3, "gtol": 1e-5})
    return res.x, res


def default_hyper():
    return dict(sd_style=0.3, sd_split=0.15, sd_kind=0.3, sd_venue=0.2, sd_day=0.2, sd_dew=0.15, sd_aff=0.1, sd_type=0.1,
                sd_era=0.3, sd_wear=0.3, sd_home=0.3,
                sd_talent=0.3, sd_form=0.15, rho_within=0.9, rho_between=0.6,
                sd_btalent=0.3, sd_bform=0.15, rho_bwithin=0.9, rho_bbetween=0.6)


def probs(design, theta):
    z = design.logits(theta)
    z = z - z.max(axis=1, keepdims=True)
    p = np.exp(z); p /= p.sum(axis=1, keepdims=True)
    return p


def ball_weights(design, p):
    # per ball 5x5 weight: D (diag p - p p') D'
    d = design
    DP = p[:, None, :] * d.D[None, :, :]                 # n x 5 x 6  (D_d * p)
    Dp = p @ d.D.T                                        # n x 5  : D p
    return np.einsum('nij,kj->nik', DP, d.D) - Dp[:, :, None] * Dp[:, None, :]   # n x 5 x 5


def hessian_data(design, theta, p=None):
    """Dense Hessian of the negative log-likelihood, nparam x nparam (fast bincount version)."""
    d = design
    if p is None:
        p = probs(d, theta)
    W = ball_weights(d, p)
    nb = len(d.ball_idx)
    flat, wts = [], []
    for a in range(nb):
        for b in range(nb):
            flat.append(d.ball_idx[a] * d.nparam + d.ball_idx[b])
            wts.append(d.ball_coef[a] * d.ball_coef[b] * W[:, d.ball_dir[a], d.ball_dir[b]])
    H = np.bincount(np.concatenate(flat), weights=np.concatenate(wts), minlength=d.nparam * d.nparam).reshape(d.nparam, d.nparam)
    return H


def hessian_data_slow(design, theta, p=None):
    d = design
    if p is None:
        p = probs(d, theta)
    W = ball_weights(d, p)
    H = np.zeros((d.nparam, d.nparam))
    cols = [np.where(d.dir_of == k)[0] for k in range(5)]
    Xd = [d.X[:, c].tocsc() for c in cols]
    for a in range(5):
        XaT = Xd[a].T.tocsr()
        for b in range(a, 5):
            M = (XaT.multiply(W[:, a, b][None, :]) @ Xd[b]).toarray()
            H[np.ix_(cols[a], cols[b])] += M
            if b != a:
                H[np.ix_(cols[b], cols[a])] += M.T
    return H


def hessian_prior(design, prior):
    H = np.diag(prior.prec.copy())
    for name, Q in prior.Q.items():
        o, (s, _) = design.offsets[name], design.blocks[name]
        P = s // design.T
        for i in range(P):
            H[o + i * design.T:o + (i + 1) * design.T, o + i * design.T:o + (i + 1) * design.T] += Q
    return H


def logdet_prior(design, prior):
    """log det of the prior precision over the non-flat parameters (constant otherwise)."""
    v = np.sum(np.log(prior.prec[prior.prec > 0]))
    for name, Q in prior.Q.items():
        s = design.blocks[name][0]
        v += (s // design.T) * np.linalg.slogdet(Q)[1]
    return v


def fit_newton(design, prior, theta0=None, maxiter=30, tol=1e-6, verbose=False):
    """Newton's method with backtracking on the convex MAP objective."""
    th = np.zeros(design.nparam) if theta0 is None else theta0.copy()
    Hp = hessian_prior(design, prior)

    def obj(t):
        a, ga = design.nll_grad(t); b, gb = prior.value_grad(t)
        return a + b, ga + gb
    f, g = obj(th)
    for it in range(maxiter):
        H = hessian_data(design, th) + Hp
        try:
            cf = cho_factor(H, lower=True, check_finite=False)
        except np.linalg.LinAlgError:
            H += 1e-6 * np.eye(len(H)); cf = cho_factor(H, lower=True, check_finite=False)
        step = -cho_solve(cf, g, check_finite=False)
        dec = -g @ step
        if verbose:
            print(it, f, dec)
        if dec < tol:
            break
        a = 1.0
        while True:
            f2, g2 = obj(th + a * step)
            if f2 <= f - 0.25 * a * dec or a < 1e-4:
                break
            a *= 0.5
        th, f, g = th + a * step, f2, g2
    return th, f


def laplace_neg_evidence(design, prior, theta):
    """-log marginal likelihood (Laplace), up to constants: nll + prior + 0.5 logdet H - 0.5 logdet prior."""
    H = hessian_data(design, theta) + hessian_prior(design, prior)
    cf = cho_factor(H, lower=True, check_finite=False)
    ld = 2 * np.sum(np.log(np.abs(np.diag(cf[0]))))
    a, _ = design.nll_grad(theta); b, _ = prior.value_grad(theta)
    return a + b + 0.5 * ld - 0.5 * logdet_prior(design, prior)
