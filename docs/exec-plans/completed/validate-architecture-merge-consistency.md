# Execution Plan: Validate Architecture Merge Consistency

## Status

- State: completed
- Owner: agent
- Created: 2026-06-26
- Last updated: 2026-06-26

## Goal

Prevent `scripts/agent/validate_architecture.py` from failing in PR merge refs due to a partial merge between the older `CODE_EXTS`-based validator and the newer skip-list-based validator.

## Scope

### In scope

- Add the smallest safe compatibility layer needed in `scripts/agent/validate_architecture.py`.
- Validate the script and focused architecture tests locally.

### Out of scope

- Reworking the broader architecture validator design.
- Changing workflow commands or unrelated test behavior.

## Relevant docs

- `docs/architecture/package-layering.md`
- `docs/architecture/provider-gateway.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Confirm the CI failure is caused by a mixed merge state of `validate_architecture.py`.
- [x] Add compatibility definitions so old merge-preserved references still resolve.
- [x] Run focused validation.

## Validation

- [x] `.quick-check-venv\Scripts\python.exe scripts/agent/validate_architecture.py`
- [x] `.quick-check-venv\Scripts\python.exe -m pytest tests/architecture -q`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-26 | Fix the merge break with compatibility definitions instead of a larger validator rewrite. | The immediate CI failure is a missing symbol in a mixed merge ref, so the smallest durable fix is to preserve that symbol. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-26 | Confirmed GitHub Actions is testing the PR merge ref and that the failing runtime still references `iter_code_files` and `CODE_EXTS`. | Add compatibility definitions in the local branch and validate. |
| 2026-06-26 | Added compatibility constants for the older `CODE_EXTS` path and passed the architecture validator plus the focused architecture pytest suite locally. | None. |

## Open questions

None.

## Follow-up debt

None.
