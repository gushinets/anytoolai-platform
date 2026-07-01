# Execution Plan: Provider Policy Ref Migration Compatibility

## Status

- State: completed
- Owner: agent
- Created: 2026-07-01
- Last updated: 2026-07-01

## Goal

Ensure the runtime storage contract consistently uses `provider_policy_ref`, and make the
Alembic chain upgrade already-migrated databases from the old `event_log.provider_policy_id`
column to `provider_policy_ref` while keeping fresh installs on the same final schema.

## Scope

### In scope

- Audit the Alembic chain for `provider_policy_id` vs `provider_policy_ref`.
- Update the baseline migration files for fresh installs where appropriate.
- Add a compatibility migration for already-upgraded databases that still carry the old event-log
  column name.
- Align shared SQLAlchemy metadata, event envelope/repository persistence, and Provider Gateway
  event correlation with the canonical `provider_policy_ref` field.
- Update focused docs/tests to reflect the final runtime/storage contract.

### Out of scope

- Unrelated runtime schema redesign.
- New provider features beyond field-name and persistence-contract consistency.
- Product-level or frontend contract changes.

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
- `docs/architecture/config-model.md`

## Contracts touched

- DB: `platform.event_log`, Alembic revisions `0002` and new head revision.
- Runtime storage: shared `event_log` SQLAlchemy metadata and event repository round-trip fields.
- Events: `EventEnvelope`, `ExecutionContext`, `EventEmitter`, provider event correlation.
- Tests/docs: migration, runtime storage, event-log, provider gateway, and architecture/runtime
  docs that still mention `provider_policy_id`.

## Implementation steps

- [x] Confirm the exact stale migration/runtime/event references and the required upgrade path.
- [x] Patch baseline and compatibility migrations so fresh and upgraded databases converge on the
  same schema.
- [x] Align event persistence models/repositories/emitter with `provider_policy_ref` and existing
  correlation columns.
- [x] Update focused docs/tests and run targeted validation plus baseline checks where available.

## Validation

- [x] `python scripts/agent/runner.py doctor` (environment failure: global Python missing `pytest`,
  `yaml`, `pydantic`)
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py`
- [x] `uv run python scripts/agent/validate_architecture.py`
- [x] `uv run python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-01 | Plan to keep `provider_policy_ref` as the canonical runtime field name. | Product/action/provider-policy contracts and current provider-call storage already use `provider_policy_ref`; the remaining `provider_policy_id` references are drift, not a desired fork. |
| 2026-07-01 | Plan to add a forward compatibility migration instead of relying only on an edited historical revision. | Databases already upgraded through the current `0005` head will not re-run `0002`, so they need an explicit path to the final schema. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-01 | Reviewed AGENTS/docs, current migrations, storage metadata, provider gateway flow, and event-log persistence. Confirmed fresh `0002` still creates `provider_policy_id` on `event_log`, while runtime/provider code expects `provider_policy_ref` semantics. | Patch migrations and event persistence together, then run focused tests for both fresh and upgraded schemas. |
| 2026-07-01 | Updated `0002` for fresh installs, added `0006` compatibility rename for already-upgraded databases, aligned event-log columns/envelopes/emitter/gateway correlation fields, refreshed docs, and passed targeted tests plus `quick_check`. | Deliver summary with the final upgrade-path behavior and note the local `doctor` fallback/module constraint. |

## Open questions

None at the moment.

## Follow-up debt

- Consider tightening generated/runtime docs so event-log top-level correlation fields and JSON
  `properties` never drift again.
