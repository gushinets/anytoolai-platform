#!/bin/sh
set -e

# The migration step runs as a backgrounded child with SIGTERM/SIGINT trapped and forwarded
# to it, so `docker stop` interrupts it immediately instead of leaving it running orphaned
# until Docker's stop grace period expires and SIGKILLs the whole container. Without this,
# this shell (PID 1, not exec'd into the migration) would not forward the signal on its own.
trap 'kill -TERM "$migrate_pid" 2>/dev/null' TERM INT

uv run --project apps/platform-api --no-sync anytoolai-platform-migrate &
migrate_pid=$!
wait "$migrate_pid"

exec uv run --project apps/platform-api --no-sync uvicorn anytoolai_platform_api.main:app --host 0.0.0.0 --port 8000 "$@"
