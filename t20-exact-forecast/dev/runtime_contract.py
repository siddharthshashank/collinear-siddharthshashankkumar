"""Verify the explicit revision without rewriting the historical runtime manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION_PATHS = {
    "task.toml", "instruction.md", "environment/app/docs/handbook.md",
    "environment/Dockerfile", "environment/requirements.lock",
    "tests/Dockerfile", "tests/docker-compose.yaml", "tests/requirements.lock", "tests/grader.py", "tests/test.sh",
}


def runtime_contract():
    baseline = json.loads((ROOT / "validation/task-runtime.json").read_text())
    revision = json.loads((ROOT / "validation/runtime-revision.json").read_text())
    if revision["baseline_commit"] != baseline["baseline_commit"]:
        raise ValueError("Revision references a different historical baseline")
    changes = revision["changed_files"]
    if not set(changes) <= REVISION_PATHS:
        raise ValueError("Revision changes data, engine, oracle, or score inputs")
    expected = dict(baseline["files"])
    for name, change in changes.items():
        if not change["reason"] or change["before_sha256"] != expected.get(name):
            raise ValueError(f"Incomplete revision record: {name}")
        if change["after_sha256"] == expected.get(name):
            raise ValueError(f"Declared revision has no change: {name}")
        expected[name] = change["after_sha256"]
    return baseline, revision, expected


def verify_runtime(task: Path):
    baseline, revision, expected = runtime_contract()
    actual = {
        str(p.relative_to(task)) for p in task.rglob("*") if p.is_file()
        and (p.parts[len(task.parts)] in {"environment", "tests", "solution"}
             or str(p.relative_to(task)) in {"task.toml", "instruction.md"})
        and "__pycache__" not in p.parts
    }
    if actual != set(expected):
        raise ValueError(f"Runtime inventory changed: {actual ^ set(expected)}")
    for name, digest in expected.items():
        path = task / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unrecorded runtime change: {name}")
    return {
        "runtime_version": revision["version"],
        "historical_baseline_commit": baseline["baseline_commit"],
        "runtime_files_checked": len(expected),
        "runtime_files_unchanged": len(expected) - len(revision["changed_files"]),
        "runtime_files_revised": sum(v["before_sha256"] is not None for v in revision["changed_files"].values()),
        "runtime_files_added": sum(v["before_sha256"] is None for v in revision["changed_files"].values()),
    }
