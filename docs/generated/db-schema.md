# DB Schema

<!-- Generated file. Do not edit by hand. -->
Canonical source: anytoolai_platform_core.storage.db.runtime_metadata.

Definitions remain in repository configuration; these tables store runtime state.

## platform.action_runs

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| product_id | VARCHAR(128) | no |
| frontend_id | VARCHAR(128) | no |
| scenario_session_id | VARCHAR(128) | no |
| job_id | VARCHAR(128) | no |
| workflow_id | VARCHAR(128) | no |
| step_id | VARCHAR(128) | no |
| action_type | VARCHAR(128) | no |
| action_config_id | VARCHAR(128) | no |
| status | VARCHAR(9) | no |
| input_artifact_id | VARCHAR(128) | yes |
| output_artifact_id | VARCHAR(128) | yes |
| error_code | VARCHAR(128) | yes |
| created_at | DATETIME | no |
| started_at | DATETIME | yes |
| completed_at | DATETIME | yes |
| metadata | JSON | no |

## platform.artifacts

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| product_id | VARCHAR(128) | no |
| frontend_id | VARCHAR(128) | no |
| scenario_session_id | VARCHAR(128) | no |
| job_id | VARCHAR(128) | yes |
| action_run_id | VARCHAR(128) | yes |
| artifact_type | VARCHAR(128) | no |
| status | VARCHAR(7) | no |
| content_text | TEXT | yes |
| content_json | JSON | yes |
| object_storage_key | VARCHAR(512) | yes |
| metadata | JSON | no |
| created_at | DATETIME | no |

## platform.event_log

| Column | Type | Nullable |
|---|---|---|
| event_id | VARCHAR(128) | no |
| event_type | VARCHAR(128) | no |
| timestamp | DATETIME | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| product_id | VARCHAR(128) | yes |
| frontend_id | VARCHAR(128) | yes |
| guest_id | VARCHAR(128) | yes |
| user_id | VARCHAR(128) | yes |
| scenario_session_id | VARCHAR(128) | yes |
| scenario_chain_id | VARCHAR(128) | yes |
| job_id | VARCHAR(128) | yes |
| workflow_id | VARCHAR(128) | yes |
| workflow_version | INTEGER | yes |
| action_run_id | VARCHAR(128) | yes |
| action_type | VARCHAR(128) | yes |
| action_config_id | VARCHAR(128) | yes |
| provider_policy_ref | VARCHAR(128) | yes |
| provider_call_id | VARCHAR(128) | yes |
| provider | VARCHAR(128) | yes |
| model | VARCHAR(256) | yes |
| physical_call_index | INTEGER | yes |
| pydantic_run_id | VARCHAR(128) | yes |
| litellm_response_id | VARCHAR(256) | yes |
| artifact_id | VARCHAR(128) | yes |
| handoff_id | VARCHAR(128) | yes |
| result_status | VARCHAR(64) | yes |
| error_code | VARCHAR(128) | yes |
| acquisition_source | VARCHAR(128) | yes |
| properties | JSON | no |

## platform.guest_identities

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| created_at | DATETIME | no |
| last_seen_at | DATETIME | yes |
| metadata | JSON | no |

## platform.guest_quota_usage

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| guest_id | VARCHAR(128) | no |
| product_id | VARCHAR(128) | no |
| quota_policy_id | VARCHAR(128) | no |
| quota_dimension | VARCHAR(64) | no |
| dimension_key | VARCHAR(128) | no |
| scenario_id | VARCHAR(128) | yes |
| period_key | VARCHAR(128) | no |
| limit_count | INTEGER | no |
| used_count | INTEGER | no |
| created_at | DATETIME | no |
| updated_at | DATETIME | no |
| metadata | JSON | no |

## platform.jobs

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| product_id | VARCHAR(128) | no |
| frontend_id | VARCHAR(128) | no |
| scenario_session_id | VARCHAR(128) | no |
| workflow_id | VARCHAR(128) | no |
| workflow_version | INTEGER | no |
| status | VARCHAR(9) | no |
| input_artifact_id | VARCHAR(128) | yes |
| result_artifact_id | VARCHAR(128) | yes |
| error_code | VARCHAR(128) | yes |
| error_message_safe | TEXT | yes |
| started_at | DATETIME | yes |
| completed_at | DATETIME | yes |
| created_at | DATETIME | no |
| metadata | JSON | no |

## platform.product_handoffs

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| handoff_definition_id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| token_hash | VARCHAR(64) | no |
| status | VARCHAR(8) | no |
| source_product_id | VARCHAR(128) | no |
| source_frontend_id | VARCHAR(128) | no |
| source_scenario_id | VARCHAR(128) | no |
| source_scenario_session_id | VARCHAR(128) | no |
| source_job_id | VARCHAR(128) | no |
| source_artifact_id | VARCHAR(128) | no |
| target_product_id | VARCHAR(128) | no |
| target_frontend_id | VARCHAR(128) | no |
| target_scenario_id | VARCHAR(128) | no |
| target_scenario_session_id | VARCHAR(128) | yes |
| target_job_id | VARCHAR(128) | yes |
| scenario_chain_id | VARCHAR(128) | no |
| created_by_guest_id | VARCHAR(128) | yes |
| accepted_by_guest_id | VARCHAR(128) | yes |
| accepted_from_frontend_instance_id | VARCHAR(128) | yes |
| consent_required | BOOLEAN | no |
| target_start_policy | VARCHAR(9) | no |
| context_payload | JSON | no |
| preview_payload | JSON | no |
| error_code | VARCHAR(128) | yes |
| metadata | JSON | no |
| created_at | DATETIME | no |
| updated_at | DATETIME | no |
| expires_at | DATETIME | no |
| viewed_at | DATETIME | yes |
| accepted_at | DATETIME | yes |
| declined_at | DATETIME | yes |
| consumed_at | DATETIME | yes |
| expired_at | DATETIME | yes |
| failed_at | DATETIME | yes |

## platform.provider_calls

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| product_id | VARCHAR(128) | no |
| frontend_id | VARCHAR(128) | no |
| scenario_session_id | VARCHAR(128) | no |
| job_id | VARCHAR(128) | no |
| action_run_id | VARCHAR(128) | no |
| workflow_id | VARCHAR(128) | no |
| workflow_version | INTEGER | no |
| step_id | VARCHAR(128) | no |
| action_type | VARCHAR(128) | no |
| action_config_id | VARCHAR(128) | no |
| provider_policy_ref | VARCHAR(128) | no |
| provider | VARCHAR(128) | no |
| model | VARCHAR(256) | no |
| gateway_backend | VARCHAR(128) | no |
| gateway_model | VARCHAR(256) | no |
| semantic_attempt_index | INTEGER | no |
| transport_attempt_index | INTEGER | no |
| physical_call_index | INTEGER | no |
| status | VARCHAR(9) | no |
| input_tokens | INTEGER | no |
| output_tokens | INTEGER | no |
| total_tokens | INTEGER | no |
| latency_ms | INTEGER | no |
| estimated_cost | FLOAT | no |
| error_code | VARCHAR(128) | yes |
| error_message_safe | TEXT | yes |
| failure_kind | VARCHAR(128) | yes |
| http_status | INTEGER | yes |
| pydantic_run_id | VARCHAR(128) | yes |
| litellm_response_id | VARCHAR(256) | yes |
| created_at | DATETIME | no |
| started_at | DATETIME | yes |
| completed_at | DATETIME | yes |
| metadata | JSON | no |

## platform.scenario_sessions

| Column | Type | Nullable |
|---|---|---|
| id | VARCHAR(128) | no |
| tenant_id | VARCHAR(128) | no |
| region | VARCHAR(64) | no |
| product_id | VARCHAR(128) | no |
| frontend_id | VARCHAR(128) | no |
| scenario_id | VARCHAR(128) | no |
| scenario_version | INTEGER | no |
| guest_id | VARCHAR(128) | yes |
| user_id | VARCHAR(128) | yes |
| status | VARCHAR(16) | no |
| current_checkpoint_id | VARCHAR(128) | yes |
| current_step | VARCHAR(128) | yes |
| scenario_chain_id | VARCHAR(128) | yes |
| parent_scenario_session_id | VARCHAR(128) | yes |
| source_frontend_instance_id | VARCHAR(128) | yes |
| metadata | JSON | no |
| created_at | DATETIME | no |
| started_at | DATETIME | no |
| last_event_at | DATETIME | no |
| completed_at | DATETIME | yes |
| expires_at | DATETIME | yes |
