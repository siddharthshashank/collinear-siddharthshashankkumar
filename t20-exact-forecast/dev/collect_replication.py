"""Collect the declared replication slots without running models or exposing logs.

An artifact grade and a normally completed model attempt are separate facts.
Agent budget exhaustion settles a slot without permitting a retry; operational
interruptions retain their grades but never count as model failures.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

from audit_submission import ROOT, FIELDS, require
from runtime_contract import runtime_contract

BATCH = ROOT / "validation/replication-20260927"
STATUSES = ("completed", "interrupted", "infrastructure_error", "running", "pending")
BUDGET_OUTCOMES = {"agent_time_limit", "agent_budget_limit"}
MODELS = {
    "gpt55": ("GPT-5.5", "Codex", "codex", "openai/gpt-5.5", "0.157.1"),
    "astra": ("GPT-6-astra", "Codex", "codex", "openai/gpt-6-astra", "0.157.1"),
    "fable": ("Claude Fable 5.1", "Claude Code", "claude-code", "anthropic/claude-fable-5-1", "2.1.274"),
    "opus": ("Claude Opus 4.7", "Claude Code", "claude-code", "anthropic/claude-opus-4-7", "2.1.274"),
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return path.relative_to(ROOT).as_posix()


def read_json(path, issues):
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError("Expected object")
        return value
    except (ValueError, UnicodeError, OSError):
        # A live writer may be between writes. Never echo raw content/errors.
        issues.append(f"unreadable_json:{relative(path)}")
        return None


def validate_plan(plan):
    require(plan["task_version"] == "0.1.1" and plan["relative_tolerance"] == 0.10, "Wrong version/bar in plan")
    require(plan["planned_trials"] == 8 and len(plan["slots"]) == 8, "Expected eight declared slots")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", plan["task_digest"]), "Invalid task digest")
    expected = {f"{key}-r{rep}" for key in MODELS for rep in (1, 2)}
    require({s["trial_id"] for s in plan["slots"]} == expected, "Replication slot identities differ")
    require(len({s["job_name"] for s in plan["slots"]}) == 8, "Duplicate base jobs")
    for slot in plan["slots"]:
        key, rep = slot["trial_id"].split("-r")
        require(tuple(slot[k] for k in ("model", "harness", "agent", "model_slug", "version")) == MODELS[key], "Model/harness plan differs")
        require(slot["replicate"] == int(rep) and slot["reasoning_effort"] == "high", "Wrong replicate/effort")
        require(slot["job_name"] == f"{plan['batch_id']}-{slot['trial_id']}", "Unexpected base job name")
        for name in slot.get("attempt_job_names", []):
            require(re.fullmatch(re.escape(slot["job_name"]) + r"(?:-retry-[1-9][0-9]*)?", name), "Unexpected linked retry name")


def snapshot_binding(plan_path, plan):
    """Verify the documented reviewer-README-only package digest correction."""
    path = plan_path.parent / "snapshot-binding.json"
    if not path.is_file():
        return {"task_digest": plan["task_digest"], "digest_correction": None}
    binding = json.loads(path.read_text())
    require(binding["plan_sha256"] == sha256(plan_path), "Snapshot binding references a different plan")
    for key in ("task_source_commit", "runtime_freeze_commit"):
        require(binding[key] == plan[key], "Snapshot source/freeze differs")
    require(binding["planned_historical_task_digest"] == plan["task_digest"], "Original planned digest differs")
    _, revision, runtime = runtime_contract()
    files = binding["snapshot_file_sha256"]
    require(len(files) == binding["harbor_hashed_file_count"] == 120, "Snapshot package inventory count differs")
    require({name: value for name, value in files.items() if name != "README.md"} == runtime, "Snapshot runtime differs from frozen contract")
    require(revision["version"] == plan["task_version"], "Snapshot task version differs")
    require(binding["snapshot_readme_copy"] == "snapshot-readme.txt", "Unexpected snapshot README path")
    require(sha256(plan_path.parent / "snapshot-readme.txt") == files["README.md"] == binding["snapshot_readme_sha256"], "Snapshot README differs")
    require(binding["difference_from_prior_digest"] == ["README.md"], "Unexpected package digest correction")
    def outer(mapping):
        content = "".join(f"{name}\0{value}\n" for name, value in sorted(mapping.items()))
        return "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    require(outer(files) == binding["actual_snapshot_task_digest"], "Snapshot digest reconstruction failed")
    prior = {**files, "README.md": binding["prior_readme_sha256"]}
    require(outer(prior) == plan["task_digest"], "Historical digest reconstruction failed")
    return {"task_digest": binding["actual_snapshot_task_digest"], "digest_correction": {
        "planned_historical_task_digest": plan["task_digest"], "snapshot_task_digest": binding["actual_snapshot_task_digest"],
        "binding_sha256": sha256(path), "runtime_files_matching_frozen_contract": len(runtime),
        "note": "Original plan digest retained. The executed snapshot differs only in reviewer README.md; both package digests reconstruct from the recorded hashes. The 119 runtime files match the frozen contract."}}


def failure_category(message):
    """Use only structured error messages, never arbitrary model/tool prose."""
    message = message.lower()
    if re.search(r"usage limit|quota|credit balance|insufficient.*credit|rate.?limit|too many requests|overloaded|capacity|429", message):
        return "provider_or_account_limit"
    if re.search(r"context.*(limit|length|exceed)|token.*limit|max.?turn|max.?budget|maximum.*turn", message):
        return "agent_budget_limit"
    if re.search(r"cancelled|canceled|keyboardinterrupt|sigterm|interrupted by", message):
        return "operator_interruption"
    return "harness_error"


def terminal_event(path):
    """Later successful completion supersedes earlier recoverable errors.

    Claude rate_limit_event telemetry and failed tool calls are not terminal.
    Evidence pointers are safe to publish; raw exception messages are not.
    """
    found = None
    if not path.is_file():
        return None
    with path.open(errors="replace") as stream:
        for line_no, line in enumerate(stream, 1):
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            kind = event.get("type")
            state, category = None, None
            if kind == "turn.completed":
                state = "completed"
            elif kind == "turn.failed":
                state, category = "failed", failure_category(json.dumps(event.get("error", {})))
            elif kind == "error":
                state, category = "failed", failure_category(str(event.get("message", "")))
            elif kind == "result":
                if event.get("subtype") == "success" and not event.get("is_error"):
                    state = "completed"
                elif event.get("is_error") or str(event.get("subtype", "")).startswith("error"):
                    state = "failed"
                    category = failure_category(str(event.get("subtype", "")) + " " + json.dumps(event.get("errors", [])) + " " + str(event.get("result", "")))
            if state:
                found = {"state": state, "category": category, "line": line_no}
    return found


def seconds(interval):
    if not isinstance(interval, dict) or not interval.get("started_at") or not interval.get("finished_at"):
        return None
    try:
        value = (datetime.fromisoformat(interval["finished_at"].replace("Z", "+00:00")) - datetime.fromisoformat(interval["started_at"].replace("Z", "+00:00"))).total_seconds()
        return round(value, 3) if value >= 0 else None
    except (ValueError, TypeError):
        return None


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def is_settled(row):
    """A fixed-budget outcome cannot be replaced by another model attempt."""
    return row["status"] == "completed" or (row["status"] == "interrupted" and row["classification"] in BUDGET_OUTCOMES)


def binding_issues(slot, plan, lock, config, result, native_event=None):
    issues = []
    if lock:
        task, agent = lock.get("task", {}), lock.get("agent", {})
        if task.get("version") != plan["task_version"] or task.get("digest") != plan["task_digest"]:
            issues.append("task_version_or_digest_mismatch")
        if lock.get("source_trial") or agent.get("resume_trajectory"):
            issues.append("regrade_or_resumed_attempt")
        verifier = lock.get("verifier", {})
        if verifier.get("disable") is not False or verifier.get("environment_mode") != "separate":
            issues.append("verifier_configuration_mismatch")
    for source, record in (("lock", lock), ("config", config)):
        if not record:
            continue
        agent = record.get("agent", {})
        if agent.get("name") != slot["agent"] or agent.get("model_name") != slot["model_slug"] or agent.get("kwargs", {}).get("reasoning_effort") != "high" or agent.get("kwargs", {}).get("version") != slot["version"]:
            issues.append(f"{source}_agent_configuration_mismatch")
    info = (result or {}).get("agent_info") or {}
    normally_finished = bool((result or {}).get("finished_at") and not (result or {}).get("exception_info") and native_event and native_event["state"] == "completed")
    if normally_finished and not info:
        issues.append("missing_executed_harness_metadata")
    if normally_finished and not info.get("model_info"):
        issues.append("missing_executed_model_metadata")
    if info:
        if info.get("name") != slot["agent"] or info.get("version") != slot["version"]:
            issues.append("executed_harness_mismatch")
        model = info.get("model_info") or {}
        if model and (str(model.get("provider", "")) + "/" + str(model.get("name", ""))) != slot["model_slug"]:
            issues.append("executed_model_mismatch")
    return issues


def classify(result, job_result, launch, event, graded, grader_error, binding_errors):
    finished = bool((result or {}).get("finished_at") or (job_result or {}).get("finished_at") or launch.get("finished_at_utc"))
    if not finished:
        return "running", "awaiting_completion"
    if binding_errors:
        return "infrastructure_error", "evidence_binding_error"
    exception = (result or {}).get("exception_info") or {}
    kind = exception.get("exception_type", "")
    message = str(exception.get("exception_message", ""))
    # Verifier/container failures are infrastructure problems even after an
    # agent interruption; the earlier interruption remains in terminal_event.
    if grader_error or re.search(r"Verifier|Environment|Docker|Container|AgentSetup|ArtifactDownload", kind, re.I):
        return "infrastructure_error", "verifier_or_environment_error"
    if event and event["state"] == "failed" and event["category"] != "harness_error":
        return "interrupted", event["category"]
    category = failure_category(kind + " " + message)
    if exception and category != "harness_error":
        return "interrupted", category
    if re.search(r"AgentTimeout|Cancelled|Canceled|KeyboardInterrupt", kind, re.I):
        return "interrupted", "agent_time_limit" if "Timeout" in kind else "operator_interruption"
    if exception or (event and event["state"] == "failed"):
        return "infrastructure_error", "harness_error"
    if launch.get("exit_code") not in (None, 0):
        return "infrastructure_error", "launcher_nonzero_exit"
    if not result or not result.get("finished_at") or not graded:
        return "infrastructure_error", "missing_completed_grading_evidence"
    if not event or event["state"] != "completed":
        return "infrastructure_error", "missing_native_completion_evidence"
    return "completed", "normal_completion"


def attempt(slot, plan, job_name, launch):
    job = ROOT / "validation/jobs" / job_name
    issues = []
    row = {"trial_id": slot["trial_id"], "attempt_id": job_name, "job_name": job_name,
           "job_path": relative(job), "status": "pending", "classification": "not_started",
           "all_world_ratio": None, "held_out_ratio": None, "overall_reward": None,
           "rewards": None, "artifact_graded": False, "counts_as_model_outcome": False,
           "settled_under_fixed_budget": False, "agent_budget_exhausted": False,
           "launcher_exit_code": launch.get("exit_code"), "credential_scan_matches": launch.get("credential_matches"),
           "launcher_started_at_utc": launch.get("started_at_utc"), "launcher_finished_at_utc": launch.get("finished_at_utc"),
           "note": "", "evidence_issues": issues}
    if not job.is_dir():
        if launch.get("started_at_utc"):
            row["status"] = "infrastructure_error" if launch.get("finished_at_utc") else "running"
            row["classification"] = "launcher_finished_without_job" if row["status"] == "infrastructure_error" else "awaiting_job_creation"
        return row
    job_result = read_json(job / "result.json", issues)
    folders = sorted({p.parent for p in job.glob("*/config.json")} | {p.parent for p in job.glob("*/lock.json")})
    if len(folders) > 1:
        issues.append("multiple_harbor_trials_in_attempt")
    folder = folders[0] if len(folders) == 1 else None
    lock = read_json(folder / "lock.json", issues) if folder else None
    config = read_json(folder / "config.json", issues) if folder else None
    result = read_json(folder / "result.json", issues) if folder else None
    reward = read_json(folder / "verifier/reward.json", issues) if folder else None
    details = read_json(folder / "verifier/details.json", issues) if folder else None
    event_path = folder / "agent" / ("codex.txt" if slot["agent"] == "codex" else "claude-code.txt") if folder else None
    event = terminal_event(event_path) if event_path else None
    binding = binding_issues(slot, plan, lock, config, result, event)
    issues.extend(binding)
    if event:
        row["terminal_event"] = {**event, "evidence": relative(event_path)}
    graded = bool(reward and details and set(reward) == FIELDS and all(number(v) is not None and 0 <= v <= 1 for v in reward.values()))
    row.update(artifact_graded=graded, rewards=reward if graded else None)
    if graded:
        ratios = details.get("total_regret_as_a_multiple_of_the_reference", {})
        row.update(all_world_ratio=number(ratios.get("all_leagues")), held_out_ratio=number(ratios.get("held_out_leagues")), overall_reward=reward["overall"])
        row["worlds"] = {name: {k: value for k, value in entry.items() if k in {"regret", "reference_regret", "seconds", "most_like"}} for name, entry in details.get("leagues", {}).items()}
    status, classification = classify(result, job_result, launch, event, graded, bool(details and "grader_error" in details), binding)
    if status == "completed":
        if reward["overall"] == 1:
            classification = "pass"
        elif reward["constraint_satisfaction"] == reward["artifact_quality"] == 1 and (reward["functional_correctness"] == 0 or reward["robustness"] == 0):
            classification = "forecast_quality_failure"
        else:
            classification = "artifact_or_constraint_failure"
    row.update(status=status, classification=classification, counts_as_model_outcome=status == "completed")
    error_kind = ((result or {}).get("exception_info") or {}).get("exception_type", "")
    row["agent_budget_exhausted"] = bool(
        classification in BUDGET_OUTCOMES
        or re.search(r"AgentTimeout", error_kind, re.I)
        or (event and event["state"] == "failed" and event["category"] == "agent_budget_limit")
    )
    row["settled_under_fixed_budget"] = is_settled(row)
    if status == "interrupted" and classification in BUDGET_OUTCOMES:
        row["note"] = "Agent budget exhausted: this fixed-budget slot is settled and must not be retried. Any artifact grade is retained separately from normal completion."
    elif graded and status != "completed":
        row["note"] = "Artifact was graded; this operationally incomplete attempt is excluded from clean model outcomes."
    elif status == "infrastructure_error":
        row["note"] = "Operational/evidence failure; not attributed to model task ability."
    if folder:
        row["trial_path"] = relative(folder)
        row["evidence_sha256"] = {name: sha256(folder / name) for name in ("lock.json", "config.json", "result.json", "agent/trajectory.json", "verifier/reward.json", "verifier/details.json", "artifacts/app/solution/forecast.py") if (folder / name).is_file()}
        if event_path and event_path.is_file():
            row["evidence_sha256"][event_path.relative_to(folder).as_posix()] = sha256(event_path)
        forecast = folder / "artifacts/app/solution/forecast.py"
        starter = ROOT / "dist/collinear-siddharthshashankkumar/t20-exact-forecast/environment/app/solution/forecast.py"
        if forecast.is_file() and starter.is_file():
            row["forecast_matches_starter"] = sha256(forecast) == sha256(starter)
    if lock:
        row.update(task_version=lock.get("task", {}).get("version"), task_digest=lock.get("task", {}).get("digest"))
    if result:
        usage = result.get("agent_result") or {}
        row["usage"] = {key: number(usage.get(key)) for key in ("n_input_tokens", "n_cache_tokens", "n_output_tokens", "cost_usd")}
        row["seconds"] = {"trial": seconds(result), **{key: seconds(result.get(key)) for key in ("agent_setup", "agent_execution", "verifier")}}
        row["started_at"], row["finished_at"] = result.get("started_at"), result.get("finished_at")
        row["actual_harness_version"] = (result.get("agent_info") or {}).get("version")
    return row


def collect(plan_path=BATCH / "plan.json"):
    plan = json.loads(plan_path.read_text())
    validate_plan(plan)
    binding = snapshot_binding(plan_path, plan)
    # Preserve the original file and its hash; use the proved executed digest
    # for job binding, rather than silently changing the predeclared plan.
    bound_plan = {**plan, "task_digest": binding["task_digest"]}
    issues = []
    launches = read_json(plan_path.parent / "launches.json", issues) or {}
    rows, attempts, assigned = [], [], set()
    for slot in plan["slots"]:
        base = slot["job_name"]
        names = {base, *slot.get("attempt_job_names", [])}
        names.update(p.name for p in (ROOT / "validation/jobs").glob(base + "-retry-*") if re.fullmatch(re.escape(base) + r"-retry-[1-9][0-9]*", p.name))
        names.update(r["job_name"] for r in launches.values() if re.fullmatch(re.escape(base) + r"-retry-[1-9][0-9]*", r.get("job_name", "")))
        names = sorted(names, key=lambda name: 0 if name == base else int(name.rsplit("-", 1)[1]))
        records = []
        for name in names:
            launch = next((r for r in launches.values() if r.get("job_name") == name), {})
            records.append(attempt(slot, bound_plan, name, launch))
            assigned.add(name)
        begun = [r for r in records if r["status"] != "pending" or (ROOT / r["job_path"]).is_dir()]
        completed = [r for r in begun if r["status"] == "completed"]
        if len(completed) > 1:
            issues.append(f"multiple_completed_attempts:{slot['trial_id']}")
        # Even if verification subsequently fails, exhausting the agent budget
        # does not authorize a fresh model attempt. Preserve that first outcome.
        fixed = [r for r in begun if r["status"] == "completed" or r["agent_budget_exhausted"]]
        selected = fixed[0] if fixed else (begun[-1] if begun else records[-1])
        if fixed and fixed[0] is not begun[-1]:
            issues.append(f"retry_after_fixed_budget_outcome:{slot['trial_id']}")
        row = {k: slot[k] for k in ("trial_id", "model", "harness", "model_slug", "reasoning_effort", "replicate")}
        row.update(selected)
        row.update(harness_version=slot["version"], selected_attempt_id=selected["attempt_id"] if selected in begun else None, attempt_ids=[r["attempt_id"] for r in begun])
        rows.append(row)
        attempts.extend(begun)
    unassigned = {p.name for p in (ROOT / "validation/jobs").glob(plan["batch_id"] + "-*") if p.is_dir() and p.name not in assigned}
    unassigned.update(r["job_name"] for r in launches.values() if r.get("job_name", "").startswith(plan["batch_id"] + "-") and r["job_name"] not in assigned)
    issues.extend(f"unassigned_batch_job:{name}" for name in sorted(unassigned))
    counts = dict(Counter(r["status"] for r in rows))
    model_counts = {model: dict(Counter(r["classification"] for r in rows if r["model"] == model)) for model in sorted({r["model"] for r in rows})}
    return {"schema_version": 1, "batch_id": plan["batch_id"], "collected_at_utc": datetime.now(timezone.utc).isoformat(),
            "task_version": plan["task_version"], "relative_tolerance": plan["relative_tolerance"], "planned_trials": 8,
            **binding, "runtime_freeze_commit": plan["runtime_freeze_commit"], "plan_sha256": sha256(plan_path),
            "trials": rows, "attempts": attempts, "status_counts": counts, "model_outcomes": model_counts,
            "settled_trials": sum(is_settled(row) for row in rows),
            "budget_outcomes": dict(Counter(row["classification"] for row in rows if row["status"] == "interrupted" and row["classification"] in BUDGET_OUTCOMES)),
            "evidence_issues": issues,
            "interpretation": "Two predeclared trials per model. Normal completions and agent budget exhaustion settle slots; neither permits a retry. Clean-completion outcomes and budget outcomes are reported separately, with interrupted artifact grades preserved. Provider/account, operator, and infrastructure interruptions remain unsettled. Earlier trials are outside this batch."}


def write_json(path, value):
    """Keep unchanged evidence snapshots byte-stable after rerunning checks.

    These timestamps identify when this substantive snapshot was first written,
    not the latest invocation. A changed result, hash, or audit scope creates a
    new snapshot and retains the fresh timestamp supplied by the caller.
    """
    timestamps = {"collected_at_utc", "audited_at_utc"}
    if path.is_file():
        try:
            previous = json.loads(path.read_text())
        except (ValueError, UnicodeError, OSError):
            previous = None
        if isinstance(previous, dict) and (
            {key: item for key, item in previous.items() if key not in timestamps}
            == {key: item for key, item in value.items() if key not in timestamps}
        ):
            return previous
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=BATCH / "plan.json")
    parser.add_argument("--output", type=Path, default=BATCH / "results.json")
    args = parser.parse_args()
    report = collect(args.plan)
    write_json(args.output, report)
    print(json.dumps({"slots": len(report["trials"]), "attempts": len(report["attempts"]), "status_counts": report["status_counts"], "evidence_issue_count": len(report["evidence_issues"]) + sum(len(r["evidence_issues"]) for r in report["attempts"])}))


if __name__ == "__main__":
    main()
