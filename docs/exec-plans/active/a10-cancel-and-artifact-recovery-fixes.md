# Execution Plan: A10 Cancel And Artifact Recovery Fixes

## Status

- State: active
- Owner: agent
- Created: 2026-07-17
- Last updated: 2026-07-17
- Review date: 2026-07-17
- Last run: 2026-07-17
- Next action: none; implementation and validation are complete.
- Blocker: none

## Goal

Fix two escaped rollback-recovery gaps:

- replay `workflow.canceled` durably during generic rollback recovery;
- keep explicitly cleared failed-action `output_artifact_id` values cleared when the artifact row rolled back.

## Scope

### In scope

- Workflow cancellation rollback-recovery event replay
- Failed-action rollback row recovery for missing structured-output artifacts
- Focused workflow/action regression coverage
- Targeted backend validation and quick-check

### Out of scope

- Unrelated workflow recovery ordering changes
- Durable workflow-engine behavior
- Schema changes or new persistence tables

## Relevant docs

- `docs/architecture/workflow-model.md`
- `docs/architecture/action-runner.md`

## Contracts touched

- Runtime: escaped workflow cancellation recovery must recreate `workflow.canceled`
- Runtime: failed-action rollback recovery must distinguish omitted artifact override from explicit `None`
- Tests: workflow cancellation recovery and failed-action missing-artifact recovery

## Implementation steps

- [x] Verify both findings against the current branch state and inspect the relevant tests.
- [x] Replay `workflow.canceled` from the generic rollback recovery path and add a regression.
- [x] Preserve explicit cleared artifact ids during failed-action rollback recovery and add a regression.
- [x] Run targeted backend validation plus quick-check.

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests -q`
- [x] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py quick-check`

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Verified both findings are still valid in the current branch: canceled rollback recovery still passes `terminal_event_type=None`, and failed-action recovery still uses a truthiness fallback that can restore a rolled-back artifact id. | Patch both paths minimally, extend the focused regressions, and validate. |
| 2026-07-17 | Replayed `workflow.canceled` from generic rollback recovery, terminalized the recovered canceled job row before event replay, preserved explicit cleared action artifact ids with a sentinel override, and passed focused tests plus full quick-check validation. | None. |
