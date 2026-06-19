# Execution Plan: A04 Runtime Storage And Repositories

## Status

- State: active
- Owner: agent
- Created: 2026-06-19
- Last updated: 2026-06-19

## Goal

Replace the current runtime storage placeholders with the first durable MVP-A execution storage
slice for scenario sessions, jobs, action runs, provider calls, and artifacts.

## Scope

### In scope

- Alembic runtime migration `0001` for the five MVP-A runtime tables in the `platform` schema.
- Shared SQLAlchemy table definitions under `platform-core/storage`.
- Frozen runtime record models and status enums for scenario sessions, jobs, action runs, provider
  calls, and artifacts.
- Repository classes for create/read/update with explicit transaction boundaries.
- Text and JSON artifact persistence, using PostgreSQL `JSONB` semantics where available.
- Repository and migration tests that stay DB-light enough for the current repo check flow.

### Out of scope

- `platform.event_log`, quota, email capture, handoff, billing, or product-definition tables.
- Worker orchestration, queue claiming, or full execution pipelines.
- Runtime editing, admin storage flows, or product-specific domain tables.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/provider-gateway.md`
- `docs/generated/db-schema.md`

## Contracts touched

- DB: `platform.scenario_sessions`, `platform.jobs`, `platform.action_runs`,
  `platform.provider_calls`, `platform.artifacts`.
- Runtime models: scenario/job/action/provider/artifact status enums and persistence DTOs.
- Storage API: explicit transaction boundary via caller-owned SQLAlchemy session lifecycle.
- Packaging: `platform-core` gains an explicit SQLAlchemy dependency.

## Implementation steps

- [ ] Replace `platform-core/storage/db.py` with shared runtime metadata, JSON/enum helpers, and
  the five SQLAlchemy table definitions.
- [ ] Replace `platform-core/storage/transactions.py` with a small session-factory helper and an
  explicit transaction-boundary context manager.
- [ ] Add frozen runtime record dataclasses and any missing status enums in:
  `scenarios/models.py`, `workflows/models.py`, `actions/models.py`, `providers/models.py`,
  `artifacts/models.py`.
- [ ] Replace placeholder repositories with focused create/read/update repositories for:
  scenario sessions, jobs, action runs, provider calls, and artifacts.
- [ ] Add `providers/repository.py` because provider-call storage has no existing repository file.
- [ ] Replace Alembic `0001` placeholder with actual schema creation and table/index DDL.
- [ ] Fix the placeholder `0002_event_log.py` revision chain if it still points to `None`.
- [ ] Replace the Alembic env placeholder with the smallest working `env.py` needed for
  programmatic migration execution.
- [ ] Add repository and migration tests using the current repo’s lightweight SQLite-based test
  approach with an attached `platform` schema.
- [ ] Run the relevant tests/checks and document any contract compromises in the final summary.

## Validation

- [ ] `.venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py`
- [ ] `.venv\Scripts\python.exe scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-19 | Use SQLAlchemy Core tables plus frozen dataclass records, not a full ORM. | The repo favors explicit, searchable code and there is no prior ORM pattern to preserve. |
| 2026-06-19 | Keep repository methods side-effect free with respect to commits. | The task explicitly requires caller-controlled transaction boundaries. |
| 2026-06-19 | Use lightweight SQLite repository tests with an attached `platform` schema, while still generating PostgreSQL `JSONB` semantics through type variants. | The current baseline checks are DB-free, but the runtime storage still needs real persistence tests in CI. |
| 2026-06-19 | Introduce the smallest new status enums only where the current runtime model does not already define one. | Scenario session and job statuses already exist; the new storage slice should extend, not fork, those contracts. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-19 | Reviewed architecture docs, generated DB schema doc, runtime model placeholders, migration placeholders, and the existing test/check harness. | Implement storage tables, repositories, migration, and tests in small reviewable slices. |

## Open questions

None. The current implementation will treat the generated DB schema doc plus MVP-A storage notes as
the active runtime contract and will call out any small schema compromises in the final summary.
