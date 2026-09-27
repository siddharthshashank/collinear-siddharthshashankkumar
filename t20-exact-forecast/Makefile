PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
PYTHON ?= python3.12
COPIES ?= 100000
T = dist/collinear-siddharthshashankkumar/t20-exact-forecast

.PHONY: venv data bar package validate audit submission
venv:          ## one-time: a local environment with the pinned libraries
	$(PYTHON) -m venv .venv && .venv/bin/pip install -q --require-hashes -r harbor/requirements.lock
data:          ## leagues, exact truth, reference regret, careless tiers (about 25 minutes at the default from Saturday's test)
	$(PY) dev/make_task_data.py --copies $(COPIES)
bar:           ## what the pass bar has to absorb
	$(PY) dev/bar_analysis.py --leagues 8 --copies 40000
validate:      ## simulated league against the real targets
	$(PY) dev/validate_world.py
package:
	$(PY) package_task.py
audit:
	$(PY) dev/audit_submission.py
	$(PY) dev/test_verifier_contract.py
	$(PY) dev/test_verifier_hardening.py
	$(PY) dev/audit_revision.py
	$(PY) dev/audit_fable_matchups.py
	$(PY) dev/test_replication_audit.py
	$(PY) dev/audit_replication.py --require-settled --check-package
submission: package audit
	$(PY) dev/build_submission.py
