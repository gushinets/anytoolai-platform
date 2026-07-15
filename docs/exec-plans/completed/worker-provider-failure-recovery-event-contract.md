# Execution Plan: Worker Provider-Failure Recovery Event Contract

## Status

- State: completed
- Owner: agent
- Created: 2026-07-13
- Last updated: 2026-07-13

## Goal

Verify whether the remaining Windows quick-check failure in the claimed-job provider-failure worker
test reflects a real rollback-recovery ordering bug or a fragile test assumption, then apply the
smallest coherent fix consistent with the documented event contract.

## Scope

### In scope

- `apps/platform-worker/tests/test_worker_boot.py`
- `packages/backend/platform-core/src/anytoolai_platform_core/workflows/runner.py`
- Event ordering and correlation expectations documented under `docs/architecture/`
- Targeted worker/workflow validation plus quick-check

### Out of scope

- Broad redesign of event-log persistence ordering
- Unrelated workflow/provider recovery changes
- CI-only workarounds

## Relevant docs

- `docs/core-beliefs.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/job-lifecycle.md`

## Contracts touched

- Events: rollback recovery must preserve durable workflow/action/provider event history and
  correlation.
- Tests: worker recovery assertions should depend only on documented durable guarantees.

## Implementation steps

- [x] Read the relevant docs and inspect the worker test plus workflow rollback-recovery path.
- [x] Reproduce the reported worker failure against the current branch.
- [x] Decide whether the bug is in runtime ordering or the test contract.
- [x] Apply the smallest coherent fix and validate with targeted tests plus quick-check.
- [x] Record summary and handoff details.

## Validation

- [x] `.quick-check-venv\Scripts\python.exe -m pytest apps/platform-worker/tests/test_worker_boot.py::test_production_worker_provider_failure_preserves_claimed_job_recovery_state -q`
- [x] `.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [ ] `python scripts/agent/quick_check.py`
- [ ] `python scripts/agent/runner.py quick-check`
  Blocked by an unrelated local Windows temp-directory permission failure in `.quick-check-tmp\pytest\pytest-of-jackd` (`WinError 5`) before the patch area is exercised.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-13 | Treat the remaining worker failure as a test-contract bug, not a workflow recovery ordering bug. | The workflow recovery code still emits recovered step events before `workflow.failed`, but persisted query order is only `timestamp,event_id`, which is not a documented durable ordering guarantee. |
| 2026-07-13 | Keep the fix scoped to `apps/platform-worker/tests/test_worker_boot.py`. | The analogous workflow unit test was already stabilized on this branch, and the runtime/storage contracts already guarantee durable presence and correlation rather than UUID tie-break order. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-13 | Read the architecture docs and inspected the worker test, workflow recovery helpers, and the analogous workflow unit test. | Reproduce the worker failure and confirm whether the runtime contract actually guarantees persisted sibling-event order. |
| 2026-07-13 | Confirmed the worker test still asserted `workflow.step_started` before `workflow.step_failed` via `timestamp,event_id` query order even though the same assumption had already been removed from the workflow unit suite. | Replace the worker test with stable presence/correlation assertions and rerun the focused worker/workflow suites. |
| 2026-07-13 | Focused worker and workflow tests passed after replacing the worker ordering assertion with durable correlation checks. | Attempt baseline quick-check validation and record any unrelated blockers. |
| 2026-07-13 | `quick_check.py` and `runner.py quick-check` both failed before reaching this patch area because pytest could not scan `.quick-check-tmp\pytest\pytest-of-jackd` on this machine (`PermissionError`, `WinError 5`). | Report the unrelated baseline blocker clearly in the final handoff. |

## Open questions

- Does any repository/runtime layer define a durable total ordering beyond the test query's
  `timestamp, event_id` sort?

## Follow-up debt

- None yet.
