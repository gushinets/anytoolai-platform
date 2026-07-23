# Execution Plan: Handoff Quota Failure Atomic Finalization

## Status

- State: blocked
- Owner: agent
- Created: 2026-07-23
- Last updated: 2026-07-23
- Review date: 2026-07-23
- Next action: run and pass the PostgreSQL-marked recovery test in CI or against a configured local
  PostgreSQL database
- Blocker: validation incomplete because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is not configured
  locally

## Goal

Make immediate-handoff quota rollback recovery atomically persist the terminal `failed` handoff,
quota audit state, and `handoff.failed` event so no process interruption can leave a stuck
`created/viewed + error_code` row.

## Research result

The current rollback callback commits only `error_code=quota_exhausted`. The router later opens a
separate transaction to call `mark_failed()`. Normal pre-consent transitions correctly exclude that
marker, but a process failure between the two transactions leaves a durable nonterminal row that
cannot progress. The router's existing `mark_failed()` operation is already idempotent when the row
is terminal, so recovery can become the durable finalization owner without changing API behavior.

## Implementation

- Replace quota failure reservation with a guarded `created/viewed -> failed` repository operation.
- Emit quota state/events and `handoff.failed` in the same recovery transaction.
- Extract shared handoff event construction so recovery and `HandoffService` use one safe contract.
- Keep the router's later `mark_failed()` call as an idempotent no-op after successful recovery.
- Update unit, API, and PostgreSQL-marked recovery coverage and architecture documentation.

## Validation

- Focused handoff/quota/API tests.
- PostgreSQL-marked test collection/execution when configured.
- Documentation/generated checks and canonical quick-check.

## Validation result

- Focused handoff, quota, and API tests: 31 passed.
- PostgreSQL suite: four tests collected and skipped because the local maintenance database URL was
  not configured.
- Canonical quick-check: 336 passed, 5 deselected.
- Config, architecture, documentation, generated-doc freshness, source lint, formatting, and diff
  checks passed.
