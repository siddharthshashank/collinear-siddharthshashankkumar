"""Empirical Bayes by L-BFGS on the Laplace evidence; gradient from the EM Q-function identity."""
import time
import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.optimize import minimize
from fitter import Prior, fit_newton, hessian_data, hessian_prior, logdet_prior

IID_BLOCKS = {"style": "sd_style", "split": "sd_split", "kind": "sd_kind", "venue": "sd_venue", "day": "sd_day",
              "dew": "sd_dew", "aff": "sd_aff", "type": "sd_type"}
SKILL_BLOCKS = {"qual": ("sd_talent", "sd_form", "rho_within", "rho_between"),
                "bowlq": ("sd_btalent", "sd_bform", "rho_bwithin", "rho_bbetween")}


def to_x(h, keys):
    return np.array([np.log(h[k]) if k.startswith("sd") else np.log(h[k] / (1 - h[k])) for k in keys])


def from_x(x, keys, base):
    h = dict(base)
    for k, v in zip(keys, x):
        h[k] = float(np.exp(v)) if k.startswith("sd") else float(1 / (1 + np.exp(-v)))
    return h


class Evidence:
    def __init__(self, design, base, keys=None, theta0=None, verbose=False, newton_iters=6, penalty=None):
        self.d = design
        self.base = dict(base)
        # penalty: {key: width} gaussian penalty on the transformed coordinate, centred at the base value
        self.penalty = penalty or {}
        if keys is None:
            keys = list(IID_BLOCKS.values()) + [k for blk in SKILL_BLOCKS.values() for k in blk]
            if design.pps == 1:
                keys = [k for k in keys if k not in ("rho_within", "rho_bwithin")]
        self.keys = keys
        self.theta = theta0
        self.verbose = verbose
        self.n = 0
        self.t0 = time.time()
        self.best = (np.inf, None, None)
        self.newton_iters = newton_iters
        d = design
        self.has_data = np.asarray(np.abs(d.X).sum(axis=0)).ravel() > 0
        self.cache = {}

    def __call__(self, x):
        d, T, K = self.d, self.d.T, self.d.pps
        h = from_x(x, self.keys, self.base)
        pr = Prior(d, h)
        th, f = fit_newton(d, pr, theta0=self.theta, maxiter=self.newton_iters, tol=1e-6)
        self.theta = th
        H = hessian_data(d, th) + hessian_prior(d, pr)
        cf = cho_factor(H, lower=True, check_finite=False)
        ld = 2 * np.sum(np.log(np.abs(np.diag(cf[0]))))
        ev = f + 0.5 * ld - 0.5 * logdet_prior(d, pr)          # negative log evidence
        C = cho_solve(cf, np.eye(d.nparam), check_finite=False)
        var = np.diag(C)
        # gradient of the negative Q-function wrt each hyperparameter (in transformed coordinates)
        g = {}
        for blk, key in IID_BLOCKS.items():
            if key not in self.keys:
                continue
            o, (s, _) = d.offsets[blk], d.blocks[blk]
            sd = h[key]
            m2 = np.sum(th[o:o + s] ** 2 + var[o:o + s])
            # -Q = s*log(sd) + m2/(2 sd^2) ; d/dlog(sd) = s - m2/sd^2
            g[key] = s - m2 / sd ** 2
        for blk, keys in SKILL_BLOCKS.items():
            o, (s, _) = d.offsets[blk], d.blocks[blk]
            P = s // T
            Q = th[o:o + s].reshape(P, T)
            M = np.zeros((T, T))
            for i in range(P):
                sl = slice(o + i * T, o + (i + 1) * T)
                M += np.outer(Q[i], Q[i]) + C[sl, sl]

            def negQ(vals):
                S = Prior.skill_cov(T, K, *vals)
                cfS = cho_factor(S)
                return 0.5 * P * 2 * np.sum(np.log(np.diag(cfS[0]))) + 0.5 * np.trace(cho_solve(cfS, M))
            vals = [h[k] for k in keys]
            for j, k in enumerate(keys):
                if k not in self.keys:
                    continue
                v = list(vals)
                eps = 1e-5
                if k.startswith("sd"):
                    v[j] = vals[j] * np.exp(eps); fp = negQ(v)
                    v[j] = vals[j] * np.exp(-eps); fm = negQ(v)
                else:
                    r = vals[j]; z = np.log(r / (1 - r))
                    v[j] = 1 / (1 + np.exp(-(z + eps))); fp = negQ(v)
                    v[j] = 1 / (1 + np.exp(-(z - eps))); fm = negQ(v)
                g[k] = (fp - fm) / (2 * eps)
        grad = np.array([g[k] for k in self.keys])
        if self.penalty:
            x0 = to_x(self.base, self.keys)
            for j, k in enumerate(self.keys):
                w = self.penalty.get(k)
                if w:
                    ev += 0.5 * ((x[j] - x0[j]) / w) ** 2
                    grad[j] += (x[j] - x0[j]) / w ** 2
        self.n += 1
        if ev < self.best[0]:
            self.best = (ev, h, th.copy())
        if self.verbose:
            print(self.n, round(ev, 2), round(time.time() - self.t0, 1), {k: round(h[k], 4) for k in self.keys}, "|g|", round(np.abs(grad).max(), 2), flush=True)
        return ev, grad


def run_eb_grad(design, base, keys=None, theta0=None, maxiter=40, time_budget=None, verbose=False, penalty=None, max_evals=None):
    """max_evals gives a deterministic stopping rule; time_budget is only an emergency brake."""
    E = Evidence(design, base, keys, theta0, verbose, penalty=penalty)
    x0 = to_x(E.base, E.keys)
    lb = np.where([k.startswith("sd") for k in E.keys], np.log(1e-3), -6.0)
    ub = np.where([k.startswith("sd") for k in E.keys], np.log(3.0), 6.0)

    class Stop(Exception):
        pass

    def wrapped(x):
        if max_evals is not None and E.n >= max_evals:
            raise Stop()
        if time_budget is not None and time.time() - E.t0 > time_budget:
            raise Stop()
        return E(x)
    try:
        minimize(wrapped, x0, jac=True, method="L-BFGS-B", bounds=list(zip(lb, ub)),
                 options={"maxiter": maxiter, "ftol": 1e-10, "gtol": 0.3})
    except Stop:
        pass
    ev, h, th = E.best
    return h, th, ev
