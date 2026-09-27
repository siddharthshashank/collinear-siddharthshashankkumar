"""Focused behavioral checks of the current grader; no container-isolation claim."""
import importlib.util
import io
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("task_grader", ROOT / "harbor/tests/grader.py")
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)

PROGRAM = '''
import argparse,csv
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument("--league")
p.add_argument("--out")
a=p.parse_args()
mode=MODE
values=[0.7,0.3]
if mode=="coin": values=[0.5,0.5]
if mode=="missing": values=values[:1]
if mode=="nan": values=[float("nan"),0.3]
if mode=="outside": values=[1.1,0.3]
if mode=="heldout_bad" and Path(a.league).name!="visible": values=[0.5,0.5]
if mode=="visible_bad" and Path(a.league).name=="visible": values=[0.01,0.99]
if mode=="nondeterministic" and Path(a.league).name=="visible":
 flag=Path("already_visible")
 if flag.exists(): values=[0.7001,0.3]
 flag.write_text("yes")
with open(a.out,"w") as f:
 w=csv.writer(f);w.writerow(["fixture","p_home"])
 for i,q in enumerate(values): w.writerow([i,q])
'''

class VerifierContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        grader.APP = self.base / "app"
        grader.TESTS = self.base / "tests"
        grader.WORK = self.base / "work"
        grader.RUN_AS = ""  # Local functional probe, not a private-file isolation test.
        (grader.APP / "solution").mkdir(parents=True)
        (grader.APP / "engine").mkdir()
        (grader.APP / "engine/model.py").write_text("# pristine\n")
        (grader.TESTS / "pristine/engine").mkdir(parents=True)
        (grader.TESTS / "pristine/engine/model.py").write_text("# pristine\n")
        (grader.TESTS / "private").mkdir()
        (grader.TESTS / "private/bar.json").write_text(json.dumps({"clip":0.002,"relative_tolerance":0.1,"absolute_tolerance":0.0}))
        for name in ("visible", *(f"heldout_{c}" for c in "abcdefg")):
            public = grader.TESTS / "leagues" / name
            private = grader.TESTS / "private" / name
            public.mkdir(parents=True)
            private.mkdir()
            (public / "fixtures.csv").write_text("fixture\n0\n1\n")
            (private / "truth.csv").write_text("fixture,p_home\n0,0.7\n1,0.3\n")
            (private / "reference.json").write_text(json.dumps({"regret":0.07,"coin_flip_regret":0.0822828785}))
            (private / "tiers.csv").write_text("fixture,reference,coin flip\n0,0.7,0.5\n1,0.3,0.5\n")

    def tearDown(self):
        self.tmp.cleanup()

    def run_mode(self, mode):
        (grader.APP / "solution/forecast.py").write_text(PROGRAM.replace("MODE", repr(mode)))
        return grader.grade()

    def test_known_probabilities_pass(self):
        reward, _ = self.run_mode("correct")
        self.assertTrue(all(value == 1.0 for value in reward.values()))

    def test_coin_flip_is_valid_but_fails_forecasting(self):
        reward, _ = self.run_mode("coin")
        self.assertEqual(reward["overall"], 0)
        self.assertEqual(reward["artifact_quality"], 1)
        self.assertEqual(reward["constraint_satisfaction"], 1)

    def test_missing_fixture_fails(self):
        reward, _ = self.run_mode("missing")
        self.assertEqual(reward["artifact_quality"], 0)
        self.assertEqual(reward["overall"], 0)

    def test_nonfinite_probability_fails(self):
        reward, _ = self.run_mode("nan")
        self.assertEqual(reward["artifact_quality"], 0)
        self.assertEqual(reward["overall"], 0)

    def test_out_of_range_probability_fails(self):
        reward, _ = self.run_mode("outside")
        self.assertEqual(reward["artifact_quality"], 0)

    def test_engine_edit_prevents_full_pass(self):
        (grader.APP / "engine/model.py").write_text("# edited\n")
        reward, detail = self.run_mode("correct")
        self.assertEqual(reward["functional_correctness"], 1)
        self.assertLess(reward["overall"], 1)
        self.assertFalse(detail["engine_untouched"])

    def test_changed_repeat_prevents_full_pass(self):
        reward, detail = self.run_mode("nondeterministic")
        self.assertEqual(reward["functional_correctness"], 1)
        self.assertLess(reward["overall"], 1)
        self.assertFalse(detail["deterministic"])

    def test_heldout_rule_cannot_be_carried_by_visible_world(self):
        reward, _ = self.run_mode("heldout_bad")
        self.assertEqual(reward["functional_correctness"], 1)
        self.assertEqual(reward["robustness"], 0)
        self.assertEqual(reward["overall"], 0.5)

    def test_visible_failure_is_not_hidden_by_heldout_success(self):
        reward, _ = self.run_mode("visible_bad")
        self.assertEqual(reward["functional_correctness"], 0)
        self.assertEqual(reward["robustness"], 1)
        self.assertEqual(reward["overall"], 0)

    def test_missing_program_fails(self):
        reward, _ = grader.grade()
        self.assertEqual(reward["overall"], 0)
        self.assertEqual(reward["artifact_quality"], 0)

    def test_log_score_known_value_and_clipping(self):
        # Independent hand-calculable Bernoulli KL at p=.7, q=.5.
        import math
        expected = .7 * math.log(1.4) + .3 * math.log(.6)
        self.assertAlmostEqual(grader.regret(np.array([.7]),np.array([.5]),.002),expected)
        self.assertEqual(grader.regret(np.array([.7]),np.array([.7]),.002),0)
        self.assertTrue(math.isfinite(grader.regret(np.array([.7]),np.array([0.]),.002)))

if __name__ == "__main__":
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(VerifierContract))
    output = stream.getvalue()
    print(output, end="")
    summary = {"grader_sha256": hashlib.sha256((ROOT / "harbor/tests/grader.py").read_bytes()).hexdigest(), "status":"passed" if result.wasSuccessful() else "failed","tests":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
               "scope":"Current grader behavior on tiny synthetic fixtures. Does not test network, privilege isolation, process cleanup or the simulator; separate hardening tests cover specific regressions.",
               "output":output}
    (ROOT / "validation/verifier-contract.json").write_text(json.dumps(summary,indent=2)+"\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
