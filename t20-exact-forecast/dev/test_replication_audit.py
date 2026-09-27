"""Regression tests for evidence accounting; no model or verifier is executed.

Synthetic Harbor records exercise native completion, interruption, and retry
handling. Archived oracle/failing verifier records supply already-validated
grades, so these tests do not duplicate the scoring implementation.
"""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_replication as auditor
import collect_replication as collector

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "validation/replication-20260927"
PLAN = BATCH / "plan.json"


def grade_files(job):
    matches = list((ROOT / "validation/jobs" / job).glob("*/verifier/reward.json"))
    if len(matches) != 1:
        raise ValueError(f"Expected one archived grading fixture: {job}")
    return matches[0], matches[0].with_name("details.json")


class ReplicationAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.declared_plan = json.loads(PLAN.read_text())
        cls.grades = {
            "pass": [json.loads(path.read_text()) for path in grade_files("revision-oracle")],
            "fail": [json.loads(path.read_text()) for path in grade_files("revision-gpt55-high")],
        }

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="replication-accounting-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for module in (collector, auditor):
            replacement = patch.object(module, "ROOT", self.root)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.batch = self.root / "validation/replication-20260927"
        self.batch.mkdir(parents=True)
        self.plan_path = self.batch / "plan.json"
        self.plan_path.write_text(json.dumps(self.declared_plan))
        self.folders = {}
        for slot in self.declared_plan["slots"]:
            self.make_attempt(slot)
        self.target = self.folders["gpt55-r1"]

    @staticmethod
    def put(path, value):
        path.write_text(json.dumps(value) + "\n")

    def make_attempt(self, slot, suffix="", outcome="pass"):
        folder = self.root / "validation/jobs" / (slot["job_name"] + suffix) / "trial"
        for child in ("agent", "verifier", "artifacts/app/solution"):
            (folder / child).mkdir(parents=True)
        agent = {"name": slot["agent"], "model_name": slot["model_slug"],
                 "kwargs": {"reasoning_effort": "high", "version": slot["version"]}}
        self.put(folder / "config.json", {"agent": agent})
        self.put(folder / "lock.json", {"agent": agent,
            "task": {"version": "0.1.1", "digest": self.declared_plan["task_digest"]},
            "verifier": {"disable": False, "environment_mode": "separate"}})
        provider, model = slot["model_slug"].split("/", 1)
        reward, details = copy.deepcopy(self.grades[outcome])
        result = {"started_at": "2026-09-27T10:00:00Z", "finished_at": "2026-09-27T10:03:00Z",
            "exception_info": None,
            "agent_execution": {"started_at": "2026-09-27T10:00:00Z", "finished_at": "2026-09-27T10:01:00Z"},
            "agent_info": {"name": slot["agent"], "version": slot["version"],
                           "model_info": {"provider": provider, "name": model}},
            "verifier_result": {"rewards": reward}}
        self.put(folder / "result.json", result)
        self.put(folder / "verifier/reward.json", reward)
        self.put(folder / "verifier/details.json", details)
        self.put(folder / "agent/trajectory.json", {"steps": [{"source": "agent", "message": "Synthetic accounting fixture."}]})
        event = {"type": "turn.completed"} if slot["agent"] == "codex" else {"type": "result", "subtype": "success", "is_error": False}
        native = "codex.txt" if slot["agent"] == "codex" else "claude-code.txt"
        self.put(folder / "agent" / native, event)
        (folder / "artifacts/app/solution/forecast.py").write_text("# Synthetic archive placeholder; never executed.\n")
        if not suffix:
            self.folders[slot["trial_id"]] = folder
        return folder

    def set_grade(self, outcome):
        reward, details = copy.deepcopy(self.grades[outcome])
        self.put(self.target / "verifier/reward.json", reward)
        self.put(self.target / "verifier/details.json", details)
        result = json.loads((self.target / "result.json").read_text())
        result["verifier_result"] = {"rewards": reward}
        self.put(self.target / "result.json", result)

    def interrupt(self, kind, message="", native=None):
        result = json.loads((self.target / "result.json").read_text())
        result["exception_info"] = {"exception_type": kind, "exception_message": message}
        result["agent_execution"]["finished_at"] = "2026-09-27T13:00:00Z"
        result["finished_at"] = "2026-09-27T13:03:00Z"
        self.put(self.target / "result.json", result)
        self.put(self.target / "agent/codex.txt", native or {"type": "thread.started"})

    def collected(self):
        return collector.collect(self.plan_path)

    def settled_audit(self):
        return auditor.audit(self.plan_path, require_settled=True)

    def test_completed_passes_are_accepted(self):
        report = auditor.audit(self.plan_path, require_complete=True)
        self.assertEqual(report["clean_model_outcomes"], {"pass": 8})
        self.assertTrue(report["all_slots_normally_completed"])
        self.assertTrue(self.settled_audit()["all_slots_settled"])

    def test_completed_failure_is_an_outcome_not_an_operational_error(self):
        self.set_grade("fail")
        report = self.settled_audit()
        self.assertEqual(report["clean_model_outcomes"], {"forecast_quality_failure": 1, "pass": 7})
        self.assertEqual(self.collected()["trials"][0]["overall_reward"], 0)

    def test_time_budget_settles_but_is_not_normal_completion(self):
        self.interrupt("AgentTimeoutError", "Agent execution timed out after 10800 seconds")
        report = self.settled_audit()
        self.assertEqual(report["budget_outcomes"], {"agent_time_limit": 1})
        self.assertEqual(report["clean_model_outcomes"], {"pass": 7})
        self.assertFalse(report["all_slots_normally_completed"])
        with self.assertRaisesRegex(ValueError, "normally completed"):
            auditor.audit(self.plan_path, require_complete=True)

    def test_native_context_budget_settles(self):
        self.interrupt("NonZeroAgentExitCodeError", "maximum context length exceeded",
                       {"type": "turn.failed", "error": {"message": "maximum context length exceeded"}})
        self.assertEqual(self.settled_audit()["budget_outcomes"], {"agent_budget_limit": 1})

    def test_provider_interruption_retains_grade_but_does_not_settle(self):
        self.set_grade("fail")
        # A terminal native error still matters when Harbor's exception field
        # is empty: a saved artifact is not evidence of normal completion.
        self.put(self.target / "agent/codex.txt", {"type": "turn.failed", "error": {"message": "You've hit your usage limit"}})
        row = self.collected()["trials"][0]
        self.assertEqual(row["classification"], "provider_or_account_limit")
        self.assertTrue(row["artifact_graded"])
        self.assertEqual(row["overall_reward"], 0)
        self.assertFalse(row["counts_as_model_outcome"])
        with self.assertRaisesRegex(ValueError, "settled slots"):
            self.settled_audit()

    def test_recovered_provider_error_does_not_override_later_completion(self):
        events = [{"type": "turn.failed", "error": {"message": "rate limit"}}, {"type": "turn.completed"}]
        (self.target / "agent/codex.txt").write_text("\n".join(json.dumps(event) for event in events))
        self.assertEqual(self.settled_audit()["clean_model_outcomes"], {"pass": 8})

    def test_operator_cancellation_does_not_settle(self):
        self.interrupt("CancelledError", "operator cancelled")
        self.assertEqual(self.collected()["trials"][0]["classification"], "operator_interruption")
        with self.assertRaisesRegex(ValueError, "settled slots"):
            self.settled_audit()

    def test_verifier_failure_does_not_settle(self):
        self.interrupt("VerifierTimeoutError", "verifier timeout")
        self.assertEqual(self.collected()["trials"][0]["status"], "infrastructure_error")
        with self.assertRaisesRegex(ValueError, "settled slots"):
            self.settled_audit()

    def test_budget_outcome_requires_grading_evidence(self):
        self.interrupt("AgentTimeoutError")
        (self.target / "verifier/reward.json").unlink()
        with self.assertRaisesRegex(ValueError, "completed grading"):
            self.settled_audit()

    def test_missing_terminal_result_cannot_settle(self):
        (self.target / "result.json").unlink()
        self.assertEqual(self.collected()["trials"][0]["status"], "running")
        with self.assertRaisesRegex(ValueError, "settled slots"):
            self.settled_audit()

    def test_completed_execution_requires_model_identity(self):
        result = json.loads((self.target / "result.json").read_text())
        result["agent_info"].pop("model_info")
        self.put(self.target / "result.json", result)
        self.assertIn("missing_executed_model_metadata", self.collected()["trials"][0]["evidence_issues"])
        with self.assertRaisesRegex(ValueError, "binding"):
            self.settled_audit()

    def assert_retry_cannot_replace(self, expected):
        self.make_attempt(self.declared_plan["slots"][0], suffix="-retry-1", outcome="pass")
        report = self.collected()
        self.assertEqual(report["trials"][0]["classification"], expected)
        self.assertEqual(len(report["trials"][0]["attempt_ids"]), 2)
        self.assertIn("retry_after_fixed_budget_outcome:gpt55-r1", report["evidence_issues"])
        with self.assertRaisesRegex(ValueError, "retry evidence"):
            self.settled_audit()

    def test_completed_failure_cannot_be_replaced_by_passing_retry(self):
        self.set_grade("fail")
        self.assert_retry_cannot_replace("forecast_quality_failure")
        self.assertEqual(self.collected()["trials"][0]["overall_reward"], 0)

    def test_budget_exhaustion_cannot_be_replaced_by_passing_retry(self):
        self.interrupt("AgentTimeoutError")
        self.assert_retry_cannot_replace("agent_time_limit")

    def test_later_verifier_error_does_not_reauthorize_budget_retry(self):
        self.interrupt("VerifierTimeoutError", "verifier timeout",
                       {"type": "turn.failed", "error": {"message": "maximum context length exceeded"}})
        self.assertTrue(self.collected()["trials"][0]["agent_budget_exhausted"])
        self.assert_retry_cannot_replace("verifier_or_environment_error")

    def test_launcher_only_retry_is_retained(self):
        self.interrupt("NonZeroAgentExitCodeError", "usage limit")
        name = self.declared_plan["slots"][0]["job_name"] + "-retry-1"
        self.put(self.batch / "launches.json", {"retry": {"job_name": name,
            "started_at_utc": "2026-09-27T14:00:00Z", "finished_at_utc": "2026-09-27T14:01:00Z",
            "exit_code": 1, "credential_matches": 0}})
        row = self.collected()["trials"][0]
        self.assertEqual(row["selected_attempt_id"], name)
        self.assertEqual(len(row["attempt_ids"]), 2)
        self.assertEqual(row["classification"], "launcher_finished_without_job")
        self.assertEqual(row["credential_scan_matches"], 0)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.append({"name": test._testMethodName, "outcome": "passed"})

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.outcomes.append({"name": test._testMethodName, "outcome": "failed"})

    def addError(self, test, error):
        super().addError(test, error)
        self.outcomes.append({"name": str(test), "outcome": "error"})


def main():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReplicationAccounting)
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
    print(stream.getvalue(), end="")
    helpers = ("dev/test_replication_audit.py", "dev/collect_replication.py", "dev/audit_replication.py",
               "dev/audit_revision.py", "dev/runtime_contract.py")
    fixtures = [PLAN, *grade_files("revision-oracle"), *grade_files("revision-gpt55-high")]
    report = {"status": "passed" if result.wasSuccessful() else "failed", "tests": result.testsRun,
              "failures": len(result.failures), "errors": len(result.errors),
              "scope": "Synthetic Harbor/native-event accounting records with archived oracle/failing grade fixtures. Checks classification, fixed-budget settlement, missing evidence, and attempt retention. Does not execute models, regrade forecasts, or test container isolation.",
              "helper_sha256": {name: collector.sha256(ROOT / name) for name in helpers},
              "fixture_sha256": {path.relative_to(ROOT).as_posix(): collector.sha256(path) for path in fixtures},
              "test_results": result.outcomes}
    collector.write_json(BATCH / "accounting-tests.json", report)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
