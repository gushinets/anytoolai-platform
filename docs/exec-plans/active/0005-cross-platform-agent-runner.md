# Execution Plan: Cross-Platform Agent Runner

## Status

- State: active
- Owner: agent
- Created: 2026-06-14
- Last updated: 2026-06-14

## Goal

Make agent and local utility commands run on Windows, Linux, and CI without requiring Bash, WSL, or Git Bash.

## Scope

### In scope

- Add a Python runner for agent validation and local utility commands.
- Point `just`, Make, Bash wrappers, and CI workflows at the Python runner.
- Document the shell-independent fallback command.

### Out of scope

- Frontend dependency reproducibility.
- Real kernel smoke implementation beyond the current placeholder tests.
- Runtime API, DB, config, or product behavior changes.
- Replacing Docker Compose as the local service backend.

## Relevant docs

- `AGENTS.md`
- `docs/agent/harness-engineering-map.md`
- `docs/agent/codex-operating-model.md`
- `docs/architecture/package-layering.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Add remaining `generate-docs` and dev utility subcommands.
- [x] Add `scripts/agent/runner.py` with validation subcommands.
- [x] Update `justfile`, `Makefile`, shell wrappers, and CI workflows to call the runner.
- [x] Update repo docs with the Python fallback command.
- [x] Run direct runner checks and available public command checks.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py full-check`
- [x] `python scripts/agent/runner.py kernel-smoke`
- [x] `just doctor`
- [x] `just quick-check`
- [x] `just generate-docs`
- [x] `just reset-db`
- [x] `just --summary`
- [x] `python scripts/agent/runner.py generate-docs`
- [x] `python scripts/agent/runner.py reset-db`
- [x] `python scripts/agent/runner.py -h`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-14 | Use Python as the canonical validation runner. | Python is already required by backend checks and works cross-platform without shell-specific syntax. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-14 | Baseline `just doctor` failed locally because `just` is not on PATH in this shell. | Add runner and update command entrypoints. |
| 2026-06-14 | Added Python runner, updated command entrypoints, and validated direct runner checks. | Verify `just` commands in an environment where `just` is on PATH. |
| 2026-06-14 | Added Windows shell configuration for Just and verified `just doctor` plus `just quick-check`. | Ready for review. |
| 2026-06-14 | Identified remaining Bash-backed recipes: `generate-docs`, `dev-up`, `dev-down`, and `reset-db`. | Extend the runner to own all `just` recipes. |
| 2026-06-14 | Added `generate-docs`, `dev-up`, `dev-down`, and `reset-db` runner commands and removed Bash-backed Just recipes. | Avoid running Docker lifecycle commands unless explicitly needed. |

## Open questions

- None.

## Follow-up debt

- Add frontend dependency lock/bootstrap in a separate slice.
- Replace placeholder smoke tests with executable kernel smoke flows in MVP-A runtime slices.
- Replace the placeholder DB reset with a real cross-platform migration/reset flow when the runtime database contract is ready.
