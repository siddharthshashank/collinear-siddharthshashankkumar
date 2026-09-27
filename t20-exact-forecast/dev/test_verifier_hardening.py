"""Regression tests for concrete false passes and a false negative in v0.1.0.

Local tests use synthetic fixtures; the separate Docker probe checks the actual
root/runner file boundary. Neither is a comprehensive sandbox-security audit.
"""
import io
import hashlib
import json
import os
import subprocess
import time
import unittest
from unittest.mock import patch

import pandas as pd

from test_verifier_contract import PROGRAM, ROOT, VerifierContract, grader


class VerifierHardening(unittest.TestCase):
    def setUp(self):
        self.fixture = VerifierContract()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def run_program(self, after_write):
        source = PROGRAM.replace("MODE", repr("correct")) + "\n" + after_write
        (grader.APP / "solution/forecast.py").write_text(source)
        return grader.grade()

    def test_repeat_nonzero_exit_prevents_full_credit(self):
        reward, detail = self.run_program(
            'if Path(a.out).name == "visible_again.csv": raise SystemExit(42)\n'
        )
        self.assertFalse(detail["deterministic"])
        self.assertFalse(detail["repeat"]["process_succeeded"])
        self.assertIn("42", detail["repeat"]["problem"])
        self.assertLess(reward["overall"], 1.0)

    def test_rewriting_both_outputs_cannot_hide_changed_predictions(self):
        reward, detail = self.run_program('''
if Path(a.out).name == "visible_again.csv":
    changed = "fixture,p_home\\n0,0.3\\n1,0.7\\n"
    Path(a.out).write_text(changed)
    Path(a.out).with_name("visible.csv").write_text(changed)
''')
        # The first forecast was [.7, .3] and was scored with zero regret. The
        # repeat replaced that evidence with [.3, .7] before comparison.
        self.assertEqual(detail["leagues"]["visible"]["regret"], 0)
        after = pd.read_csv(grader.WORK / "out/visible.csv")
        self.assertEqual(after.p_home.tolist(), [.3, .7])
        self.assertFalse(detail["deterministic"])
        self.assertLess(reward["overall"], 1.0)

    def test_same_fixture_predictions_reordered_receive_full_credit(self):
        reward, detail = self.run_program('''
if Path(a.out).name == "visible_again.csv":
    rows = Path(a.out).read_text().splitlines()
    Path(a.out).write_text("\\n".join([rows[0], *reversed(rows[1:])]) + "\\n")
''')
        first = pd.read_csv(grader.WORK / "out/visible.csv").set_index("fixture").p_home
        again = pd.read_csv(grader.WORK / "out/visible_again.csv").set_index("fixture").p_home
        self.assertEqual(first.to_dict(), again.to_dict())
        self.assertTrue(detail["deterministic"])
        self.assertEqual(reward["functional_correctness"], 1.0)
        self.assertEqual(reward["overall"], 1.0)

    def test_artifact_symlink_to_private_truth_is_rejected_before_copy(self):
        (grader.APP / "solution/private").symlink_to(grader.TESTS / "private", target_is_directory=True)
        reward, detail = self.run_program("")
        self.assertEqual(reward["overall"], 0)
        self.assertIn("link or special file", detail["submission_error"])
        self.assertFalse((grader.WORK / "run/solution/private").exists())

    def test_output_symlink_to_private_truth_is_rejected(self):
        reward, detail = self.run_program(f'''
Path(a.out).unlink()
Path(a.out).symlink_to(Path({str(grader.TESTS / "private")!r}) / Path(a.league).name / "truth.csv")
''')
        self.assertEqual(reward["overall"], 0)
        self.assertEqual(reward["artifact_quality"], 0)
        self.assertTrue(all("could not read" in entry["problem"] for entry in detail["leagues"].values()))

    def test_output_directory_symlink_is_rejected(self):
        out = grader.WORK / "out"
        grader.WORK.mkdir()
        out.symlink_to(grader.TESTS / "private/visible", target_is_directory=True)
        with self.assertRaises(OSError):
            grader.read_forecast(out / "truth.csv", pd.Index([0, 1]))

    def test_output_fifo_is_rejected_without_waiting_for_a_writer(self):
        reward, _ = self.run_program('import os\nPath(a.out).unlink()\nos.mkfifo(a.out)\n')
        self.assertEqual(reward["overall"], 0)
        self.assertEqual(reward["artifact_quality"], 0)

    def test_extra_fixture_is_rejected(self):
        reward, _ = self.run_program('with open(a.out, "a") as f: f.write("99,0.5\\n")\n')
        self.assertEqual(reward["overall"], 0)
        self.assertEqual(reward["artifact_quality"], 0)

    def test_duplicate_fixture_is_rejected(self):
        reward, _ = self.run_program('with open(a.out, "a") as f: f.write("0,0.7\\n")\n')
        self.assertEqual(reward["overall"], 0)
        self.assertEqual(reward["artifact_quality"], 0)

    def test_added_engine_file_prevents_full_credit(self):
        (grader.APP / "engine/extra.py").write_text("# added\n")
        reward, detail = self.run_program("")
        self.assertFalse(detail["engine_untouched"])
        self.assertLess(reward["overall"], 1)

    def test_special_file_artifact_is_rejected(self):
        os.mkfifo(grader.APP / "solution/pipe")
        reward, detail = self.run_program("")
        self.assertEqual(reward["overall"], 0)
        self.assertIn("link or special file", detail["submission_error"])

    def test_timeout_kills_child_in_same_process_group(self):
        marker = self.fixture.base / "child_survived"
        child = f"import time; from pathlib import Path; time.sleep(1.2); Path({str(marker)!r}).write_text('alive')"
        (grader.APP / "solution/forecast.py").write_text(
            f"import subprocess,sys,time\nsubprocess.Popen([sys.executable,'-c',{child!r}])\ntime.sleep(10)\n"
        )
        with patch.object(grader, "SECONDS_PER_LEAGUE", .5):
            ok, seconds, problem = grader.run_forecaster(grader.APP, self.fixture.base, self.fixture.base / "out.csv")
        self.assertFalse(ok)
        self.assertEqual(seconds, .5)
        self.assertIn("no forecast", problem)
        time.sleep(1.3)
        self.assertFalse(marker.exists())

    def test_startup_failure_replaces_stale_success_with_zero_and_error(self):
        logs = self.fixture.base / "logs"
        logs.mkdir()
        (logs / "reward.json").write_text('{"overall":1.0}')
        (logs / "details.json").write_text('{"old_result":true}')
        binary = self.fixture.base / "bin"
        binary.mkdir()
        python = binary / "python"
        python.write_text("#!/bin/sh\nexit 17\n")
        python.chmod(0o755)
        script = self.fixture.base / "test.sh"
        script.write_text((ROOT / "harbor/tests/test.sh").read_text().replace("/logs/verifier", str(logs)))
        env = dict(os.environ, PATH=f"{binary}:{os.environ['PATH']}")
        subprocess.run(["bash", str(script)], env=env, capture_output=True, check=True)
        self.assertEqual(json.loads((logs / "reward.json").read_text())["overall"], 0)
        detail = json.loads((logs / "details.json").read_text())
        self.assertIn("status 17", detail["grader_error"])
        self.assertNotIn("old_result", detail)


if __name__ == "__main__":
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(VerifierHardening)
    )
    output = stream.getvalue()
    print(output, end="")
    summary = {"grader_sha256": hashlib.sha256((ROOT / "harbor/tests/grader.py").read_bytes()).hexdigest(), 
        "status": "passed" if result.wasSuccessful() else "failed",
        "tests": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "security_assurance": False,
        "scope": "Tiny local fixtures, with privilege dropping disabled. Tests reject concrete previously accepted invalid submissions and accept reordered valid forecasts. Container privilege isolation is tested separately. Historical model trials are not rerun here.",
        "remaining_limits": [
            "Repeatability is checked only on the visible world.",
            "Process-group cleanup does not contain a deliberately detached process; a stronger boundary requires PID or cgroup supervision.",
            "These targeted checks are not a complete adversarial sandbox audit.",
        ],
        "output": output,
    }
    (ROOT / "validation/verifier-hardening.json").write_text(json.dumps(summary, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
