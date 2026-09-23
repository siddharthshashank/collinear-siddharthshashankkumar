import json
import sys
from pathlib import Path
import numpy as np

fit = json.loads(Path("data/state_fit.json").read_text())
con = json.loads(Path("data/constants_fit.json").read_text())
RUNS = np.array([0, 0, 1, 2, 4, 6])

def unit(v, positive=None, negative=None):
    # Turns a six-number direction into a standard form: centred so the numbers sum to zero (adding the same
    # amount to all six scores changes no probability, so that part carries no information), scaled to length
    # one (so "one unit" means the same thing for every direction), and given a fixed sign. An eigenvector's
    # sign is arbitrary; the convention makes batter style point toward more sixes, batter quality toward fewer
    # dismissals, bowler type toward more sixes conceded, bowler quality toward fewer fours conceded.
    v = np.array(v, float)
    v = v - v.mean()
    v = v / np.linalg.norm(v)
    if positive is not None and v[positive] < 0:
        v = -v
    if negative is not None and v[negative] > 0:
        v = -v
    return v


# THE ERA. The situation model gave every season its own effect on the six outcomes, with 2019 as zero. Fit a
# straight line through the eight seasons for each outcome; the slope is how much that outcome drifts per season.
# The six slopes together are a direction (the way the game moves as scoring rises) and a length (how fast).
# The length is era_step, 0.0934 per season. The direction becomes "conditions" below: venue level, dew, the
# pitch on the day and the season level all push the outcomes along this same axis in the simulator.
seasons = sorted(fit["season_effects"])
effects = np.array([[0.0] * 6] + [fit["season_effects"][s] for s in seasons])
years = np.arange(len(effects))
trend = np.array([np.polyfit(years, effects[:, k], 1)[0] for k in range(6)])
trend -= trend.mean()
era_step = float(np.linalg.norm(trend))
# THE MODERN OVER PROFILES. The fitted profiles are relative to 2019. Adding the mean effect of the last four
# seasons moves them to the game as it is now. These twenty rows of six are what the ball model starts from.
recent = np.mean([fit["season_effects"][s] for s in ("2023", "2024", "2025", "2026")], axis=0)
overs = np.array(fit["overs"]) + recent
# A TYPICAL BALL: the six probabilities averaged over the twenty overs. Used only to express directions in cricket units.
p = np.exp(overs)
p /= p.sum(1, keepdims=True)
p = p.mean(0)
# CRICKET UNITS. value(d): how many runs per ball one unit along direction d is worth. A unit step multiplies
# each outcome's odds by exp(d_k), so to first order each probability moves by p_k * (d_k - mean of d under p);
# weighting those moves by runs gives the change in expected runs. risk(d) is the same for the wicket outcome alone.
value = lambda d: float((p * d * RUNS).sum() - (p * d).sum() * (p * RUNS).sum())
risk = lambda d: float(p[0] * (d[0] - (p * d).sum()))

# THE FIVE DIRECTIONS in standard form: the first and second player axes from file 5 for batters and bowlers, and the era trend.
directions = {"bat_style": unit(fit["batter"]["direction"], positive=5), "bat_quality": unit(fit["batter"]["second"], negative=0),
              "bowl_type": unit(fit["bowler"]["direction"], positive=5), "bowl_quality": unit(fit["bowler"]["second"], negative=4),
              "conditions": unit(trend)}
# THE SPREADS: how widely real players are spread along each direction, with sampling noise already removed in
# file 5. The first axis's spread is the square root of its eigenvalue; the second's is scaled by the ratio of the
# second eigenvalue to the first. The simulator draws each invented player's hidden values from these spreads.
bat, bowl = fit["batter"]["shares"], fit["bowler"]["shares"]
spreads = {"bat_style": fit["batter"]["sd"], "bat_quality": fit["batter"]["sd"] * np.sqrt(bat[1] / bat[0]),
           "bowl_type": fit["bowler"]["sd"], "bowl_quality": fit["bowler"]["sd"] * np.sqrt(bowl[1] / bowl[0])}

# THE FILE. Public constants (profiles, situation responses, directions, extras) that the agent will see through the
# engine, plus the measured spreads and the real targets that only the generator and the validation script use.
# The first entry is the attribution the Cricsheet licence requires.
out = {"source": "Calibration constants derived from data sourced from Cricsheet (cricsheet.org), licensed under the Open Data Commons Attribution License (ODC-BY 1.0). Aggregates only.",
       "over_logits": overs.round(4).tolist(), "position_vectors": [[0.0] * 6] + fit["pos"],
       "wickets_in_hand_vector": fit["wk_excess"], "chase_pressure_vector": fit["pressure"], "second_innings_vector": fit["inn2"],
       "typical_wickets_by_over": fit["typical_wk"], "par_rate_from_over": fit["par_from"],
       "directions": {k: v.round(4).tolist() for k, v in directions.items()}, "spreads": {k: round(float(v), 4) for k, v in spreads.items()},
       "era_step": round(era_step, 4), "runs_per_unit": {k: round(value(v), 4) for k, v in directions.items()},
       "wicket_risk_per_unit": {k: round(risk(v), 4) for k, v in directions.items()},
       "extras_per_legal_ball": con["extras_per_legal_ball"], "venue_level_sd_runs": con["venue"]["true_sd_runs_per_ball"],
       "batter_venue_sd_runs": con["batter_at_venue"]["true_sd_runs_per_ball"],
       "measured": {k: con[k] for k in ("batter_vs_bowler", "batter_at_venue", "bowler_at_venue", "batter_season_reliability", "bowler_season_reliability")},
       "real_targets": con["real_targets"]}
Path("league/calibration.json").write_text(json.dumps(out, indent=1))
for k, d in directions.items():
    print(f"{k:<13} spread {spreads.get(k, float('nan')):.3f} | one unit is worth {value(d):+.3f} runs per ball and {risk(d):+.4f} wicket chance per ball")
print("era step per season:", round(era_step, 4))

# THE COMPARISON. If a path to another calibration file is given on the command line, flatten each block of both
# files into one long vector and print the largest absolute difference per block, then overall. This is the check
# of the whole calibration stage: constants rebuilt from raw data against the constants the piloted task used.
original = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if original and original.is_file():
    old = json.loads(original.read_text())
    flat = lambda x: np.concatenate([np.ravel(np.array(v, float)) for v in (x.values() if isinstance(x, dict) else [x])])
    worst = 0.0
    for key in ("over_logits", "position_vectors", "wickets_in_hand_vector", "chase_pressure_vector", "second_innings_vector", "typical_wickets_by_over",
                "par_rate_from_over", "directions", "spreads", "era_step", "runs_per_unit", "wicket_risk_per_unit", "extras_per_legal_ball", "venue_level_sd_runs", "batter_venue_sd_runs"):
        gap = float(np.abs(flat(out[key]) - flat(old[key])).max())
        worst = max(worst, gap)
        print(f"   {key:<26} largest difference from the original {gap:.4f}")
    print("largest difference anywhere:", round(worst, 4))