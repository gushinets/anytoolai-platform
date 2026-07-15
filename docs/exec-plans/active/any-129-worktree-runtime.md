# Execution Plan: ANY-129 Worktree-Aware Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: validate worktree identity, ports, readiness, status, and teardown.
- Blocker: GitHub authentication is required to publish the prepared branch.
- Linear: ANY-129

## Goal

Let concurrent agent worktrees operate the existing Compose topology without default project or
host-port collisions.

## Scope

- Derive Compose project and deterministic ports from normalized repository path.
- Preflight host ports and support CLI/environment overrides.
- Add dev-up, dev-ready, dev-status, and scoped idempotent dev-down.
- Wait on API health rather than sleeping for a fixed interval.
- Keep the existing PostgreSQL, API, and worker topology.

## Validation

- [x] focused runtime command tests (11 passed)
- [x] Docker Compose configuration validation
- [x] python scripts/agent/runner.py validate-docs
- [x] python scripts/agent/runner.py quick-check (243 passed)

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-15 | Added path-derived project/ports, collision preflight, actual health readiness, endpoint discovery, and scoped teardown. | Publish after GitHub authentication is restored. |
