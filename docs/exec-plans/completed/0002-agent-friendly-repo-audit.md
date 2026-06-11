# Execution Plan: Agent-Friendly Repo Audit

## Status

- State: completed
- Owner: agent
- Created: 2026-06-11
- Last updated: 2026-06-11

## Goal

Assess the current repository against the harness-engineering checklist for an AI-agent friendly repo and identify existing gaps.

## Scope

### In scope

- Repository knowledge map and `AGENTS.md` structure.
- Execution plans and documentation system of record.
- Validation commands and architecture/config checks.
- Local boot, smoke, observability, review, and cleanup harness assets.
- Mechanical enforcement of documented architecture boundaries.

### Out of scope

- Implementing missing checks or product behavior.
- Refactoring application code.
- Changing CI or runtime infrastructure.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Read required architecture and agent-operation docs.
- [x] Run `just doctor`.
- [x] Inventory repo assets against the harness-engineering checklist.
- [x] Report gaps and recommended priority.

## Validation

- [x] `just doctor` attempted; blocked because `just` is not installed/on PATH in the current Windows environment.
- [x] `python scripts/agent/validate_configs.py`
- [x] `python scripts/agent/validate_architecture.py`
- [x] `python -m pytest -q` with explicit local package `PYTHONPATH`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-11 | Keep this as an audit-only plan. | The user asked for a gap check, not implementation changes. |
| 2026-06-11 | Treat direct validator/test results as audit evidence when Bash/just entrypoints are unavailable. | The repo command surface is Bash-first, but this Windows environment has no WSL distro and no `just` executable. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-11 | Created audit plan. | Run baseline checks and inspect mapped assets. |
| 2026-06-11 | Completed checklist audit. Config validation, architecture validation, architecture tests, e2e placeholder tests, and full Python pytest pass when invoked directly. Frontend typecheck, `just`, and Bash wrappers are not locally reproducible in this environment. | Convert selected gaps into implementation plans if requested. |

## Open questions

- None.

## Follow-up debt

- Add Windows-native or documented bootstrap support for `just`/Bash entrypoints.
- Replace placeholder kernel smoke/e2e tests with runtime tests.
- Strengthen frontend CI so typecheck failures are blocking and reproducible.
- Replace generated-doc placeholders with real generated outputs and freshness checks.
