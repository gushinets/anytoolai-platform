# Event Taxonomy

Event log is a core runtime contract.

It is not an optional analytics afterthought, and runtime-owned execution code is responsible for
emitting platform events as durable history inside the same transaction boundary as the state
changes that produced them.

## Required dimensions where applicable

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

`tenant_id` and `region` are required for every emitted platform event. The shared emitter rejects
events that do not provide them.

## Runtime ownership

The event log belongs to execution flow code, not a separate BI/export layer.

Current MVP-A runtime-owned emission points:

- scenario session service:
  - `scenario.started`
  - `scenario.checkpoint_reached`
  - `scenario.completed`
  - `scenario.failed`
- workflow/job service:
  - `workflow.started`
  - `workflow.canceled`
  - `workflow.step_started`
  - `workflow.step_skipped`
  - `workflow.step_succeeded`
  - `workflow.step_failed`
  - `workflow.succeeded`
  - `workflow.failed`
- action run service:
  - `action.started`
  - `action.succeeded`
  - `action.failed`
- provider gateway execution path:
  - `provider.request_started`
  - `provider.request_succeeded`
  - `provider.request_failed`
- artifact service:
  - `artifact.created`

Other taxonomy groups remain part of the platform contract even when their concrete runtime service
slice lands later.

For provider events, the event log must persist deterministic correlation to
`platform.provider_calls` through `provider_call_id`, `action_run_id`, `provider_policy_ref`,
`physical_call_index`, and auxiliary `pydantic_run_id` / `litellm_response_id` when present.
These domain events are emitted by runtime-owned execution flow and do not depend on LiteLLM
callbacks or PydanticAI tracing.

## Taxonomy source

The machine-readable source of truth lives in:

- `configs/kernel/platform_events.yaml`

Generated documentation mirrors that source in:

- `docs/generated/event-catalog.md`

## MVP-A platform events by group

### `guest`

- `guest.created`

### `quota`

- `quota.checked`
- `quota.consumed`
- `quota.exhausted`

### `scenario`

- `scenario.started`
- `scenario.checkpoint_reached`
- `scenario.completed`
- `scenario.failed`

### `workflow`

- `workflow.started`
- `workflow.canceled`
- `workflow.step_started`
- `workflow.step_skipped`
- `workflow.step_succeeded`
- `workflow.step_failed`
- `workflow.succeeded`
- `workflow.failed`

### `action`

- `action.started`
- `action.succeeded`
- `action.failed`

### `provider`

- `provider.request_started`
- `provider.request_succeeded`
- `provider.request_failed`

### `artifact`

- `artifact.created`

### `handoff`

- `handoff.created`
- `handoff.viewed`
- `handoff.accepted`
- `handoff.declined`
- `handoff.consumed`

### `client`

- `client.result_copied`
- `client.next_action_clicked`

### `access_lite`

- `email_capture.submitted`
- `paywall.shown`
- `waitlist.intent_submitted`

Product-specific events begin in MVP-B.

## Safe properties rules

Event `properties` must be JSON-safe and bounded.

Rules:

- allow `str`, `int`, `bool`, `None`, and finite `float`
- stringify `datetime`, `date`, `UUID`, and enum-like scalar values
- sanitize list/tuple/set values as arrays
- stringify dictionary keys
- replace unsupported values with a bounded sentinel instead of failing persistence
- redact sensitive values when keys indicate secrets, tokens, credentials, cookies, or
  authorization data
- truncate large strings and summarize oversized collections

Never store secrets, raw credentials, bearer tokens, cookies, or large raw provider payloads in
event properties.
