# Execution Plan: A13 Quota Dimension Migration History Fix

## Status

- State: completed
- Owner: agent
- Created: 2026-07-22
- Last updated: 2026-07-22
- Completion note: fixed the contradictory `0007` downgrade behavior and added a migration
  regression for the current `0003` quota-dimension contract.

## Goal

Keep the guest quota dimension migration history internally consistent and reversible for the
current Alembic chain.

## Scope

- Inspect `0003_guest_quota.py` and `0007_guest_quota_dimension.py`.
- Confirm whether the current repository treats `0003` as the baseline owner of quota dimension
  columns.
- Update the smallest migration behavior needed so `head -> 0006` preserves the schema that current
  `0003` creates.
- Add focused migration regression coverage and update runtime-storage docs.

## Decision

`0003_guest_quota.py` owns the current quota dimension columns, index, and unique constraint for
clean databases. `0007_guest_quota_dimension.py` remains a compatibility upgrade for older local/dev
databases that reached `0006` before the `0003` baseline was folded. Because the current `0006`
schema already includes the quota dimension fields, `0007.downgrade()` must be a no-op.

## Validation

- [x] Focused runtime-storage migration test.
- [x] Migration/doc checks.
- [x] Relevant quick-check or targeted backend check.

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-22 | Confirmed `0003` already creates the final quota-dimension schema and changed `0007.downgrade()` to preserve it. Added a regression for `head -> 0006`. | Run focused validation. |
| 2026-07-22 | Focused migration checks, runtime-storage suite, docs checks, generated-docs check, and quick-check passed. | None. |
