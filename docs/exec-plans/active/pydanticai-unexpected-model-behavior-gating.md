# Execution Plan: PydanticAI UnexpectedModelBehavior Gating

## Status

- State: completed
- Owner: agent
- Created: 2026-07-04
- Last updated: 2026-07-04

## Goal

Preserve non-validation `UnexpectedModelBehavior` failures from the PydanticAI runner while still translating validation-retry exhaustion into the existing platform-specific error.

## Scope

### In scope

- Verify the reported exception-wrapping behavior against the current runner.
- Narrow the `UnexpectedModelBehavior` translation gate.
- Add focused regression coverage.

### Out of scope

- Changing executor behavior outside this exception branch.
- Redesigning structured-output retry policy.

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/architecture/package-layering.md`
- `docs/exec-plans/active/pydantic-ai-boundary-restoration.md`

## Contracts touched

- Runtime: PydanticAI validation error translation semantics
- API: none
- DB: none
- Config: none
- Events: none

## Implementation steps

- [x] Confirm the finding against current `pydanticai_runner.py`.
- [x] Restrict `PydanticAIValidationExhaustedError` translation to the validation exhaustion path.
- [x] Add targeted regression coverage and run focused tests.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-04 | Treat `state.pydantic_run_id` as the missing validation-path signal for translation | The runner only sets it once the validator/run context is engaged, so it distinguishes retry exhaustion from unrelated model-behavior failures after a provider response. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-04 | Confirmed current code wraps every `UnexpectedModelBehavior` with any `last_response` present | Patch the gate and add a direct regression test |
| 2026-07-04 | Updated the exception branch and added focused test coverage | Run the platform-actions test file |

## Open questions

## Follow-up debt
