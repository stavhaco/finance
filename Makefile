.PHONY: test cycle dry-cycle dashboard enrich enrich-loop sim help

REPO_ROOT := $(CURDIR)
export PYTHONPATH := $(REPO_ROOT)
PY ?= $(REPO_ROOT)/.venv/bin/python

help:
	@echo "Targets: test | cycle | dry-cycle | dashboard | enrich | enrich-loop | sim"

test:
	$(PY) -m unittest discover -s tests -v

cycle:
	./scripts/mac/run_cycle.sh

dry-cycle:
	DEMO_TRADER_DRY_RUN=1 $(PY) -m demo_trader --once --dry-run

dashboard:
	./scripts/mac/run_dashboard.sh

enrich:
	$(PY) -m demo_trader.enrich_worker --limit 12

enrich-loop:
	$(PY) -m demo_trader.enrich_worker --loop --limit 8 --sleep-sec 20

sim:
	DEMO_TRADER_SIMULATION=1 DEMO_TRADER_SIM_INGEST_LIVE=0 $(PY) -m demo_trader --once
