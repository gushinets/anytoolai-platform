# Execution Plan: Source-of-Truth Alignment

## Status

- State: completed
- Owner: agent
- Created: 2026-06-11
- Last updated: 2026-06-11

## Goal

Validate and align repo-local guidance, architecture docs, product specs, and related scaffold with the concept source file at `D:\Work\AI\AnytoolAI\platform concept\anytoolai-mvp-a-platform-kernel-and-mvp-b-freelancer-validation-bundle.md`.

## Scope

### In scope

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/**`
- Config and package scaffold that directly encodes MVP-A/MVP-B scope, action names, product order, DB/runtime boundaries, frontend boundaries, and validation rules.

### Out of scope

- Implementing runtime behavior beyond documentation/config alignment.
- Replacing placeholder application code unless it contradicts the source.
- Changing the external concept file.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/*`
- `docs/product-specs/*`
- `docs/agent/*`

## Contracts touched

- API: docs only
- DB: docs only
- Config: docs/config validation audit only
- Events: docs only
- Frontend: docs only

## Implementation steps

- [x] Read the source concept file and extract controlling requirements.
- [x] Run baseline repo validation or direct substitutes if local command wrappers are unavailable.
- [x] Compare AGENTS, architecture docs, product specs, generated docs, and related scaffold.
- [x] Patch concrete drift in repo-local source-of-truth files.
- [x] Re-run targeted validation.

## Validation

- [x] `just doctor` attempted; blocked because `just` is not installed/on PATH in this Windows environment.
- [x] `python scripts/agent/validate_configs.py`
- [x] `python scripts/agent/validate_architecture.py`
- [x] `python -m pytest -q` with local package `PYTHONPATH`
- [x] targeted text searches for source requirements
- [x] `pnpm -r typecheck` attempted; blocked because local `node_modules` / `tsc` are missing.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-11 | Treat the external concept markdown as controlling source for this alignment pass. | User explicitly identified it as source of truth for this repo. |
| 2026-06-11 | Mirror the controlling source into a repo-local summary. | Future agents must be able to work from repo context without relying on external files. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-11 | Created alignment plan. | Compare repo docs and patch drift. |
| 2026-06-11 | Aligned root guidance, product specs, architecture docs, generated docs, kernel demo config, event taxonomy, validation scripts/tests, and MVP-B scaffold with the source file. | Move plan to completed. |

## Open questions

- None.

## Follow-up debt

- Implement real migration DDL for the source-aligned runtime tables.
- Implement the source-aligned MVP-A API surface beyond the current health route.
- Replace placeholder e2e smoke tests with real one-action, three-action, quota, and handoff flows.
- Install or document local `just`/Bash and frontend dependency bootstrap for Windows.
