# Execution Plan: A05 Async Provider Gateway Enforcement

## Status

- State: completed
- Owner: agent
- Created: 2026-06-22
- Last updated: 2026-06-23

## Goal

Implement an async `ProviderGateway` as the only allowed runtime path for model/provider calls, with
provider policy resolution, deterministic fake-provider fixture selection, durable
`platform.provider_calls` persistence for both success and failure outcomes, and LiteLLM behind the
provider-adapter boundary for real routed provider transport.

## Scope

### In scope

- Async provider request/response DTOs and adapter protocol under `platform-core/providers`.
- Gateway-owned provider policy resolution from the config registry / `configs/kernel/provider_policies.yaml`.
- Gateway-owned timeout handling, safe retry metadata, and latency measurement.
- Provider call persistence to `platform.provider_calls` for success and failure paths.
- Deterministic fake-provider fixture selection based on request metadata instead of prompt text.
- LiteLLM router-backed adapter and separate `configs/kernel/litellm_router.yaml` deployment config.
- Action/runtime wiring so provider calls flow through `ProviderGateway`.
- Architecture tests that prohibit direct adapter imports outside the provider adapter boundary.
- Provider docs and fixture docs aligned with the new gateway contract.

### Out of scope

- Real OpenAI production hardening or new external provider integrations.
- Billing-grade cost accounting or a new billing ledger.
- Broad workflow/scenario engine rewrites unrelated to the provider path.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/config-model.md`
- `docs/exec-plans/active/a02-config-loader-and-registry-validation.md`
- `docs/exec-plans/active/a04-runtime-storage-and-repositories.md`

## Contracts touched

- API: none directly yet; runtime/provider services only.
- DB: `platform.provider_calls` persistence shape and safe metadata usage.
- Config: `configs/kernel/provider_policies.yaml` policy resolution behavior.
- Events: none added in this slice.
- Frontend: none; frontend still does not choose provider/model.

## Implementation steps

- [x] Add async provider DTOs and an async adapter protocol.
- [x] Implement policy resolution helpers that read `ProviderPolicy` from the config registry.
- [x] Rework `ProviderGateway` into an async orchestration service with persistence and safe failure handling.
- [x] Make the fake provider deterministic via request metadata and fixture files.
- [x] Add a LiteLLM adapter and separate router config, while keeping the gateway as the only platform boundary.
- [x] Route action/runtime provider execution through the gateway only.
- [x] Strengthen architecture tests to block adapter imports, direct provider bypasses, and direct LiteLLM usage outside the boundary.
- [x] Add focused unit tests for success, failure, deterministic fixtures, metadata capture, policy resolution, and LiteLLM request/response normalization.
- [x] Update provider documentation and fixture docs.

## Validation

- [ ] `python scripts/agent/runner.py doctor`
- [ ] `python scripts/agent/runner.py validate-configs`
- [ ] `python scripts/agent/runner.py validate-architecture`
- [ ] `python scripts/agent/quick_check.py`
- [ ] `python -m pytest packages/backend/platform-core/tests packages/backend/platform-actions/tests tests/architecture`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-22 | Keep provider adapters behind an async gateway-owned protocol. | The architecture docs define Provider Gateway as the only allowed path and forbid direct provider SDK usage outside adapters. |
| 2026-06-22 | Persist a safe `provider_calls` row for both success and failure, without secrets or raw unsafe payloads. | The runtime-storage and provider-gateway docs require durable operational metadata even before billing. |
| 2026-06-22 | Select fake-provider fixtures by explicit metadata instead of prompt text. | Deterministic fixture lookup is required and avoids prompt-coupled test behavior. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-22 | Reviewed required architecture docs, provider docs, config loader, runtime storage, current adapters/gateway, and the existing provider architecture test. | Implement the async provider contract and gateway persistence path, then wire tests and docs. |
| 2026-06-23 | Added LiteLLM behind the adapter boundary, switched real provider-policy routing to `provider: litellm`, removed the public sync gateway bypass, and updated provider/event/config/architecture tests. | Run targeted validation plus `quick_check`, then capture any remaining validation gaps in the summary. |
| 2026-06-23 | Declared `platform-actions` runtime dependencies on `anytoolai-platform-core` and `sqlalchemy`, and added a package metadata test so executor imports do not rely on the root monorepo install order. | Validate package tests plus an isolated package import path. |
| 2026-06-23 | Fixed provider lifecycle event emission so normalized failed/timed-out `ProviderResponse` objects emit `provider.request_failed` instead of `provider.request_succeeded`. | Run focused provider gateway and event-log validation plus `quick_check`. |

## Open questions

None yet. If the current runtime skeleton lacks a concrete action execution seam for the gateway, the
smallest explicit integration point will be added and documented.

## Follow-up debt

- Add provider request events once the event-log slice is implemented.
- Revisit provider call schema if production cost/accounting requirements become first-class.
