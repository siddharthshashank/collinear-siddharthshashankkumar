"""Reruns each first-round pilot program on one graded world with one constant changed, and reports regret before and after.

    python dev/ablate_pilots.py heldout_c

The programs are read straight from the job records under jobs/ (review finding F-21), the harness's
redaction of the word "true" is restored in memory, and the shipped engine is copied beside each program.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.exact import ExactScorer

world = sys.argv[1] if len(sys.argv) > 1 else "heldout_c"
ENGINE = ROOT / "dist" / "collinear-siddharthshashankkumar" / "t20-exact-forecast" / "environment" / "app" / "engine"
league = ROOT / "task_data" / "leagues" / world
truth = pd.read_csv(ROOT / "task_data" / "private" / world / "truth.csv").set_index("fixture").p_home
reference = json.loads((ROOT / "task_data" / "private" / world / "reference.json").read_text())["regret"]
scorer = ExactScorer(truth.to_numpy())

# the six first-round programs, by job
JOBS = {
    "run 1, Opus 4.7": "2026-09-23__19-48-37",
    "run 2, GPT-5.5": "2026-09-23__20-04-36",
    "run 3, Opus 4.7": "2026-09-23__20-29-40",
    "run 4, GPT-5.5": "2026-09-23__20-54-41",
    "run 5, Opus 4.7": "2026-09-23__21-13-35",
    "run 6, GPT-5.5": "2026-09-23__21-34-46",
}
# one edit per experiment: (program, label, text to find, text to put in its place)
EXPERIMENTS = [
    ("run 1, Opus 4.7", "ridge 1.0 on everything -> 25", "def fit_skills(model, history, lam=1.0,", "def fit_skills(model, history, lam=25.0,"),
    ("run 2, GPT-5.5", "every prior sd x 0.33", "self.parts.append((name, self.size, self.size + n, shape, float(sigma)))", "self.parts.append((name, self.size, self.size + n, shape, float(sigma) * 0.33))"),
    ("run 3, Opus 4.7", "every ridge x 12", "lam_vec[a:b] = lam[name]", "lam_vec[a:b] = lam[name] * 12.0"),
    ("run 4, GPT-5.5", "every ridge x 12", "lam = _penalty(layout)\n    dirs", "lam = _penalty(layout) * 12.0\n    dirs"),
    ("run 5, Opus 4.7", "quality ridges 4 -> 44 and 31", '"quality": 4.0,\n        "split": 16.0,\n        "kind": 4.0,\n        "bowl_quality": 4.0,', '"quality": 44.0,\n        "split": 16.0,\n        "kind": 4.0,\n        "bowl_quality": 31.0,'),
    ("run 6, GPT-5.5", "hedge removed: logit scale 0.90 -> 1.0", "PROB_LOGIT_SCALE = 0.90", "PROB_LOGIT_SCALE = 1.0"),
    ("run 6, GPT-5.5", "hedge deepened: logit scale 0.90 -> 0.75", "PROB_LOGIT_SCALE = 0.90", "PROB_LOGIT_SCALE = 0.75"),
    ("run 6, GPT-5.5", "every prior sd x 0.5, hedge kept", "self.prior.extend([sd] * size)", "self.prior.extend([sd * 0.5] * size)"),
]


def program(job):
    # the submitted program is the archived artifact; the harness replaced the env value "true" with [REDACTED] in every artifact
    matches = list((ROOT / "jobs" / job).glob("*/artifacts/app/solution/forecast.py"))
    if len(matches) != 1:
        raise SystemExit(f"expected one archived program for job {job}, found {len(matches)}")
    return matches[0].read_text().replace("[REDACTED]", "true")


def run(source, label):
    # a scratch folder shaped like /app: the program in solution/, a copy of the shipped engine beside it
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "solution").mkdir()
        shutil.copytree(ENGINE, tmp / "engine")
        (tmp / "solution" / "forecast.py").write_text(source)
        out = tmp / "out.csv"
        done = subprocess.run([sys.executable, "solution/forecast.py", "--league", str(league), "--out", str(out)], cwd=tmp,
                              capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(tmp)}, timeout=900)
        if done.returncode != 0:
            print(f"   {label}: failed to run: {done.stderr.strip()[-300:]}")
            return None
        got = pd.read_csv(out).set_index("fixture").p_home.reindex(truth.index).to_numpy()
        r = scorer.regret(got)
        print(f"   {label}: regret {r:.4f} = {r / reference:.2f} x reference")
        return r


print(f"world {world}: reference regret {reference:.4f}, coin flip {scorer.coin / reference:.2f} x")
seen = set()
for name, label, old, new in EXPERIMENTS:
    source = program(JOBS[name])
    if name not in seen:
        print(f"== {name} ({JOBS[name]})")
        run(source, "as submitted")
        seen.add(name)
    if old not in source:
        print(f"   {label}: edit target not found, skipped")
        continue
    run(source.replace(old, new, 1), label)
