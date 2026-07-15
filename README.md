# AnytoolAI Platform

This repository contains the AnytoolAI platform monorepo and its current MVP-A/MVP-B implementation.

The repo is intentionally agent-friendly: short `AGENTS.md`, repo-local docs, executable plans,
validation scripts, architecture tests, config validation, CI, and generated documentation are kept
alongside the implementation.

## Quick start

```bash
python scripts/agent/runner.py doctor
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py frontend-check
python scripts/agent/runner.py full-check
```

`python scripts/agent/runner.py <command>` is the canonical cross-platform interface. Use
`python3` where that is the Python 3 executable. `just` recipes are optional thin aliases.
The baseline gate includes:

- config validation
- architecture validation
- a DB-free backend pytest subset

It intentionally excludes frontend checks and any test DB provisioning.
The script self-manages `.quick-check-venv` so it does not need to install packages into a system Python.
It always re-execs into `.quick-check-venv`, even if you started from another active virtualenv.
It strips caller-provided `PYTHONPATH`, so no manual `PYTHONPATH` setup is required.
GitHub Actions runs this same baseline command on both Linux and Windows, and the backend workflow is required on pull requests plus pushes to `main`.

Python dependency management uses `uv`, not `pip`. Use `uv add <package>` for runtime dependencies,
`uv add --dev <package>` for dev dependencies, and do not hand-edit `uv.lock`.

`full-check` runs the baseline, locked frontend compile checks, and the implemented Freelancer suite
tests. Kernel and browser smoke commands will be added only when feature issues deliver real vertical
slices.

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
