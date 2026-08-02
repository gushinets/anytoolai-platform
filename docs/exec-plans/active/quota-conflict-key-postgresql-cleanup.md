# Execution Plan: Quota Conflict Key PostgreSQL Cleanup

## Status

- State: active
- Owner: agent
- Created: 2026-07-30
- Last updated: 2026-07-30
- Review date: 2026-07-30
- Next action: rerun the PostgreSQL-backed quota suites with a configured
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` if local production-dialect proof is required; the code,
  docs, and fast quota suites are already updated.
- Blocker: no `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is configured in this environment, so the
  PostgreSQL quota/runtime-storage suites currently collect cleanly and skip instead of exercising a
  live disposable database.

## Goal

Remove duplicated guest-quota conflict-key definitions, make the PostgreSQL unique constraint the
single runtime concurrency contract, and stop using SQLite-specific quota race handling as if it
were production behavior.

## Scope

### In scope

- `packages/backend/platform-core/src/anytoolai_platform_core/quotas/repository.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/storage/db.py`
- `migrations/platform/versions/0003_guest_quota.py`
- `migrations/platform/versions/0007_guest_quota_dimension.py`
- quota-focused tests in `packages/backend/platform-core/tests/`
- quota/API concurrency tests in `apps/platform-api/tests/`
- quota architecture docs that still need PostgreSQL-only clarity

### Out of scope

- Rewriting all lightweight SQLite test harnesses across unrelated runtime areas
- Changing the production migration contract beyond quota conflict-key consistency
- General storage-layer refactors outside the quota path

## Relevant docs

- `ARCHITECTURE.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/core-beliefs.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/quota-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- API: quota-protected scenario start and quota-check paths
- DB: `platform.guest_quota_usage` unique constraint `uq_guest_quota_usage_dimension`
- Config: quota dimension policy interpretation
- Events: `quota.checked`, `quota.consumed`, `quota.exhausted`
- Frontend: none

## Implementation steps

- [ ] Confirm all runtime quota conflict handling and classify remaining SQLite references.
- [ ] Replace duplicated quota conflict-key definitions with one canonical PostgreSQL contract.
- [ ] Remove SQLite-specific quota race emulation and retain only test-safe generic non-concurrent
      inserts for lightweight harnesses.
- [ ] Move quota concurrency assertions off SQLite and onto PostgreSQL-backed tests.
- [ ] Update docs to state that PostgreSQL owns runtime quota concurrency semantics.
- [ ] Run focused quota tests plus repo validation commands and record results.

## Validation

- [ ] `uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q`
- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -m "slow and postgresql" -q`
- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_quota_service.py apps/platform-api/tests/test_identity_quota_api.py apps/platform-api/tests/test_scenario_runtime_api.py -q`
- [ ] `python scripts/agent/runner.py validate-architecture`
- [ ] `python scripts/agent/runner.py validate-docs`
- [ ] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-30 | Treat `uq_guest_quota_usage_dimension` as the durable quota conflict contract. | The migration and shared SQLAlchemy table metadata already define the real uniqueness rule. |
| 2026-07-30 | Remove SQLite-specific quota duplicate-key parsing instead of keeping two synchronized conflict-key lists. | Runtime and production behavior are PostgreSQL-only, so SQLite race emulation adds drift risk without owning the real contract. |
| 2026-07-30 | Retain ordinary SQLite test harnesses only where they do not claim concurrency correctness. | The repo still uses lightweight SQLite DBs for fast non-concurrent unit/API checks, but PostgreSQL must own concurrency proof. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-30 | Read architecture, storage, quota, and MVP docs; confirmed runtime state is PostgreSQL-backed and quota concurrency proof is documented as PostgreSQL-only. | Patch the quota repository and add consistency/concurrency coverage. |
| 2026-07-30 | Classified current SQLite-specific quota/runtime code: one SQLite quota race-emulation branch in `quotas/repository.py`; broad SQLite harness usage in unit/API tests; SQLite concurrency assertions in `test_quota_service.py`, `test_scenario_runtime_api.py`, and `test_quota_concurrency_stress.py`. | Remove obsolete runtime emulation, then migrate or delete unsupported SQLite concurrency coverage. |

## Open questions

- None at the moment. The remaining design choice is implementation style: named PostgreSQL
  constraint vs derived ordered column tuple. Prefer the named constraint if SQLAlchemy accepts it
  cleanly in the current repository path.

## Follow-up debt

- The repo still has many SQLite-backed fast tests outside the quota path. They are acceptable only
  as lightweight non-concurrent scaffolding and may be worth centralizing later.
