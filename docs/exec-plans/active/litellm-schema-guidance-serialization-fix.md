# Execution Plan: LiteLLM Schema Guidance Serialization Fix

## Status

- State: completed
- Owner: agent
- Created: 2026-07-05
- Last updated: 2026-07-05

## Goal

Make LiteLLM schema guidance serialization handle real frozen registry schemas without breaking before request dispatch.

## Scope

### In scope

- Inspect the adapter schema-guidance path.
- Reuse the canonical structured-output schema normalizer.
- Add focused regression coverage for frozen/nested schemas.

### Out of scope

- Changing schema ownership boundaries.
- Adding a second schema transformation path.

## Relevant docs

- `docs/architecture/structured-output.md`
- `docs/architecture/llm-runtime.md`
- `docs/exec-plans/active/litellm-structured-schema-delivery-restoration.md`

## Contracts touched

- Runtime: LiteLLM model-input schema guidance serialization
- Tests: provider adapter frozen-schema coverage

## Implementation steps

- [x] Confirm the failure path against current adapter and registry freezing behavior.
- [x] Reuse the canonical schema normalizer for LiteLLM guidance serialization.
- [x] Add focused tests and run requested validations.

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests -q`
- [x] `python -m pytest packages/backend/platform-actions/tests -q`
- [ ] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-05 | Reuse `normalize_schema_mapping()` in the LiteLLM adapter | The project already has one canonical deep conversion path for frozen schemas, so reusing it avoids schema-normalization drift. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-05 | Confirmed the adapter serialized only `dict(schema)` and therefore failed on nested `MappingProxyType` and tuple values from the real frozen registry path | Switch to the canonical schema normalizer and add regression coverage |
| 2026-07-05 | Updated LiteLLM schema guidance serialization to normalize deeply and added tests for nested frozen values and real registry-provided schemas | Run requested validation commands and record any environment blockers |

## Open questions

## Follow-up debt
