"""Regrade a preserved historical artifact; never starts a model or edits raw evidence.

python dev/regrade_archived.py --job-name revision-replay-gpt55
The packaged equivalent lives in reviewer_tools/ and uses the extracted task.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT if (ROOT / "task.toml").is_file() else ROOT / "dist/collinear-siddharthshashankkumar/t20-exact-forecast"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", default="2026-09-23__20-04-36")
    parser.add_argument("--job-name", required=True, help="A new validation job name")
    args = parser.parse_args()
    source = ROOT / "jobs" / args.job
    if source.parent != ROOT / "jobs" or not source.is_dir():
        parser.error("--job must name one archived job directory")
    output = ROOT / "validation/jobs"
    if (output / args.job_name).exists():
        parser.error("Choose a new job name; existing validation evidence is preserved")
    with tempfile.TemporaryDirectory(prefix="collinear-regrade-") as directory:
        staged = Path(directory) / args.job
        shutil.copytree(source, staged)
        restored = []
        for path in sorted(staged.rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".py"}:
                continue
            before = path.read_bytes()
            text = before.decode()
            if path.suffix == ".json":
                # Only known boolean fields are restored. Quoted redactions,
                # including credentials, remain opaque and are never inferred.
                text = re.sub(r'("(?:delete|engine_untouched|deterministic)"\s*:\s*)\[REDACTED\]', r'\1true', text)
                json.loads(text)
            elif "artifacts" in path.parts:
                # The documented historical redaction changed this literal in
                # comments and argparse's store_true. These are staged copies.
                text = text.replace("[REDACTED]", "true")
            after = text.encode()
            if after != before:
                path.write_bytes(after)
                restored.append({"path": str(path.relative_to(staged)),
                                 "before_sha256": hashlib.sha256(before).hexdigest(),
                                 "after_sha256": hashlib.sha256(after).hexdigest()})
        # The archived engine's restored bytes must match the unchanged engine.
        for original in (TASK / "tests/pristine/engine").rglob("*"):
            if original.is_file():
                copies = list(staged.glob("*/artifacts/app/engine/" + str(original.relative_to(TASK / "tests/pristine/engine"))))
                if len(copies) != 1 or copies[0].read_bytes() != original.read_bytes():
                    raise ValueError(f"Archived engine does not match pristine engine: {original.name}")
        command = ["harbor", "jobs", "regrade", str(staged), "-p", str(TASK),
                   "--jobs-dir", str(output), "--job-name", args.job_name]
        result = subprocess.run(command, check=False)
        record = {"source_job": args.job, "kind": "artifact_regrade_not_model_trial",
                  "raw_evidence_changed": False, "restorations": restored,
                  "exit_code": result.returncode, "task_version": "0.1.1"}
        output.mkdir(parents=True, exist_ok=True)
        (ROOT / "validation" / f"{args.job_name}-preparation.json").write_text(json.dumps(record, indent=2) + "\n")
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
