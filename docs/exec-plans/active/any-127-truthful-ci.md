# Execution Plan: ANY-127 Canonical Commands and Truthful CI

## Status

- State: active
- Owner: agent
- Created: 2026-07-15
- Last updated: 2026-07-15
- Review date: 2026-07-15
- Next action: implement and validate canonical runner, locked frontend checks, and CI parity.
- Blocker: GitHub authentication is required to publish the prepared branch.
- Linear: `ANY-127`

## Goal

Provide one cross-platform command interface whose local and CI results represent only implemented
repository behavior.

## Scope

- Add doctor, quick, frontend, full, config, architecture, and minimal context commands.
- Lock pnpm and require frozen installation.
- Remove ignored required failures and placeholder smoke/E2E evidence.
- Pin third-party GitHub Actions to immutable revisions.
- Keep quick-check DB-free and defer unfinished MVP journeys to product specifications.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py quick-check` (233 passed)
- [x] `python scripts/agent/runner.py frontend-check`
- [x] `python scripts/agent/runner.py full-check` (233 baseline + 2 Freelancer tests)
- [x] focused runner and ordering regression tests

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-15 | Added the canonical command surface, frozen pnpm install, real TypeScript checks, pinned actions, and removed placeholder gates. | Review and publish after GitHub authentication is restored. |

The previous timestamp-plus-random-ID test ordering exposed real nondeterminism. Runtime IDs now
include a sortable creation prefix while remaining opaque and unique, so same-timestamp ledger rows
retain causal order.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-15 | Compile current TypeScript packages without inventing product bundling. | MVP web and CE journeys remain feature-owned. |
| 2026-07-15 | Remove placeholder kernel/E2E gates. | Unimplemented journeys cannot count as passing evidence. |
