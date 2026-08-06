# Execution Plan: A10 Terminal Event Timestamp Tiebreak

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

Make recovered `workflow.step_failed` sort before recovered `workflow.failed` by timestamp when both
would otherwise share `record.completed_at`.

## Scope

### In scope

- Workflow recovery timestamp selection for no-action-run failed steps
- Regression assertions for causal timestamp ordering

### Out of scope

- Unrelated workflow recovery ordering changes
- Schema or persistence changes

## Relevant docs

- `docs/architecture/workflow-model.md`

## Contracts touched

- Runtime: workflow failed-step replay timestamp tie-break
- Tests: no-action-run recovery ordering assertions

## Implementation steps

- [x] Add a completion-side tie-break for recovered failed steps without action runs.
- [x] Update the workflow recovery regression to assert timestamp ordering directly.
- [x] Run focused validation plus quick-check.

## Validation

- [x] The workflow regression directly asserts `workflow.step_failed.timestamp <
  workflow.failed.timestamp` for the no-action-run path.
- [x] PR #54 `quick-check` passed on Linux and Windows baseline jobs.

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Verified the finding is still valid: no-action-run failed-step replay still shares `record.completed_at` with `workflow.failed`, so ordering depends on replay ID tie-breaks. | Patch the timestamp helper and assert direct timestamp causality in the regression. |
| 2026-08-05 | Verified commit `1881c79` contains the timestamp tie-break and direct-order regression; PR #54 quick-check passed. | None. |
