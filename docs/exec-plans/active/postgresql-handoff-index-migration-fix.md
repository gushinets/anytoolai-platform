# Execution Plan: PostgreSQL Handoff Index Migration Fix

## Status

- State: active
- Owner: Codex
- Created: 2026-07-31
- Last updated: 2026-07-31
- Review date: 2026-07-31
- Next action: correct revision `0010` PostgreSQL index DDL and verify offline SQL output.
- Blocker: local PostgreSQL maintenance URL is not configured, so online migration validation must run in CI.

## Goal

Make clean and compatibility upgrades to Alembic head valid on PostgreSQL without changing the
canonical handoff index contract.

## Scope

### In scope

- Revision `0010` online/offline PostgreSQL DDL
- Offline SQL and migration regression assertions
- Migration task documentation

### Out of scope

- Worker test changes
- A new compatibility revision: `0010` is the unreleased failing revision and is edited in place.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/architecture/runtime-storage.md`

## Contracts touched

- DB: `platform.product_handoffs` index migration only

## Implementation steps

- [x] Identify the invalid DDL source and inspect the handoff migration chain.
- [x] Correct index-name qualification and add regression coverage.
- [x] Run offline generation and all available migration checks.
- [x] Record PostgreSQL-only validation status and create the task handoff.

## Validation

- [x] `apps/platform-api/tests/test_migrate.py -q` (`7 passed, 2 skipped`)
- [x] `.venv\\Scripts\\python.exe -m alembic -c migrations/platform/alembic.ini upgrade head --sql`
- [ ] PostgreSQL migration tests when a maintenance URL is available
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [ ] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-31 | Edit `0010` in place. | It is the unreleased failing compatibility revision; adding another revision would leave every clean upgrade broken. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-31 | Located invalid raw SQL in `0010`; `0004`/`0008` already use schema-aware Alembic APIs and the canonical head index set excludes the redundant target-session index. | Replace the qualified raw index identifiers and verify rendered SQL. |
| 2026-07-31 | Replaced schema-qualified raw `CREATE INDEX` identifiers with bare index names; SQLAlchemy/Alembic output confirmed the valid PostgreSQL form. | Run the required PostgreSQL CI migration/storage coverage with a maintenance URL. |

## Open questions

- None.

## Follow-up debt

- None.
