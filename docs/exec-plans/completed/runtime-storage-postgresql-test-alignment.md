# Execution Plan: Runtime Storage PostgreSQL Test Alignment

## Status

- State: completed
- Owner: agent
- Created: 2026-07-29
- Last updated: 2026-08-05
- Review date: 2026-07-29
- Next action: none; implementation and required production-dialect validation are complete.
- Blocker: none

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

- Historical local runtime-storage run collected but skipped without a database URL; a second
  local attempt reached PostgreSQL but failed maintenance-database authentication. Neither attempt
  is counted as successful validation.
- [x] PR #54 required CI ran canonical `python scripts/agent/runner.py postgresql-check`
  successfully against PostgreSQL, including runtime-storage coverage.
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
| 2026-08-05 | Reconciled the historical local skip/authentication failure with PR #54's successful canonical PostgreSQL CI evidence. | None. |
