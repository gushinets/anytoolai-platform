# Worktree-Aware Development Runtime

The runner derives an eight-character identity from the normalized repository path. That identity
selects a Compose project and a deterministic API/PostgreSQL port pair, so separate worktrees do not
share default containers or ports.

## Commands

    python scripts/agent/runner.py dev-up
    python scripts/agent/runner.py dev-ready
    python scripts/agent/runner.py dev-status
    python scripts/agent/runner.py dev-down

dev-up checks both host ports before starting Compose and then waits for the API health endpoint.
dev-status prints the Compose project, API URL, database URL, and current Compose service state.
dev-down is scoped to the derived Compose project and is safe to repeat.

## Overrides

Use CLI flags when a derived port is occupied:

    python scripts/agent/runner.py dev-up --api-port 18123 --postgres-port 15555

The equivalent environment variables are ANYTOOLAI_API_PORT, ANYTOOLAI_POSTGRES_PORT, and
ANYTOOLAI_READY_TIMEOUT. Agents should discover endpoints from dev-status rather than assuming
8000/5432.

The runtime never resets databases or tears down a different worktree automatically.
