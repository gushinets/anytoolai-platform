# Scenario Session Model

Every accepted scenario start creates `scenario_session_id`.

For A12, the public API creates the scenario session before it creates the linked workflow job.
With A13 guest quota enabled, `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` first
passes product, scenario, frontend, input, workflow, and guest quota validation, then reserves capacity
in the same transaction as session/job creation. The endpoint is therefore the ownership boundary
for backend quota enforcement, initial session creation, durable session input, and the first
frontend-safe polling response.
The quota policy decides whether the reserved counter is product-wide or specific to the scenario
being started.

Scenario session stores:

- `id`;
- `tenant_id`;
- `region`;
- `product_id`;
- `frontend_id`;
- `scenario_id`;
- `scenario_version`;
- `guest_id` nullable;
- `user_id` nullable;
- `status`;
- `current_checkpoint_id` nullable;
- `current_step` nullable;
- `scenario_chain_id` nullable;
- `parent_scenario_session_id` nullable;
- `source_frontend_instance_id` nullable;
- `metadata` JSON;
- `created_at`;
- `started_at`;
- `last_event_at`;
- `completed_at` nullable;
- `expires_at` nullable.

For worker-owned workflow execution, `metadata["input"]` is the durable JSON object passed as
`scenario.input` to the workflow runner. The worker loads it from the linked scenario session,
not from the job row. Missing or non-object input is recorded as a safe failed job.

For A12, `metadata["input"]` is owned by the API start request and must remain a JSON object. The
job row keeps correlation metadata, but the session remains the authoritative store for scenario
input.

Initial statuses:

- `started`
- `waiting_for_user`
- `running`
- `completed`
- `failed`
- `expired`

## A12 runtime checkpoints

`current_checkpoint_id` is the frontend-safe runtime checkpoint for the session.

Current A12 checkpoints are:

- `processing`: non-actionable state while the job is `created` or `running`;
- `handoff_ready`: non-actionable state for an accepted deferred handoff with no job yet;
- `result_ready`: actionable success state after the linked workflow job succeeded;
- `failed`: terminal safe-failure state with no next actions.

`allowed_next_actions` is derived from the current checkpoint:

- `processing` -> `[]`
- `handoff_ready` -> `[]`
- `failed` -> `[]`
- `result_ready` -> `ScenarioDefinition.allowed_next_actions`

The public polling response also exposes `current_checkpoint_id` so the frontend can send it back
to `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}` for stale-check protection.

## A12 session progression

The A12 public lifecycle is:

```text
API start:
  quota reserved + started + processing + created job

Worker claim:
  running + processing

Workflow success:
  completed + result_ready + result_artifact_id + consumed reservation

Workflow failure or worker cancellation:
  failed + failed + released reservation
```

An accepted scenario start is the queue-and-return transaction that commits the capacity reservation,
started scenario session, and created linked job. If quota is exhausted, the start is not accepted,
no scenario session or job is created, and the API returns standardized `quota_exhausted`.
Temporary occupancy returns
`quota_capacity_reserved` without exhaustion or failed handoff; the same logical request is retryable.
Successful canonical publication consumes the original reservation; failure/cancellation releases it.
For quota-protected products, a missing `guest_id` is also rejected before session/job creation with
frontend-safe `422`; an unknown `guest_id` is rejected before session/job creation with
frontend-safe `404`.

If a queued job is canceled before the worker claims it, polling must still resolve the frontend
snapshot as terminal `failed + failed` even if the stored session row still carries the initial
`processing` checkpoint. Frontends must never observe a terminal failed status paired with the
processing checkpoint.

`GET /v1/scenario-sessions/{id}` is the frontend-safe polling endpoint for this progression. The
response must not expose prompts, provider policies, provider/model names, retry budgets,
PydanticAI run ids, or LiteLLM response ids.

Without `scenario_session_id`, there is no user journey.

## Idempotent scenario start (ANY-150 / ANY-507)

Guest HTTP start accepts an optional `Idempotency-Key`; typed paid start requires it. One logical
submission keeps one key across transport retries and temporary `quota_capacity_reserved` responses.
CE-kit's `prepareScenarioStart()` captures that immutable request and key; each `execute()` reuses
both. `startScenario()` is the one-shot wrapper. Quota reads and result/poll retries create no start.

For metered executions, replay uniqueness is stored on `execution_reservations`:

```text
tenant + region + owner_kind + owner_id + product + scenario + namespace + replay_key
```

Namespace is `start` for ordinary start and `handoff` for the stable runtime handoff ID. The request
hash covers scope, product/scenario/frontend and normalized input; handoff additionally includes
its runtime ID. Guest requests retain guest/body-user correlation. Paid requests use the trusted
owner and exclude untrusted guest/body-user identity, allowance ID and access revision. Non-public
runtime scope also participates; clients cannot select that scope. Origin telemetry
`source_frontend_instance_id` is excluded.

`ScenarioRuntimeService.find_execution_replay(session, owner, replay_identity, request_hash)` reads
the original reservation/session/job and returns their current safe snapshot with `is_replay=True`.
Changed request hashes produce `409 idempotency_key_conflict`; accepted replay reserves nothing,
including after terminal failure or a paid cycle change. Authentication remains ANY-766's boundary;
new-start access/snapshot refresh must not hide a previously accepted execution from its valid owner.

Replay lookup precedes validation required only for new admission, after request-shape/internal-only
visibility checks. New admission uses one candidate savepoint for session/job/bucket/reservation,
reserved increment and events. A competing guest-session or owner-reservation unique violation
rolls back the complete losing candidate before resolving the winner; nothing partially accepted
survives. This path calls `ScenarioSessionService.start`, not the earlier `start_or_get_existing`
helper. The caller still owns final commit/rollback and any final access check.

Historical guest and unmetered starts retain `scenario_sessions.idempotency_key` and
`idempotency_request_hash` plus the migration-0009 unique constraint
`(tenant_id, region, product_id, scenario_id, guest_id, idempotency_key)`. Legacy guest replay creates
no synthetic reservation. This nullable guest constraint alone does not deduplicate `guest_id=NULL`
requests; paid execution always uses its explicit owner-scoped reservation and never this NULL path.
The HTTP request/response DTOs gain no paid authority fields from this internal mechanism.

Both replay paths resolve the persisted product/scenario against current config without pinning the
old scenario version. A version bump therefore remains replayable; removal of the definition may
still return not found. `allowed_next_actions` follows the current definition, including when two
API processes have different config snapshots during an update. This does not create another
execution or move its original quota bucket.

## A17 linked handoff sessions

First handoff acceptance creates the target session immediately; accepted replay returns the
existing target without creating another session or job. It sets
`parent_scenario_session_id` to the source session, inherits the source `scenario_chain_id` (falling
back to the source session id), and persists `handoff_id`, source session id, source artifact id, and
mapped target input in target metadata.

For an `immediate` definition the target session is `started/processing` and has a newly queued job.
For a `deferred` definition it is `waiting_for_user/handoff_ready`, has no job, reserves no quota,
and is still a valid polling snapshot. Consequently `ScenarioSessionSnapshot.job_id` and the public
`ScenarioSessionResponse.job_id` are nullable, while ordinary start responses continue to return a
non-null job id.
