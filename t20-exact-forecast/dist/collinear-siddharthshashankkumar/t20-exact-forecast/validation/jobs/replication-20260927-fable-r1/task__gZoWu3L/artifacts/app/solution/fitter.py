"""Penalized multinomial fit of the hidden ball effects, with Gaussian priors whose scales are hyperparameters.

Parameters live in named blocks; each block belongs to one of the five public directions. The prior is Gaussian: independent
for most blocks, and for the drifting qualities an AR(1)-around-a-talent covariance over periods (including one unobserved
future period, the fixture period, whose posterior we need)."""
import numpy as np
import scipy.sparse as sp
from scipy.optimize import minimize
from scipy.linalg import cho_factor, cho_solve, solve_triangular

D_NAMES = ("bat_style", "bat_quality", "bowl_type", "bowl_quality", "conditions")


class Block:
    def __init__(self, name, size, direction, start):
        self.name, self.size, self.direction, self.start = name, size, direction, start
        self.stop = start + size

    @property
    def sl(self):
        return slice(self.start, self.stop)


class Design:
    """Sparse design: for each direction d a matrix X_d (N x P) so that the coordinate of ball i along d is (X_d theta)_i."""

    def __init__(self):
        self.blocks, self.P = {}, 0
        self.rows = [[] for _ in range(5)]
        self.cols = [[] for _ in range(5)]
        self.vals = [[] for _ in range(5)]

    def add_block(self, name, size, direction):
        b = Block(name, size, direction, self.P)
        self.blocks[name] = b
        self.P += size
        return b

    def add_entries(self, block, rows, cols, vals=None):
        rows = np.asarray(rows); cols = np.asarray(cols)
        vals = np.ones(len(rows)) if vals is None else np.asarray(vals, float)
        d = block.direction
        self.rows[d].append(rows); self.cols[d].append(block.start + cols); self.vals[d].append(vals)

    def build(self, N):
        self.N = N
        self.X = []
        for d in range(5):
            if self.rows[d]:
                r, c, v = np.concatenate(self.rows[d]), np.concatenate(self.cols[d]), np.concatenate(self.vals[d])
                X = sp.csr_matrix((v, (r, c)), shape=(N, self.P))
            else:
                X = sp.csr_matrix((N, self.P))
            self.X.append(X)
        self.XT = [X.T.tocsr() for X in self.X]
        # per-ball fixed-width table of (column, direction, value) for the fast Hessian; padded with a dummy column P
        width = max(int(np.diff(X.indptr).max()) if X.nnz else 0 for X in self.X)
        counts = np.zeros(N, int)
        for X in self.X:
            counts += np.diff(X.indptr)
        W = int(counts.max())
        cols = np.full((N, W), self.P, int); dirs = np.zeros((N, W), int); vals = np.zeros((N, W))
        fill = np.zeros(N, int)
        for d, X in enumerate(self.X):
            X = X.tocsr(); X.sort_indices()
            nnz_row = np.diff(X.indptr)
            row = np.repeat(np.arange(N), nnz_row)
            pos = fill[row] + (np.arange(X.nnz) - np.repeat(X.indptr[:-1], nnz_row))
            cols[row, pos] = X.indices; dirs[row, pos] = d; vals[row, pos] = X.data
            fill += nnz_row
        self.h_cols, self.h_dirs, self.h_vals = cols, dirs, vals
        return self


def ar_covariance(rhos, sd_talent, sd_form):
    """Covariance over K+1 periods of talent + stationary AR(1) form; rhos[k] links period k to k+1."""
    K = len(rhos) + 1
    R = np.eye(K)
    for i in range(K):
        acc = 1.0
        for j in range(i + 1, K):
            acc *= rhos[j - 1]
            R[i, j] = R[j, i] = acc
    return sd_talent ** 2 * np.ones((K, K)) + sd_form ** 2 * R


class Fitter:
    def __init__(self, design, public, y, directions):
        self.des, self.public, self.y = design, public, y
        self.D = np.array([directions[k] for k in D_NAMES])          # 5 x 6
        self.onehot = np.eye(6)[y]
        self.N = len(y)

    # ---- prior ----
    def set_prior(self, prec_blocks):
        """prec_blocks: dict block name -> precision (scalar for iid, or dense matrix per unit with unit layout (n_units, K) row-major)."""
        P = self.des.P
        rows, cols, vals = [], [], []
        logdet = 0.0
        for name, b in self.des.blocks.items():
            spec = prec_blocks[name]
            if np.isscalar(spec):
                idx = np.arange(b.start, b.stop)
                rows.append(idx); cols.append(idx); vals.append(np.full(b.size, float(spec)))
                logdet += b.size * np.log(spec)
            else:
                Q, n_units = spec  # Q is K x K precision, block laid out unit-major
                K = Q.shape[0]
                assert n_units * K == b.size
                base = b.start + np.arange(n_units)[:, None, None] * K
                ii, jj = np.meshgrid(np.arange(K), np.arange(K), indexing="ij")
                rows.append((base + ii[None]).ravel()); cols.append((base + jj[None]).ravel())
                vals.append(np.tile(Q.ravel(), n_units))
                logdet += n_units * np.linalg.slogdet(Q)[1]
        self.Lam = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(P, P))
        self.Lam_logdet = logdet

    # ---- likelihood pieces ----
    def coords(self, theta):
        return np.stack([X @ theta for X in self.des.X], axis=1)  # N x 5

    def probs(self, theta):
        z = self.public + self.coords(theta) @ self.D
        z -= z.max(axis=1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(axis=1, keepdims=True)
        return p

    def objective(self, theta):
        p = self.probs(theta)
        ll = np.log(p[np.arange(self.N), self.y] + 1e-300).sum()
        Lt = self.Lam @ theta
        f = -ll + 0.5 * theta @ Lt
        g = (self.onehot - p) @ self.D.T          # N x 5
        grad = -sum(self.des.XT[d] @ g[:, d] for d in range(5)) + Lt
        return f, grad

    def loglik(self, theta):
        p = self.probs(theta)
        return np.log(p[np.arange(self.N), self.y] + 1e-300).sum()

    def hessian_ll(self, theta):
        """Negative Hessian of the log-likelihood (dense P x P), accumulated from per-ball outer products."""
        p = self.probs(theta)
        DP = p[:, None, :] * self.D[None, :, :]                  # N x 5 x 6
        M = np.einsum("ndk,ek->nde", DP, self.D) - np.einsum("nd,ne->nde", DP.sum(2), DP.sum(2))
        des = self.des
        cols, dirs, vals = des.h_cols, des.h_dirs, des.h_vals
        N, W = cols.shape
        P1 = des.P + 1
        # weight of the (i, j) pair for each ball: v_i v_j M[d_i, d_j]; accumulated in chunks to bound memory
        H = np.zeros(P1 * P1)
        step = 16384
        for s in range(0, N, step):
            e = min(N, s + step)
            c, d, v = cols[s:e], dirs[s:e], vals[s:e]
            Mij = M[np.arange(s, e)[:, None, None], d[:, :, None], d[:, None, :]]
            w = (v[:, :, None] * v[:, None, :] * Mij).ravel()
            idx = (c[:, :, None] * P1 + c[:, None, :]).ravel()
            H += np.bincount(idx, weights=w, minlength=P1 * P1)
        H = H.reshape(P1, P1)
        return np.ascontiguousarray(H[:des.P, :des.P])

    # ---- fitting ----
    def fit_lbfgs(self, theta0=None, maxiter=2000, gtol=1e-6):
        theta0 = np.zeros(self.des.P) if theta0 is None else theta0
        res = minimize(self.objective, theta0, jac=True, method="L-BFGS-B", options=dict(maxiter=maxiter, maxfun=maxiter * 2, gtol=gtol, ftol=1e-12, maxcor=30))
        return res.x

    def _newton_steps(self, theta, chol, iters, tol):
        f, grad = self.objective(theta)
        for _ in range(iters):
            step = cho_solve(chol, grad, check_finite=False)
            decrement = grad @ step
            if decrement < tol:
                break
            t = 1.0
            while True:
                th_new = theta - t * step
                f_new, g_new = self.objective(th_new)
                if f_new <= f - 1e-4 * t * decrement or t < 1e-3:
                    break
                t *= 0.5
            theta, f, grad = th_new, f_new, g_new
        return theta, f, grad

    def fit(self, theta0=None, outer=4, inner=25, tol=1e-7, verbose=False, refactor=True):
        """MAP fit: Newton steps with a Hessian that is refactored only every `inner` steps. Leaves the Laplace factor in place.
        With refactor=False the factor from the start of the last outer pass is kept (cheaper, slightly stale)."""
        theta = np.zeros(self.des.P) if theta0 is None else theta0.copy()
        Lam = self.Lam.toarray()
        for o in range(outer):
            A = self.hessian_ll(theta) + Lam
            chol = cho_factor(A, lower=True, check_finite=False)
            theta, f, grad = self._newton_steps(theta, chol, inner, tol)
            step = cho_solve(chol, grad, check_finite=False)
            if verbose:
                print(f"  outer {o}: f={f:.4f} decrement={grad @ step:.3e}")
            if grad @ step < tol:
                break
        self.theta = theta
        if refactor:
            A = self.hessian_ll(theta) + Lam
            chol = cho_factor(A, lower=True, check_finite=False)
        self.post_chol = chol
        return theta

    def posterior_linv(self):
        """Returns Linv with posterior covariance = Linv^T Linv."""
        c, lower = self.post_chol
        L = np.tril(c) if lower else np.triu(c).T
        return solve_triangular(L, np.eye(self.des.P), lower=True, check_finite=False)

    def posterior_cov(self):
        Linv = self.posterior_linv()
        return Linv.T @ Linv

    def evidence(self, theta=None):
        """Laplace approximation of log marginal likelihood (up to a constant)."""
        theta = self.theta if theta is None else theta
        f, _ = self.objective(theta)
        c, lower = self.post_chol
        logdet_post = 2 * np.log(np.abs(np.diag(c))).sum()
        return -f + 0.5 * self.Lam_logdet - 0.5 * logdet_post

    def posterior_cov_diag(self):
        c, lower = self.post_chol
        Linv = np.linalg.inv(np.tril(c)) if lower else np.linalg.inv(np.triu(c)).T
        return (Linv ** 2).sum(0)

    def sample(self, n, rng, antithetic=True):
        """Draws from the Laplace posterior N(theta, (H+Lam)^-1), as antithetic pairs when asked. Returns P x n."""
        c, lower = self.post_chol
        L = np.tril(c) if lower else np.triu(c).T
        half = (n + 1) // 2 if antithetic else n
        z = rng.standard_normal((self.des.P, half))
        dev = np.linalg.solve(L.T, z)
        if antithetic:
            dev = np.concatenate([dev, -dev], axis=1)[:, :n]
        return self.theta[:, None] + dev
