"""Penalized multinomial-logit fit of the engine's ball model (v2: general quality time series)."""
import numpy as np, pandas as pd, scipy.sparse as sp, scipy.linalg as sla
from engine.model import load_public_model, PACE, SPIN

class Blocks:
    def __init__(self): self.idx = {}; self.P = 0
    def add(self, name, size):
        r = np.arange(self.P, self.P + size); self.idx[name] = r; self.P += size; return r
    def __getitem__(self, k): return self.idx[k]

class Design:
    """period(season, week) -> integer period index in [0, T). Fixture period index is T (predicted by conditioning)."""
    def __init__(self, history, period=None, T=None):
        b = history.balls
        self.hist = history
        m = load_public_model(); self.model = m
        N = len(b); self.N = N
        over = b.over.to_numpy(); ballno = over * 6 + b.ball.to_numpy()
        chasing = (b.innings.to_numpy() == 2).astype(float)
        target = b.target.to_numpy(); runs = b.runs_before.to_numpy()
        pressure = np.where(chasing > 0, m.pressure(np.maximum(target, 1), runs, ballno), 0.0)
        self.z0 = m.situation(over, b.position.to_numpy(), b.wickets_before.to_numpy(), chasing, pressure)
        self.y = b.outcome.to_numpy()
        d = m.cal.directions
        self.D = np.stack([d["bat_style"], d["bat_quality"], d["bowl_type"], d["bowl_quality"], d["conditions"]])
        pl, ve = history.players, history.venues
        self.nP, self.nV = len(pl.role), len(ve.pitch)
        self.nS = int(history.seasons)
        matches = history.matches.set_index("match"); self.matches = matches
        season = b.season.to_numpy(); bat = b.batter.to_numpy(); bowl = b.bowler.to_numpy(); venue = b.venue.to_numpy()
        match = b.match.to_numpy(); team = b.batting_team.to_numpy()
        week = matches.week.reindex(match).to_numpy()
        if period is None: period = lambda s, w: s; T = self.nS
        per = period(season, week); self.T = T
        home_team = matches.home.reindex(match).to_numpy()
        at_home = (team == home_team).astype(float)
        hand = pl.hand[bat]; bstyle = pl.style[bowl]; pitch = ve.pitch[venue]
        sign = np.where(bstyle == PACE, 0.5, -0.5)
        self.bowls = np.zeros(self.nP, bool); self.bowls[np.unique(bowl)] = True
        B = Blocks(); self.B = B
        rows, cols, vals = [], [], []
        def put(k, params, coef=1.0):
            rows.append(k * N + np.arange(N)); cols.append(np.asarray(params)); vals.append(np.broadcast_to(np.asarray(coef, float), (N,)))
        nP, nV, nS = self.nP, self.nV, self.nS
        role = pl.role
        B.add("style", nP); B.add("style_mean", 3)
        put(0, B["style"][bat]); put(0, B["style_mean"][role[bat]])
        B.add("bat_q", nP * T); B.add("bat_mean", 3)
        put(1, B["bat_q"][bat * T + per]); put(1, B["bat_mean"][role[bat]])
        B.add("split", nP); put(1, B["split"][bat], sign)
        B.add("kind", nP); B.add("kind_mean", 2)
        put(2, B["kind"][bowl]); put(2, B["kind_mean"][bstyle])
        B.add("bowl_q", nP * T); B.add("bowl_mean", 3)
        put(3, B["bowl_q"][bowl * T + per]); put(3, B["bowl_mean"][role[bowl]])
        B.add("venue", nV); put(4, B["venue"][venue])
        B.add("era", nS); put(4, B["era"][season])
        nM = int(matches.index.max()) + 1; self.nM = nM
        B.add("day", nM); put(4, B["day"][match])
        B.add("chase", nV); B.add("chase_mean", 1)
        put(4, B["chase"][venue], chasing); put(4, B["chase_mean"][np.zeros(N, int)], chasing)
        B.add("affinity", nP * nV); put(4, B["affinity"][bat * nV + venue])
        B.add("home", 1); put(4, B["home"][np.zeros(N, int)], at_home)
        B.add("type", 4); put(4, B["type"][hand * 2 + bstyle])
        B.add("pitch", 6); put(4, B["pitch"][bstyle * 3 + pitch])
        self.P = B.P
        X = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(5 * N, self.P)).tocsr()
        self.X = X
        self.Xk = [X[k * N:(k + 1) * N] for k in range(5)]
        self.XkT = [x.T.tocsr() for x in self.Xk]

    def precision(self, hp):
        """hp: scalar sds for simple blocks; hp['bat_K'], hp['bowl_K'] are T x T prior covariances of the quality series."""
        B, nP, nS, nV, T = self.B, self.nP, self.nS, self.nV, self.T
        lam = np.full(self.P, 1e-4)
        for k in ("style", "split", "kind", "venue", "day", "chase", "affinity"):
            lam[B[k]] = 1 / hp[k] ** 2
        lam[B["type"][0]] = 1e6; lam[B["pitch"][[0, 1, 2, 3]]] = 1e6
        lam[B["type"][1:]] = 1 / hp["type"] ** 2; lam[B["pitch"][[4, 5]]] = 1 / hp["pitch"] ** 2
        lam[B["bat_q"]] = 0; lam[B["bowl_q"]] = 0
        rows = [np.arange(self.P)]; cols = [np.arange(self.P)]; vals = [lam]
        for name, K, mask in (("bat_q", hp["bat_K"], np.ones(nP, bool)), ("bowl_q", hp["bowl_K"], np.ones(nP, bool))):
            Q = np.linalg.inv(K)
            idx = B[name].reshape(nP, T)
            ii, jj = np.meshgrid(np.arange(T), np.arange(T), indexing="ij")
            r = idx[mask][:, ii].ravel(); c = idx[mask][:, jj].ravel()
            rows.append(r); cols.append(c); vals.append(np.tile(Q.ravel(), mask.sum()))
            if (~mask).any():
                d = idx[~mask].ravel(); rows.append(d); cols.append(d); vals.append(np.full(len(d), 1e6))
        e = B["era"]; q = 1 / hp["era"] ** 2
        for s in range(1, nS):
            rows.append(np.array([e[s], e[s-1], e[s], e[s-1]])); cols.append(np.array([e[s], e[s-1], e[s-1], e[s]])); vals.append(np.array([q, q, -q, -q]))
        L = sp.coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(self.P, self.P)).tocsr()
        return L

    def logits(self, theta):
        A = (self.X @ theta).reshape(5, self.N)
        return self.z0 + A.T @ self.D
    def nll_grad_hess(self, theta, Lam, hess=True):
        z = self.logits(theta)
        z = z - z.max(axis=1, keepdims=True)
        e = np.exp(z); s = e.sum(axis=1); p = e / s[:, None]
        nll = -(z[np.arange(self.N), self.y] - np.log(s)).sum()
        pen = 0.5 * theta @ (Lam @ theta)
        G = p.copy(); G[np.arange(self.N), self.y] -= 1
        GA = G @ self.D.T
        grad = np.concatenate([self.XkT[k] @ GA[:, k] for k in range(5)]).reshape(5, -1).sum(axis=0) + Lam @ theta
        if not hess: return nll + pen, grad, None
        Dp = p @ self.D.T
        H = Lam.toarray()
        for k in range(5):
            T = None
            for l in range(5):
                w = (p * (self.D[k] * self.D[l])).sum(axis=1) - Dp[:, k] * Dp[:, l]
                t = sp.diags(w) @ self.Xk[l]
                T = t if T is None else T + t
            H += (self.XkT[k] @ T).toarray()
        return nll + pen, grad, H

    def fit(self, hp, theta=None, tol=1e-6, maxit=30, verbose=False):
        Lam = self.precision(hp)
        theta = np.zeros(self.P) if theta is None else theta.copy()
        f, g, H = self.nll_grad_hess(theta, Lam)
        for it in range(maxit):
            c, low = sla.cho_factor(H)
            d = -sla.cho_solve((c, low), g)
            dec = -(g @ d)
            step = 1.0
            while True:
                f2, g2, _ = self.nll_grad_hess(theta + step * d, Lam, hess=False)
                if f2 <= f - 1e-4 * step * dec or step < 1e-4: break
                step *= 0.5
            theta = theta + step * d
            if verbose: print(f"it {it} f {f2:.3f} step {step} dec {dec:.3e}")
            f, g, H = self.nll_grad_hess(theta, Lam)
            if dec < tol: break
        self.theta, self.H, self.Lam, self.obj = theta, H, Lam, f
        self.chol = sla.cho_factor(H)
        return theta

    def posterior_cov(self):
        return sla.cho_solve(self.chol, np.eye(self.P))

    def laplace_logml(self):
        """log marginal likelihood (Laplace), up to constants that do not depend on hp given fixed pins."""
        Lam = self.Lam.toarray()
        sL = np.linalg.slogdet(Lam)[1]
        sH = 2 * np.log(np.diag(self.chol[0])).sum()
        return -self.obj + 0.5 * sL - 0.5 * sH

def em_update(des, hp, Sig, theta, free_cov=True):
    B, nP, T = des.B, des.nP, des.T
    new = dict(hp); d = np.diag(Sig)
    def sd_of(name, mask=None):
        idx = B[name] if mask is None else B[name][mask]
        return float(np.sqrt(np.mean(theta[idx] ** 2 + d[idx])))
    for k in ("style", "split", "venue", "day", "chase", "affinity"): new[k] = sd_of(k)
    new["kind"] = sd_of("kind", des.bowls)
    for name, key, mask in (("bat_q", "bat_K", np.ones(nP, bool)), ("bowl_q", "bowl_K", des.bowls)):
        idx = B[name].reshape(nP, T)[mask]
        K = np.zeros((T, T))
        for row in idx:
            K += np.outer(theta[row], theta[row]) + Sig[np.ix_(row, row)]
        new[key] = K / len(idx)
    e = B["era"]
    new["era"] = float(np.sqrt(np.mean([theta[e[s]] ** 2 + theta[e[s-1]] ** 2 - 2 * theta[e[s]] * theta[e[s-1]] + Sig[e[s], e[s]] + Sig[e[s-1], e[s-1]] - 2 * Sig[e[s], e[s-1]] for s in range(1, des.nS)])))
    return new
