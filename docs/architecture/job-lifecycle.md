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
execution. This is the MVP coordination mechanism; it is not a lease, distributed lock, or queue
engine.

## Worker flow

The worker application polls PostgreSQL for the oldest `created` job id. Polling is discovery only;
the conditional claim remains the coordination boundary, so multiple observations cannot create
duplicate execution. For each discovered id, the worker handler:

1. Atomically claims the job and persists `workflow.started`, then commits that unit of work.
2. Loads the linked scenario session using the job's tenant, region, product, frontend, and
   `scenario_session_id` dimensions.
3. Reads the workflow input from `scenario_session.metadata["input"]`.
4. Builds an execution context containing the session and job identifiers.
5. Runs the existing sequential workflow runner against the claimed job.
6. Returns the durable final job snapshot.

The runner's claimed-job entrypoint never creates another job row.

## A12 scenario runtime start flow

`POST /v1/products/{product_id}/scenarios/{scenario_id}/start` is queue-and-return in A12. It does
not execute the workflow inline in the API process.

The durable ordering is:

1. create `scenario_sessions` row with `status=started`;
2. persist `current_checkpoint_id=processing`;
3. persist `metadata["input"]` from the request body;
4. create one linked `jobs` row with `status=created`;
5. commit;
6. return a stable polling payload containing `scenario_session_id`, `job_id`, `status`,
   `allowed_next_actions`, and optional `result_artifact_id`.

The job create path already enforces that the linked scenario session exists and that the job's
tenant, region, product, and frontend dimensions match the session.

If a pre-claim job already has an invalid `scenario_session_id` link or mismatched runtime
dimensions, the worker terminalizes that poison job as `failed` with a safe integrity error instead
of leaving it `created`. This prevents one broken row from blocking the queue forever.

## Terminal behavior

- Success writes `succeeded`, `completed_at`, and `result_artifact_id`.
- Workflow failure writes `failed`, `completed_at`, `error_code`, and `error_message_safe`, and
  emits `workflow.failed`.
- Poison pre-claim integrity failures may write `created -> failed` with a safe integrity error when
  the worker proves the job cannot be executed because its scenario-session linkage is invalid.
- A user cancellation is limited to `created -> canceled`. A canceled job is not claimable; running
  work is not interrupted by that API path. If the worker task itself is canceled after claim, the
  handler persists `running -> canceled` and `workflow.canceled` in a recovery transaction, then
  re-raises `asyncio.CancelledError` so cooperative shutdown behavior is preserved.

## Session updates during job execution

The worker also advances the linked scenario session:

- claim success: `started -> running`
- workflow success: `running -> completed`, `current_checkpoint_id -> result_ready`
- workflow failure: `running -> failed`, `current_checkpoint_id -> failed`
- worker cancellation after claim: `running -> failed`, `current_checkpoint_id -> failed`

If the workflow runner already terminalized the job before the outer worker error handler runs, the
worker must still advance the scenario session to the matching terminal state instead of leaving it
stuck in `running`.

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
