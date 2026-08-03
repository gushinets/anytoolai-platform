# Handoff: Worker Cancellation Recovery

## Status

Implementation complete; focused and baseline validation pass.

## Finding verification

Valid at the time. `asyncio.CancelledError` was not handled by the worker's `except Exception`
block after the job claim committed, leaving a cancelled execution as `running` indefinitely.

Update (ANY-147, 2026-08-03): a lease/recovery mechanism now exists. The worker holds a
Postgres session-scoped advisory lock on a dedicated connection for the duration of each
`running` job (acquired before the `created -> running` claim commits). If the holding
process crashes, is OOM-killed, or is force-killed past a `SIGTERM` grace period, Postgres
drops the lock when the connection dies -- no wall-clock TTL involved. A reconciliation sweep
(run once at worker startup and on every idle loop iteration) non-blockingly probes each
`running` job's lock; a job whose lock nobody holds is terminalized to `failed` with
`error_code=worker_lease_lost`, no auto-retry (side effects inside workflow/provider calls are
not guaranteed idempotent). `main.py` also now registers a real `SIGTERM` handler that drains
the current job before exiting, so an ordinary rolling restart no longer hits this recovery
path at all. See `docs/exec-plans/active/any-147-worker-lease-recovery.md` for the full design
and the one known accepted residual race.

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
