# Execution Plan: A05 Runtime Event Log As Core Contract

## Status

- State: completed
- Owner: agent
- Created: 2026-06-19
- Last updated: 2026-06-19

## Goal

Make `platform.event_log` a required runtime contract backed by durable storage, a shared emitter,
runtime-owned emission points, safe event properties, and generated documentation.

## Scope

### In scope

- Alembic `0002` migration for `platform.event_log`, chained after runtime tables.
- Shared SQLAlchemy event-log table definition in `platform-core/storage`.
- Event repository plus session-bound emitter API with runtime-dimension mapping.
- Machine-readable platform event taxonomy source and generated event catalog support.
- Thin runtime services for scenario, workflow/job, action, artifact, and provider execution paths.
- Tests for migration chain, persistence, required dimensions, sanitization, taxonomy coverage, and
  success/failure event emission.
- Documentation updates for event taxonomy and generated event catalog.

### Out of scope

- Dashboards, BI exports, billing ledger, or product analytics infrastructure.
- Full workflow/scenario engine implementation beyond thin wrappers around existing runtime
  surfaces.
- New tracing infrastructure beyond dimensions already available in current runtime/request
  context.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/event-taxonomy.md`
- `docs/generated/event-catalog.md`

## Contracts touched

- DB: `platform.event_log`
- Runtime API: `emit(event_type, context, result_status=None, properties=None)`
- Runtime context: `ExecutionContext` optional event dimensions
- Docs/config: repo-local taxonomy source and generated event catalog

## Implementation steps

- [ ] Replace Alembic `0002_event_log.py` placeholder with the durable event-log schema and
  indexes.
- [ ] Add shared SQLAlchemy event-log table definitions and export them through storage modules.
- [ ] Align `EventEnvelope` with the SDK contract and add an event-log repository.
- [ ] Implement taxonomy loading, event validation, and safe-properties sanitization in the shared
  emitter.
- [ ] Extend `ExecutionContext` with optional event dimensions used by runtime emission.
- [ ] Replace thin runtime service placeholders with explicit repository-backed services that emit
  required success/failure events.
- [ ] Extend provider gateway execution flow to persist provider-call events on both success and
  failure.
- [ ] Add a machine-readable platform taxonomy source and generate `docs/generated/event-catalog.md`
  from it.
- [ ] Update event-taxonomy architecture docs to reflect runtime-contract ownership and safety
  rules.
- [ ] Add persistence, sanitization, taxonomy, and runtime-emission tests, then run targeted
  validation and quick-check.

## Validation

- [ ] `python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py`
- [ ] `python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py tests/architecture/test_events_have_required_dimensions.py packages/backend/platform-core/tests/test_contract_field_compatibility.py`
- [ ] `python scripts/agent/quick_check.py`

## Assumptions

- Runtime success/failure emission will be added only for the concrete scenario/job/action/provider
  and artifact flows implemented in this slice.
- Event persistence must share the caller-owned SQLAlchemy transaction boundary.
- Request/correlation identifiers are not currently part of the discovered runtime/request
  contracts, so no new tracing columns are introduced here.
