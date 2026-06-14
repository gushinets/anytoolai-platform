set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

doctor:
    python scripts/agent/runner.py doctor

quick-check:
    python scripts/agent/runner.py quick-check

full-check:
    python scripts/agent/runner.py full-check

validate-configs:
    python scripts/agent/runner.py validate-configs

validate-architecture:
    python scripts/agent/runner.py validate-architecture

kernel-smoke:
    python scripts/agent/runner.py kernel-smoke

generate-docs:
    python scripts/agent/runner.py generate-docs

dev-up:
    python scripts/agent/runner.py dev-up

dev-down:
    python scripts/agent/runner.py dev-down

reset-db:
    python scripts/agent/runner.py reset-db
