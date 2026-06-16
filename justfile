set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
python_cmd := if os() == "windows" { "py -3" } else { "python3" }

doctor:
    {{python_cmd}} scripts/agent/runner.py doctor

quick-check:
    {{python_cmd}} scripts/agent/runner.py quick-check

full-check:
    {{python_cmd}} scripts/agent/runner.py full-check

validate-configs:
    {{python_cmd}} scripts/agent/runner.py validate-configs

validate-architecture:
    {{python_cmd}} scripts/agent/runner.py validate-architecture

kernel-smoke:
    {{python_cmd}} scripts/agent/runner.py kernel-smoke

generate-docs:
    {{python_cmd}} scripts/agent/runner.py generate-docs

dev-up:
    {{python_cmd}} scripts/agent/runner.py dev-up

dev-down:
    {{python_cmd}} scripts/agent/runner.py dev-down

reset-db:
    {{python_cmd}} scripts/agent/runner.py reset-db
