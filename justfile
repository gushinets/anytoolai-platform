set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]
python_cmd := if os() == "windows" { "python" } else { "python3" }

doctor:
    {{python_cmd}} scripts/agent/runner.py doctor

quick-check:
    {{python_cmd}} scripts/agent/runner.py quick-check

frontend-check:
    {{python_cmd}} scripts/agent/runner.py frontend-check

full-check:
    {{python_cmd}} scripts/agent/runner.py full-check

validate-configs:
    {{python_cmd}} scripts/agent/runner.py validate-configs

validate-architecture:
    {{python_cmd}} scripts/agent/runner.py validate-architecture

validate-docs:
    {{python_cmd}} scripts/agent/runner.py validate-docs

generate-docs:
    {{python_cmd}} scripts/agent/runner.py generate-docs

check-generated-docs:
    {{python_cmd}} scripts/agent/runner.py generate-docs --check

dev-up:
    {{python_cmd}} scripts/agent/runner.py dev-up

dev-down:
    {{python_cmd}} scripts/agent/runner.py dev-down

collect-context:
    {{python_cmd}} scripts/agent/runner.py collect-context
