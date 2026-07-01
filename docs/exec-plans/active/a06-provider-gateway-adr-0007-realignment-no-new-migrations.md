# Execution Plan: A06 Provider Gateway ADR-0007 Realignment Without New Migrations

## Status

- State: active
- Owner: agent
- Created: 2026-07-01
- Last updated: 2026-07-01

## Goal

Realign the Provider Gateway to the ADR-0007 runtime contract using LiteLLM for transport,
PydanticAI for structured validation/retry, and the existing migration chain only.

## Scope

### In scope

- Replace flat provider retry fields with the ADR-0007 nested retry-policy contract.
- Update provider runtime DTOs, gateway flow, and persistence to track physical transport attempts.
- Integrate PydanticAI inside the provider boundary for structured validation retries.
- Realign existing runtime migrations in place so `upgrade head` produces the new provider-call
  ledger without adding `0006`.
- Update provider/event/config/docs/tests to match the new contract.

### Out of scope

- New Alembic revision files.
- Live provider credential setup or production provider hardening.
- LiteLLM Proxy, analytics/dashboard work, or billing-grade accounting.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/event-taxonomy.md`
- `docs/exec-plans/active/a02-config-loader-and-registry-validation.md`
- `docs/exec-plans/active/a04-runtime-storage-and-repositories.md`
- `docs/exec-plans/active/a05-runtime-event-log-as-core-contract.md`
- `docs/exec-plans/active/a05-async-provider-gateway-enforcement.md`

## Contracts touched

- Config: `ProviderPolicy` shape and provider-policy YAML parsing.
- Runtime models: provider request/response/record DTOs and structured-output handoff.
- DB: `platform.provider_calls` schema created by the existing `0001`/`0005` chain.
- Events: provider-request event properties for deterministic correlation.
- Architecture: direct-import restrictions for `litellm` and `pydantic_ai`.

## Implementation steps

- [ ] Update the provider-policy SDK/core contract to ADR-0007 nested retry-policy fields and
  rename `provider_policy_id` to `provider_policy_ref`.
- [ ] Add provider-boundary PydanticAI and JSON Schema validation support through repo-managed
  dependencies.
- [ ] Refactor the gateway/adapters so one provider-call row equals one physical transport attempt,
  with hard physical-call limit enforcement and event correlation metadata.
- [ ] Realign the existing migration chain in place, keeping `0005` as the head and avoiding new
  revision files.
- [ ] Refresh provider/runtime/config/generated docs and active plan references that still describe
  flat retry fields or new-migration expectations.
- [ ] Expand tests for retry ownership, ledger fields, structured validation retries, fake-provider
  determinism, architecture guards, and migration-chain expectations.

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_litellm_adapter.py`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_config_loader.py`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py`
- [x] `python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py`
- [x] `python -m pytest packages/backend/platform-sdk/tests/test_contracts_importable.py`
- [x] `python -m pytest tests/architecture/test_no_direct_provider_calls_outside_gateway.py`
- [x] `python -m pytest tests/architecture/test_events_have_required_dimensions.py`
- [x] `python scripts/agent/quick_check.py`

## Assumptions

- Migration history is still editable in place because production rollout has not locked it yet.
- Event correlation keys beyond the standard event-log columns continue to live in
  `event_log.properties`.
- LiteLLM remains the only transport/router layer; PydanticAI owns structured validation and
  validation retry only.
