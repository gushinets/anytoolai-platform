# Execution Plan: Runtime Storage PostgreSQL Test Alignment

## Status

- State: completed
- Owner: agent
- Created: 2026-07-29
- Last updated: 2026-07-29
- Review date: 2026-07-29
- Next action: keep runtime-storage validation aligned with the repo's PostgreSQL-only test path.
- Blocker: a live PostgreSQL-backed runtime-storage run still needs valid
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` credentials; the documented localhost URL reaches a server
  on this machine, but authentication for user `anytoolai` failed.

## Goal

Keep the implementation guidance and primary storage regression suite aligned with the PostgreSQL-only
runtime database contract.

## Scope

### In scope

- Keep `packages/backend/platform-core/tests/unit/test_runtime_storage.py` on the disposable
  PostgreSQL database harness that runs the real Alembic migration chain.
- Keep `docs/architecture/runtime-storage.md` explicit that PostgreSQL is the only supported
  storage verification strategy.
- Re-run the focused runtime-storage and migration validation commands that remain available in the
  current environment.

### Out of scope

- Broader runtime or test-database redesign outside the PostgreSQL-only contract.
- Changing runtime schema, revision IDs, or application behavior.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/architecture/runtime-storage.md`
- `apps/platform-api/tests/test_quota_concurrency_postgresql.py`
- `apps/platform-api/tests/test_migrate.py`

## Contracts touched

- Tests: runtime-storage migration and repository coverage now rely on PostgreSQL semantics.
- Docs: runtime-storage testing guidance and validation commands.

## Implementation steps

- [x] Inspect the current runtime-storage harness, PostgreSQL test helpers, and storage docs.
- [x] Patch `test_runtime_storage.py` to provision disposable PostgreSQL databases.
- [x] Update runtime-storage documentation to reflect PostgreSQL-only validation.
- [x] Run the focused validation ladder and record any environment-side skips/blockers.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -m "slow and postgresql" -q`
  - With no env var set, the suite collected cleanly and skipped the PostgreSQL-backed cases.
  - With `postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres`, the suite reached the
    new PostgreSQL harness and failed fast on maintenance-DB authentication.
- [x] `uv run python -m pytest apps/platform-api/tests/test_migrate.py -q`
- [x] `uv run alembic -c migrations/platform/alembic.ini upgrade head --sql`
- [x] `uv run python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-29 | Move runtime-storage DB-backed verification onto disposable PostgreSQL instead of keeping the legacy attached-temp harness. | The repository runtime database is PostgreSQL, and the user explicitly asked to remove the non-PostgreSQL decision from both the tests and the docs. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-29 | Confirmed that `test_runtime_storage.py` still used a legacy attached-temp schema harness and that `docs/architecture/runtime-storage.md` still documented that choice as intentional. Found reusable disposable PostgreSQL helper patterns in `apps/platform-api/tests/test_quota_concurrency_postgresql.py` and `apps/platform-api/tests/test_migrate.py`. | Patch the runtime-storage suite and storage docs, then run the available validation commands. |
| 2026-07-29 | Replaced the legacy harness in `test_runtime_storage.py` with a disposable PostgreSQL harness, marked the suite `slow`/`postgresql`, updated the storage docs, and reran the validation ladder with a repo-local `UV_CACHE_DIR` workaround for local `uv` cache ACL issues. The live PostgreSQL attempt reached a server on `127.0.0.1:5432` but failed authentication for the documented `anytoolai` user. | Re-run the PostgreSQL-backed runtime-storage suite with valid maintenance-DB credentials when available. |
