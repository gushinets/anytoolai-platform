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
- `started_at`;
- `last_event_at`;
- `completed_at` nullable;
- `expires_at` nullable.

Initial statuses:

- `started`
- `waiting_for_user`
- `running`
- `completed`
- `failed`
- `expired`

Without `scenario_session_id`, there is no user journey.
