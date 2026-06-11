# Event Taxonomy

Event log is core platform history.

## Required dimensions where applicable

- event_id
- event_type
- timestamp
- tenant_id
- region
- product_id
- frontend_id
- guest_id/user_id
- scenario_session_id
- scenario_chain_id
- job_id
- workflow_id
- workflow_version
- action_type
- action_config_id
- provider
- model
- artifact_id
- handoff_id
- result_status
- error_code
- acquisition_source

## MVP-A events

- guest.created
- product.opened
- quota.checked
- quota.consumed
- quota.exhausted
- scenario.started
- scenario.checkpoint_reached
- scenario.completed
- scenario.failed
- workflow.started
- workflow.succeeded
- workflow.failed
- action.started
- action.succeeded
- action.failed
- provider.request_started
- provider.request_succeeded
- provider.request_failed
- artifact.created
- email_capture.submitted
- paywall.shown
- waitlist.intent_submitted
- handoff.created
- handoff.viewed
- handoff.accepted
- handoff.declined
- handoff.consumed
- client.result_copied
- client.next_action_clicked

Product-specific events begin in MVP-B.
