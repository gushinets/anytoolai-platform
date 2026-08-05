# Execution Plan: PostgreSQL Handoff Index Migration Fix

## Status

- State: completed
- Owner: Codex
- Created: 2026-07-31
- Last updated: 2026-08-05
- Review date: 2026-07-31
- Next action: none; the migration fix and required validation are complete.
- Blocker: none

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

- Historical local migration selection passed seven non-PostgreSQL cases and skipped two
  PostgreSQL cases; the skips are not counted as production-dialect evidence.
- [x] `.venv\\Scripts\\python.exe -m alembic -c migrations/platform/alembic.ini upgrade head --sql`
- [x] PR #54 required CI ran canonical `python scripts/agent/runner.py postgresql-check`
  successfully against PostgreSQL, including migration coverage.
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] PR #54 required CI ran canonical `python scripts/agent/runner.py quick-check` successfully
  on Linux and Windows.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-31 | Edit `0010` in place. | It is the unreleased failing compatibility revision; adding another revision would leave every clean upgrade broken. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-31 | Located invalid raw SQL in `0010`; `0004`/`0008` already use schema-aware Alembic APIs and the canonical head index set excludes the redundant target-session index. | Replace the qualified raw index identifiers and verify rendered SQL. |
| 2026-07-31 | Replaced schema-qualified raw `CREATE INDEX` identifiers with bare index names; SQLAlchemy/Alembic output confirmed the valid PostgreSQL form. | Run the required PostgreSQL CI migration/storage coverage with a maintenance URL. |
| 2026-08-05 | PR #54 required CI supplied the canonical PostgreSQL migration proof and Linux/Windows quick-check evidence. | None. |

## Open questions

- None.

## Follow-up debt

- None.
