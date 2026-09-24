import hashlib, json, os, shutil, subprocess, sys, time, traceback
from pathlib import Path
import numpy as np
import pandas as pd

# every path can be overridden by an environment variable, so the grader can be run outside the container for a local check
APP = Path(os.environ.get("GRADER_APP", "/app"))
TESTS = Path(os.environ.get("GRADER_TESTS", "/tests"))
WORK = Path(os.environ.get("GRADER_WORK", "/work"))
LOGS = Path(os.environ.get("GRADER_LOGS", "/logs/verifier"))
RUN_AS = os.environ.get("GRADER_RUN_AS", "runner")
SECONDS_PER_LEAGUE = 720
# functional correctness gates everything; the other three keys are weighted into the overall score
WEIGHTS = {"robustness": 0.5, "constraint_satisfaction": 0.25, "artifact_quality": 0.25}

def untouched(pristine, submitted):
    # every file of the pristine engine must exist in the agent's copy with an identical hash
    for original in sorted(p for p in pristine.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        copy = submitted / original.relative_to(pristine)
        if not copy.is_file() or hashlib.sha256(copy.read_bytes()).hexdigest() != hashlib.sha256(original.read_bytes()).hexdigest():
            return False
    return True

def run_forecaster(run_dir, league, out_file):
    # runs the submission in a clean folder, with a stripped environment, a time limit, and as the unprivileged user when possible
    options = dict(cwd=run_dir, capture_output=True, text=True, timeout=SECONDS_PER_LEAGUE,
                   env={"PATH": os.environ.get("PATH", ""), "HOME": "/tmp", "PYTHONPATH": str(run_dir), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
    if RUN_AS and os.geteuid() == 0:
        options["user"] = RUN_AS
    began = time.time()
    try:
        done = subprocess.run([sys.executable, "solution/forecast.py", "--league", str(league), "--out", str(out_file)], **options)
        return done.returncode == 0, time.time() - began, done.stderr.strip()[-400:]
    except subprocess.TimeoutExpired:
        return False, float(SECONDS_PER_LEAGUE), f"no forecast within {SECONDS_PER_LEAGUE} seconds"

def regret(truth, forecast, clip):
    # the same formula as scoring/exact.py, kept self-contained so the verifier ships without the development package
    q = np.clip(forecast, clip, 1 - clip)
    return float(np.mean(truth * np.log(truth / q) + (1 - truth) * np.log((1 - truth) / (1 - q))))

def grade():
    bar = json.loads((TESTS / "private" / "bar.json").read_text())
    run_dir, out_dir = WORK / "run", WORK / "out"
    shutil.rmtree(WORK, ignore_errors=True); out_dir.mkdir(parents=True)
    # the submission runs beside a pristine copy of the engine, never beside the agent's own copy
    shutil.copytree(TESTS / "pristine" / "engine", run_dir / "engine")
    delivered = (APP / "solution" / "forecast.py").is_file()
    if delivered:
        shutil.copytree(APP / "solution", run_dir / "solution", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(TESTS / "leagues", WORK / "leagues")
    if RUN_AS and os.geteuid() == 0:
        subprocess.run(["chown", "-R", RUN_AS, str(WORK)], check=True)
    details = {"bar": bar, "leagues": {}}
    valid, in_time, mine, ref, coin = {}, {}, {}, {}, {}
    names = sorted(p.name for p in (TESTS / "leagues").iterdir())
    for name in names:
        entry = {}
        ok, seconds, problem = run_forecaster(run_dir, WORK / "leagues" / name, out_dir / f"{name}.csv") if delivered else (False, 0.0, "solution/forecast.py is missing")
        entry["seconds"], in_time[name] = round(seconds), seconds < SECONDS_PER_LEAGUE
        truth = pd.read_csv(TESTS / "private" / name / "truth.csv").set_index("fixture").p_home
        reference = json.loads((TESTS / "private" / name / "reference.json").read_text())
        ref[name], coin[name], valid[name] = reference["regret"], reference["coin_flip_regret"], False
        if ok and (out_dir / f"{name}.csv").is_file():
            try:
                # a forecast is valid only if every fixture has a finite number between 0 and 1
                got = pd.read_csv(out_dir / f"{name}.csv").set_index("fixture").p_home.reindex(truth.index)
                valid[name] = bool(got.notna().all() and np.isfinite(got).all() and ((got >= 0) & (got <= 1)).all())
            except Exception as problem_reading:
                problem = f"could not read the forecast file: {problem_reading}"
            if valid[name]:
                mine[name] = regret(truth.to_numpy(), got.to_numpy(), bar["clip"])
                # for attribution: which ladder tier does this forecast most resemble, by root-mean-square distance?
                tiers = pd.read_csv(TESTS / "private" / name / "tiers.csv").set_index("fixture")
                nearest = min(tiers.columns, key=lambda c: float(np.sqrt(np.mean((tiers[c].reindex(truth.index).to_numpy() - got.to_numpy()) ** 2))))
                entry.update(regret=round(mine[name], 5), reference_regret=ref[name], times_reference=round(mine[name] / ref[name], 3), most_like=nearest)
        if not valid[name]:
            entry["problem"] = problem or "the forecast file is missing, incomplete, or holds values outside 0 to 1"
        details["leagues"][name] = entry

    def within_bar(group):
        """The pre-registered rule: total regret over the group at most the reference's total times one plus the tolerance."""
        if not group or not all(valid[n] for n in group):
            return False, None
        total, limit = sum(mine[n] for n in group), sum(ref[n] for n in group) * (1 + bar["relative_tolerance"]) + bar["absolute_tolerance"]
        return total <= limit, round(total / sum(ref[n] for n in group), 3)

    # the rule is applied twice: to all eight leagues, and to the seven held-out ones on their own
    held = [n for n in names if n != "visible"]
    passed_all, ratio_all = within_bar(names)
    passed_held, ratio_held = within_bar(held or names)
    details["total_regret_as_a_multiple_of_the_reference"] = {"all_leagues": ratio_all, "held_out_leagues": ratio_held,
                                                              "coin_flip_for_comparison": round(sum(coin.values()) / sum(ref.values()), 3)}
    # determinism: the visible league is run a second time and must give the same numbers to twelve decimals
    deterministic = False
    if delivered and valid.get("visible"):
        run_forecaster(run_dir, WORK / "leagues" / "visible", out_dir / "visible_again.csv")
        try:
            a, b = pd.read_csv(out_dir / "visible.csv"), pd.read_csv(out_dir / "visible_again.csv")
            deterministic = bool(np.allclose(a.p_home.to_numpy(), b.p_home.to_numpy(), rtol=0, atol=1e-12))
        except Exception:
            deterministic = False
    engine_ok = untouched(TESTS / "pristine" / "engine", APP / "engine")
    rewards = {"functional_correctness": 1.0 if passed_all else 0.0, "robustness": 1.0 if passed_held else 0.0,
               "constraint_satisfaction": round(float(np.mean([engine_ok, deterministic, all(in_time.values())])), 4),
               "artifact_quality": round(float(np.mean([valid[n] for n in names])), 4)}
    # nothing counts unless the forecast passes: overall is functional correctness times the weighted mean of the rest
    rewards["overall"] = round(rewards["functional_correctness"] * sum(WEIGHTS[k] * rewards[k] for k in WEIGHTS), 4)
    details.update(engine_untouched=engine_ok, deterministic=deterministic)
    return rewards, details


if __name__ == "__main__":
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        rewards, details = grade()
    except Exception:
        # a crash in the grader is a zero with the traceback in details, never a missing reward file
        rewards = {"overall": 0.0, "functional_correctness": 0.0, "robustness": 0.0, "constraint_satisfaction": 0.0, "artifact_quality": 0.0}
        details = {"grader_error": traceback.format_exc()[-1500:]}
    (LOGS / "reward.json").write_text(json.dumps(rewards))
    (LOGS / "details.json").write_text(json.dumps(details, indent=1))
    print(json.dumps(rewards))