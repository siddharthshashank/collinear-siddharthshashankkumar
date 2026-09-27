"""Empirical Bayes for the prior scales: EM with the Laplace posterior as the E-step."""
import numpy as np
from scipy.optimize import minimize
from fitter import ar_covariance

SD_FLOOR = 0.003

IID = {"style": "sd_style", "split": "sd_split", "kind": "sd_kind", "venue": "sd_venue", "chase": "sd_chase",
       "day": "sd_day", "aff": "sd_aff", "type": "sd_type", "pitch": "sd_pitch"}


def _ar_mstep(E, n_units, transitions_fn, start, fixed_rho=None):
    """Maximizes n*(-0.5 logdet C) - 0.5 tr(C^-1 E) over (sd_talent, sd_form, rho_w, rho_o)."""
    def unpack(x):
        sdt, sdf = np.exp(x[0]), np.exp(x[1])
        rw, ro = 1 / (1 + np.exp(-x[2])), 1 / (1 + np.exp(-x[3]))
        return sdt, sdf, rw, ro

    def nll(x):
        sdt, sdf, rw, ro = unpack(x)
        C = ar_covariance(transitions_fn(rw, ro), sdt, sdf)
        try:
            Ci = np.linalg.inv(C)
            s, ld = np.linalg.slogdet(C)
        except np.linalg.LinAlgError:
            return 1e30
        if s <= 0:
            return 1e30
        return 0.5 * n_units * ld + 0.5 * np.sum(Ci * E)

    x0 = np.array([np.log(start[0]), np.log(start[1]), np.log(start[2] / (1 - start[2])), np.log(start[3] / (1 - start[3]))])
    res = minimize(nll, x0, method="Nelder-Mead", options=dict(xatol=1e-4, fatol=1e-6, maxiter=4000))
    return unpack(res.x)


def em_step(spec, Linv, theta, update=None, verbose=False):
    """One M-step given Linv (posterior covariance = Linv^T Linv) and mode theta. Returns new hyper dict."""
    h = dict(spec.h)
    des = spec.des
    diag = (Linv ** 2).sum(0)

    def block_cov(b, K1):
        n_units = b.size // K1
        Lb = Linv[:, b.start:b.stop].reshape(Linv.shape[0], n_units, K1)
        return np.einsum("pik,pil->kl", Lb, Lb)      # summed over units
    update = set(update) if update is not None else set(IID.values()) | {"ar_bat", "ar_bowl", "sd_era"}
    for name, key in IID.items():
        if key not in update:
            continue
        b = des.blocks[name]
        s2 = (theta[b.sl] ** 2 + diag[b.sl]).sum() / b.size
        h[key] = float(max(np.sqrt(s2), SD_FLOOR))
    K1 = spec.K + 1
    for name, key, keys in (("q", "ar_bat", ("sd_talent", "sd_form", "rho_w", "rho_o")), ("r", "ar_bowl", ("sd_btalent", "sd_bform", "rho_bw", "rho_bo"))):
        if key not in update:
            continue
        b = des.blocks[name]
        n_units = b.size // K1
        th = theta[b.sl].reshape(n_units, K1)
        E = th.T @ th + block_cov(b, K1)
        start = tuple(h[k] for k in keys)
        vals = _ar_mstep(E, n_units, spec.transitions, start)
        for k, v in zip(keys, vals):
            h[k] = float(np.clip(v, 0.01, 0.995)) if k.startswith("rho") else float(max(v, SD_FLOOR))
    if "sd_era" in update:
        b = des.blocks["era"]
        S1 = b.size
        C0 = np.array([[min(i, j) + 1 for j in range(S1)] for i in range(S1)], float)
        E = np.outer(theta[b.sl], theta[b.sl]) + block_cov(b, S1)
        h["sd_era"] = float(max(np.sqrt(np.sum(np.linalg.inv(C0) * E) / S1), SD_FLOOR))
    return h


def run_em(spec, iters=15, update=None, verbose=True, theta=None, tol=0.01, budget=None):
    import time
    t0 = time.time()
    F = spec.fitter
    hist = []
    for it in range(iters):
        if budget is not None and time.time() - t0 > budget:
            break
        theta = F.fit(theta, refactor=(theta is None))
        ev = F.evidence()
        Linv = F.posterior_linv()
        h_new = em_step(spec, Linv, theta, update)
        rel = max(abs(np.log(h_new[k] / spec.h[k])) for k in h_new if k in spec.h and not k.startswith("rho") and k != "sd_fixed")
        hist.append((ev, dict(spec.h)))
        if verbose:
            print(f"EM {it}: evidence={ev:.2f} maxrel={rel:.3f}", {k: round(v, 4) for k, v in h_new.items() if k != "sd_fixed"}, flush=True)
        spec.set_hyper(h_new)
        if rel < tol:
            break
    theta = F.fit(theta)
    return spec.h, theta, hist
