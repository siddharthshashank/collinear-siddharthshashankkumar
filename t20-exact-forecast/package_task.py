import json, shutil, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from league.calibration import Calibration
from league.engine import PublicConstants
from dev.runtime_contract import verify_runtime

TASK = ROOT / "dist" / "collinear-siddharthshashankkumar" / "t20-exact-forecast"
SKIP = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".DS_Store", "*.pyc")

def write_engine(folder):
    # the engine as the agent gets it: the simulator, the file reader, and only the public constants
    folder.mkdir(parents=True)
    (folder / "__init__.py").write_text("")
    shutil.copy(ROOT / "league" / "engine.py", folder / "model.py")
    shutil.copy(ROOT / "league" / "league_io.py", folder / "league_io.py")
    (folder / "public.json").write_text(json.dumps(PublicConstants.from_calibration(Calibration.load()), indent=1))

def assemble(task):
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
    docs = ("RUN_REPORT.md", "REPLICATION_REPORT.md", "DESIGN_DOCUMENT.md", "DECISIONS.md", "ASSUMPTIONS.md", "NOTES.md", "PROVENANCE.md", "ASSIGNMENT_BRIEF.md", "VALIDATION.md", "ablations.log", "bar.log")
    for name in (*docs, "docs/TASK_README.md", "validation/task-runtime.json"):
        if not (ROOT / name).is_file():
            sys.exit(f"Missing reviewer artifact: {name}")
    # start from harbor/ (instruction, task.toml, Dockerfiles, test.sh, grader, solution), leaving bar.json for the private side
    shutil.copytree(ROOT / "harbor", task, ignore=shutil.ignore_patterns("bar.json", "__pycache__"))
    bar = json.loads((ROOT / "harbor" / "bar.json").read_text())
    # the agent's side: engine, the visible league, the starter, and the handbook with its placeholders filled from the bar
    app = task / "environment" / "app"
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
        shutil.copy(ROOT / "harbor" / "requirements.lock", task / side / "requirements.lock")
    (task / "requirements.lock").unlink()
    # the verifier's side: a pristine engine, all eight leagues, the private truth and reference numbers, and the bar
    write_engine(task / "tests" / "pristine" / "engine")
    shutil.copytree(data / "leagues", task / "tests" / "leagues")
    shutil.copytree(data / "private", task / "tests" / "private")
    (task / "tests" / "private" / "bar.json").write_text(json.dumps(bar, indent=1))
    # the oracle's forecaster is the ladder file, with its import pointed at the task's engine package
    reference = (ROOT / "forecasters" / "ladder.py").read_text().replace("from league.engine import", "from engine.model import")
    (task / "solution" / "reference_forecaster.py").write_text(reference)
    # Documents and evidence stay outside both Docker build contexts: agents see
    # no oracle, private truth, reviewer analysis or archived model solutions.
    shutil.copy(ROOT / "docs" / "TASK_README.md", task / "README.md")
    for name in docs:
        shutil.copy(ROOT / name, task / name)
    (task / "figures").mkdir()
    figures = json.loads((ROOT / "figures" / "architecture-manifest.json").read_text())["figures"]
    for name in figures:
        for suffix in ("svg", "png"):
            shutil.copy(ROOT / "figures" / f"{name}.{suffix}", task / "figures" / f"{name}.{suffix}")
    for name in ("README.md", "architecture-manifest.json", "package.json", "package-lock.json"):
        shutil.copy(ROOT / "figures" / name, task / "figures" / name)
    (task / "figures" / "src").mkdir()
    for name in ("architecture.py", "render.cjs"):
        shutil.copy(ROOT / "figures" / "src" / name, task / "figures" / "src" / name)
    (task / "reviewer_tools").mkdir()
    for name in ("regrade_archived.py", "plot_replication.py", "audit_fable_matchups.py"):
        shutil.copy(ROOT / "dev" / name, task / "reviewer_tools" / name)
    for name in ("jobs", "validation"):
        shutil.copytree(ROOT / name, task / name, ignore=shutil.ignore_patterns("sessions", "__pycache__", "*.pyc", ".DS_Store"))
    verify_runtime(task)


def main():
    TASK.parent.mkdir(parents=True, exist_ok=True)
    # Build and verify off to the side. A bad input cannot destroy the last good package.
    with tempfile.TemporaryDirectory(prefix=".t20-package-", dir=TASK.parent) as directory:
        stage = Path(directory) / TASK.name
        assemble(stage)
        backup = Path(directory) / "previous"
        if TASK.exists():
            TASK.rename(backup)
        try:
            stage.rename(TASK)
        except BaseException:
            if backup.exists():
                backup.rename(TASK)
            raise
    print(f"Task directory: {TASK.relative_to(ROOT)}; {verify_runtime(TASK)}")

if __name__ == "__main__":
    main()
