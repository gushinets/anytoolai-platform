# Execution Plan: ANY-61 Provider-Call Ledger Backfill

## Status

- State: completed
- Owner: agent
- Created: 2026-06-29
- Last updated: 2026-06-29

## Goal

Backfill the ADR 0007 provider-call ledger and provider-event correlation contract so
`platform.provider_calls` records one row per physical `ProviderGateway` attempt, and
`platform.event_log` can deterministically correlate provider events to that ledger
without relying on LiteLLM callbacks or PydanticAI tracing.

## Scope

### In scope

- Extend baseline runtime and event-log migrations in place.
- Extend shared SQLAlchemy table metadata to match the final baseline schema.
- Extend provider call, gateway response, execution context, and event envelope models.
- Update provider-call repository round-trip behavior for new fields.
- Update `ProviderGateway` success/failure persistence and event correlation payloads.
- Add focused gateway tests plus storage/event-log regression coverage.
- Refresh docs for runtime storage, provider gateway, event taxonomy, generated event
  catalog, and generated DB schema.

### Out of scope

- LiteLLM Proxy, live provider integration, billing-grade cost accounting, dashboards,
  BI exports, or product-specific runtime changes.
- PydanticAI executor redesign beyond optional correlation metadata threading.
- Forward-only migration branching or additional Alembic repair revisions.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/event-taxonomy.md`
- `docs/adr/0006-event-log-as-core.md`
- `docs/adr/0007-llm-runtime-pydanticai-litellm-sdk.md`
- `docs/generated/db-schema.md`
- `docs/generated/event-catalog.md`
- `docs/exec-plans/active/predeployment-migration-history-cleanup.md`

## Contracts touched

- API: none.
- DB: `platform.provider_calls`, `platform.event_log`, Alembic `0001` and `0002`.
- Config: `configs/kernel/platform_events.yaml`.
- Events: `EventEnvelope`, `ExecutionContext`, provider request/success/failure event
  correlation fields.
- Frontend: none.

## Implementation steps

- [x] Update baseline migrations plus shared SQLAlchemy metadata for provider-call and
  event-log correlation fields.
- [x] Extend core and SDK dataclasses/contracts for provider-call ledger and event
  correlation fields.
- [x] Update provider-call repository and `ProviderGateway` success/failure handling to
  preserve one-row-per-physical-attempt semantics.
- [x] Add targeted repository, gateway, and event-log tests for round-trip persistence,
  deterministic event correlation, and optional tracing metadata.
- [x] Refresh docs/generated docs and run targeted validation plus quick-check.

## Validation

- [x] `.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py`
- [x] `.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py`
- [x] `.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_event_log.py`
- [x] `.quick-check-venv\Scripts\python.exe -m pytest tests/architecture/test_events_have_required_dimensions.py packages/backend/platform-core/tests/test_contract_field_compatibility.py packages/backend/platform-sdk/tests/test_contracts_importable.py`
- [x] `.quick-check-venv\Scripts\python.exe scripts/agent/validate_configs.py`
- [x] `.quick-check-venv\Scripts\python.exe scripts/agent/validate_architecture.py`
- [x] `.quick-check-venv\Scripts\python.exe scripts/agent/quick_check.py`
- [x] `.quick-check-venv\Scripts\python.exe scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-29 | Keep `provider_policy_id` as the canonical runtime/storage/event field name. | Configs already use `provider_policy_ref`, but the persisted runtime contract and current code use `provider_policy_id`; backfill should clarify, not fork, the naming. |
| 2026-06-29 | Update `0001` and `0002` in place instead of adding a new migration. | The repo is still in pre-deployment baseline-folding mode with one clean head and explicit cleanup guidance to keep the baseline chain clean. |
| 2026-06-29 | Persist provider correlation as first-class `event_log` columns, not only JSON properties. | The event log is the domain source of truth and should support deterministic joins without auxiliary callback/tracing systems. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-29 | Reviewed repo guidance, runtime/event/provider docs, current migrations, storage models, gateway code, and current storage/event tests. Confirmed targeted baseline tests pass before edits. | Patch baseline schema/types, then wire repository and gateway changes. |
| 2026-06-29 | Implemented baseline schema/type/gateway/event/doc backfill, added dedicated provider-gateway tests, refreshed generated docs, and passed targeted tests plus quick-check. | Deliver implementation summary and note the minor non-blocking quick-check UV cache warning. |

## Open questions

None at implementation start. The current MVP path can default attempt indexes to `1` and
document the semantics until higher-level semantic or transport retries land.

## Follow-up debt

- When structured PydanticAI execution lands, thread `pydantic_run_id` through the
  executor/gateway boundary instead of relying on the current optional parameter.
- If provider adapters begin exposing richer provider errors, replace the simple HTTP status
  extraction heuristic with adapter-normalized error metadata.
