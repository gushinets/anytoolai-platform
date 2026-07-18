# Provider Gateway

All provider/model calls go through `ProviderGateway`.

The runtime boundary remains:

```text
Structured LLM Action
        ->
ProviderGateway
        ->
Resolve ProviderPolicy
        ->
Create provider_calls row
        ->
LiteLLM / fake adapter
        ->
Normalize response
        ->
Update provider_calls row
        ->
Emit provider events
```

`ProviderGateway` is not replaced by LiteLLM or PydanticAI. It owns:

- provider-policy resolution
- runtime dimensions
- provider-call persistence
- provider event emission
- safe platform errors
- hard physical-call limits
- deterministic fake-provider behavior

## Boundaries

Runtime code must use:

```text
action/runtime code -> ProviderGateway -> provider adapter protocol -> concrete adapter
```

Direct `litellm` imports are allowed only inside provider adapters. Direct `pydantic_ai` imports are
allowed only inside the structured LLM execution layer under
`packages/backend/platform-actions/**/structured_llm*`.

Actions, workflows, products, scenarios, and executors must not call LiteLLM directly.

## Runtime DTOs

`ProviderRequest`

- carries runtime dimensions through `action_run_id`
- carries `provider_policy_ref`, `workflow_version`, prompt/messages, response schema, and safe
  metadata

`ResolvedProviderRequest`

- is the adapter-facing request after policy resolution
- carries resolved provider/model settings plus ADR-0007 attempt fields:
  `semantic_attempt_index`, `transport_attempt_index`, `physical_call_index`
- carries nested `retry_policy`

`ProviderResponse`

- carries normalized provider/model/output
- carries usage, latency, estimated cost, safe failure data, `http_status`,
  `pydantic_run_id`, and `litellm_response_id` when available

## Retry Ownership

Provider policy is the only owner of retry intent.

The runtime contract is:

```text
retry_policy.transport.owner
retry_policy.transport.max_attempts
retry_policy.transport.litellm_num_retries_per_attempt

retry_policy.validation.owner
retry_policy.validation.max_attempts

retry_policy.hard_limits.max_physical_provider_calls_per_action
```

Ownership is split deliberately:

- `ProviderGateway` owns transport retries around LiteLLM SDK calls inside one semantic
  validation attempt.
- PydanticAI owns structured-output validation retries.
- `ProviderGateway` enforces the hard cap on total physical provider calls for one action run.

Legacy flat fields such as `max_retries` are not part of the contract anymore.

## Provider-Call Lifecycle

Provider-call persistence is gateway-owned and caller-transactional.

The lifecycle is:

1. resolve `ProviderPolicy`
2. create one `platform.provider_calls` row for one physical attempt
3. invoke exactly one physical adapter call
4. update the same row with success or failure data
5. emit provider events with deterministic correlation columns/properties

Invariant:

```text
one provider_calls row == one physical ProviderGateway attempt
```

The gateway must not:

- collapse multiple transport attempts into one row
- create synthetic rows from LiteLLM callbacks
- create synthetic rows for validation retries

## Persistence Contract

`platform.provider_calls` rows persist both success and failure paths.

If a later action-layer exception escapes the caller's `transaction_boundary()` and rolls back the
main unit of work, `ProviderGateway` still preserves each already-executed physical attempt by
replaying the final `platform.provider_calls` row snapshot in the shared row-recovery phase. This
keeps the ledger contract intact without swallowing the original exception.

Escaped rollback recovery also has an event-completeness contract. Every recovered
`platform.provider_calls` row with `status=failed` or `status=timed_out` must have a matching
`provider.request_failed` event, and every recovered succeeded row must have its matching
`provider.request_succeeded` event. Row existence alone is not treated as proof that the matching
provider event already exists.

Key ledger fields:

- `workflow_version`
- `provider_policy_ref`
- `gateway_backend`
- `gateway_model`
- `semantic_attempt_index`
- `transport_attempt_index`
- `physical_call_index`
- `failure_kind`
- `http_status`
- `total_tokens`
- `pydantic_run_id` nullable
- `litellm_response_id` nullable

Required execution dimensions gate persistence. If required dimensions such as `tenant_id` or
`region` are invalid, the gateway must not persist a provider-call row.

## Event Emission

When the shared event emitter is configured, the gateway emits:

- `provider.request_started`
- `provider.request_succeeded`
- `provider.request_failed`

The event log remains the domain source of truth. LiteLLM callbacks and PydanticAI tracing are
auxiliary only.

During escaped rollback recovery, provider events are backfilled from recovered ledger rows using
their original timestamps when available:

- `provider.request_started` from `provider_calls.started_at`
- terminal provider events from `provider_calls.completed_at`

Replay is idempotent at the event level. If the ledger row already exists but one matching provider
event is missing, recovery emits only the missing event and does not duplicate the rest of that
provider call's history.

Provider-event correlation data is persisted both in top-level `event_log` columns and in
`event_log.properties`. It includes:

- `provider_call_id`
- `action_run_id`
- `provider_policy_ref`
- `physical_call_index`
- `semantic_attempt_index`
- `transport_attempt_index`
- `pydantic_run_id` when present
- `litellm_response_id` when present

## LiteLLM Responsibilities

LiteLLM stays inside `providers/adapters/litellm.py`.

It owns:

- provider transport
- router/deployment selection from `configs/kernel/litellm_router.yaml`
- provider response normalization inputs such as usage, model ids, and response ids
- per-attempt transport retry count through
  `retry_policy.transport.litellm_num_retries_per_attempt`

LiteLLM does not own:

- provider-policy resolution
- runtime persistence
- event emission
- structured-output validation
- hard physical-call limits

## PydanticAI Responsibilities

PydanticAI stays inside the structured LLM execution layer in `platform-actions`.

It owns:

- structured-output validation
- JSON Schema enforcement
- validation retry loops
- propagation of `pydantic_run_id` when available

It does not replace the gateway persistence boundary. Structured executors call `ProviderGateway`
through AnytoolAI request/response DTOs, and each actual model call still flows through
gateway-managed row creation, row update, and event emission.

## Fake Provider

The fake provider remains deterministic and does not inspect prompt text for fixture selection.

Selection order:

1. explicit `fixture_key`
2. `request.metadata["fixture_key"]`
3. `action_config_id`
4. `request.metadata["action_config_id"]`

Fixture files live in `tests/fixtures/provider/fake_provider_outputs/`.

## Config Split

Provider policy intent lives in `configs/kernel/provider_policies.yaml`.

It owns:

- provider selection
- model-group selection
- timeout policy
- retry policy
- structured-output mode

LiteLLM router config lives separately in `configs/kernel/litellm_router.yaml`.

It owns:

- deployments
- routing strategy
- credentials
- provider-specific transport settings
