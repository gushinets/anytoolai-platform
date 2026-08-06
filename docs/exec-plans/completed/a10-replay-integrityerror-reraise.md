# Execution Plan: A10 Replay IntegrityError Reraise

## Status

- State: completed
- Owner: agent
- Created: 2026-07-17
- Last updated: 2026-08-05
- Review date: 2026-07-17
- Last run: 2026-07-17
- Next action: none; implementation and validation are complete.
- Blocker: none

## Goal

Preserve the original `IntegrityError` when replay insertion fails and no stored duplicate event can
be read back.

## Scope

### In scope

- `EventLogRepository.create(...)` replay-only IntegrityError handling
- Focused event-log regression coverage

### Out of scope

- New schema changes
- Normal non-replay event insertion behavior
- Unrelated replay ordering or dedup logic

## Relevant docs

- `docs/architecture/event-taxonomy.md`
- `docs/architecture/runtime-storage.md`

## Contracts touched

- Events: replay insertion error handling
- Tests: non-duplicate replay IntegrityError propagation

## Implementation steps

- [x] Re-raise the original replay `IntegrityError` when no stored duplicate is found.
- [x] Add a focused regression for the non-duplicate failure path.
- [x] Run targeted validation.

## Validation

- [x] The event-log regression asserts propagation of the original `sa.exc.IntegrityError`.
- [x] PR #54 `quick-check` passed on Linux and Windows baseline jobs.

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Verified the finding is still valid: the replay insert handler currently masks some non-duplicate `IntegrityError` cases by converting them into a round-trip failure. | Patch the handler and add a focused propagation regression. |
| 2026-08-05 | Verified commit `1881c79` contains the replay error fix and regression; PR #54 quick-check passed. | None. |
