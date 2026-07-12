# Handoff: Worker PostgreSQL Runtime Driver

## Status

Implementation complete. Focused worker/runtime validation passes. Container-level validation was
not runnable because the local Docker daemon is unavailable.

## Problem and root cause

The worker image installs only the `apps/platform-worker` production dependency graph. That graph
had SQLAlchemy but no PostgreSQL DBAPI. The repository root's `asyncpg` dependency is not installed
by the worker image and is incompatible with the worker's synchronous `create_engine` / `Session`
path anyway. Compose supplied a plain `postgresql://` URL, whose SQLAlchemy default expects the
psycopg2 DBAPI.

## Implemented changes

- Declared `psycopg[binary]>=3.2` as an `apps/platform-worker` runtime dependency.
- Regenerated `apps/platform-worker/uv.lock` with `uv add`.
- Added the same explicit Psycopg dependency to the root managed test environment and lockfile.
- Changed only the worker compose URL to `postgresql+psycopg://...`, explicitly matching Psycopg 3.
- Added a regression test that constructs the real production worker graph with that URL.
- Added the execution plan and task record for repository continuity.

## Why this driver

Psycopg 3 supports SQLAlchemy's synchronous PostgreSQL dialect used by `create_sync_engine()` and
ships a binary extra suitable for the slim runtime image. Reusing `asyncpg` would require converting
the engine, sessions, repositories, queue, handlers, and worker flow to SQLAlchemy async APIs, which
is outside this fix and materially larger.

## Validation evidence

- `uv sync --project apps/platform-worker --frozen --no-dev`: passed (66 packages checked).
- Production environment engine/composition probe: passed; dialect driver was `psycopg` and
  `build_worker(...)` returned `Worker` without a DBAPI import failure.
- `uv run --project apps/platform-worker --with pytest --with alembic python -m pytest apps/platform-worker/tests -q`:
  passed, 6 tests.
- `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -q`: passed, 6 tests;
  the root managed environment imports `psycopg 3.3.4`.
- `docker compose -f infra/compose/docker-compose.yml config`: passed and rendered the worker's
  `postgresql+psycopg://` URL.
- Config validation and architecture validation inside quick-check: passed.
- `git diff --check`: passed.

## Environment-limited checks

- Worker image build and compose boot were not run: `docker info` could not connect because
  `//./pipe/docker_engine` does not exist.
- Full quick-check did not complete cleanly: its pytest phase hit `PermissionError` while scanning
  `.quick-check-tmp/pytest/pytest-of-jackd`. Before that failure, config and architecture validation
  passed; the focused worker suite passed separately using a writable temp directory.

## Suggested next bot action

On a host with Docker running, execute:

```powershell
docker compose -f infra/compose/docker-compose.yml build platform-worker
docker compose -f infra/compose/docker-compose.yml up postgres platform-worker
```

Ensure migrations have been applied before expecting the polling query to succeed. Confirm the
worker remains running and does not report a Psycopg/DBAPI import error.
