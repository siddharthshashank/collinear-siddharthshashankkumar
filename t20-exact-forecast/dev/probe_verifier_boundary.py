"""Probe privileged staging/reading with synthetic data in a disposable container.

Requires root and a runner account, plus the task's Python dependencies. Mount
the source task read-only and run this script there. --grader may point to an
earlier grader snapshot for a before/after comparison. No model or network is
used, and no real task probabilities are accessed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

import test_verifier_contract as contract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--grader", type=Path, default=contract.ROOT / "harbor/tests/grader.py")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Run inside a disposable container as root; this probe tests the root/runner boundary.")
    pwd.getpwnam("runner")
    spec = importlib.util.spec_from_file_location("probed_grader", args.grader)
    grader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grader)
    contract.grader = grader
    cases = []
    for route in ("artifact_symlink", "output_symlink"):
        fixture = contract.VerifierContract()
        fixture.setUp()
        try:
            fixture.base.chmod(0o755)
            grader.TESTS.chmod(0o700)
            grader.RUN_AS = "runner"
            truth = grader.TESTS / "private/visible/truth.csv"
            direct = subprocess.run(
                [sys.executable, "-c", f"open({str(truth)!r}).read()"],
                user="runner", group="runner", extra_groups=(), capture_output=True,
            )
            if route == "artifact_symlink":
                (grader.APP / "solution/private").symlink_to(grader.TESTS / "private", target_is_directory=True)
                action = "shutil.copy(Path(__file__).parent/'private'/Path(a.league).name/'truth.csv',a.out)"
            else:
                action = f"Path(a.out).symlink_to(Path({str(grader.TESTS / 'private')!r})/Path(a.league).name/'truth.csv')"
            program = (
                "import argparse,shutil\nfrom pathlib import Path\n"
                "p=argparse.ArgumentParser();p.add_argument('--league');p.add_argument('--out');a=p.parse_args()\n"
                + action + "\n"
            )
            (grader.APP / "solution/forecast.py").write_text(program)
            reward, detail = grader.grade()
            copied = grader.WORK / "run/solution/private"
            cases.append({
                "route": route,
                "direct_private_read_denied": direct.returncode != 0,
                "private_truth_materialized_in_submission": copied.is_dir() and not copied.is_symlink(),
                "reward": reward,
                "submission_error": detail.get("submission_error"),
                "visible_problem": detail["leagues"]["visible"].get("problem"),
            })
        finally:
            fixture.tearDown()
    print(json.dumps({
        "probe": "synthetic_private_truth_boundary",
        "grader_sha256": hashlib.sha256(args.grader.read_bytes()).hexdigest(),
        "scope": "Disposable Docker root/runner boundary with two synthetic fixtures per world. No model run, Harbor artifact transfer, real private truth or network access.",
        "cases": cases,
    }))


if __name__ == "__main__":
    main()
