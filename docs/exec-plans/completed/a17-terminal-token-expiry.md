# Execution Plan: A17 Terminal Handoff Token Expiry

## Status

- State: completed
- Owner: agent
- Created: 2026-07-23
- Last updated: 2026-07-23
- Review date: 2026-07-23
- Next action: none
- Blocker: none

## Goal

Ensure an expired opaque handoff token cannot expose mapped preview data or linked target runtime
identifiers, while preserving durable accepted, consumed, declined, and failed states.

## Research result

- `expire_if_due()` intentionally mutates only pre-consent `created`/`viewed` rows.
- `get_preview()` currently returns full safe-preview fields for terminal rows even after TTL.
- The API contract already returns HTTP 200 with `status: expired` for consent-page rendering, so a
  redacted representation is less disruptive than changing GET to HTTP 410.

## Implementation and validation

- [x] Enforce token TTL independently of the persisted lifecycle status.
- [x] Redact expired token previews and linked target identifiers without mutating terminal rows.
- [x] Return safe expired errors for token-based accept/decline after TTL.
- [x] Cover accepted, consumed, declined, and failed states before and after expiry.
- [x] Run focused handoff/API tests and canonical repository checks.

## Validation result

- Terminal-state and expired API focused cases: 5 passed.
- Full handoff unit selection: 17 passed.
- Full handoff API selection: 5 passed.
- Canonical DB-free aggregate: 334 passed, 3 deselected.
- Config, architecture, docs, generated-doc freshness, formatting, source lint, and diff checks passed.
