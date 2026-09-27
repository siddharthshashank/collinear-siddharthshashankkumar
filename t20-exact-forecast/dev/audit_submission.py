"""Audit the frozen task and archived results without rerunning a model."""
import hashlib
import json
import math
import re
import sys
import struct
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "dist/collinear-siddharthshashankkumar/t20-exact-forecast"
FIELDS = {"overall", "functional_correctness", "robustness", "constraint_satisfaction", "artifact_quality"}
TARGETS = {"anthropic/claude-opus-4-7", "openai/gpt-5.5"}
EXCLUDED = {"2026-09-24__17-35-36", "2026-09-24__19-41-42", "2026-09-25__01-34-12", "2026-09-25__01-51-10"}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def read_record(path):
    # A documented historical redaction replaced this literal, even inside code.
    # Preserve the source bytes; never reconstruct an unknown credential.
    return json.loads(path.read_text().replace("[REDACTED]", "true"))

def audit():
    manifest = json.loads((ROOT / "validation/task-runtime.json").read_text())
    for name, expected in manifest["files"].items():
        path = TASK / name
        require(path.is_file(), f"Missing runtime file: {name}")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, f"Runtime changed: {name}")
    actual_runtime = {
        str(p.relative_to(TASK)) for p in TASK.rglob("*") if p.is_file()
        and (p.parts[len(TASK.parts)] in {"environment", "tests", "solution"} or p.name in {"task.toml", "instruction.md"})
        and "__pycache__" not in p.parts
    }
    require(actual_runtime == set(manifest["files"]), "Unexpected runtime file inventory")
    for name in ("solution/solve.sh", "tests/test.sh"):
        require((TASK / name).stat().st_mode & 0o111, f"Not executable: {name}")
    reviewer_docs = ("README.md", "RUN_REPORT.md", "DESIGN_DOCUMENT.md", "DECISIONS.md", "ASSUMPTIONS.md", "NOTES.md", "PROVENANCE.md", "ASSIGNMENT_BRIEF.md", "VALIDATION.md", "figures/README.md")
    for name in reviewer_docs:
        require((TASK / name).is_file(), f"Missing packaged document: {name}")
    figures = json.loads((TASK / "figures/architecture-manifest.json").read_text())["figures"]
    require(len(figures) == 7 and len(set(figures)) == 7, "Expected seven architecture figures")
    for name in figures:
        svg = TASK / "figures" / f"{name}.svg"
        png = TASK / "figures" / f"{name}.png"
        require(ET.parse(svg).getroot().get("viewBox") == "0 0 1600 960", f"Invalid SVG canvas: {name}")
        data = png.read_bytes()
        require(data[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", data[16:24]) == (2400, 1440), f"Invalid PNG export: {name}")
    names = {"visible", *(f"heldout_{letter}" for letter in "abcdefg")}
    require({p.name for p in (TASK / "tests/leagues").iterdir()} == names, "Expected eight worlds")
    require(len(list(TASK.rglob("task.toml"))) == 1, "Package contains more than one task")

    rows = []
    for config in sorted((ROOT / "jobs").glob("*/*/config.json")):
        trial = config.parent
        job = trial.parent.name
        c = read_record(config)
        agent = c.get("agent", {})
        model = agent.get("model_name")
        if model not in TARGETS | {"anthropic/claude-fable-5-1", "openai/gpt-6-astra"}:
            continue
        reward_path = trial / "verifier/reward.json"
        row = {"job": job, "model": model, "excluded": job in EXCLUDED, "graded": reward_path.is_file()}
        if row["graded"]:
            reward = read_record(reward_path)
            detail = read_record(trial / "verifier/details.json")
            require(set(reward) == FIELDS, f"Reward fields: {job}")
            require("grader_error" not in detail, f"Grader error: {job}")
            require(set(detail["leagues"]) == names, f"Missing graded world: {job}")
            require(all(math.isfinite(v) and 0 <= v <= 1 for v in reward.values()), f"Invalid reward: {job}")
            ratios = detail["total_regret_as_a_multiple_of_the_reference"]
            # The per-world regrets are rounded to five decimals in the archive.
            for selected, key, field in ((names, "all_leagues", "functional_correctness"), (names - {"visible"}, "held_out_leagues", "robustness")):
                mine = sum(detail["leagues"][n]["regret"] for n in selected)
                reference = sum(detail["leagues"][n]["reference_regret"] for n in selected)
                ratio = mine / reference
                require(abs(ratio - ratios[key]) < 0.002, f"Inconsistent rounded ratio: {job}/{key}")
                require(float(ratio <= 1.1) == reward[field], f"Inconsistent verdict: {job}/{field}")
            overall = round(reward["functional_correctness"] * (0.5 * reward["robustness"] + 0.25 * reward["constraint_satisfaction"] + 0.25 * reward["artifact_quality"]), 4)
            require(overall == reward["overall"], f"Overall formula: {job}")
            require(read_record(trial / "result.json")["verifier_result"]["rewards"] == reward, f"Result/reward disagreement: {job}")
            require((trial / "artifacts/app/solution/forecast.py").is_file(), f"No archived program: {job}")
            row.update(overall=reward["overall"], total_ratio=ratios["all_leagues"], heldout_ratio=ratios["held_out_leagues"])
            if not row["excluded"]:
                require(reward["constraint_satisfaction"] == reward["artifact_quality"] == 1, f"Non-forecast failure: {job}")
        if model in TARGETS:
            require(agent.get("kwargs", {}).get("reasoning_effort") == "high", f"Target effort not high: {job}")
            require(agent.get("name") == ("codex" if model.startswith("openai/") else "claude-code"), f"Wrong harness: {job}")
            require(row.get("overall") == 0, f"Unexpected target outcome: {job}")
        rows.append(row)

    counts = Counter(r["model"] for r in rows if not r["excluded"])
    require(counts == {"anthropic/claude-opus-4-7": 5, "openai/gpt-5.5": 5, "anthropic/claude-fable-5-1": 3, "openai/gpt-6-astra": 2}, "Model counts differ from report")
    require(len(rows) == 19 and sum(r["graded"] for r in rows) == 16, "Historical job count differs from report")

    # Check current reviewer links, not historical notes with external context.
    link_count = 0
    current_docs = [ROOT.parent / "README.md", ROOT.parent / "START_HERE.md"]
    current_docs += [ROOT / p for p in reviewer_docs]
    current_docs += [TASK / p for p in reviewer_docs]
    for document in current_docs:
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', document.read_text()):
            target = target.strip()
            if target.startswith(("https://", "http://", "#")):
                continue
            target = target.split("#", 1)[0]
            destination = (document.parent / target).resolve()
            # This report is created after a successful audit; the archive builder
            # copies it into the task before checking and writing the zip.
            generated = {ROOT / "validation/evidence-audit.json", TASK / "validation/evidence-audit.json"}
            require(destination.exists() or destination in generated, f"Broken link: {document.relative_to(ROOT.parent)} -> {target}")
            link_count += 1

    return {"status": "passed", "baseline_commit": manifest["baseline_commit"], "runtime_files_unchanged": len(manifest["files"]), "task_directories": 1,
            "historical_model_jobs": len(rows), "graded_model_jobs_including_excluded_starter": sum(r["graded"] for r in rows),
            "included_model_submissions": sum(not r["excluded"] for r in rows), "local_document_links_checked": link_count, "architecture_figures_checked": len(figures),
            "evidence_note": "Known literal true redaction restored only in memory; rounded regrets checked within 0.002 ratio tolerance.",
            "trials": rows}

if __name__ == "__main__":
    try:
        report = audit()
    except Exception as error:
        print(f"Submission audit failed: {error}", file=sys.stderr)
        sys.exit(1)
    (ROOT / "validation/evidence-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Audit passed: {report['runtime_files_unchanged']} runtime files unchanged; 19 original model jobs reconciled; {report['local_document_links_checked']} document links checked.")
