# Execution Plan: Worker Cancellation Ledger Recovery

## Status

- State: completed
- Owner: agent
- Created: 2026-07-13
- Last updated: 2026-07-13

## Goal

Ensure worker-task cancellation preserves a durable runtime ledger for in-flight workflow/action/provider
execution, including provider-call rows, action-run rows, and correlated events, before the handler
terminalizes the job as `canceled`.

## Scope

### In scope

- Worker claimed-job cancellation path.
- Shared transaction rollback-recovery execution.
- Action/provider/workflow rollback-recovery behavior for `asyncio.CancelledError`.
- Production-composed worker cancellation regression coverage.

### Out of scope

- New queue semantics, leases, or distributed cancellation coordination.
- Product-specific workflow behavior.
- Changing the existing minimal `running -> canceled` worker terminal model.

## Relevant docs

- `docs/architecture/workflow-model.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/job-lifecycle.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/runtime-storage.md`
- `docs/agent/failure-recovery.md`

## Contracts touched

- Worker: cooperative cancellation must still leave a durable terminal job snapshot.
- Events: workflow/action/provider event history must remain correlated and durable on cancellation.
- Runtime ledger: every physical provider attempt must still produce a durable `provider_calls` row.

## Implementation steps

- [x] Inspect the worker cancellation path, transaction boundary, and current rollback-recovery callbacks.
- [x] Reproduce the current cancellation-ledger loss with a production-composed provider cancellation path.
- [x] Patch cancellation-aware recovery with the smallest coherent changes.
- [x] Add/update production-composed regression coverage.
- [x] Run focused and baseline validation.

## Validation

- [x] `D:\Devpy\anytoolai-platform\.quick-check-venv\Scripts\python.exe -m pytest apps/platform-worker/tests -q`
- [x] `D:\Devpy\anytoolai-platform\.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests -q`
- [x] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-13 | Run rollback recovery callbacks for `BaseException`, not only `Exception`. | `asyncio.CancelledError` is the cancellation path the worker intentionally re-raises, and skipping callback execution there loses in-flight provider/action ledger rows. |
| 2026-07-13 | Recover canceled in-flight action runs as failed rows/events with safe cancellation-specific error codes. | The platform already has `action.failed`/`workflow.step_failed` and `provider.request_failed` events, but no action/workflow canceled event taxonomy; reusing the existing failure ledger keeps correlation durable without expanding the runtime model. |
| 2026-07-13 | Persist workflow step recovery metadata/events on cancellation before the handler marks the job canceled. | This preserves workflow/action/provider correlation for the interrupted step while keeping `workflow.canceled` as the terminal job event. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-13 | Verified that `RunWorkflowHandler` re-raises `asyncio.CancelledError` after terminalizing the job, but `transaction_boundary()` only runs rollback recovery callbacks for `Exception`. | Patch cancellation-aware rollback recovery and cover the real provider/action execution path. |
| 2026-07-13 | Confirmed the current production-composed cancellation path would roll back in-flight provider/action/workflow ledger state because provider/action/workflow recovery is registered in the execution transaction but never invoked on `CancelledError`. | Update the shared transaction boundary and add cancellation-specific recovery registration where needed. |
| 2026-07-13 | Added `BaseException`-aware rollback recovery plus cancellation recovery in the action/workflow layers, and covered it with direct provider/action tests plus a production-composed worker/provider cancellation test. | Run the full worker/core suites and the canonical quick-check commands. |
| 2026-07-13 | Worker tests, platform-core tests, direct quick-check, and runner quick-check all passed. | No further work for this task. |

## Open questions

- None yet.

## Follow-up debt

- None yet.
