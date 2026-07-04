# Execution Plan: LiteLLM Structured Schema Delivery Restoration

## Status

- State: completed
- Owner: agent
- Created: 2026-07-04
- Last updated: 2026-07-04

## Goal

Restore generation-time schema context for LiteLLM-backed structured actions without reintroducing a second conflicting schema validation path.

## Scope

### In scope

- Trace schema flow through the structured executor, provider gateway, and LiteLLM adapter.
- Restore schema delivery on the model-facing LiteLLM call path.
- Add focused tests for schema-aware model input.

### Out of scope

- Reintroducing LiteLLM `response_format` validation.
- Moving structured-output retry ownership out of PydanticAI.
- Broad executor or provider gateway redesign.

## Relevant docs

- `docs/architecture/llm-runtime.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/package-layering.md`

## Contracts touched

- Runtime: LiteLLM adapter schema delivery to model calls
- Providers: structured model-input payload construction
- Docs/tests: schema ownership and model-path coverage

## Implementation steps

- [x] Verify the schema-delivery regression against current code and tests.
- [x] Restore schema-aware model input in the LiteLLM adapter without adding a second validation path.
- [x] Add targeted tests and run structured-output/provider checks.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_litellm_adapter.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py -q`
- [x] `uv run python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-04 | Deliver schema context to LiteLLM through a synthesized system message instead of `response_format` | This gives the model the declared structure at generation time while keeping LiteLLM out of a second schema-enforcement role. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-04 | Confirmed `response_schema` survived on provider DTOs and into `ResolvedProviderRequest`, but the LiteLLM adapter stopped forwarding any schema signal to the model after `response_format` removal | Patch the adapter message builder and cover the router call with focused tests |
| 2026-07-04 | Added schema guidance injection for LiteLLM model messages and updated tests/docs around the model path | Run targeted pytest validation and summarize the restored ownership split |

## Open questions

## Follow-up debt
