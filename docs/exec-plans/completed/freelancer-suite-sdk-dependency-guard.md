# Execution Plan: Freelancer Suite SDK Dependency Guard

## Status

- State: completed
- Owner: agent
- Created: 2026-06-16
- Last updated: 2026-06-16

## Goal

Ensure `anytoolai-freelancer-suite` declares its required SDK dependency and add a regression test so standalone installs do not silently break while shared check environments continue to pass.

## Scope

### In scope

- Add explicit package metadata dependency from `freelancer-suite` to `platform-sdk`.
- Add a test that asserts the dependency remains declared in package metadata.
- Re-run focused validation for the bundle package tests.

### Out of scope

- Broad packaging standardization across all future product bundles.
- Changing quick-check baseline scope.
- Publishing/versioning policy beyond the current local package contract.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/architecture/package-layering.md`
- `docs/exec-plans/active/a03-cross-platform-baseline-checks.md`

## Contracts touched

- API: none
- DB: none
- Config: Python package metadata for `freelancer-suite`
- Events: none
- Frontend: none

## Implementation steps

- [x] Add `anytoolai-platform-sdk` dependency to `freelancer-suite` package metadata.
- [x] Extend bundle tests to assert the dependency is declared.
- [x] Run focused bundle validation and capture any remaining gaps.

## Validation

- [x] `.quick-check-venv/bin/python -m pytest packages/backend/product-platforms/freelancer-suite/tests`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-16 | Guard the fix with a metadata test instead of depending on installer behavior in `full-check`. | The shared quick-check environment already installs `platform-sdk`, so import-only tests do not prove standalone package metadata is correct. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-16 | Reviewed MR feedback, package metadata, bundle imports, and `runner.py` install flow. Confirmed `full-check` can mask a missing SDK dependency because the environment is already primed. | Apply metadata + test fix, then run focused validation. |
| 2026-06-16 | Added explicit SDK dependency and a metadata regression test; focused bundle pytest passed with 2 tests green. | No further required fix found for this review note. |

## Open questions

None.

## Follow-up debt

- If more installable product bundles are added, extract a shared packaging checklist or architecture test for required local SDK dependencies.
