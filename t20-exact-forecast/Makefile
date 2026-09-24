PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
COPIES ?= 100000
T = dist/collinear-siddharthshashankkumar/t20-exact-forecast

.PHONY: venv data bar package validate
venv:          ## one-time: a local environment with the pinned libraries
	python3 -m venv .venv && .venv/bin/pip install -q -r harbor/requirements.lock
data:          ## leagues, exact truth, reference regret, careless tiers (about 25 minutes at the default from Saturday's test)
	$(PY) dev/make_task_data.py --copies $(COPIES)
bar:           ## what the pass bar has to absorb
	$(PY) dev/bar_analysis.py --leagues 8 --copies 40000
validate:      ## simulated league against the real targets
	$(PY) dev/validate_world.py
package:
	$(PY) package_task.py