# Execution Plan: UV Bootstrap And Main Rebase

## Status

- State: completed
- Owner: agent
- Created: 2026-06-17
- Last updated: 2026-06-17

## Goal

Replace remaining direct `pip` usage in the repo's Python bootstrap/check flows with `uv`-based commands, then rebase the current branch onto `main`.

## Scope

### In scope

- Update repo-local bootstrap/check scripts that still invoke `pip`.
- Add or update focused tests for the new `uv` command paths.
- Validate the changed scripts as far as the local environment allows.
- Rebase the current branch onto `main`.

### Out of scope

- Broad Python packaging redesign beyond the current bootstrap flow.
- Dependency version changes unrelated to the `uv` migration.
- Frontend, DB, or product behavior changes.

## Relevant docs

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/core-beliefs.md`
- `docs/architecture/package-layering.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Replace direct `pip` invocations in `scripts/agent/quick_check.py` and `scripts/agent/runner.py`.
- [x] Add focused regression tests for the `uv` install path.
- [x] Run available validation commands or document environment blockers.
- [x] Rebase the working branch onto `main`.

## Validation

- [x] `python3 scripts/agent/runner.py doctor` (fails in this environment: Python 3.10, missing `pytest`, `yaml`, `pydantic`, and `uv`)
- [ ] `python3 -m pytest tests/test_quick_check.py tests/test_runner.py` (not runnable here because `pytest` is unavailable)
- [ ] `python3 scripts/agent/runner.py quick-check` (not runnable here because the environment lacks Python 3.12 and `uv`)
- [x] `python3 -m py_compile scripts/agent/quick_check.py scripts/agent/runner.py tests/test_quick_check.py tests/test_runner.py`
- [x] `git diff --check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-17 | Keep the existing quick-check bootstrap structure and swap installer commands to `uv` rather than redesigning package topology in the same change. | The user request is targeted at replacing `pip`, and a narrow migration keeps the diff reviewable. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-17 | Read required architecture docs, confirmed `just` is unavailable in this environment, and located the remaining direct `pip` usage in `scripts/agent/quick_check.py` and `scripts/agent/runner.py`. | Patch the scripts, add focused tests, validate, and rebase. |
| 2026-06-17 | Migrated the remaining direct install calls to `uv`, updated CI to bootstrap `uv`, added focused regression tests, and rebased `cross-platform` onto `origin/main`. | Share the result and note the local validation blockers caused by the current Python/tooling environment. |

## Open questions

None.

## Follow-up debt

- Consider teaching `doctor` to report `uv` availability more explicitly if it becomes a hard repo requirement for all contributors.
