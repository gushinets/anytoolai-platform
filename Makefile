PYTHON := $(shell command -v python3 2>/dev/null || command -v python)

.PHONY: doctor quick-check frontend-check full-check validate-configs validate-architecture validate-docs generate-docs check-generated-docs dev-up dev-ready dev-status dev-down prod-up prod-status prod-down collect-context

doctor:
	$(PYTHON) scripts/agent/runner.py doctor

quick-check:
	$(PYTHON) scripts/agent/runner.py quick-check

frontend-check:
	$(PYTHON) scripts/agent/runner.py frontend-check

full-check:
	$(PYTHON) scripts/agent/runner.py full-check

validate-configs:
	$(PYTHON) scripts/agent/runner.py validate-configs

validate-architecture:
	$(PYTHON) scripts/agent/runner.py validate-architecture

validate-docs:
	$(PYTHON) scripts/agent/runner.py validate-docs

generate-docs:
	$(PYTHON) scripts/agent/runner.py generate-docs

check-generated-docs:
	$(PYTHON) scripts/agent/runner.py generate-docs --check

dev-up:
	$(PYTHON) scripts/agent/runner.py dev-up

dev-ready:
	$(PYTHON) scripts/agent/runner.py dev-ready

dev-status:
	$(PYTHON) scripts/agent/runner.py dev-status

dev-down:
	$(PYTHON) scripts/agent/runner.py dev-down

prod-up:
	$(PYTHON) scripts/agent/runner.py prod-up

prod-status:
	$(PYTHON) scripts/agent/runner.py prod-status

prod-down:
	$(PYTHON) scripts/agent/runner.py prod-down

collect-context:
	$(PYTHON) scripts/agent/runner.py collect-context
