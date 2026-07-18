# Execution Plan: A10 Replay Event Atomic Dedup

## Status

- State: completed
- Owner: agent
- Created: 2026-07-17
- Last updated: 2026-07-17
- Review date: 2026-07-17
- Last run: 2026-07-17
- Next action: none; replay event atomic dedup implementation and validation are complete.
- Blocker: none

## Goal

Make rollback-recovery event replay deduplication atomic so concurrent recovery transactions cannot
persist duplicate semantic events.

## Scope

### In scope

- Replay event insertion in `events.repository` and `events.emitter`
- Replay call sites in workflow/action/provider/artifact recovery helpers
- Focused event-log and rollback recovery validation

### Out of scope

- Normal runtime event emission semantics
- Schema migrations or new event-log uniqueness constraints
- Unrelated recovery ordering behavior

## Relevant docs

- `docs/architecture/event-taxonomy.md`
- `docs/architecture/runtime-storage.md`

## Contracts touched

- Events: replay event IDs and atomic dedup behavior
- Runtime: rollback recovery emit paths
- Tests: replay dedup coverage while preserving `step_id` lookup behavior

## Implementation steps

- [x] Verify the race is still present in current recovery code.
- [x] Add deterministic replay IDs plus conflict-safe insert for replayed events only.
- [x] Update replay call sites and add focused tests.
- [x] Run targeted validation.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py packages/backend/platform-core/tests/unit/test_workflow_runner.py packages/backend/platform-core/tests/unit/test_action_runner.py packages/backend/platform-core/tests/unit/test_provider_gateway.py -q`
- [x] `python scripts/agent/runner.py quick-check`

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Verified the recovery race is still present: replay paths still do `exists_event(...)` followed by plain insert with a fresh `event_id`. | Patch replay-only atomic dedup and validate it with focused regressions. |
| 2026-07-17 | Implemented deterministic replay IDs, conflict-safe replay insert handling, replay call-site wiring, and focused event-log coverage; targeted suites and repo quick-check passed. | None. |
