import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from forecasters.ladder import BallModelForecaster
from league.world import League, TruthEngine
from scoring.exact import ExactScorer

parser = argparse.ArgumentParser()
parser.add_argument("--leagues", type=int, default=8); parser.add_argument("--copies", type=int, default=40_000); parser.add_argument("--fixtures", type=int, default=24)
args = parser.parse_args()
rows = []
# seeds 1001 onward are never graded, so the tolerance is chosen on worlds the task does not use
for seed in range(1001, 1001 + args.leagues):
    began = time.time()
    league = League(seed); history = league.play_history(); fixtures = league.draw_fixtures(args.fixtures)
    scorer, model = ExactScorer(TruthEngine(league, copies=args.copies).probabilities(fixtures)), league.simulator.innings.model
    ref = BallModelForecaster("reference", model, copies=4000).fit(history)
    repeats = []
    for k in range(4):                                        # the same fitted model, four different simulation seeds
        ref.seed = 400_000 + 10_000 * k
        repeats.append(scorer.regret(ref.predict(fixtures)))
    loose = scorer.regret(BallModelForecaster("x", model, shrink=False, copies=4000).fit(history).predict(fixtures))
    recent = scorer.regret(BallModelForecaster("x", model, season_weights=[0, 0, 1], copies=4000).fit(history).predict(fixtures))
    # noise as a share of the reference's regret, and each careless tier as a multiple of it
    rows.append((seed, repeats[0], np.std(repeats) / repeats[0], loose / repeats[0], recent / repeats[0], scorer.coin / repeats[0]))
    print(f"league {seed}: reference regret {repeats[0]:.4f} | simulation noise {rows[-1][2]:.1%} of it | no shrinkage x{rows[-1][3]:.2f} | last season only x{rows[-1][4]:.2f} | coin flip x{rows[-1][5]:.2f}  [{time.time() - began:.0f}s]", flush=True)
r = np.array(rows)
print(f"\nsimulation noise, worst league: {r[:, 2].max():.1%} of the reference's regret. A tolerance should be at least three times that: {3 * r[:, 2].max():.1%}")
print(f"closest careless tier: no shrinkage x{r[:, 3].min():.2f}, last season only x{r[:, 4].min():.2f}. The tolerance must stay below the smaller of these minus one.")
print(f"leagues where no shrinkage would pass a 10% tolerance: {(r[:, 3] <= 1.10).sum()} of {len(r)}; last season only: {(r[:, 4] <= 1.10).sum()} of {len(r)}")