"""Forecast home-win probabilities for every fixture of a league folder.

Method: the engine's ball model is a multinomial logit whose hidden effects enter linearly along five public
directions. We fit all hidden effects (batter style/quality per season, bowler type/quality per season, venue,
era, pitch-of-the-day, dew, affinity, home lift, hand-vs-style and pitch tables) by penalized maximum likelihood
(Newton's method; Gaussian priors with scales estimated offline by marginal likelihood), draw skills from the
Laplace posterior, project the quality time series to the coming season, and play each fixture many times
with a per-copy vectorized copy of the engine's simulator."""
import os, sys, argparse
os.environ.setdefault("OMP_NUM_THREADS", "2"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np, pandas as pd

N_COPIES = 25000       # simulated matches per batting order per fixture
N_SAMPLES = 1000       # posterior skill draws (copies cycle through them)

def _import_engine(league):
    # the grader supplies engine/ unchanged; look beside solution/, in the working directory and beside the league folder
    for root in (os.path.dirname(HERE), os.getcwd(), os.path.dirname(os.path.abspath(league)), "/app"):
        if os.path.isdir(os.path.join(root, "engine")) and root not in sys.path:
            sys.path.append(root)
    import engine.league_io  # noqa

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--league", required=True); ap.add_argument("--out", required=True)
    args = ap.parse_args()
    _import_engine(args.league)
    from engine.league_io import load_league
    from engine.model import load_public_model
    from fitlib import Design
    import forecastlib, simlib
    from hyper import HP, K_full
    history, fixtures = load_league(args.league)
    des = Design(history)
    hp = dict(HP); hp["bat_K"] = K_full("bat", des.T)[:des.T, :des.T]; hp["bowl_K"] = K_full("bowl", des.T)[:des.T, :des.T]
    theta = des.fit(hp)
    Sig = des.posterior_cov()
    weights = {}
    for key in ("bat", "bowl"):
        w, r = forecastlib.prediction_weights(K_full(key, des.T), des.T); weights[key] = w; weights[key + "_resid"] = r
    model = load_public_model()
    rows = []
    for i, f in enumerate(fixtures):
        gen = np.random.default_rng([12345, int(f.match), i])
        cards = forecastlib.card_builder(des, theta, Sig, f, weights, N_SAMPLES, gen, sample=True)
        p = simlib.win_probability(model, cards, N_COPIES, gen, hp["day"])
        rows.append((int(f.match), float(np.clip(p, 0.002, 0.998))))
    pd.DataFrame(rows, columns=["fixture", "p_home"]).to_csv(args.out, index=False)

if __name__ == "__main__":
    main()
