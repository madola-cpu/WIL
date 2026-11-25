# Measured impact engine (steps 4-9). On Windows without make, run the python commands directly.
PY ?= python
DATA ?= tests/fixtures/mini

.PHONY: setup fixture test run validate check

setup:
	$(PY) -m pip install pytest jsonschema

fixture:
	$(PY) tests/fixtures/make_mini.py

test:
	$(PY) -m pytest -q --tb=short

check:
	$(PY) -m engine.validate $(DATA)

run:
	$(PY) -m engine.cli run $(DATA)

validate:
	$(PY) -m engine.cli score $(DATA)
