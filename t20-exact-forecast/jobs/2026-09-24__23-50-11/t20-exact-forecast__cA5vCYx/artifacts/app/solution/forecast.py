"""Forecast home-win probabilities for the fixtures of a simulated T20 league.

    python solution/forecast.py --league <folder> --out <file.csv>

Method: fit the engine's ball model to the history (solution/fit.py), a multinomial logistic regression with one
scalar per hidden quantity and hierarchical Gaussian priors whose variances are estimated by Laplace-EM. Then play
each fixture many times with the engine's own innings mechanics, where every copy of the match uses its own draw of
the hidden numbers from the Laplace posterior (extrapolated one off-season ahead), so the average is the posterior
mean of the [REDACTED] win probability.
"""
import argparse, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from engine.model import RUNS, PACE, SPIN, load_public_model
    from engine.league_io import load_league
except ImportError:  # the engine may also live inside a `league` package
    from league.engine.model import RUNS, PACE, SPIN, load_public_model
    from league.engine.league_io import load_league
from fit import LeagueFit

FLOORS = dict(style=1e-3, split=1e-3, kind=1e-3, level=1e-4, era=1e-4, day=1e-4, chase=1e-4, aff=1e-4, type=1e-4, pitch=1e-4)


class Posterior:
    """Draws skill books for a fixture from the Laplace posterior of a LeagueFit, extrapolated to the coming season."""

    def __init__(self, F, kappa=0.85, era_step_var=None):
        self.F = F
        S = F.S
        self.kappa = kappa
        self.ar = {}
        for name, Sig, tau, fv in (("q", F.Sigma_q, F.ar["tau_q"], F.ar["f_q"]), ("bq", F.Sigma_bq, F.ar["tau_b"], F.ar["f_b"])):
            a = dict(tau2=tau, f2=fv, rho=F.ar["rho"])
            # covariance of season-level qualities with the fixture-time quality, under talent + AR(1) form
            gaps = (S - np.arange(S)) - 1 + kappa  # seasons between each past season's middle and the fixture
            c = a["tau2"] + a["f2"] * a["rho"] ** gaps
            Sinv = np.linalg.inv(Sig)
            A = c @ Sinv
            cond_var = max(a["tau2"] + a["f2"] - c @ Sinv @ c, 1e-8)
            self.ar[name] = (A, cond_var, a)
        self.era_step_var = F.hyper["era"] if era_step_var is None else era_step_var

    def draw(self, fixture, n, gen):
        F, S, h = self.F, self.F.S, self.F.h
        f = fixture
        players = np.concatenate([f.home_xi, f.away_xi])
        bowlers = np.concatenate([f.home_bowlers, f.away_bowlers])
        v = f.venue
        B = F.B
        idx = [B.index("style", players), B.index("q", (players[:, None] * S + np.arange(S)).ravel()), B.index("split", players),
               B.index("level", [v]), B.index("chase", [v]), B.index("era", [S - 1]), B.index("wear", [0]), B.index("home", [0]),
               B.index("aff", players * F.V + v), B.index("type", np.arange(4)), B.index("pitch", np.arange(6))]
        known = np.isin(bowlers, F.bowlers)
        bidx = np.searchsorted(F.bowlers, bowlers[known])
        idx += [B.index("kind", bidx), B.index("bq", (bidx[:, None] * S + np.arange(S)).ravel())]
        sizes = [len(i) for i in idx]
        allidx = np.concatenate(idx)
        mean = F.theta[allidx]
        C = F.cov[np.ix_(allidx, allidx)]
        L = np.linalg.cholesky(C + 1e-10 * np.eye(len(allidx)))
        draws = mean[None, :] + gen.standard_normal((n, len(allidx))) @ L.T
        parts = np.split(draws, np.cumsum(sizes)[:-1], axis=1)
        (style, q, split, level, chase, era, wear, home, aff, type_, pitch, kind_k, bq_k) = parts
        np_ = len(players)
        A, cv, _ = self.ar["q"]
        q3 = q.reshape(n, np_, S) @ A + np.sqrt(cv) * gen.standard_normal((n, np_))
        A, cv, _ = self.ar["bq"]
        nb = len(bowlers)
        kind = np.empty((n, nb)); bq3 = np.empty((n, nb))
        kind[:, known] = kind_k
        bq3[:, known] = bq_k.reshape(n, known.sum(), S) @ A + np.sqrt(cv) * gen.standard_normal((n, known.sum()))
        if (~known).any():
            unk = np.where(~known)[0]
            kind[:, unk] = F.kind_mean[h.players.style[bowlers[unk]]] + np.sqrt(F.hyper["kind"]) * gen.standard_normal((n, len(unk)))
            _, _, a = self.ar["bq"]
            bq3[:, unk] = np.sqrt(a["tau2"] + a["f2"]) * gen.standard_normal((n, len(unk)))
        era3 = era[:, 0] + np.sqrt(self.era_step_var) * gen.standard_normal(n)
        out = dict(style=style, q=q3, split=split, kind=kind, bq=bq3, level=level[:, 0], chase=chase[:, 0], era=era3, wear=wear[:, 0],
                   home=home[:, 0], aff=aff, type=type_.reshape(n, 2, 2), pitch=pitch.reshape(n, 2, 3))
        return out


class Simulator:
    """The engine's innings and match mechanics, with a different skill book in every copy."""

    def __init__(self, model, history):
        self.m = model
        self.h = history

    def innings(self, style, quality, cond, kind, bq, shift, n, gen, target=None):
        m, rows = self.m, np.arange(n)
        striker, partner, next_in = np.zeros(n, int), np.ones(n, int), np.full(n, 2)
        wickets = np.zeros(n, int); runs = np.zeros(n, int); live = np.ones(n, bool)
        chasing = 0.0 if target is None else 1.0
        chase_vec = np.full(n, chasing)
        for ball in range(120):
            over = ball // 6
            who = over % 5
            pressure = 0.0 if target is None else m.pressure(target, runs, ball)
            z = m.situation(over, striker, wickets, chase_vec, pressure)
            z = z + np.outer(style[rows, striker], m.bs) + np.outer(quality[rows, striker, who], m.bq)
            z = z + np.outer(kind[:, who], m.wt) + np.outer(bq[:, who], m.wq) + np.outer(shift + cond[rows, striker, who], m.c)
            p = m.shares(z)
            kind_ = np.minimum((gen.random(n)[:, None] > p.cumsum(axis=1)).sum(axis=1), 5)
            extra = (gen.random(n) < m.cal.extras_per_ball) & live
            out = (kind_ == 0) & live
            scored = np.where(live & ~out, RUNS[kind_], 0)
            runs += scored + extra
            wickets += out
            striker = np.where(out, next_in, striker)
            next_in = next_in + out
            swap = (scored % 2 == 1) ^ (ball % 6 == 5)
            striker, partner = np.where(swap, partner, striker), np.where(swap, striker, partner)
            striker, partner = np.minimum(striker, 10), np.minimum(partner, 10)
            live &= wickets < 10
            if target is not None:
                live &= runs < target
        return runs

    def cards(self, d, bat_slice, team, bowl_slice, venue, n):
        """Per-copy batting arrays for the eleven in bat_slice against the five bowlers in bowl_slice."""
        h = self.h
        xi = self.players[bat_slice]; five = self.bowlers[bowl_slice]
        hand = h.players.hand[xi]; how = h.players.style[five]
        sign = np.where(how == PACE, 0.5, -0.5)
        at_home = d["home"] if h.venues.home_team[venue] == team else np.zeros(n)
        quality = d["q"][:, bat_slice][:, :, None] + d["split"][:, bat_slice][:, :, None] * sign[None, None, :]
        meeting = (d["aff"][:, bat_slice] + at_home[:, None])[:, :, None] + d["type"][:, hand][:, :, how] - d["pitch"][:, how][:, :, venue_pitch(h, venue)][:, None, :]
        return d["style"][:, bat_slice], quality, meeting, d["kind"][:, bowl_slice], d["bq"][:, bowl_slice]

    def win_probability(self, d, f, n, gen, day_sd):
        self.players = np.concatenate([f.home_xi, f.away_xi]); self.bowlers = np.concatenate([f.home_bowlers, f.away_bowlers])
        sl = {f.home: (slice(0, 11), slice(0, 5)), f.away: (slice(11, 22), slice(5, 10))}
        base = d["level"] + d["era"]
        chase_shift = d["chase"] - d["wear"]
        total = 0.0
        for first, second in ((f.home, f.away), (f.away, f.home)):
            day = gen.normal(0.0, day_sd, n)
            s1, q1, c1, k1, b1 = self.cards(d, sl[first][0], first, sl[second][1], f.venue, n)
            set_ = self.innings(s1, q1, c1, k1, b1, base + day, n, gen)
            s2, q2, c2, k2, b2 = self.cards(d, sl[second][0], second, sl[first][1], f.venue, n)
            chase = self.innings(s2, q2, c2, k2, b2, base + chase_shift + day, n, gen, target=set_ + 1)
            second_wins = (chase > set_).mean() + 0.5 * (chase == set_).mean()
            total += 0.5 * (second_wins if second == f.home else 1 - second_wins)
        return float(total)


def venue_pitch(h, venue):
    return int(h.venues.pitch[venue])


def fit_league(history, em_iters=12, log=print, prior=None, prior_weight=1.0, deadline=None):
    """MAP fit with Laplace-EM for the prior variances. Stops early if the deadline (wall-clock seconds) is near."""
    F = LeagueFit(history)
    if prior is not None and prior.get("S") == F.S:
        F.prior_moments = (np.array(prior["C_q"]), prior["n_q"], np.array(prior["C_b"]), prior["n_b"])
        F.prior_weight = prior_weight
        F.ar = dict(prior["ar"])
        F.hyper.update({k: v for k, v in prior["hyper"].items() if k in F.hyper})
    theta = None
    last = None
    for it in range(em_iters + 1):
        t = time.time()
        res = F.fit(theta); theta = res.x
        F.laplace()
        last = time.time() - t
        final = it == em_iters or (deadline is not None and time.time() + 1.5 * last > deadline)
        if not final:
            F.em_step()
            for k, fl in FLOORS.items():
                F.hyper[k] = max(F.hyper[k], fl)
        log(f"em {it}: obj {res.fun:.1f} nit {res.nit} {last:.1f}s hyper " + " ".join(f"{k}={v:.4f}" for k, v in F.hyper.items())
            + " ar " + " ".join(f"{k}={v:.4f}" for k, v in F.ar.items()))
        if final:
            break
    return F


def forecast(folder, n=10000, seed=12345, em_iters=12, log=print, posterior=True, prior=None, prior_weight=1.0, budget=450.0, hard=600.0):
    """Returns (forecast table, fit, posterior).

    `budget` is the wall-clock time (seconds) the run aims for; `hard` is the time it must not exceed. EM stops early
    if it would overrun the budget, and the number of simulated copies is cut if the simulation would overrun `hard`.
    """
    t0 = time.time()
    history, fixtures = load_league(folder)
    # leave time for simulation: about 2.5 seconds per fixture at n = 10000 on two cores
    F = fit_league(history, em_iters, log, prior, prior_weight, deadline=t0 + budget - 4.0 * len(fixtures) * n / 10000)
    model = load_public_model()
    post = Posterior(F)
    sim = Simulator(model, history)
    day_sd = float(np.sqrt(F.hyper["day"]))
    out = []
    for i, f in enumerate(fixtures):
        t = time.time()
        gen = np.random.default_rng(seed + i)
        d = post.draw(f, n, gen)
        if not posterior:
            d = {k: np.repeat(np.mean(v, axis=0, keepdims=True), n, axis=0) for k, v in d.items()}
        p = sim.win_probability(d, f, n, gen, day_sd)
        out.append((f.match, p))
        # if the machine is slow, shrink the remaining simulations so the whole run stays under the hard limit
        left = len(fixtures) - i - 1
        if left and (time.time() - t) * left > hard - (time.time() - t0):
            n = max(2000, int(n * (hard - (time.time() - t0)) / ((time.time() - t) * left) / 1000) * 1000)
            log(f"fixture {i}: {time.time() - t:.1f}s, reducing copies to {n}")
    log(f"simulated {len(fixtures)} fixtures, {time.time() - t0:.1f}s since start")
    return pd.DataFrame(out, columns=["fixture", "p_home"]), F, post


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--n", type=int, default=10000)
    parser.add_argument("--em", type=int, default=12)
    parser.add_argument("--budget", type=float, default=450.0, help="wall-clock seconds to aim for (the limit is 720)")
    parser.add_argument("--hard", type=float, default=600.0, help="wall-clock seconds not to exceed")
    parser.add_argument("--map", action="store_[REDACTED]", help="simulate at the posterior mean instead of drawing")
    parser.add_argument("--quiet", action="store_[REDACTED]")
    parser.add_argument("--prior", default=None, help="JSON of pooled moments from another league (default: none)")
    parser.add_argument("--prior-weight", type=float, default=1.0)
    args = parser.parse_args()
    t0 = time.time()
    log = (lambda *a: None) if args.quiet else (lambda *a: print(*a, file=sys.stderr))
    prior = json.load(open(args.prior)) if args.prior else None
    df, F, post = forecast(args.league, n=args.n, em_iters=args.em, log=log, posterior=not args.map, prior=prior, prior_weight=args.prior_weight, budget=args.budget, hard=args.hard)
    df["p_home"] = df.p_home.clip(0.002, 0.998)
    df.to_csv(args.out, index=False)
    log(f"done in {time.time() - t0:.1f}s")
