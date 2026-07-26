PYTHON ?= $(shell \
	for candidate in python3 python; do \
		bin="$$(command -v $$candidate 2>/dev/null)"; \
		if [ -n "$$bin" ] && "$$bin" -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 12) else 1)' >/dev/null 2>&1; then \
			echo "$$bin"; \
			exit 0; \
		fi; \
	done \
)

ifeq ($(strip $(PYTHON)),)
$(error No Python 3.12+ interpreter found (checked python3, python); set PYTHON=/path/to/python3.12+ or install Python 3.12+)
endif

.PHONY: doctor quick-check frontend-check full-check validate-configs validate-architecture validate-docs generate-docs check-generated-docs dev-up dev-ready dev-status dev-down collect-context

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
	$(PYTHON) scripts/agent/runner.py dev-down

prod-status:
	$(PYTHON) scripts/agent/runner.py prod-status

prod-down:
	$(PYTHON) scripts/agent/runner.py prod-down

collect-context:
	$(PYTHON) scripts/agent/runner.py collect-context
