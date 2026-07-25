# Execution Plan: A17 Handoff Expiry CAS Follow-up

## Status

- State: completed
- Owner: agent
- Created: 2026-07-22
- Last updated: 2026-07-22
- Review date: 2026-07-22
- Next action: none
- Blocker: none

## Goal

Verify the reported quota rollback issue and make preview, decline, and accept boundary behavior
deterministic when time crosses handoff expiry between service precheck and repository transition.

## Research result

- Quota exhaustion durability is already implemented by phased rollback recovery and covered by
  service/API tests; no additional quota change is required.
- `claim_accept` already guards `expires_at > now`, while `mark_viewed` and `decline` do not.
- A failed expiry CAS can leave an actionable-status row that the service must atomically expire
  before producing its final preview/error.

## Implementation and validation

- [x] Add `expires_at > now` to viewed/declined repository transitions.
- [x] Resolve failed boundary CAS operations through guarded expiry and existing expiry events.
- [x] Add repository/service race-boundary tests for preview, decline, and accept consistency.
- [x] Re-run existing quota durability coverage, focused handoff tests, and repository checks.

## Resolution

- Fix 1 required no new code: current quota rollback recovery and API coverage already preserve the
  usage row, `quota.checked`, `quota.exhausted`, safe 429 response, and `handoff.failed` state.
- Fix 2 added storage-level unexpired guards and deterministic service fallback to the guarded
  expired transition/event when time crosses the boundary before the CAS.

## Validation result

- Focused expiry/quota cases: 6 passed.
- Full handoff/quota unit selection: 20 passed.
- Handoff API selection: 5 passed.
- Canonical DB-free aggregate: 330 passed, 3 deselected.
- Config, architecture, docs, generated-doc freshness, formatting, source lint, and diff checks passed.
