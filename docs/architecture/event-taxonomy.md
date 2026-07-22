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

- guest identity service:
  - `guest.created`
- guest quota service:
  - `quota.checked`
  - `quota.consumed`
  - `quota.exhausted`
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

For A13, `quota.consumed` is emitted only for backend-accepted scenario starts. `quota.exhausted`
is emitted when the backend rejects a scenario start because the configured guest quota dimension is
exhausted. Quota events include `quota_dimension` and `quota_dimension_key`; scenario-dimension
quota events also include `quota_scenario_id`. These events do not depend on frontend clicks,
workflow success, provider calls, validation retries, transport retries, PydanticAI telemetry, or
LiteLLM telemetry.

For provider events, the event log must persist deterministic correlation to
`platform.provider_calls` through `provider_call_id`, `action_run_id`, `provider_policy_ref`,
`physical_call_index`, and auxiliary `pydantic_run_id` / `litellm_response_id` when present.
These domain events are emitted by runtime-owned execution flow and do not depend on LiteLLM
callbacks or PydanticAI tracing.

Escaped rollback recovery is part of this durability contract, not a best-effort convenience. When
runtime code reconstructs durable history after a transaction rollback, the recovered event set must
be:

- complete relative to recovered runtime state;
- causally ordered, with replay timestamps clamped monotonically when source timestamps collide or
  regress;
- correlation-preserving across workflow, action, provider, job, and artifact identifiers;
- idempotent enough not to duplicate events that are already durable.

When idempotent recovery encounters an existing deterministic replay-owned event whose timestamp no
longer fits the causal sequence, recovery may repair that replay-owned timestamp. It must not
rewrite ordinary non-replay committed events indiscriminately.

For example, a recovered failed `provider_calls` row requires a matching
`provider.request_failed`, and recovered workflow/action terminal events must not appear before the
recovered `workflow.started` and step-start history they depend on.

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
