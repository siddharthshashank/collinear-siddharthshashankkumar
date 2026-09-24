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