import sys, time
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from league.calibration import Design
from league.world import League

def summary(design, seeds=(1, 2, 3)):
    # play three independent leagues under this design and pool their matches and balls
    M, B = [], []
    for seed in seeds:
        h = League(seed, design=design).play_history()
        M.append(h.matches.assign(league=seed)); B.append(h.balls.assign(league=seed))
    import pandas as pd
    M, B = pd.concat(M), pd.concat(B)
    first = B[B.innings == 1]
    # wickets to bowlers per first innings, runs per over from the bat outcomes plus extras, and chase results
    wk = first[first.outcome == 0].groupby(["league", "match"]).size().reindex(M.set_index(["league", "match"]).index).fillna(0)
    runs = np.array([0, 0, 1, 2, 4, 6])[first.outcome] + first.extra
    per_over = (runs.groupby(first.over).sum() / first.groupby("over").size() * 6).to_numpy()
    chase_won = M.winner != M.batted_first
    bands = {f"{lo}-{hi}": round(float(chase_won[(M.first_total + 1 >= lo) & (M.first_total + 1 < hi)].mean()), 3) for lo, hi in ((0, 160), (160, 180), (180, 200), (200, 220), (220, 400))}
    return M.first_total.mean(), M.first_total.std(), wk.mean(), chase_won.mean(), per_over, bands

if __name__ == "__main__":
    # the real targets measured in file 6, read from the constants file
    real = League(0).cal.real_targets
    # with any argument, also try two other wear settings, which is how wear_runs was chosen
    grid = [Design()] if len(sys.argv) < 2 else [replace(Design(), wear_runs=w) for w in (0.08, 0.12)]
    for design in grid:
        began = time.time()
        mean, sd, wk, chase, per_over, bands = summary(design)
        print(f"day {design.day_sd_runs} wear {design.wear_runs}: mean {mean:.1f} (real {real['first_innings_mean']})  sd {sd:.1f} (real {real['first_innings_sd']})  "
              f"wickets {wk:.2f} (real {real['first_innings_wickets']})  chaser wins {chase:.3f} (real {real['chasing_side_wins']})  [{time.time() - began:.0f}s]")
    real_over = np.array(real["runs_per_over_first_innings"])
    print("runs per over, real     :", np.round(real_over[[0, 3, 6, 10, 14, 17, 19]], 1).tolist(), "(overs 1, 4, 7, 11, 15, 18, 20)")
    print("runs per over, simulated:", np.round(per_over[[0, 3, 6, 10, 14, 17, 19]], 1).tolist(), f"| correlation across the 20 overs {np.corrcoef(real_over, per_over)[0, 1]:.3f}")
    print("chase success by target, real     :", {k: v[1] for k, v in real["chase_success_by_target"].items()})
    print("chase success by target, simulated:", bands)