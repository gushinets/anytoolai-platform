# Execution Plan: Handoff Quota Failure Reservation Transition Guard

> Superseded on 2026-07-23 by atomic quota-failure finalization. Recovery no longer commits a
> pre-terminal reservation; see `docs/exec-plans/active/handoff-quota-failure-atomic-finalization.md`.

## Status

- State: completed
- Owner: agent
- Created: 2026-07-23
- Last updated: 2026-07-23
- Review date: 2026-07-23
- Next action: run PostgreSQL-marked coverage in CI or a configured local environment
- Blocker: none

## Goal

Ensure a handoff with an atomically reserved quota-exhaustion failure can only finalize as
`failed`, and cannot be overtaken by view, decline, expiry, or another accept transition.

## Research result

The quota rollback recovery reserves `error_code=quota_exhausted` while retaining the pre-consent
`created` or `viewed` status until the API router's separate failure transaction calls
`mark_failed()`. `claim_accept` already requires `error_code IS NULL`, but `mark_viewed`, `decline`,
and `expire_if_due` do not. Those operations can therefore win during the reservation/finalization
window and produce contradictory terminal state.

## Implementation

- Make every non-failure transition out of `created`/`viewed` require `error_code IS NULL`.
- Keep `mark_failed` as the sole transition allowed to consume a reserved failure.
- Return safe non-actionable behavior from token operations that encounter a reservation.
- Add repository/service regression coverage for reserved failure versus decline and expiry,
  asserting final `failed` state and exactly one `handoff.failed`.
- Update handoff, quota, runtime-storage, and event durability documentation.

## Validation

- Focused handoff, quota, and API tests.
- PostgreSQL handoff concurrency test collection/execution when configured.
- Documentation/generated checks and canonical quick-check.

## Validation result

- Focused handoff, quota, and API tests: 32 passed.
- PostgreSQL suite: four tests collected and skipped because the local maintenance database URL was
  not configured.
- Canonical quick-check: 337 passed, 5 deselected.
- Config, architecture, documentation, generated-doc freshness, source lint, formatting, and diff
  checks passed.
