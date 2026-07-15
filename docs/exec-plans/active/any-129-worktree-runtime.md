# Execution Plan: ANY-129 Worktree-Aware Runtime

## Status

- State: active
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: complete fresh CI on PR #28, then merge.
- Blocker: None. The PR was rebased onto current `main` after ANY-128 merged; it inherits the
  pinned pnpm setup required by full-check CI.
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
| 2026-07-15 | Rebased PR #28 onto merged ANY-128; previous red full-check was CI tool provisioning, not worktree-runtime behavior. | Push with lease and verify fresh CI. |
