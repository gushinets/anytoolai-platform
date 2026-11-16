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
- quota admission/finalization services:
  - `quota.checked`
  - `quota.reserved`
  - `quota.consumed` (accessible canonical success only)
  - `quota.released`
  - `quota.capacity_reserved` (temporary rejected admission)
  - `quota.exhausted` (used limit reached)
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
- handoff service:
  - `handoff.created`
  - `handoff.viewed`
  - `handoff.accepted`
  - `handoff.declined`
  - `handoff.expired`
  - `handoff.failed`
  - `handoff.consumed`
- client-events ingestion endpoint (`POST /v1/client-events`, ANY-17):
  - `web.product_viewed`
  - `web.form_started`
  - `web.form_submitted`
  - `web.result_viewed`
  - `web.retry_clicked`
  - `web.mode_selected`
  - `web.gap_selected`
  - `web.feedback_submitted`

Other taxonomy groups remain part of the platform contract even when their concrete runtime service
slice lands later.

`web.result_viewed` is emitted once per completed result the page has rendered (after the result
phase commits, not when it is fetched), unless the product's
`ProductDefinition.emitsResultViewed(result)` returns false (the shared runtime still emits its
`scenario_completed` run event, with `resultViewed: false`; only the client-events tracker skips
the `web.*` event). Brief Decoder (ANY-248) uses that hook so the event means "a non-empty
clarifying-question list was rendered"; a zero-question run still renders and the backend still
records `scenario.completed`, but no `web.result_viewed` is sent.

ANY-507 reserves capacity on accepted start (`quota.reserved`), consumes it only when an accessible
canonical result is published (`quota.consumed`), and releases it on terminal failure/cancellation
(`quota.released`). These events commit with their actual state change; replay and losing terminal
decisions emit none. `result_status` is respectively `reserved`, `consumed` or `released`.

`quota.capacity_reserved` records admission rejected while reserves occupy capacity, with
`result_status=failed` and `error_code=quota_capacity_reserved`. Its counter snapshot and event
timestamp retain the observation made before rollback. `quota.exhausted` records a rejected start
whose used quota reached its limit; it is not the one-time successful-consumption edge. ANY-766's
future exhaustion outbox uses `ConsumptionTransition.became_exhausted`, not rejection-event counts.
Frontend clicks, provider calls and retries do not themselves produce consumption.

Reserve/consume/release/capacity events carry owner kind/ID, scope, product/scenario/frontend,
session/job/workflow, applicable handoff/result, and the original bucket identity. Their properties
include `quantity`, `used_count`, `successful_used_count`, `legacy_used_count`, `reserved_count`,
`remaining_count`, `available_count` and `exhausted`; applied transitions also name `reservation_id`.
Guest bucket properties include `guest_quota_usage_id`, `quota_policy_id`, `quota_dimension`,
`quota_dimension_key`, `period_key` and `unit`. Paid bucket properties instead include
`paid_allowance_usage_id`, `allowance_id`, `metric_key` and `unit`. Guest evaluation/rejection events
(`quota.checked`/`quota.exhausted`) retain their existing policy, period and counter properties,
including `quota_scenario_id` for scenario-dimension policies. See [quota model](quota-model.md).

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

If immediate handoff acceptance observes target quota exhaustion and then rolls back its accept
claim, quota recovery must retain one `quota.checked` / `quota.exhausted` pair with the target
product, frontend, scenario-session/chain, guest or trusted paid user, and `handoff_id`. The ordinary
scenario-start path also uses rollback recovery for its final-exhaustion audit.
Temporary occupancy records `quota.capacity_reserved` and keeps handoff consent retryable; it does
not emit this exhausted/failed chain. Ordinary rejection audit recovery is non-critical; handoff
rejection audit recovery is critical.
Once accept has reached exhausted target quota evaluation under the handoff lifecycle advisory lock,
quota recovery owns terminal arbitration: decline and expiry must wait and then observe the durable
`failed` state. The critical recovery transaction recreates the quota pair and emits
`handoff.failed` only if its conditional `created/viewed -> failed` transition wins; if recovery is
retried after a committed pass, the existing quota pair suppresses duplicates. A terminal-CAS loss
without the quota pair is recovery failure and must not produce a returned `429 quota_exhausted`.
`handoff.declined` and `handoff.expired` are not emitted for races after quota-rejection ownership,
so the terminal event chain is not contradictory.

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
- `quota.reserved`
- `quota.consumed`
- `quota.released`
- `quota.capacity_reserved`
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
- `handoff.expired`
- `handoff.failed`

Handoff lifecycle events are emitted only when the guarded durable transition changes state.
Created/viewed/declined/expired/failed correlate primarily to the source session; accepted uses the
pre-generated target session id; consumed uses the linked target session and job. Every event keeps
the shared scenario chain and runtime `handoff_id`. Source-side handoff events also carry the
canonical source job and source artifact dimensions. Target-side events do not reuse those source
rows as top-level runtime dimensions: accepted has no target job yet, while consumed carries the
linked target job. Protected event properties retain canonical source and target identifiers for
auditing. Target workflow, action, provider, and artifact events retain their own dimensions under
the target session. Tokens, mapped context, preview source paths, raw artifacts, prompts, and LLM
debug/provider payloads are forbidden event properties.

### `client`

- `client.result_copied`
- `client.next_action_clicked`

### `web`

- `web.product_viewed`
- `web.form_started`
- `web.form_submitted`
- `web.result_viewed`
- `web.retry_clicked`
- `web.mode_selected`
- `web.gap_selected`
- `web.feedback_submitted`

`web.*` events are the v1 client-event allowlist (ANY-17): the only event types
`POST /v1/client-events` accepts. They are emitted by the client-events ingestion endpoint, not by a
domain runtime service, and carry a client-generated `web_session_id` (30-minute inactivity
rotation) in `properties`. Allowed scalar `properties` keys are `mode`, `field_count`, and
`gap_category`; no other key, and no non-scalar value, is accepted.

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

Task Finder (ANY-247) activates on the first rendered fit score. Every valid result contains the
score, so it uses the default `emitsResultViewed` behavior without a product hook. Copying records
`copy_result` independently and does not emit another `web.result_viewed` for the same result.
