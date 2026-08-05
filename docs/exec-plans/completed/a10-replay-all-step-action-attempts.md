# Execution Plan: A10 Replay All Step Action Attempts

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

Ensure workflow rollback recovery replays every persisted action attempt for a step in persistence
order instead of only replaying the last attempt.

## Scope

### In scope

- Workflow recovery loading of step action runs
- Step started/terminal timestamp selection for recovered multi-attempt steps
- Focused workflow recovery regression coverage

### Out of scope

- Normal non-recovery workflow execution
- New schema changes
- Unrelated recovery orchestration changes

## Relevant docs

- `docs/architecture/workflow-model.md`
- `docs/architecture/runtime-storage.md`

## Contracts touched

- Runtime: workflow rollback replay of multi-attempt step history
- Tests: recovered retry-step ordering and timestamps

## Implementation steps

- [x] Add ordered action-run lookup for one job/step pair.
- [x] Replay all recovered step action attempts before the workflow step terminal event.
- [x] Use the earliest attempt for recovered step-start timing while preserving current terminal timing.
- [x] Validate with focused workflow tests and quick-check.

## Validation

- [x] `test_workflow_recovery_replays_all_step_action_attempts_in_order` is present in the focused
  workflow regression suite introduced by commit `1881c79`.
- [x] PR #54 `quick-check` passed on Linux and Windows baseline jobs.

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Verified the finding is still valid: workflow recovery uses only `last_action_run_id`, so earlier retry attempts are not replayed. | Patch ordered per-step action-run loading and add a recovery regression for retried steps. |
| 2026-08-05 | Verified commit `1881c79` contains the ordered all-attempt replay implementation and focused regression; PR #54 quick-check passed. | None. |
