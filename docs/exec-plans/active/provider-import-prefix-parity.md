# Execution Plan: Provider Import Prefix Parity

## Status

- State: completed
- Owner: agent
- Created: 2026-06-26
- Last updated: 2026-06-26

## Goal

Keep the focused provider-import architecture test aligned with `scripts/agent/validate_architecture.py` so both enforce the same `openai` and `openai.*` import boundary.

## Scope

### In scope

- Update `_imports_openai()` in `tests/architecture/test_no_direct_provider_calls_outside_gateway.py`.
- Run focused validation for the test and architecture validator.

### Out of scope

- Broader validator redesign.
- Changes to unrelated workflows or architecture tests.

## Relevant docs

- `docs/architecture/provider-gateway.md`
- `docs/architecture/package-layering.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Verify the current mismatch between the test helper and architecture validator.
- [x] Update the test helper to use the same prefix rule.
- [x] Run focused validation.

## Validation

- [x] `.quick-check-venv\Scripts\python.exe -m pytest tests/architecture/test_no_direct_provider_calls_outside_gateway.py -q`
- [ ] `.quick-check-venv\Scripts\python.exe scripts/agent/validate_architecture.py`
  Current result: fails for a separate pre-existing scan issue in nested `packages/backend/**/.venv` and `.uv-cache` trees, not from this test change.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-26 | Mirror the validator's prefix rule in the focused test instead of weakening the validator. | The architecture test should enforce the same import boundary the validator already applies. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-26 | Confirmed `_imports_openai()` only matched the bare module while the validator uses `imports_module(..., "openai")` prefix semantics. | Update the AST helper and validate. |
| 2026-06-26 | Updated `_imports_openai()` to catch `openai` and `openai.*`; the focused pytest check passed. The broader validator still fails due to unrelated nested environment/cache scanning under `packages/backend/**`. | None for this finding. |

## Open questions

None.

## Follow-up debt

None.
