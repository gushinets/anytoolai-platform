# Execution Plan: A10 Step Failure Recovery Timestamp Fix

## Status

- State: active
- Owner: agent
- Created: 2026-07-17
- Last updated: 2026-07-17
- Review date: 2026-07-17
- Last run: 2026-07-17
- Next action: none; implementation is complete, with direct `quick_check.py` still subject to the known Windows pytest temp-root PermissionError.
- Blocker: `python scripts/agent/quick_check.py` still intermittently fails on this machine when pytest enumerates `.quick-check-tmp/pytest/pytest-of-jackd`, although `python scripts/agent/runner.py quick-check` passes.

## Goal

Keep recovered `workflow.step_failed` timestamps causally ordered when a workflow step fails before
any `action_run` exists.

## Scope

### In scope

- Workflow rollback-recovery timestamp selection for terminal step events without action execution
- Regression coverage for recovered `workflow.step_failed` ordering in the no-action-run path
- Validation needed for docs and backend/runtime checks

### Out of scope

- Changes to unrelated workflow recovery ordering
- Durable workflow-engine behavior
- Provider/action recovery changes outside the step timestamp fallback

## Relevant docs

- `docs/architecture/workflow-model.md`
- `docs/architecture/runtime-storage.md`

## Contracts touched

- Runtime: workflow step terminal-event timestamp replay fallback
- Tests: recovered failed-step ordering without an action run

## Implementation steps

- [x] Update the failed-step terminal timestamp fallback for no-action-run recovery.
- [x] Extend workflow recovery tests to assert causal ordering for the pre-action failure path.
- [x] Run targeted backend tests plus quick-check validation.

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests -q`
- [ ] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py quick-check`

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Reviewed the workflow recovery timestamp path, found the no-action-run fallback, and identified the existing pre-start failure regression to extend. | Patch the fallback and verify recovered `workflow.step_failed` order stays causal. |
| 2026-07-17 | Patched failure-specific step replay timestamps, extended the pre-action failure regression, passed `packages/backend/platform-core/tests`, and passed `python scripts/agent/runner.py quick-check`. | None; direct `python scripts/agent/quick_check.py` remains affected by the known Windows pytest temp-root PermissionError on this machine. |
