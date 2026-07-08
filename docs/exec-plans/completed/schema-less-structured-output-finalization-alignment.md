# Execution Plan: Schema-less Structured Output Finalization Alignment

## Status

- State: completed
- Owner: agent
- Created: 2026-07-04
- Last updated: 2026-07-04

## Goal

Make schema-less structured LLM responses behave the same whether artifact persistence is configured or not.

## Scope

### In scope

- Verify current executor/finalizer behavior for `response_schema is None`.
- Align the artifact and no-artifact paths with a minimal code change.
- Add focused regression coverage.

### Out of scope

- Redesigning structured artifact contracts for non-object payloads.
- Changing schema-backed validation behavior.

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/exec-plans/active/a08-structured-output-finalization-pipeline.md`

## Contracts touched

- Runtime: structured-output finalization control flow
- Artifacts: schema-less response persistence behavior
- API: none
- DB: none

## Implementation steps

- [x] Confirm the inconsistency against current executor and finalizer code.
- [x] Align `response_schema is None` handling between artifact and non-artifact execution paths.
- [x] Add targeted regression coverage and run focused validation.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_structured_output.py -q`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-04 | Skip finalizer invocation when `response_schema` is `None` | This matches the existing no-artifact executor behavior and avoids widening artifact helper contracts or changing schema-backed validation semantics. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-04 | Verified the finding: artifact-enabled execution still forced object validation through `StructuredOutputFinalizer.finalize()` when `response_schema` was absent | Patch executor control flow and add a regression test |
| 2026-07-04 | Updated `_finalize_response` to bypass finalization for schema-less responses and added artifact-branch coverage | Run focused tests |

## Open questions

## Follow-up debt
