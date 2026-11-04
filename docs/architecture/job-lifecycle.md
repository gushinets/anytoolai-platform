# Job Lifecycle And Worker Integration

MVP-A jobs are small PostgreSQL-backed workflow execution records. The lifecycle is:

```text
created -> running -> succeeded
                 -> failed
                 -> canceled
```

## Claim semantics

`JobRepository.claim_created(job_id)` performs one conditional database update:

```text
WHERE id = job_id AND status = created
```

On success it sets `status=running` and `started_at`. `WorkflowJobService.claim_created(...)` emits
`workflow.started` in that same caller-owned transaction, so either both the running state and its
start event commit or neither does. The transaction commits before action execution starts. A
repeated claim returns no claim for running or terminal jobs, so it cannot create a duplicate
execution. This conditional update remains the lifecycle idempotency guard even when another
coordination mechanism observes the same row first.

PostgreSQL is the production concurrency contract for this lifecycle. Independent worker processes
are not preassigned jobs; they may all observe the same `created` row, but they first contend for the
PostgreSQL advisory job lease. Only the lease winner proceeds to the conditional `created ->
running` repository transition and may execute the workflow. Workers that do not acquire the lease
return before attempting the repository claim and must not invoke the workflow runner.

The advisory lease and the conditional claim are complementary protections. The lease is held only
while one worker is actively processing a job; it is not permanent ownership or queue assignment.
The guarded repository update is still necessary because lease acquisition does not prove the row is
still `created`: cancellation, a terminal transition, or a stale/repeated processing attempt may
already have changed the lifecycle state.

## Worker flow

The worker application polls PostgreSQL for the oldest `created` job id. Polling is discovery only;
the lease and conditional claim remain the coordination boundaries, so multiple observations cannot
create duplicate execution. For each discovered id, the worker handler:

1. Attempts to acquire the PostgreSQL advisory job lease; lease loss is a normal no-work result.
2. If the lease is acquired, attempts the conditional claim. If no claim is returned, the claim
   path releases the lease, skips scenario loading and runner execution, and returns the current
   durable job snapshot. If the claim succeeds, it persists `workflow.started` in the same
   transaction and commits that unit of work.
3. Loads the linked scenario session using the job's tenant, region, product, frontend, and
   `scenario_session_id` dimensions.
4. Reads the workflow input from `scenario_session.metadata["input"]`.
5. Builds an execution context containing the session and job identifiers.
6. Runs the existing sequential workflow runner against the claimed job.
7. Releases the advisory lease and returns the durable final job snapshot.

The runner's claimed-job entrypoint never creates another job row.

Worker instances do not run Alembic migrations as part of polling, claim, or execution. Deployment
and test database setup apply the migration graph before workers start, then workers use the
migrated `platform` schema.

## A12 scenario runtime start flow

`POST /v1/products/{product_id}/scenarios/{scenario_id}/start` is queue-and-return in A12. It does
not execute the workflow inline in the API process.

The acceptance transaction validates product/scenario/frontend/input/workflow/owner and quota,
creates a `started/processing` session with durable input and one linked `created` job, reserves
capacity against the original bucket, emits admission events, then commits and returns the stable
polling snapshot. All candidate rows, counters and events commit together. A replay returns the
original session/job without another reservation.

Capacity uses `used_count + reserved_count < quantity`. `429 quota_capacity_reserved` means active
reserves temporarily occupy capacity; it leaves no candidate execution and immediate handoff stays
retryable. `429 quota_exhausted` means used quota reached the limit, preserves the rejection audit
through rollback recovery, and immediate handoff also durably fails. Missing/unknown guest identity
returns 422/404 before execution writes. Guest policy selects product-wide or scenario counters;
paid authority arrives only through trusted typed arguments (ANY-766 owns paid HTTP).

Success consumes once when the canonical result is accessible, atomically with publication, job and
scenario completion. Failure/cancellation releases without debit. Neither frontend clicks, provider
attempts nor retries consume quota. Legacy history remains charged under its original rules.
See [quota lifecycle/readback](quota-model.md) for counters, transition events and recovery.

If a pre-claim job already has an invalid `scenario_session_id` link or mismatched runtime
dimensions, the worker terminalizes that poison job as `failed` with a safe integrity error instead
of leaving it `created`. This prevents one broken row from blocking the queue forever.

## Terminal behavior

- Success writes `succeeded`, `completed_at`, and `result_artifact_id`.
- Workflow failure writes `failed`, `completed_at`, `error_code`, and `error_message_safe`, and
  emits `workflow.failed`.
- Poison pre-claim integrity failures may write `created -> failed` with a safe integrity error when
  the worker execution path proves the job cannot be executed because its scenario-session linkage
  is invalid.
- A user cancellation is limited to `created -> canceled`. Before the terminal transition is
  attempted, the cancellation transaction loads the linked scenario session using the job's
  tenant, region, product, frontend, and `scenario_session_id` dimensions. Invalid or missing
  linkage aborts the transaction, leaves the job `created`, and emits no cancellation event.
  Valid cancellation enriches job metadata with the session's `guest_id`, `user_id`, and
  `scenario_chain_id`, then emits `workflow.canceled` through the standard job event context in the
  same transaction. A canceled job is not claimable; running work is not interrupted by that API
  path. If the worker task itself is canceled after claim, the handler persists
  `running -> canceled` and `workflow.canceled` in a recovery transaction, then re-raises
  `asyncio.CancelledError` so cooperative shutdown behavior is preserved.

## Session updates during job execution

The worker also advances the linked scenario session:

- claim success: `started -> running`
- workflow success: `running -> completed`, `current_checkpoint_id -> result_ready`
- workflow failure: `running -> failed`, `current_checkpoint_id -> failed`
- worker cancellation after claim: `running -> failed`, `current_checkpoint_id -> failed`

For reserved jobs, the common finalizer publishes success and completes the running scenario in
the same transaction; failure/cancellation releases through the same metering service. An already
consumed/released decision replays without another scenario mutation. A competing terminal scenario
(such as independently expired) is preserved: late success cannot restore it or publish a result.
Legacy/unmetered reconciliation also preserves an independently expired scenario while projecting
an otherwise active session to the durable job outcome. Runtime updates are guarded by current state.

Safe validation errors retain validation-specific codes such as
`structured_output_validation_failed`. Provider and transport failures retain gateway-owned safe
codes such as `provider_request_failed` or timeout codes. Unknown failures use the generic
`workflow_execution_failed` code and message. Raw provider output, prompts, credentials, and
unsafe exception text never enter job failure fields.

## Correlation and recovery

The job's `scenario_session_id` and `job_id` are propagated to workflow events, action runs,
provider-call ledger rows, and artifacts. The final workflow artifact points back to the job, while
action/provider artifacts retain their action-run linkage. If an execution exception escapes its
transaction boundary after the earlier claim transaction already committed `created -> running` and
`workflow.started`, later rollback recovery must treat that claimed-job start as already durable.

The recovery contract is therefore:

1. the claim transaction owns the first durable `workflow.started`;
2. the later execution transaction may still need recovery for failed workflow/action/provider rows;
3. ordered event backfill must recreate only the missing downstream lifecycle events and must not
   duplicate the earlier claimed-job `workflow.started`.

This keeps claimed-job worker execution aligned with the same causal event history as direct runner
usage while preserving correlation fields across the job row, workflow events, action runs,
provider calls, and artifacts.

`JobRepository` also enforces the critical success contract directly: a `succeeded` transition must
carry `completed_at` plus a real final artifact linked back to the same job.
