# Execution Plan: A05 Async Provider Gateway Enforcement

## Status

- State: active
- Owner: agent
- Created: 2026-06-22
- Last updated: 2026-06-22

## Goal

Implement an async `ProviderGateway` as the only allowed runtime path for model/provider calls, with
provider policy resolution, deterministic fake-provider fixture selection, and durable
`platform.provider_calls` persistence for both success and failure outcomes.

## Scope

### In scope

- Async provider request/response DTOs and adapter protocol under `platform-core/providers`.
- Gateway-owned provider policy resolution from the config registry / `configs/kernel/provider_policies.yaml`.
- Gateway-owned timeout/retry metadata handling and latency measurement.
- Provider call persistence to `platform.provider_calls` for success and failure paths.
- Deterministic fake-provider fixture selection based on request metadata instead of prompt text.
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

- [ ] Add async provider DTOs and an async adapter protocol.
- [ ] Implement policy resolution helpers that read `ProviderPolicy` from the config registry.
- [ ] Rework `ProviderGateway` into an async orchestration service with persistence and safe failure handling.
- [ ] Make the fake provider deterministic via request metadata and fixture files.
- [ ] Route action/runtime provider execution through the gateway only.
- [ ] Strengthen architecture tests to block adapter imports and direct provider bypasses outside the boundary.
- [ ] Add focused unit tests for success, failure, deterministic fixtures, metadata capture, and policy resolution.
- [ ] Update provider documentation and fixture docs.

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

## Open questions

None yet. If the current runtime skeleton lacks a concrete action execution seam for the gateway, the
smallest explicit integration point will be added and documented.

## Follow-up debt

- Add provider request events once the event-log slice is implemented.
- Revisit provider call schema if production cost/accounting requirements become first-class.
