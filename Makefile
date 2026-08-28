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

.PHONY: doctor quick-check frontend-check full-check validate-configs validate-architecture validate-docs generate-docs check-generated-docs dev-up dev-ready dev-status dev-down dev-smoke live-canary prod-up prod-ready prod-status prod-down prod-smoke collect-context

# doctor is the one target that stays on the bare $(PYTHON) interpreter (never `uv run`): its own
# job is diagnosing a broken/incomplete environment (missing modules, missing uv itself), so it
# must still run and report something useful even when the environment it's reporting on can't
# support `uv run` at all.
doctor:
	$(PYTHON) scripts/agent/runner.py doctor

# Every other target uses `uv run python`, not $(PYTHON): most runner.py commands (validate-*,
# collect-context, dev-*, ...) import real project packages (pyyaml, pydantic, sqlalchemy,
# pytest, the editable backend packages, ...) directly in the current interpreter -- they need
# the caller's environment to already have them, which a bare $(PYTHON) (e.g. a system python3)
# does not guarantee. `uv run` resolves/syncs the project's own environment first, so every
# target behaves the same way regardless of which Python happened to be first on PATH.
# atoms-proof/live-canary are a further exception: they launch their proof subprocess with
# .quick-check-venv's own python explicitly (ANY-390), not the caller's interpreter -- `uv run`
# here only resolves runner.py's own import environment, not the child process it spawns, so
# `.quick-check-venv` still needs bootstrapping via quick-check first.
# (quick-check/full-check are the exception that still works either way: they self-bootstrap
# their own separate `.quick-check-venv` -- `uv run` on top of that is harmless, just resolves
# uv's own `.venv` first before quick_check.py re-execs into `.quick-check-venv`.)
quick-check:
	uv run python scripts/agent/runner.py quick-check

frontend-check:
	uv run python scripts/agent/runner.py frontend-check

full-check:
	uv run python scripts/agent/runner.py full-check

validate-configs:
	uv run python scripts/agent/runner.py validate-configs

validate-architecture:
	uv run python scripts/agent/runner.py validate-architecture

validate-docs:
	uv run python scripts/agent/runner.py validate-docs

generate-docs:
	uv run python scripts/agent/runner.py generate-docs

check-generated-docs:
	uv run python scripts/agent/runner.py generate-docs --check

dev-up:
	uv run python scripts/agent/runner.py dev-up

dev-ready:
	uv run python scripts/agent/runner.py dev-ready

dev-status:
	uv run python scripts/agent/runner.py dev-status

dev-down:
	uv run python scripts/agent/runner.py dev-down

dev-smoke:
	uv run python scripts/agent/runner.py dev-smoke

# Costs real money (real OpenAI calls) -- needs OPENAI_API_KEY and ANYTOOLAI_LIVE_CANARY_TOKEN set;
# never part of quick-check/full-check/postgresql-check. See scripts/agent/live_canary.py.
live-canary:
	uv run python scripts/agent/runner.py live-canary

prod-up:
	uv run python scripts/agent/runner.py prod-up

prod-ready:
	uv run python scripts/agent/runner.py prod-ready

prod-status:
	uv run python scripts/agent/runner.py prod-status

prod-down:
	uv run python scripts/agent/runner.py prod-down

prod-smoke:
	uv run python scripts/agent/runner.py prod-smoke

collect-context:
	uv run python scripts/agent/runner.py collect-context
