# Task: Worker PostgreSQL Runtime Driver

## Brief task description

Fix the production worker's PostgreSQL startup mismatch: its synchronous SQLAlchemy engine used a
PostgreSQL URL, but the worker's `--no-dev` image environment did not install a compatible DBAPI.

## Implementation summary

Declared Psycopg 3 with its binary runtime in `apps/platform-worker`, updated the worker lockfile,
and selected it explicitly with `postgresql+psycopg://` in compose. Added a production-composition
regression test that fails if the configured synchronous DBAPI cannot be loaded. Added Psycopg to
the root test dependency set so quick-check's managed environment also executes that real boot path.
