# Execution Plan: Test Import Boundary Fix For PydanticAI

## Status

- State: completed
- Owner: agent
- Created: 2026-07-04
- Last updated: 2026-07-04

## Goal

Fix the architecture validation failure caused by a direct `pydantic_ai` import in a `platform-actions` test without weakening the documented boundary.

## Scope

### In scope

- Inspect the import-boundary validator.
- Replace the offending test import with an allowed path.
- Run architecture validation and quick-check.

### Out of scope

- Loosening architecture validation rules.
- Changing runtime boundary ownership.

## Relevant docs

- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/exec-plans/active/pydantic-ai-boundary-restoration.md`

## Contracts touched

- Architecture: test import boundary compliance
- Tests: `platform-actions` structured executor coverage

## Implementation steps

- [x] Confirm the failure source in the validator and test file.
- [x] Replace the direct `pydantic_ai` test import with an allowed module reference.
- [x] Run architecture validation and quick-check.

## Validation

- [x] `python scripts/agent/validate_architecture.py`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-04 | Keep the validator unchanged and remove the forbidden test import | The documented boundary already allows `pydantic_ai` only inside `platform-actions/**/structured_llm/**`, not from tests outside that path. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-04 | Confirmed `ATAI006` comes from `from pydantic_ai import UnexpectedModelBehavior` in `test_structured_llm_executor.py` | Replace the import with a symbol reference through the approved structured LLM module |
| 2026-07-04 | Updated the test to reference `UnexpectedModelBehavior` via `anytoolai_platform_actions.structured_llm.pydanticai_runner` and kept the validator unchanged | Run `validate_architecture.py` and `quick_check.py` |

## Open questions

## Follow-up debt
