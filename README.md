# AnytoolAI Agent-First Starter Repo

This is the first-commit starter repository for AnytoolAI MVP-A and MVP-B.

The repo is intentionally agent-friendly: short `AGENTS.md`, repo-local docs, executable plans, validation scripts, architecture tests, config validation, CI templates, and generated documentation placeholders are included from day one.

## Quick start

```bash
just doctor
just quick-check
just validate-configs
just validate-architecture
```

`just` is the preferred human-facing command interface.

`just quick-check` is the baseline backend gate. It includes:

- config validation
- architecture validation
- a DB-free backend pytest subset

It intentionally excludes frontend checks, `tests/e2e`, `kernel-smoke`, and any test DB provisioning.
The script self-manages `.quick-check-venv` so it does not need to install packages into a system Python.
It always re-execs into `.quick-check-venv`, even if you started from another active virtualenv.

On systems where `just` or shell integration is unavailable, run the Python baseline entrypoint directly:

```bash
python3 scripts/agent/quick_check.py
```

Windows fallback:

```powershell
py -3 scripts/agent/quick_check.py
```

Other Python-owned commands still route through the runner:

```bash
python3 scripts/agent/runner.py doctor
python3 scripts/agent/runner.py full-check
```

`just full-check` runs the same baseline first and then runs `tests/e2e`.
Today those e2e placeholders are DB-free, so no extra test DB settings are required.
When DB-backed e2e coverage is added, it must use an explicit test-only database configuration; `quick-check` will remain DB-free and must not provision or select a test DB implicitly.

## MVPs

- MVP-A: Platform Kernel — execution runtime for typed atoms, workflows, scenario sessions, artifacts, events, guest quota, email capture, and handoff.
- MVP-B: Freelancer Validation Bundle v0 — eight thin Freelancer CE-first products added through configs, prompts, schemas, workflows, result renderers, handoff maps, product events, and separate Chrome Extension wrappers.

## First places to read

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/core-beliefs.md`
- `docs/agent/harness-engineering-map.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-b-freelancer-validation-bundle.md`
