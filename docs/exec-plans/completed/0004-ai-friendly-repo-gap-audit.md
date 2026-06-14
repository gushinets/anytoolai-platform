# Execution Plan: AI-Friendly Repo Gap Audit

## Status

- State: completed
- Owner: agent
- Created: 2026-06-14
- Last updated: 2026-06-14

## Goal

Audit the current repository against the AI-friendly repo checklist and report existing gaps sorted by recommended fix order.

## Scope

### In scope

- Root agent guidance and repo-local source of truth.
- Validation commands and local reproducibility.
- CI checks and mechanical architecture enforcement.
- Runtime smoke tests, local boot, observability, review, and cleanup harness.
- Docs, generated docs, execution plans, and maintenance files.

### Out of scope

- Implementing fixes.
- Changing application runtime behavior.
- Creating GitHub issues or PRs.

## Relevant docs

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Read current repo guidance and source docs.
- [x] Run baseline validation commands.
- [x] Inspect checklist coverage.
- [x] Report prioritized gaps.

## Validation

- [x] `just doctor` failed locally because `just` is not installed.
- [x] `python scripts/agent/validate_configs.py`
- [x] `python scripts/agent/validate_architecture.py`
- [x] `python -m pytest -q`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-14 | Keep this as audit-only. | User asked for gap analysis sorted by recommended fixes. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-14 | Created audit plan. | Complete checklist inspection and report. |
| 2026-06-14 | Completed checklist inspection and validation pass. | Move plan to completed and report prioritized gaps. |

## Open questions

- None.

## Follow-up debt

- Convert selected gaps into implementation execution plans.
