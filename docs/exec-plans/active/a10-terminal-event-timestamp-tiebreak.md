# Execution Plan: A10 Terminal Event Timestamp Tiebreak

## Status

- State: active
- Owner: agent
- Created: 2026-07-17
- Last updated: 2026-07-17
- Review date: 2026-07-17
- Last run: 2026-07-17
- Next action: patch the no-action-run failed-step replay timestamp tie-break and validate.
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

- [ ] Add a completion-side tie-break for recovered failed steps without action runs.
- [ ] Update the workflow recovery regression to assert timestamp ordering directly.
- [ ] Run focused validation plus quick-check.

## Validation

- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [ ] `python scripts/agent/runner.py quick-check`

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Verified the finding is still valid: no-action-run failed-step replay still shares `record.completed_at` with `workflow.failed`, so ordering depends on replay ID tie-breaks. | Patch the timestamp helper and assert direct timestamp causality in the regression. |
