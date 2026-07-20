# Scenario Session Model

Every accepted scenario start creates `scenario_session_id`.

For A12, the public API creates the scenario session before it creates the linked workflow job.
With A13 guest quota enabled, `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` first
passes product, scenario, frontend, input, workflow, and guest quota validation, then consumes quota
in the same transaction as session/job creation. The endpoint is therefore the ownership boundary
for backend quota enforcement, initial session creation, durable session input, and the first
frontend-safe polling response.

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
- `result_ready`: actionable success state after the linked workflow job succeeded;
- `failed`: terminal safe-failure state with no next actions.

`allowed_next_actions` is derived from the current checkpoint:

- `processing` -> `[]`
- `failed` -> `[]`
- `result_ready` -> `ScenarioDefinition.allowed_next_actions`

The public polling response also exposes `current_checkpoint_id` so the frontend can send it back
to `POST /v1/scenario-sessions/{id}/next-actions/{next_action_id}` for stale-check protection.

## A12 session progression

The A12 public lifecycle is:

```text
API start:
  quota consumed + started + processing + created job

Worker claim:
  running + processing

Workflow success:
  completed + result_ready + result_artifact_id

Workflow failure or worker cancellation:
  failed + failed
```

An accepted scenario start is the queue-and-return transaction that commits the consumed quota,
started scenario session, and created linked job. If quota is exhausted, the start is not accepted,
no scenario session or job is created, and the API returns standardized `quota_exhausted`.
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
