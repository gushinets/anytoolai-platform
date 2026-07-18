# Execution Plan: A10 Replay All Step Action Attempts

## Status

- State: active
- Owner: agent
- Created: 2026-07-17
- Last updated: 2026-07-17
- Review date: 2026-07-17
- Last run: 2026-07-17
- Next action: patch workflow recovery to replay all step action attempts in order, then validate.
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

- [ ] Add ordered action-run lookup for one job/step pair.
- [ ] Replay all recovered step action attempts before the workflow step terminal event.
- [ ] Use the earliest attempt for recovered step-start timing while preserving current terminal timing.
- [ ] Validate with focused workflow tests and quick-check.

## Validation

- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [ ] `python scripts/agent/runner.py quick-check`

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Verified the finding is still valid: workflow recovery uses only `last_action_run_id`, so earlier retry attempts are not replayed. | Patch ordered per-step action-run loading and add a recovery regression for retried steps. |
