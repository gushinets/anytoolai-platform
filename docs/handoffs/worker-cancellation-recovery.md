# Handoff: Worker Cancellation Recovery

## Status

Implementation complete; focused and baseline validation pass.

## Finding verification

Valid. `asyncio.CancelledError` was not handled by the worker's `except Exception` block after the
job claim committed, leaving a cancelled execution as `running` indefinitely. No lease or other
recovery mechanism exists in the current worker.

## Implemented changes

- Added `JobRepository.mark_canceled()` for `running -> canceled`.
- Added `WorkflowJobService.mark_canceled()` to emit `workflow.canceled` atomically with that state.
- Added an explicit `except asyncio.CancelledError` in the worker handler: it persists cancellation
  in a new transaction, then re-raises.
- Kept the existing ordinary `Exception` failure handling unchanged.
- Documented the distinction between user pre-claim cancellation and worker-task cancellation.

## Regression coverage

The worker test confirms a cancelled claimed job re-raises `CancelledError`, reaches terminal
`canceled` state with `completed_at`, and emits exactly `workflow.started` then `workflow.canceled`.

## Validation

- Worker, workflow-runner, and storage focused suites: 48 passed.
- Platform-core tests: 146 passed.
- Worker tests: 8 passed.
- `python scripts/agent/quick_check.py`: 205 passed.
- `python scripts/agent/runner.py quick-check`: 205 passed.
