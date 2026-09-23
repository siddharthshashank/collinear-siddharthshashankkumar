import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from forecasters.ladder import BallModelForecaster, CoinFlip, TeamRatings
from league.world import League, TruthEngine
from scoring.exact import ExactScorer

seeds = [int(s) for s in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1]
fixtures_n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
table = {}
for seed in seeds:
    began = time.time()
    league = League(seed)
    history = league.play_history()
    fixtures = league.draw_fixtures(fixtures_n)
    # the truth at 10,000 copies is enough here: its error is about one percent of the reference's regret
    truth = TruthEngine(league, copies=10_000).probabilities(fixtures)
    scorer, engine = ExactScorer(truth), league.simulator.innings.model
    ladder = [CoinFlip(), TeamRatings(),
              BallModelForecaster("players, no shrinkage", engine, shrink=False),
              BallModelForecaster("players, shrunk, last season only", engine, season_weights=[0, 0, 1]),
              BallModelForecaster("players, shrunk", engine),
              BallModelForecaster("players, shrunk, raw head-to-head table", engine, head_to_head=True),
              BallModelForecaster("players, shrunk, type-level matchups", engine, matchups=True),
              BallModelForecaster("players, shrunk, matchups and venue affinity", engine, matchups=True, affinity=True)]
    print(f"seed {seed}: truth sd {truth.std():.3f}, range {truth.min():.2f}-{truth.max():.2f}  ({time.time() - began:.0f}s)", flush=True)
    for f in ladder:
        r = ExactScorer.report(scorer, f.fit(history).predict(fixtures))
        table.setdefault(f.name, []).append(r["skill"])
        # every result is appended to a log so that runs accumulate
        with open(Path(__file__).resolve().parents[1] / "results" / "ladder_v2.jsonl", "a") as out:
            out.write(json.dumps({"seed": seed, "name": f.name, "skill": round(r["skill"], 4), "regret": round(r["regret"], 5)}) + "\n")
        print(f"   {f.name:<48} skill {r['skill']:+.2f}  regret {r['regret']:.4f}  slope {r['slope']:.2f}" + (f"  shrink x{f.scale}" if hasattr(f, 'scale') else ""), flush=True)
    print(f"   ({time.time() - began:.0f}s)", flush=True)
print("\nmean skill over seeds (min to max)")
for name, v in table.items():
    print(f"   {name:<48} {np.mean(v):+.2f}   ({min(v):+.2f} to {max(v):+.2f})")