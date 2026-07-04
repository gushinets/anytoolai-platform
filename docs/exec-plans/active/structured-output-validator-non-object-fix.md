# Execution Plan: Structured Output Validator Non-Object Fix

## Status

- State: completed
- Owner: agent
- Created: 2026-07-04
- Last updated: 2026-07-04

## Goal

Allow `validate_structured_output` to honor `requires_object=False` for parsed non-object JSON values while preserving object-only behavior by default.

## Scope

### In scope

- Verify the reported bug against current code.
- Apply the smallest validator/type fix.
- Add a focused regression test.

### Out of scope

- Changing finalizer behavior for persisted structured-output artifacts.
- Broad structured-output contract redesign.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/package-layering.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: `validate_structured_output` return shape typing
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Verify the finding against current validator logic.
- [x] Update validator enforcement and typing for non-object outputs.
- [x] Add targeted regression coverage and run focused validation.

## Validation

- [ ] `just quick-check`
- [ ] `just validate-configs`
- [ ] `just validate-architecture`
- [ ] `just kernel-smoke`
- [x] Focused `pytest` for `test_structured_output.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-04 | Skip `just doctor` and `just`-based validation commands | `just` is not installed in the current environment, so use repo-documented fallbacks and targeted validation instead. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-04 | Confirmed validator still unconditionally rejects non-dict outputs after parse | Patch validator and add a focused regression test |
| 2026-07-04 | Applied minimal validator/type fix and added regression coverage | Run targeted pytest validation |

## Open questions

## Follow-up debt
