# Execution Plan: Provider Import Guard Coverage For Tests And Scripts

## Status

- State: completed
- Owner: agent
- Created: 2026-06-26
- Last updated: 2026-06-26

## Goal

Tighten the architecture guard so direct provider SDK imports are checked in `tests/` and `scripts/` as well as the main codebase.

## Scope

### In scope

- Remove the overbroad `tests` and `scripts` exclusions from the provider-import architecture test.
- Run focused validation for the updated guard.

### Out of scope

- Changing the provider-import rule itself.
- Refactoring unrelated architecture tests or scripts.

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

- [x] Verify the finding against current code.
- [x] Remove `tests` and `scripts` from the skip list.
- [x] Run targeted validation.

## Validation

- [x] `pytest tests/architecture/test_no_direct_provider_calls_outside_gateway.py`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-26 | Keep the change limited to path filtering. | The current guard logic is correct; only its coverage is too narrow. |
| 2026-06-26 | Use AST-based import detection inside the existing test. | Removing the `tests` exclusion made the old substring check self-match on its own assertion text. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-26 | Confirmed `SKIP_PATH_PARTS` still excludes `tests` and `scripts`, so the finding is valid. | Remove those exclusions and validate the test. |
| 2026-06-26 | Removed the exclusions, replaced substring matching with real import parsing, and passed focused plus baseline validation. | None. |

## Open questions

None.

## Follow-up debt

None.
