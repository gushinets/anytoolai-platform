# DB Schema

Generated-doc mirror of the MVP-A runtime schema from `docs/product-specs/mvp-scope-source-of-truth.md`.

Definitions stay in YAML/Markdown. PostgreSQL stores runtime state only.

## Runtime Tables

- `platform.scenario_sessions`
- `platform.jobs`
- `platform.action_runs`
- `platform.provider_calls`
- `platform.artifacts`
- `platform.event_log`
- `platform.guest_identities`
- `platform.guest_quota_usage`
- `platform.email_captures`
- `platform.paywall_intents`
- `platform.product_handoffs`

## Tables Not Needed In MVP-A

- `platform.products`
- `platform.workflow_definitions`
- `platform.action_definitions`
- `platform.action_configurations`
- `platform.prompt_versions`
- `platform.subscriptions`
- `platform.wallets`
- `platform.ledger_entries`
- `platform.admin_users`

## `platform.scenario_sessions`

```text
id
tenant_id
region
product_id
frontend_id
scenario_id
scenario_version
guest_id nullable
user_id nullable
status
current_checkpoint_id nullable
current_step nullable
scenario_chain_id nullable
parent_scenario_session_id nullable
source_frontend_instance_id nullable
metadata jsonb
started_at
last_event_at
completed_at nullable
expires_at nullable
```

Initial statuses: `started`, `waiting_for_user`, `running`, `completed`, `failed`, `expired`.

## `platform.jobs`

```text
id
tenant_id
region
product_id
frontend_id
scenario_session_id
workflow_id
workflow_version
status
input_artifact_id nullable
result_artifact_id nullable
error_code nullable
error_message_safe nullable
started_at nullable
completed_at nullable
created_at
metadata jsonb
```

Initial statuses: `created`, `running`, `succeeded`, `failed`, `canceled`.

## `platform.action_runs`

```text
id
tenant_id
region
product_id
frontend_id
scenario_session_id
job_id
workflow_id
step_id
action_type
action_config_id
status
input_artifact_id nullable
output_artifact_id nullable
error_code nullable
created_at
started_at nullable
completed_at nullable
metadata jsonb
```

Initial statuses: `created`, `running`, `succeeded`, `failed`, `canceled`, `skipped`.

## `platform.provider_calls`

```text
id
tenant_id
region
product_id
frontend_id
scenario_session_id
job_id
action_run_id
workflow_id
step_id
action_type
action_config_id
provider_policy_id
provider
model
status
input_tokens
output_tokens
latency_ms
estimated_cost
error_code nullable
created_at
started_at nullable
completed_at nullable
metadata jsonb
```

Initial statuses: `created`, `running`, `succeeded`, `failed`, `timed_out`.

## `platform.artifacts`

```text
id
tenant_id
region
product_id
frontend_id
scenario_session_id
job_id nullable
action_run_id nullable
artifact_type
status
content_text nullable
content_json jsonb nullable
object_storage_key nullable
metadata jsonb
created_at
```

MVP-A may store text and JSON directly in PostgreSQL. Keep object storage as an interface.
Initial statuses: `created`, `stored`, `failed`.

## `platform.event_log`

```text
event_id
event_type
timestamp
tenant_id
region
product_id nullable
frontend_id nullable
guest_id nullable
user_id nullable
scenario_session_id nullable
scenario_chain_id nullable
job_id nullable
workflow_id nullable
workflow_version nullable
action_type nullable
action_config_id nullable
provider nullable
model nullable
artifact_id nullable
handoff_id nullable
result_status nullable
error_code nullable
acquisition_source nullable
properties jsonb
```

Event log is required for analytics, debugging, future billing, and later consumers.

## `platform.product_handoffs`

```text
id
handoff_token
tenant_id
region
source_product_id
source_frontend_id
source_scenario_session_id
source_artifact_id nullable
target_product_id
target_frontend_id nullable
target_scenario_id
target_scenario_session_id nullable
status
consent_required
consent_accepted_at nullable
created_by_guest_id nullable
accepted_by_guest_id nullable
context_payload jsonb
created_at
expires_at
```

Statuses: `created`, `viewed`, `accepted`, `declined`, `consumed`, `expired`, `failed`.
