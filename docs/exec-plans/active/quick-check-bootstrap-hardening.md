# Execution Plan: Quick-Check Bootstrap Hardening

## Status

- State: completed
- Owner: agent
- Created: 2026-06-16
- Last updated: 2026-06-16

## Goal

Harden the quick-check bootstrap and legacy-venv migration flow so review-discovered edge cases stop resurfacing and the migration behavior is covered by focused tests.

## Scope

### In scope

- Fix legacy quick-check migration so an active `.venv/quick-check` environment is not deleted before creating or re-entering `.quick-check-venv`.
- Add focused tests for quick-check environment detection and migration behavior.
- Re-run focused validation for quick-check bootstrap logic and recent architecture exclusions.

### Out of scope

- Rewriting the quick-check workflow around a different toolchain.
- Broad CI changes outside the current bootstrap logic.
- Frontend or DB-backed validation expansion.

## Relevant docs

- `AGENTS.md`
- `docs/architecture/package-layering.md`
- `docs/exec-plans/active/a03-cross-platform-baseline-checks.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Fix legacy active-venv migration ordering in `scripts/agent/quick_check.py`.
- [x] Add tests for safe cleanup and legacy/new environment detection.
- [x] Run focused pytest coverage for quick-check bootstrap and architecture exclusions.

## Validation

- [x] `.quick-check-venv/bin/python -m pytest tests/test_quick_check.py`
- [x] `.quick-check-venv/bin/python -m pytest tests/architecture/test_no_direct_provider_calls_outside_gateway.py`
- [x] `.quick-check-venv/bin/python -m pytest packages/backend/product-platforms/freelancer-suite/tests`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-16 | Add unit-style tests around `quick_check.py` instead of relying on end-to-end bootstrap behavior alone. | The recent review comments target edge-case control flow that is easy to miss in happy-path validation runs. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-16 | Reviewed the latest MR comment and current `quick_check.py` flow. Confirmed `migrate_legacy_virtualenv()` currently runs before any active-environment guard and can delete the interpreter backing the current process. | Patch migration ordering and add focused tests. |
| 2026-06-16 | Reordered legacy cleanup so active legacy environments survive until re-exec, added focused tests for environment detection and cleanup timing, and re-ran the targeted architecture and bundle regressions. | No further required fix found in the reviewed quick-check bootstrap paths. |

## Open questions

None.

## Follow-up debt

- Consider moving bootstrap helper tests into a dedicated `scripts` test module pattern if more command-entrypoint logic accumulates.
