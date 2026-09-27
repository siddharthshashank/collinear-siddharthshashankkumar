"""Check completed v0.1.1 evidence without rerunning jobs or requiring model failure."""
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from audit_submission import FIELDS, ROOT, TASK, require, read_record
from runtime_contract import verify_runtime

JOBS = ("revision-oracle", "revision-nop", "revision-replay-gpt55", "revision-gpt55-high")
WORLDS = {"visible", *(f"heldout_{c}" for c in "abcdefg")}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    """Match the packager's evidence exclusions, while checking every copied file."""
    return {p.relative_to(folder).as_posix(): digest(p) for p in sorted(folder.rglob("*"))
            if p.is_file() and not any(part in {"sessions", "__pycache__"} for part in p.parts)
            and p.suffix != ".pyc" and p.name != ".DS_Store"}


def trial_lock(job, freeze, version):
    paths = list((ROOT / "validation/jobs" / job).glob("*/lock.json"))
    require(len(paths) == 1, f"Expected one trial lock: {job}")
    lock = json.loads(paths[0].read_text())
    require(lock["task"]["version"] == version, f"Wrong runtime version: {job}")
    require(lock["task"]["digest"] == freeze["task_digest"], f"Wrong task digest: {job}")
    require(lock["verifier"]["environment_mode"] == "separate" and not lock["verifier"]["disable"], f"Verifier configuration differs: {job}")
    return paths[0].parent, lock


def grading_consistency(job, reward, details):
    require(set(reward) == FIELDS and "grader_error" not in details, f"Invalid grading evidence: {job}")
    require(all(isinstance(v, (int, float)) and math.isfinite(v) and 0 <= v <= 1 for v in reward.values()), f"Nonfinite/out-of-range reward: {job}")
    require(reward["functional_correctness"] in (0, 1) and reward["robustness"] in (0, 1), f"Nonbinary grading gate: {job}")
    require(set(details["leagues"]) == WORLDS, f"Incomplete worlds: {job}")
    bar = json.loads((TASK / "tests/private/bar.json").read_text())
    require(details["bar"] == bar, f"Scoring rule differs: {job}")
    references = {name: json.loads((TASK / "tests/private" / name / "reference.json").read_text()) for name in WORLDS}
    valid = set()
    for name, entry in details["leagues"].items():
        require(math.isfinite(entry["seconds"]) and entry["seconds"] >= 0, f"Invalid timing: {job}/{name}")
        if "regret" in entry:
            require(math.isfinite(entry["regret"]) and entry["regret"] >= 0, f"Invalid regret: {job}/{name}")
            require(entry["reference_regret"] == references[name]["regret"], f"Reference differs: {job}/{name}")
            require(not entry.get("problem"), f"Invalid forecast has a scored regret: {job}/{name}")
            valid.add(name)
        else:
            require(bool(entry.get("problem")), f"Unexplained missing forecast: {job}/{name}")
    require(reward["artifact_quality"] == round(len(valid) / len(WORLDS), 4), f"Artifact fraction differs: {job}")
    ratios = details["total_regret_as_a_multiple_of_the_reference"]
    ambiguous = []
    for names, key, field in ((WORLDS, "all_leagues", "functional_correctness"), (WORLDS - {"visible"}, "held_out_leagues", "robustness")):
        if not names <= valid:
            require(ratios[key] is None and reward[field] == 0, f"Invalid group received a verdict: {job}/{key}")
            continue
        total = sum(details["leagues"][name]["regret"] for name in names)
        ref = sum(references[name]["regret"] for name in names)
        require(ref > 0 and isinstance(ratios[key], (int, float)) and math.isfinite(ratios[key]), f"Invalid aggregate ratio: {job}/{key}")
        # Per-world regrets have five decimals; published ratios have three.
        # Use their rounding intervals so a legitimate near-boundary verdict is
        # never reversed solely by reconstruction from rounded records.
        error = len(names) * 0.000005 + 1e-12
        lower, upper = max(0.0, total - error), total + error
        require(abs(total / ref - ratios[key]) <= error / ref + 0.0005 + 1e-12, f"Aggregate ratio differs: {job}/{key}")
        limit = ref * (1 + bar["relative_tolerance"]) + bar["absolute_tolerance"]
        if upper < limit:
            require(reward[field] == 1, f"Clear passing score marked failed: {job}/{key}")
        elif lower > limit:
            require(reward[field] == 0, f"Clear failing score marked passed: {job}/{key}")
        else:
            ambiguous.append(key)
    coin = round(sum(v["coin_flip_regret"] for v in references.values()) / sum(v["regret"] for v in references.values()), 3)
    require(ratios["coin_flip_for_comparison"] == coin, f"Coin-flip comparison differs: {job}")
    overall = round(reward["functional_correctness"] * (0.5 * reward["robustness"] + 0.25 * reward["constraint_satisfaction"] + 0.25 * reward["artifact_quality"]), 4)
    require(overall == reward["overall"], f"Overall formula differs: {job}")
    return ambiguous


def trial(job, freeze, version):
    folder, lock = trial_lock(job, freeze, version)
    result = json.loads((folder / "result.json").read_text())
    require(result.get("finished_at") and not result.get("exception_info"), f"Unfinished/infrastructure exception is not model evidence: {job}")
    reward = json.loads((folder / "verifier/reward.json").read_text())
    details = json.loads((folder / "verifier/details.json").read_text())
    rounding_ambiguous = grading_consistency(job, reward, details)
    require(result["verifier_result"]["rewards"] == reward, f"Result/reward mismatch: {job}")
    return folder, lock, result, reward, details, rounding_ambiguous


def clean_builds():
    folder = ROOT / "validation/clean-builds"
    report = json.loads((folder / "report.json").read_text())
    require(report["status"] == "passed", "Clean-build report failed")
    require(len(report["builds"]) == 2 and {b["role"] for b in report["builds"]} == {"agent", "verifier"}, "Expected both build roles")
    closure = {}
    for build in report["builds"]:
        role = build["role"]
        context = TASK / ("environment" if role == "agent" else "tests")
        require(build["exit_code"] == build["freeze_exit_code"] == 0, f"Build/package inspection failed: {role}")
        require(build["dockerfile_sha256"] == digest(context / "Dockerfile") and build["requirements_lock_sha256"] == digest(context / "requirements.lock"), f"Stale build inputs: {role}")
        require(build["log"] == f"{role}.build.log" and build["freeze_file"] == f"{role}.pip-freeze.txt", f"Unexpected build evidence path: {role}")
        log = folder / build["log"]
        require(digest(log) == build["log_sha256"] and log.stat().st_size == build["log_bytes"], f"Build log differs: {role}")
        files = inventory(context)
        context_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        require(context_hash == build["context_sha256"] and len(files) == build["context_file_count"], f"Build context differs: {role}")
        installed = {}
        for line in (folder / build["freeze_file"]).read_text().splitlines():
            match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", line)
            require(match is not None and match[1].lower() not in installed, f"Invalid installed-package inventory: {role}")
            installed[match[1].lower()] = match[2]
        declared = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s]+)", (context / "requirements.lock").read_text(), re.M))
        require(len(declared) == 5, f"Expected five task dependencies: {role}")
        require(installed == report["package_versions"], f"Installed inventory differs from report: {role}")
        require({k: v for k, v in installed.items() if k != "pip"} == declared, f"Installed inventory differs from dependency lock: {role}")
        require(build["image"]["os"] == "linux" and build["image"]["architecture"] == "amd64", f"Build platform differs: {role}")
        closure[role] = installed
    require(closure["agent"] == closure["verifier"], "Agent/verifier package inventories differ")
    return {"status": "passed", "roles": sorted(closure), "package_versions": closure["agent"], "scope": report["scope"]}


def fresh_execution(folder, lock, result):
    require(not lock.get("source_trial") and not lock["agent"].get("resume_trajectory"), "A regrade/resumed trajectory is not a fresh model trial")
    execution = result.get("agent_execution") or {}
    require(execution.get("started_at") and execution.get("finished_at"), "Fresh trial has no completed agent execution")
    require(datetime.fromisoformat(execution["started_at"].replace("Z", "+00:00")) < datetime.fromisoformat(execution["finished_at"].replace("Z", "+00:00")), "Invalid fresh agent execution interval")
    trajectory = json.loads((folder / "agent/trajectory.json").read_text())
    require(any(step.get("source") == "agent" for step in trajectory.get("steps", [])), "Fresh trial has no agent trajectory")
    require((folder / "artifacts/app/solution/forecast.py").is_file(), "Fresh trial has no delivered program")


def audit_revision():
    runtime = verify_runtime(TASK)
    freeze = json.loads((ROOT / "validation/revision-freeze.json").read_text())
    require(freeze["version"] == runtime["runtime_version"] and freeze["fresh_target_job"] == "revision-gpt55-high", "Freeze version/job differs")
    require(re.fullmatch(r"sha256:[0-9a-f]{64}", freeze["task_digest"]) is not None, "Missing frozen task digest")
    grader_hash = digest(TASK / "tests/grader.py")
    for file, count in (("verifier-contract.json", 11), ("verifier-hardening.json", 13)):
        check = json.loads((ROOT / "validation" / file).read_text())
        require(check["status"] == "passed" and check["tests"] == count and check["failures"] == check["errors"] == 0 and check["grader_sha256"] == grader_hash, f"Stale or failing checks: {file}")
    network = json.loads((ROOT / "validation/network-isolation.json").read_text())
    require(network["containers"] and all(c["network_mode"] == "none" and c["nano_cpus"] == 2_000_000_000 and c["memory_bytes"] == 4_294_967_296 for c in network["containers"]), "Network/resources not established")
    records = {job: trial(job, freeze, runtime["runtime_version"]) for job in JOBS}
    _, oracle_lock, _, oracle, _, _ = records["revision-oracle"]
    _, nop_lock, _, nop, _, _ = records["revision-nop"]
    require(oracle_lock["agent"]["name"] == "oracle" and nop_lock["agent"]["name"] == "nop", "Control agent identity differs")
    require(all(v == 1 for v in oracle.values()), "Oracle must pass every component")
    require(nop == {"overall": 0.0, "functional_correctness": 0.0, "robustness": 0.0, "constraint_satisfaction": 1.0, "artifact_quality": 1.0}, "No-op control changed")
    _, replay_lock, replay_result, replay, replay_details, _ = records["revision-replay-gpt55"]
    require(replay_lock.get("source_trial", {}).get("action") == "regrade" and replay_result.get("agent_execution") is None, "Replay is not identified as an artifact regrade")
    historical = next((ROOT / "jobs/2026-09-23__20-04-36").glob("*/verifier"))
    require(replay == read_record(historical / "reward.json"), "Archived artifact rewards changed")
    require(replay_details["total_regret_as_a_multiple_of_the_reference"] == read_record(historical / "details.json")["total_regret_as_a_multiple_of_the_reference"], "Archived artifact regret ratios changed")
    folder, lock, result, reward, details, ambiguous = records["revision-gpt55-high"]
    agent = json.loads((folder / "config.json").read_text())["agent"]
    require(agent["name"] == "codex" and agent["model_name"] == "openai/gpt-5.5" and agent["kwargs"]["reasoning_effort"] == "high", "Fresh target configuration differs")
    require(lock["agent"]["name"] == agent["name"] and lock["agent"]["model_name"] == agent["model_name"] and lock["agent"]["kwargs"]["reasoning_effort"] == "high", "Fresh configuration/lock mismatch")
    fresh_execution(folder, lock, result)
    copied_count = 0
    for job in JOBS:
        source, copied = inventory(ROOT / "validation/jobs" / job), inventory(TASK / "validation/jobs" / job)
        require(source and copied == source, f"Packaged current evidence differs: {job}")
        copied_count += len(source)
    require(digest(ROOT / "dev/regrade_archived.py") == digest(TASK / "reviewer_tools/regrade_archived.py"), "Packaged regrade helper differs")
    builds = clean_builds()
    require(inventory(ROOT / "validation/clean-builds") == inventory(TASK / "validation/clean-builds"), "Packaged clean-build evidence differs")
    # Record either outcome. A legitimate pass must never become an audit error.
    fresh = {"job": "revision-gpt55-high", "kind": "fresh_model_trial", "reward": reward,
             "ratios": details.get("total_regret_as_a_multiple_of_the_reference"),
             "forecast_quality_failure": reward["functional_correctness"] == 0 and reward["constraint_satisfaction"] == reward["artifact_quality"] == 1,
             "rounding_ambiguous_verdict_groups": ambiguous,
             "model": agent["model_name"], "harness": agent["name"], "reasoning_effort": "high"}
    return {"status": "passed", **runtime, "runtime_freeze_commit": freeze["commit"],
            "harbor_task_digest": freeze["task_digest"], "current_evidence_files_preserved": copied_count,
            "contract_tests": 11, "hardening_tests": 13, "oracle": oracle, "nop": nop,
            "clean_builds": builds,
            "historical_replay": {"kind": "artifact_regrade_not_model_trial", "reward": replay,
                                  "ratios": replay_details["total_regret_as_a_multiple_of_the_reference"],
                                  "recorded_reward_and_ratios_preserved": True},
            "fresh_target": fresh}


if __name__ == "__main__":
    report = audit_revision()
    (ROOT / "validation/revision-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"Revision audit passed: oracle=1, no-op=0, replay unchanged; fresh target overall={report['fresh_target']['reward']['overall']}")
