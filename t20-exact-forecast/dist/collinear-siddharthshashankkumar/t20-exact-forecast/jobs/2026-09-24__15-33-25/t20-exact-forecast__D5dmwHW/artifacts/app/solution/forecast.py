"""Forecast P(home wins) for every fixture of a league folder.

Method: the engine's ball model is a multinomial logit whose hidden numbers are scalars along public directions, so the
whole skill book (per player per period, per venue, per match, ...) is fitted by penalised maximum likelihood with
Gaussian priors; the prior spreads and the form dynamics are chosen per league by empirical Bayes (Laplace evidence);
the fitted skill book is then played with the engine's own match simulator.
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
import sys
import time
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import numpy as np
import pandas as pd

from engine.model import load_public_model
from engine.league_io import load_league
from fitter import Design, Prior, fit_newton
from eb_grad import run_eb_grad
from forecaster import forecast

PERIODS_PER_SEASON = 1
# starting values: empirical-Bayes estimates on the league shipped with the task (Laplace evidence, L-BFGS)
BASE_HYPER = dict(sd_style=0.377, sd_split=0.083, sd_kind=0.151, sd_venue=0.02, sd_day=0.291, sd_dew=0.02, sd_aff=0.086,
                  sd_type=0.02, sd_era=0.3, sd_wear=0.3, sd_home=0.3,
                  sd_talent=0.134, sd_form=0.131, rho_within=0.9, rho_between=0.485,
                  sd_btalent=0.084, sd_bform=0.170, rho_bwithin=0.9, rho_bbetween=0.658)
# Deterministic budgets: a fixed number of evidence evaluations and a fixed number of simulated copies per fixture.
# The wall-clock limits below only act as an emergency brake on a machine far slower than expected.
EB_MAX_EVALS = 30
EB_TIME_BRAKE = 420.0
SIM_COPIES = 48000
SIM_TIME_BRAKE = 600.0     # if this much time has passed before simulating, cut the copies
SEED = 12345
# widths of the gaussian penalty (in log-sd / logit-rho units) pulling the per-league estimates toward BASE_HYPER
PENALTY = dict(sd_style=0.3, sd_split=0.7, sd_kind=0.3, sd_venue=1.0, sd_day=0.3, sd_dew=1.0, sd_aff=0.5, sd_type=1.0,
               sd_talent=0.5, sd_form=0.5, rho_between=0.75, sd_btalent=0.5, sd_bform=0.5, rho_bbetween=0.75)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--eb-evals", type=int, default=EB_MAX_EVALS)
    ap.add_argument("--copies", type=int, default=SIM_COPIES)
    ap.add_argument("--no-eb", action="store_[REDACTED]")
    ap.add_argument("--no-penalty", action="store_[REDACTED]")
    ap.add_argument("--hyper", default=None, help="json file of hyperparameters to start from")
    ap.add_argument("--verbose", action="store_[REDACTED]")
    args = ap.parse_args()
    t0 = time.time()
    model = load_public_model()
    hist, fixtures = load_league(args.league)
    design = Design(model, hist, periods_per_season=PERIODS_PER_SEASON)
    hyper = dict(BASE_HYPER)
    if args.hyper:
        import json
        hyper.update(json.load(open(args.hyper)))
    theta = None
    if not args.no_eb:
        hyper, theta, _ = run_eb_grad(design, hyper, max_evals=args.eb_evals, time_budget=EB_TIME_BRAKE, verbose=args.verbose,
                                      maxiter=100, penalty=None if args.no_penalty else PENALTY)
    prior = Prior(design, hyper)
    theta, _ = fit_newton(design, prior, theta0=theta, maxiter=30, tol=1e-8)
    if args.verbose:
        print("fit done", round(time.time() - t0, 1), {k: round(v, 4) for k, v in hyper.items()}, flush=True)
    copies = args.copies
    if time.time() - t0 > SIM_TIME_BRAKE:
        copies = max(2000, copies // 4)
    p = forecast(design, hist, fixtures, theta, hyper, model, n=copies, seed=SEED)
    p = np.round(np.clip(p, 0.002, 0.998), 5)
    pd.DataFrame({"fixture": [f.match for f in fixtures], "p_home": p}).to_csv(args.out, index=False)
    if args.verbose:
        print("done", round(time.time() - t0, 1), "copies", copies, flush=True)


if __name__ == "__main__":
    main()
