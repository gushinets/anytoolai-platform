# Execution Plan: PostgreSQL-Only SQLite Eradication

## Status

- State: active
- Scope status: regression found during 2026-08-05 gardening; implementation is not complete
- Owner: agent
- Created: 2026-07-30
- Last updated: 2026-08-05
- Review date: 2026-07-30
- Next action: decide whether the current SQLite fast-test and worker fallback paths are accepted
  test-only compatibility or must be removed to satisfy this plan's original zero-SQLite goal.
- Blocker: current code and docs intentionally use SQLite in fast tests and non-PostgreSQL worker
  fallbacks, which conflicts with this plan's stated goal and needs an explicit scope decision.

## Goal

Bring the repository to a PostgreSQL-only model with no remaining SQLite-specific code paths,
SQLite-based test infrastructure, or current docs/plans that present SQLite as supported.

## Scope

### In scope

- Remove SQLite-specific migration branches and assumptions.
- Replace attached-SQLite DB harnesses in tracked tests with disposable PostgreSQL patterns.
- Update runtime, test, and migration documentation so PostgreSQL is the only supported DB path.
- Clean active execution plans that still describe SQLite as a valid or tolerated approach.

### Out of scope

- Rewriting completed historical plans unless a stale SQLite reference is misleading enough to
  require cleanup.
- Changing unrelated runtime behavior outside the DB/harness/documentation scope.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/core-beliefs.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/quota-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- DB: PostgreSQL is the only supported runtime and test database contract.
- Migrations: runtime migrations no longer branch for SQLite compatibility.
- Tests: tracked database-backed test infrastructure uses disposable PostgreSQL only.
- Docs: SQLite is not documented as a valid runtime or test circuit.

## Inventory

### Runtime / production-impacting

- `migrations/platform/versions/0001_runtime_tables.py`
  - SQLite-specific schema create/drop branches.

### Tests / fixtures / harnesses

- API tests:
  - `apps/platform-api/tests/test_identity_quota_api.py`
  - `apps/platform-api/tests/test_migrate.py`
  - `apps/platform-api/tests/test_scenario_runtime_api.py`
- Worker tests:
  - `apps/platform-worker/tests/test_settings.py`
  - `apps/platform-worker/tests/test_worker_boot.py`
- Platform actions tests:
  - `packages/backend/platform-actions/tests/test_structured_llm_executor.py`
- Platform core tests:
  - `packages/backend/platform-core/tests/unit/test_action_runner.py`
  - `packages/backend/platform-core/tests/unit/test_artifact_service.py`
  - `packages/backend/platform-core/tests/unit/test_event_log.py`
  - `packages/backend/platform-core/tests/unit/test_handoffs.py`
  - `packages/backend/platform-core/tests/unit/test_provider_gateway.py`
  - `packages/backend/platform-core/tests/unit/test_quota_service.py`
  - `packages/backend/platform-core/tests/unit/test_scenario_runtime.py`
  - `packages/backend/platform-core/tests/unit/test_structured_output.py`
  - `packages/backend/platform-core/tests/unit/test_workflow_runner.py`

### Docs / plans / historical references

- Current docs:
  - `docs/architecture/runtime-storage.md`
  - `docs/architecture/quota-model.md`
- Completed plans retained as historical evidence:
  - `docs/exec-plans/completed/a13-guest-identity-and-quota.md`
  - `docs/exec-plans/completed/a13-postgresql-concurrency-and-ce-scope.md`
  - `docs/exec-plans/completed/runtime-storage-postgresql-test-alignment.md`
- Completed plans with historical references:
  - `docs/exec-plans/completed/a04-runtime-storage-and-repositories.md`
  - `docs/exec-plans/completed/a13-configurable-quota-dimension.md`
  - `docs/exec-plans/completed/a13-review-followup-contract-storage.md`
  - `docs/exec-plans/completed/handoff-source-schema-and-quota-recovery-idempotency.md`
  - `docs/exec-plans/completed/predeployment-migration-history-cleanup.md`

## Implementation steps

- [x] Add a shared disposable-PostgreSQL test helper for tracked DB-backed tests.
- [ ] Convert all attached-SQLite DB-backed tests to the PostgreSQL helper pattern; later work
  reintroduced `tests/support/sqlite_harness.py` and SQLite-backed fast tests.
- [ ] Remove SQLite-specific migration branches from runtime migrations; revision `0009` currently
  contains SQLite branches.
- [ ] Update docs and active plans so SQLite is no longer presented as supported; current runtime
  docs intentionally describe the fast SQLite suite and worker fallback.
- [ ] Re-run the final PostgreSQL-only validation ladder after the zero-SQLite contract is restored
  or explicitly narrowed.

## Validation

- Historical local migration selection passed six cases and skipped two PostgreSQL cases; the
  skips are not counted as successful production-dialect validation.
- Local attempt, not completion evidence: `uv run python -m pytest
  apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q`
  collected and skipped 5 tests because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was unset.
- Local attempt, not completion evidence: `uv run python -m pytest
  packages/backend/platform-core/tests/unit/test_event_log.py -m "slow and postgresql" -q`
  reported 2 non-PostgreSQL passes and 18 skipped PostgreSQL tests.
- [x] PR #54 required CI ran `python scripts/agent/runner.py postgresql-check` against PostgreSQL
  successfully; this is production-dialect evidence, but it does not close the reintroduced SQLite
  scope regression above.
- [x] `python -m compileall ...` across the converted helper and DB-backed test modules
- [x] `uv run python scripts/agent/runner.py validate-architecture`
- [x] `uv run python scripts/agent/runner.py validate-docs`
- [x] `uv run python scripts/agent/runner.py quick-check`
- [x] PR #54 required CI ran canonical `python scripts/agent/runner.py quick-check` successfully
  on Linux and Windows after the shared-helper import cleanup.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-30 | Treat every tracked SQLite test harness as technical debt to be removed, not just concurrency-specific ones. | The user explicitly requested complete SQLite abandonment in any form. |
| 2026-07-30 | Use disposable PostgreSQL helpers instead of inventing a second PostgreSQL test pattern. | The repository already accepts the slow/postgresql disposable-database approach in runtime-storage and quota suites. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-30 | Re-read the required architecture/product docs, ran the canonical `doctor`, and confirmed again that runtime state belongs in PostgreSQL. | Inventory every tracked SQLite trace and classify it before editing. |
| 2026-07-30 | Completed a tracked-file inventory of SQLite references across migrations, DB-backed tests, docs, and plans. Identified one remaining runtime migration branch and a broad attached-SQLite test harness layer. | Introduce shared PostgreSQL test helpers and start converting the SQLite-backed tests. |
| 2026-07-30 | Added `repo_test_support.postgresql`, migrated the tracked DB-backed test harnesses to disposable PostgreSQL patterns, removed the remaining SQLite migration branch, deleted the obsolete SQLite stress test, and scrubbed current docs/plans so PostgreSQL is the only supported DB path. | Re-run PostgreSQL-marked suites against a live disposable maintenance database URL when available. |
| 2026-07-30 | Local validation passed on the supported fast path: targeted migration/event-log suites collected cleanly, `validate-architecture` passed, `validate-docs` passed, and `quick-check` passed with `207 passed, 230 deselected`. | None in-repo; only live PostgreSQL execution remains environment-dependent. |
| 2026-07-30 | A later `quick-check` surfaced a pytest collection bug: several tests imported shared DB helpers via `from conftest import ...`, which resolved to the wrong `conftest.py`. The follow-up cleanup moved those reusable helpers into an explicit test-only module under `tests/` so `conftest.py` returned to pure pytest wiring. | Re-run the affected pytest slice and `quick-check` to confirm collection is stable again. |
| 2026-08-05 | Gardening found tracked SQLite branches/harnesses again in migration `0009`, scenario conflict handling, worker lease fallbacks, and `tests/support/sqlite_harness.py`; current architecture docs also describe the fast SQLite suite. | Keep the plan active and obtain an explicit contract decision before claiming eradication. |
