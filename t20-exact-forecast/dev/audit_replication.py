"""Audit a partial or completed eight-slot replication snapshot without model calls.

Default success means that the evidence present is internally consistent, not
that all trials finished. --require-complete requires eight clean completions;
--require-settled also accepts verified fixed-budget exhaustion, without retry;
--check-package also compares every packaged attempt file with its source.
It also checks the complete batch evidence inventory, bundled plot helper,
deterministic SVG regeneration, and PNG structure and canvas dimensions.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET
import zlib

from audit_revision import grading_consistency, inventory
from audit_submission import ROOT, TASK, require
from collect_replication import BATCH, BUDGET_OUTCOMES, collect, is_settled, sha256, write_json
from plot_replication import draw, load_results
from runtime_contract import verify_runtime


def png_canvas(path):
    """Validate the PNG container without adding an image-library dependency."""
    data = path.read_bytes()
    require(data[:8] == b"\x89PNG\r\n\x1a\n", "Replication PNG has an invalid signature")
    offset, canvas, saw_pixels, ended = 8, None, False, False
    while offset + 12 <= len(data):
        size = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        end = offset + size + 12
        require(end <= len(data), "Replication PNG contains a truncated chunk")
        payload = data[offset + 8:offset + size + 8]
        recorded_crc = struct.unpack(">I", data[offset + size + 8:end])[0]
        require(zlib.crc32(kind + payload) & 0xffffffff == recorded_crc, "Replication PNG chunk checksum differs")
        if offset == 8:
            require(kind == b"IHDR" and size == 13, "Replication PNG is missing its image header")
            canvas = struct.unpack(">II", payload[:8])
            require(all(value > 0 for value in canvas), "Replication PNG has an invalid canvas")
        else:
            require(kind != b"IHDR", "Replication PNG repeats its image header")
        if kind == b"IDAT":
            saw_pixels = True
        if kind == b"IEND":
            require(size == 0 and end == len(data), "Replication PNG has an invalid end marker")
            ended = True
            break
        offset = end
    require(canvas is not None and saw_pixels and ended, "Replication PNG is incomplete")
    return canvas


def publication_checks(batch_folder, source_root=ROOT, package_root=TASK):
    """Bind every published batch file and its chart to the source evidence.

    Only the root audit.json is excluded: this command replaces that file after
    succeeding. All other packager-eligible evidence, including new resource
    observations and nested launcher logs, must be present byte-for-byte.
    """
    batch_relative = batch_folder.relative_to(source_root)
    packaged_batch = package_root / batch_relative
    helper = source_root / "dev/plot_replication.py"
    copied_helper = package_root / "reviewer_tools/plot_replication.py"
    require(copied_helper.is_file() and helper.read_bytes() == copied_helper.read_bytes(), "Bundled replication plot helper differs")
    probe_helper = source_root / "dev/audit_fable_matchups.py"
    copied_probe = package_root / "reviewer_tools/audit_fable_matchups.py"
    require(copied_probe.is_file() and probe_helper.read_bytes() == copied_probe.read_bytes(), "Bundled matchup audit helper differs")
    probe = json.loads((batch_folder / "fable-r1-matchup-audit.json").read_text())
    require(probe["audit_script"] == {"path": "reviewer_tools/audit_fable_matchups.py", "sha256": sha256(probe_helper)}, "Matchup audit helper binding differs")
    for source in probe["source_files"]:
        require(sha256(source_root / source["path"]) == source["sha256"], "Matchup audit archived source differs")
    for world in probe["fixture_audit"]:
        for source in world["source_files"]:
            require(sha256(package_root / source["path"]) == source["sha256"], "Matchup audit world input differs")
    cases = probe["differential_cases"]
    require(len(cases) == 12 and sum(case["equal_style_control"] for case in cases) == 6, "Incomplete matchup differential probe")
    require(all(case["matches_public"] == case["equal_style_control"] for case in cases), "Matchup probe/control conclusions differ")
    results = batch_folder / "results.json"
    data, rows, digest = load_results(results)
    require(not data.get("test_fixture"), "A layout test fixture cannot be published as model evidence")
    expected_svg = draw(data, rows, digest, (batch_relative / "results.json").as_posix()).encode("utf-8")
    svg = batch_folder / "replication-results.svg"
    png = batch_folder / "replication-results.png"
    require(svg.is_file() and svg.read_bytes() == expected_svg, "Replication SVG does not regenerate from published results")
    root = ET.fromstring(expected_svg)
    canvas = (int(root.attrib["width"]), int(root.attrib["height"]))
    require(root.attrib.get("viewBox") == f"0 0 {canvas[0]} {canvas[1]}", "Replication SVG canvas differs")
    require(png.is_file(), "Replication PNG export is missing")
    rendered_canvas = png_canvas(png)
    require(rendered_canvas == tuple(value * 2 for value in canvas), "Replication PNG canvas differs from the SVG at density 144")
    source_files, copied_files = inventory(batch_folder), inventory(packaged_batch)
    source_files.pop("audit.json", None)
    copied_files.pop("audit.json", None)
    require(source_files and source_files == copied_files, "Packaged batch evidence inventory differs (excluding audit.json)")
    return {"batch_files_compared": len(source_files), "excluded_file": "audit.json",
            "plot_helper_sha256": sha256(helper), "matchup_helper_sha256": sha256(probe_helper),
            "matchup_probe_cases": len(cases), "results_sha256": digest,
            "svg_sha256": sha256(svg), "svg_canvas": list(canvas),
            "png_sha256": sha256(png), "png_canvas": list(rendered_canvas),
            "svg_regenerated_exactly": True}


def completion_requirement(report, require_complete=False, require_settled=False):
    require(not (require_complete and require_settled), "Choose complete or settled, not both")
    if require_complete or require_settled:
        require(len(report["trials"]) == 8, "Eight declared slots are required")
    if require_complete:
        require(all(row["status"] == "completed" for row in report["trials"]), "Eight normally completed model slots are required")
    if require_settled:
        require(all(is_settled(row) for row in report["trials"]), "Eight settled slots are required; missing, live, provider/account, operator, or infrastructure outcomes do not settle a fixed-budget slot")


def audit(plan_path=BATCH / "plan.json", require_complete=False, check_package=False, require_settled=False):
    runtime = verify_runtime(TASK)
    report = collect(plan_path)
    require(not report["evidence_issues"], "Batch inventory/retry evidence is inconsistent")
    require(runtime["runtime_version"] == report["task_version"], "Runtime version differs")
    if check_package:
        require(all(row["status"] not in {"pending", "running"} for row in report["trials"]), "Cannot publish a batch with unfinished slots")
    checks, warnings, publication = [], [], None
    for row in report["attempts"]:
        label = row["attempt_id"]
        issues = row["evidence_issues"]
        # A partial JSON write is a transient observation only while running.
        permitted = [issue for issue in issues if row["status"] == "running" and issue.startswith("unreadable_json:")]
        require(len(permitted) == len(issues), f"Evidence binding/inventory error: {label}")
        warnings.extend(f"live_write:{label}" for _ in permitted)
        if row["status"] == "pending":
            checks.append({"attempt_id": label, "status": "pending"})
            continue
        folder = ROOT / row["trial_path"] if row.get("trial_path") else None
        reward = details = None
        ambiguous = []
        if row["artifact_graded"]:
            require(folder is not None, f"Missing graded trial directory: {label}")
            reward = json.loads((folder / "verifier/reward.json").read_text())
            details = json.loads((folder / "verifier/details.json").read_text())
            # A grader-error output is operational evidence, not a forecast
            # verdict. Preserve it without pretending to audit eight worlds.
            if "grader_error" in details:
                require(row["status"] == "infrastructure_error", f"Grader exception attributed to model: {label}")
            else:
                ambiguous = grading_consistency(label, reward, details)
                require(reward == row["rewards"], f"Collected reward differs: {label}")
                require(type(details.get("engine_untouched")) is bool and type(details.get("deterministic")) is bool, f"Missing constraint evidence: {label}")
                # Seconds are rounded to an integer. A recorded 720 can mean
                # either side of the 720-second limit, so retain both possible
                # timeout contributions instead of inventing precision.
                times = [entry["seconds"] for entry in details["leagues"].values()]
                timed = {1} if max(times) < 720 else ({0} if max(times) > 720 else {0, 1})
                constraints = {round((int(details["engine_untouched"]) + int(details["deterministic"]) + timing) / 3, 4) for timing in timed}
                require(reward["constraint_satisfaction"] in constraints, f"Constraint components disagree: {label}")
            result_path = folder / "result.json"
            if result_path.is_file():
                result = json.loads(result_path.read_text())
                if result.get("finished_at") or result.get("verifier_result"):
                    require((result.get("verifier_result") or {}).get("rewards") == reward, f"Harbor/reward disagreement: {label}")
        budget_exhausted = row["status"] == "interrupted" and row["classification"] in BUDGET_OUTCOMES
        if row["status"] == "completed" or budget_exhausted:
            require(row["artifact_graded"] and folder is not None, f"Settled model outcome lacks completed grading: {label}")
            result = json.loads((folder / "result.json").read_text())
            require(result.get("finished_at"), f"Settled outcome lacks terminal Harbor result: {label}")
            if not budget_exhausted:
                require(not result.get("exception_info"), f"Operational exception labeled completed: {label}")
            require((folder / "lock.json").is_file() and (folder / "config.json").is_file(), f"Missing execution binding: {label}")
            info = result.get("agent_info") or {}
            require(info.get("name") and info.get("version") and (info.get("model_info") or {}).get("provider") and info["model_info"].get("name"), f"Missing executed model/harness identity: {label}")
            require(row["seconds"]["agent_execution"] is not None and row["seconds"]["agent_execution"] > 0, f"Missing fresh agent execution: {label}")
            trajectory_path = folder / "agent/trajectory.json"
            require(trajectory_path.is_file(), f"Missing native trajectory: {label}")
            trajectory = json.loads(trajectory_path.read_text())
            require(any(step.get("source") == "agent" for step in trajectory.get("steps", [])), f"No model activity: {label}")
            if not budget_exhausted:
                require(row["terminal_event"]["state"] == "completed", f"Missing native completion: {label}")
            # Missing/broken candidate output is a legitimate model failure;
            # requiring a forecast file here would incorrectly discard it.
            if reward["artifact_quality"] > 0:
                require((folder / "artifacts/app/solution/forecast.py").is_file(), f"Successfully graded program was not archived: {label}")
            require(budget_exhausted or row["classification"] in {"pass", "forecast_quality_failure", "artifact_or_constraint_failure"}, f"Wrong model outcome class: {label}")
        require(row["counts_as_model_outcome"] == (row["status"] == "completed"), f"Operational attempt counted as model outcome: {label}")
        require(row["settled_under_fixed_budget"] == is_settled(row), f"Wrong fixed-budget settlement flag: {label}")
        if row.get("credential_scan_matches") is not None:
            require(row["credential_scan_matches"] == 0, f"Launcher credential scan did not clear: {label}")
        if check_package:
            require(row["status"] not in {"pending", "running"}, f"Cannot publish an incomplete attempt: {label}")
            require(row.get("credential_scan_matches") == 0, f"No completed credential check: {label}")
            source = inventory(ROOT / row["job_path"])
            if (ROOT / row["job_path"]).is_dir():
                require(source and source == inventory(TASK / row["job_path"]), f"Packaged attempt differs: {label}")
            else:
                # A launcher can fail before Harbor creates its directory.
                # The copied launches.json is the complete evidence in that
                # case; never silently drop this real attempted invocation.
                require(row["classification"] == "launcher_finished_without_job" and row["launcher_started_at_utc"] and row["launcher_finished_at_utc"], f"Unexplained absent job: {label}")
                require(not (TASK / row["job_path"]).exists(), f"Unexpected packaged job: {label}")
        checks.append({"attempt_id": label, "status": row["status"], "classification": row["classification"],
                       "artifact_graded": row["artifact_graded"], "rounding_ambiguous_verdict_groups": ambiguous})
    completion_requirement(report, require_complete, require_settled)
    if check_package:
        published = json.loads((plan_path.parent / "results.json").read_text())
        require({key: value for key, value in published.items() if key != "collected_at_utc"} == {key: value for key, value in report.items() if key != "collected_at_utc"}, "Published results do not match current evidence")
        publication = publication_checks(plan_path.parent)
    outcomes = Counter(row["classification"] for row in report["trials"] if row["counts_as_model_outcome"])
    return {"status": "passed", "scope": "complete_batch" if require_complete else ("settled_fixed_budget_batch" if require_settled else "available_evidence_snapshot"),
            "audited_at_utc": datetime.now(timezone.utc).isoformat(), **runtime,
            "task_digest": report["task_digest"], "digest_correction": report["digest_correction"],
            "runtime_freeze_commit": report["runtime_freeze_commit"], "plan_sha256": report["plan_sha256"],
            "planned_trials": 8, "attempts_checked": len(checks), "status_counts": report["status_counts"],
            "clean_model_outcomes": dict(outcomes), "package_checked": check_package,
            "budget_outcomes": report["budget_outcomes"], "settled_trials": report["settled_trials"],
            "all_slots_settled": all(is_settled(row) for row in report["trials"]),
            "all_slots_normally_completed": all(row["status"] == "completed" for row in report["trials"]),
            "warnings": warnings, "checks": checks,
            **({"publication_checks": publication} if check_package else {})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=BATCH / "plan.json")
    parser.add_argument("--output", type=Path, default=BATCH / "audit.json")
    terminal = parser.add_mutually_exclusive_group()
    terminal.add_argument("--require-complete", action="store_true", help="Require eight normal completions")
    terminal.add_argument("--require-settled", action="store_true", help="Require eight normal completions or verified fixed-budget outcomes; never retry a budget outcome")
    parser.add_argument("--check-package", action="store_true")
    args = parser.parse_args()
    try:
        report = audit(args.plan, args.require_complete, args.check_package, args.require_settled)
    except (ValueError, KeyError, TypeError, OSError) as error:
        # Error messages originate in these audit modules, never raw logs.
        print(f"Replication audit failed: {error}", file=sys.stderr)
        return 1
    write_json(args.output, report)
    print(json.dumps({key: report[key] for key in ("status", "scope", "attempts_checked", "status_counts", "clean_model_outcomes", "budget_outcomes", "all_slots_normally_completed", "all_slots_settled", "package_checked")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
