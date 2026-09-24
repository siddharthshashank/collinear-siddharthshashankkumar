"""Reruns each submitted program on one graded world with one constant changed, and reports regret before and after.

    python dev/ablate_pilots.py heldout_c ~/Downloads/rebuild_pilots
"""
import json, os, subprocess, sys, tempfile
from pathlib import Path

import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scoring.exact import ExactScorer

world, folder = sys.argv[1], Path(sys.argv[2]).expanduser()
ENGINE = ROOT / "dist" / "collinear-siddharthshashankkumar" / "t20-exact-forecast" / "environment" / "app" / "engine"
league = ROOT / "task_data" / "leagues" / world
truth = pd.read_csv(ROOT / "task_data" / "private" / world / "truth.csv").set_index("fixture").p_home
reference = json.loads((ROOT / "task_data" / "private" / world / "reference.json").read_text())["regret"]
scorer = ExactScorer(truth.to_numpy())

# one edit per experiment: (trial file, label, text to find, text to put in its place)
EXPERIMENTS = [
    ("trial1_claude-code_forecast.py", "ridge 1.0 on everything -> 25", "def fit_skills(model, history, lam=1.0,", "def fit_skills(model, history, lam=25.0,"),
    ("trial2_codex_forecast.py", "every prior sd x 0.33", "self.parts.append((name, self.size, self.size + n, shape, float(sigma)))", "self.parts.append((name, self.size, self.size + n, shape, float(sigma) * 0.33))"),
    ("trial3_claude-code_forecast.py", "every ridge x 12", "lam_vec[a:b] = lam[name]", "lam_vec[a:b] = lam[name] * 12.0"),
    ("trial4_codex_forecast.py", "every ridge x 12", "lam = _penalty(layout)\n    dirs", "lam = _penalty(layout) * 12.0\n    dirs"),
    ("trial5_claude-code_forecast.py", "quality ridges 4 -> 44 and 31", '"quality": 4.0,\n        "split": 16.0,\n        "kind": 4.0,\n        "bowl_quality": 4.0,', '"quality": 44.0,\n        "split": 16.0,\n        "kind": 4.0,\n        "bowl_quality": 31.0,'),
    ("trial6_codex_forecast.py", "hedge removed: logit scale 0.90 -> 1.0", "PROB_LOGIT_SCALE = 0.90", "PROB_LOGIT_SCALE = 1.0"),
    ("trial6_codex_forecast.py", "hedge deepened: logit scale 0.90 -> 0.75", "PROB_LOGIT_SCALE = 0.90", "PROB_LOGIT_SCALE = 0.75"),
    ("trial6_codex_forecast.py", "every prior sd x 0.5, hedge kept", "self.prior.extend([sd] * size)", "self.prior.extend([sd * 0.5] * size)"),
]


def run(source, label):
    # a scratch folder shaped like /app: the program in solution/, the shipped engine beside it
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "solution").mkdir()
        os.symlink(ENGINE, tmp / "engine")
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
for file, label, old, new in EXPERIMENTS:
    source = (folder / file).read_text().replace("[REDACTED]", "true")
    if file not in seen:
        print(f"== {file}")
        run(source, "as submitted")
        seen.add(file)
    if old not in source:
        print(f"   {label}: edit target not found, skipped")
        continue
    run(source.replace(old, new, 1), label)
