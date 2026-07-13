# Scenario Session Model

Every scenario start creates `scenario_session_id`.

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

Initial statuses:

- `started`
- `waiting_for_user`
- `running`
- `completed`
- `failed`
- `expired`

Without `scenario_session_id`, there is no user journey.
