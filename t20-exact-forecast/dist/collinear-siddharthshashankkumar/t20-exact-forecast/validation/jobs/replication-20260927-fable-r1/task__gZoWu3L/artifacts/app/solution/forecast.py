"""Forecast the home-win probability of every fixture in a league folder.

Method: fit every hidden effect of the public ball model (player styles and drifting qualities, bowler types and qualities, venue,
season, dew, day, affinity, home lift, hand/style and pitch/style tables) by penalized multinomial regression with Gaussian priors
whose scales are set by empirical Bayes; then simulate each fixture many times with the engine's rules, integrating over posterior
draws of the hidden values."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
import sys, json, time, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))

import numpy as np
import pandas as pd
from prep import LeagueData
from spec import Spec
from hyper import run_em
from simulate import win_probability

SEED = 20260927


def forecast(folder, out, n_samples=960, n_per_sample=50, em_iters=40, em_budget=360.0, verbose=True):
    t0 = time.time()
    L = LeagueData(folder)
    hyper = json.load(open(os.environ.get("HYPER_FILE", HERE / "hyper.json")))
    S = Spec(L, hyper=hyper)
    theta = None
    if em_iters > 0:
        _, theta, _ = run_em(S, iters=em_iters, verbose=verbose, tol=0.003, budget=em_budget)
        if verbose:
            print("hyper:", {k: round(v, 4) for k, v in S.h.items()}, flush=True)
    F = S.fitter
    theta = F.fit(theta)
    if verbose:
        print(f"fit done {time.time() - t0:.1f}s evidence={F.evidence():.2f}", flush=True)
    rng = np.random.default_rng(SEED)
    draws = F.sample(n_samples, rng).T if n_samples > 0 else theta[None, :]      # S x P
    rows = []
    for f in L.fixtures:
        sides, sf, sc = S.cards(draws, f)
        p = win_probability(L.model, sides, sf, sc, f, S.h["sd_day"], n_per_sample, rng)
        rows.append((f.match, min(max(p, 0.002), 0.998)))
        if verbose:
            print(f"fixture {f.match}: p_home={p:.3f}  ({time.time() - t0:.0f}s)", flush=True)
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(out, index=False)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--samples", type=int, default=960)
    ap.add_argument("--per_sample", type=int, default=50)
    ap.add_argument("--em", type=int, default=40)
    ap.add_argument("--em_budget", type=float, default=360.0)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    forecast(a.league, a.out, a.samples, a.per_sample, a.em, a.em_budget, not a.quiet)
