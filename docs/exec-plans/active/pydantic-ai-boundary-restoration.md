# Execution Plan: PydanticAI Boundary Restoration

## Status

- State: completed
- Owner: agent
- Created: 2026-07-02
- Last updated: 2026-07-02

## Goal

Restore one coherent architecture decision for PydanticAI ownership so package boundaries,
documentation, and validation tests all agree on whether structured validation belongs in
`platform-actions` or `platform-core`.

## Scope

### In scope

- Audit repo-local architecture sources for the intended PydanticAI boundary.
- Inspect the current dependency direction between `platform-core` and `platform-actions`.
- Remove the accidental architecture violation if the original boundary still applies.
- Realign docs and architecture validation to the chosen boundary.
- Update affected runtime and unit tests.

### Out of scope

- Expanding ProviderGateway scope beyond transport, persistence, and event ownership.
- Changing product/runtime scope outside the PydanticAI boundary decision.
- Suppressing architecture checks without fixing the underlying contract.

## Relevant docs

- `AGENTS.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/provider-gateway.md`
- `docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md`

## Contracts touched

- Config: provider retry-policy ownership semantics
- Runtime: provider request/response DTOs, validation retry ownership, gateway/event metadata
- Events: provider event correlation with `pydantic_run_id`
- Architecture: documented import boundaries and enforcement rules
- Packaging: `platform-core` vs `platform-actions` runtime dependencies

## Implementation steps

- [x] Confirm the intended architecture from repo-local docs, tests, and package metadata.
- [x] Move PydanticAI validation ownership back to `platform-actions` unless the repo proves an intentional boundary change.
- [x] Update architecture docs and validators so the enforced rule matches the chosen design.
- [x] Run architecture validation and the affected unit tests.

## Validation

- [x] `uv run python scripts/agent/runner.py doctor`
- [x] `uv run python scripts/agent/runner.py validate-architecture`
- [x] `uv run python -m pytest tests/architecture/test_no_direct_provider_calls_outside_gateway.py -q`
- [x] `uv run python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py -q`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-02 | Start from the existing documented boundary unless the repo shows a deliberate replacement. | AGENTS.md and ADR 0007 still name `platform-actions` as the only allowed PydanticAI layer, so a stray implementation or validator change is not enough to treat the architecture as evolved. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-02 | Audited AGENTS, package-layering, LLM runtime docs, ADR 0007, provider-gateway docs, architecture tests, and package metadata. Found conflicting repo state: most docs keep PydanticAI in `platform-actions`, while `provider-gateway.md`, `validate_architecture.py`, and `platform-core/providers/pydanticai_runner.py` moved it into `platform-core`. | Restore a single rule by moving validation ownership back behind `platform-actions` and realigning docs/tests. |
| 2026-07-02 | Moved the PydanticAI runner into `platform-actions/structured_llm`, removed direct `pydantic_ai` imports from `platform-core`, updated package metadata, refreshed architecture docs/validators, and passed architecture validation plus quick-check. | No further work for this fix. |

## Open questions

- None currently. The repo-local majority contract is strong enough to proceed without a product decision escalation.

## Follow-up debt

- Consider a small architecture test that explicitly verifies `platform-core` package metadata does not depend on `pydantic-ai-slim` once the boundary is restored.
