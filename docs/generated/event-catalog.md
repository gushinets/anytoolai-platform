# Event Catalog

Generated-doc mirror of the MVP-A platform event taxonomy from `configs/kernel/platform_events.yaml`.

## Platform Events By Group

### guest

- `guest.created`

### quota

- `quota.checked`
- `quota.consumed`
- `quota.exhausted`

### scenario

- `scenario.started`
- `scenario.checkpoint_reached`
- `scenario.completed`
- `scenario.failed`

### workflow

- `workflow.started`
- `workflow.step_started`
- `workflow.step_skipped`
- `workflow.step_succeeded`
- `workflow.step_failed`
- `workflow.succeeded`
- `workflow.failed`

### action

- `action.started`
- `action.succeeded`
- `action.failed`

### provider

- `provider.request_started`
- `provider.request_succeeded`
- `provider.request_failed`

### artifact

- `artifact.created`

### handoff

- `handoff.created`
- `handoff.viewed`
- `handoff.accepted`
- `handoff.declined`
- `handoff.consumed`

### client

- `client.result_copied`
- `client.next_action_clicked`

### access_lite

- `email_capture.submitted`
- `paywall.shown`
- `waitlist.intent_submitted`

## Required Dimensions Where Applicable

- `event_id`
- `event_type`
- `timestamp`
- `tenant_id`
- `region`
- `product_id`
- `frontend_id`
- `guest_id`
- `user_id`
- `scenario_session_id`
- `scenario_chain_id`
- `job_id`
- `workflow_id`
- `workflow_version`
- `action_run_id`
- `action_type`
- `action_config_id`
- `provider_policy_ref`
- `provider_call_id`
- `provider`
- `model`
- `physical_call_index`
- `pydantic_run_id`
- `litellm_response_id`
- `artifact_id`
- `handoff_id`
- `result_status`
- `error_code`
- `acquisition_source`

Product-specific events begin in MVP-B.
