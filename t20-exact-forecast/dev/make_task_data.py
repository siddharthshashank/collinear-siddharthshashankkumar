import argparse, json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from forecasters.ladder import BallModelForecaster, CoinFlip, TeamRatings
from league.league_io import load_league, save_league
from league.world import League, TruthEngine
from scoring.exact import ExactScorer

# one seed per graded world; the agent sees only "visible"
LEAGUES = {"visible": 101, "heldout_a": 202, "heldout_b": 303, "heldout_c": 404, "heldout_d": 505, "heldout_e": 606, "heldout_f": 707, "heldout_g": 808}
REFERENCE_COPIES = 4000

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--copies", type=int, default=100_000)
    parser.add_argument("--fixtures", type=int, default=24)
    parser.add_argument("--no-tiers", action="store_true")
    args = parser.parse_args()
    out = ROOT / "task_data"
    for name, seed in LEAGUES.items():
        began = time.time()
        # a world already built at this precision is kept, so a rerun only builds what is missing
        done = out / "private" / name / "reference.json"
        if done.is_file() and json.loads(done.read_text()).get("truth_copies") == args.copies and (args.no_tiers or len(json.loads(done.read_text())["tiers"]) > 1):
            print(f"{name}: already built at {args.copies} copies, kept", flush=True)
            continue
        league = League(seed)
        history = league.play_history()
        fixtures = league.draw_fixtures(args.fixtures)
        save_league(out / "leagues" / name, history, fixtures)
        # the truth: every fixture played `copies` times with the hidden skills
        truth = TruthEngine(league, copies=args.copies).probabilities(fixtures)
        private = out / "private" / name; private.mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"fixture": [f.match for f in fixtures], "p_home": truth}).to_csv(private / "truth.csv", index=False)
        history, fixtures = load_league(out / "leagues" / name)                 # from here on, exactly what a solver would load
        model, scorer = league.simulator.innings.model, ExactScorer(truth)
        tiers = {"reference": BallModelForecaster("reference", model, copies=REFERENCE_COPIES)}
        if not args.no_tiers:
            tiers.update({"coin flip": CoinFlip(), "team ratings": TeamRatings(), "no shrinkage": BallModelForecaster("x", model, shrink=False),
                          "last season only": BallModelForecaster("x", model, season_weights=[0, 0, 1]), "raw head-to-head": BallModelForecaster("x", model, head_to_head=True)})
        table, report = {}, {}
        for tier, f in tiers.items():
            table[tier] = f.fit(history).predict(fixtures)
            report[tier] = round(scorer.regret(table[tier]), 6)
        # tiers.csv lets the grader say which tier a submission most resembles; reference.json holds the numbers the bar is set against
        pd.DataFrame({"fixture": [f.match for f in fixtures], **table}).to_csv(private / "tiers.csv", index=False)
        (private / "reference.json").write_text(json.dumps({"regret": report["reference"], "coin_flip_regret": round(scorer.coin, 6), "truth_copies": args.copies, "tiers": report}, indent=1))
        print(f"{name}: truth sd {truth.std():.3f} | " + "  ".join(f"{k} {v:.4f}" for k, v in report.items()) + f"  [{time.time() - began:.0f}s]", flush=True)

if __name__ == "__main__":
    main()