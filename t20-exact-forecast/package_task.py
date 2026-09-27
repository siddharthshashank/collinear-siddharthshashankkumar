import hashlib, json, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from league.calibration import Calibration
from league.engine import PublicConstants

TASK = ROOT / "dist" / "collinear-siddharthshashankkumar" / "t20-exact-forecast"
SKIP = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".DS_Store", "*.pyc")

def write_engine(folder):
    # the engine as the agent gets it: the simulator, the file reader, and only the public constants
    folder.mkdir(parents=True)
    (folder / "__init__.py").write_text("")
    shutil.copy(ROOT / "league" / "engine.py", folder / "model.py")
    shutil.copy(ROOT / "league" / "league_io.py", folder / "league_io.py")
    (folder / "public.json").write_text(json.dumps(PublicConstants.from_calibration(Calibration.load()), indent=1))

def main():
    data = ROOT / "task_data"
    # Check every world before replacing an existing package. A partial data build
    # must not silently become a smaller, easier task.
    names = {"visible", *(f"heldout_{letter}" for letter in "abcdefg")}
    public_files = ("balls.csv", "matches.csv", "lineups.csv", "players.csv", "venues.csv", "fixtures.csv", "fixture_lineups.csv", "meta.json")
    for side in ("leagues", "private"):
        if not (data / side).is_dir() or {p.name for p in (data / side).iterdir() if p.is_dir()} != names:
            sys.exit(f"task_data/{side} must contain exactly the eight graded worlds")
        for name in sorted(names):
            for filename in public_files if side == "leagues" else ("truth.csv", "reference.json", "tiers.csv"):
                path = data / side / name / filename
                if not path.is_file() or path.stat().st_size == 0:
                    sys.exit(f"Missing or empty task input: {path.relative_to(ROOT)}")
    docs = ("RUN_REPORT.md", "DESIGN_DOCUMENT.md", "PROVENANCE.md", "ASSIGNMENT_BRIEF.md", "VALIDATION.md", "ablations.log", "bar.log")
    for name in (*docs, "docs/TASK_README.md", "validation/task-runtime.json"):
        if not (ROOT / name).is_file():
            sys.exit(f"Missing reviewer artifact: {name}")
    # start from harbor/ (instruction, task.toml, Dockerfiles, test.sh, grader, solution), leaving bar.json for the private side
    shutil.rmtree(TASK, ignore_errors=True)
    shutil.copytree(ROOT / "harbor", TASK, ignore=shutil.ignore_patterns("bar.json", "__pycache__"))
    bar = json.loads((ROOT / "harbor" / "bar.json").read_text())
    # the agent's side: engine, the visible league, the starter, and the handbook with its placeholders filled from the bar
    app = TASK / "environment" / "app"
    write_engine(app / "engine")
    shutil.copytree(data / "leagues" / "visible", app / "league")
    shutil.copytree(ROOT / "task_src" / "solution", app / "solution", ignore=SKIP)
    (app / "docs").mkdir()
    handbook = (ROOT / "task_src" / "docs" / "handbook.md").read_text()
    handbook = handbook.replace("{clip}", str(bar["clip"])).replace("{one_minus_clip}", str(1 - bar["clip"]))
    handbook = handbook.replace("{relative_pct}", f"{bar['relative_tolerance'] * 100:g}")
    (app / "docs" / "handbook.md").write_text(handbook)
    # both images get the lock file; the copy at the task root is not needed
    for side in ("environment", "tests"):
        shutil.copy(ROOT / "harbor" / "requirements.lock", TASK / side / "requirements.lock")
    (TASK / "requirements.lock").unlink()
    # the verifier's side: a pristine engine, all eight leagues, the private truth and reference numbers, and the bar
    write_engine(TASK / "tests" / "pristine" / "engine")
    shutil.copytree(data / "leagues", TASK / "tests" / "leagues")
    shutil.copytree(data / "private", TASK / "tests" / "private")
    (TASK / "tests" / "private" / "bar.json").write_text(json.dumps(bar, indent=1))
    # the oracle's forecaster is the ladder file, with its import pointed at the task's engine package
    reference = (ROOT / "forecasters" / "ladder.py").read_text().replace("from league.engine import", "from engine.model import")
    (TASK / "solution" / "reference_forecaster.py").write_text(reference)
    # Documents and evidence stay outside both Docker build contexts: agents see
    # no oracle, private truth, reviewer analysis or archived model solutions.
    shutil.copy(ROOT / "docs" / "TASK_README.md", TASK / "README.md")
    for name in docs:
        shutil.copy(ROOT / name, TASK / name)
    (TASK / "figures").mkdir()
    for name in ("system_overview", "calibration_pipeline", "grading_rule", "harbor_runtime"):
        shutil.copy(ROOT / "figures" / f"{name}.png", TASK / "figures" / f"{name}.png")
    for name in ("jobs", "validation"):
        shutil.copytree(ROOT / name, TASK / name, ignore=shutil.ignore_patterns("sessions", "__pycache__", "*.pyc", ".DS_Store"))
    manifest = json.loads((ROOT / "validation" / "task-runtime.json").read_text())
    for name, expected in manifest["files"].items():
        if hashlib.sha256((TASK / name).read_bytes()).hexdigest() != expected:
            sys.exit(f"Evaluated runtime changed during packaging: {name}")
    print(f"task directory: {TASK.relative_to(ROOT)}  | leagues: {sorted(p.name for p in (data / 'leagues').iterdir())} | bar: {bar['relative_tolerance']:.0%} + {bar['absolute_tolerance']}")

if __name__ == "__main__":
    main()
