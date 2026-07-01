# Structured Output

Structured output is enforced in the structured LLM execution layer around `ProviderGateway`.

MVP-A supports:

- input schema validation at the action boundary
- structured provider output validation against JSON Schema
- validation retry on invalid JSON or schema mismatch
- raw normalized provider output handling
- standardized safe failures

## Ownership

`ProviderGateway` remains the transport, persistence, and event boundary.

Responsibility split:

- LiteLLM: transport/router only
- PydanticAI: structured validation and validation retry inside `platform-actions`
- `ProviderGateway`: persistence, event emission, policy resolution, safe errors, hard call limits

## Validation Flow

For structured actions, the runtime flow is:

```text
action input
  ->
action/request validation
  ->
StructuredLlmActionExecutor
  ->
ProviderGateway transport attempt
  ->
physical provider call
  ->
PydanticAI output validation
  ->
success or validation retry
```

If the provider output is invalid:

- PydanticAI owns the validation retry loop
- each retry still produces a new physical provider call through the gateway
- each physical call gets its own `provider_calls` row

## Retry Contract

Structured-output validation uses provider-policy-owned nested retry config:

```text
retry_policy.validation.owner
retry_policy.validation.max_attempts
```

Transport retries are separate:

```text
retry_policy.transport.owner
retry_policy.transport.max_attempts
retry_policy.transport.litellm_num_retries_per_attempt
```

`ProviderGateway` also enforces:

```text
retry_policy.hard_limits.max_physical_provider_calls_per_action
```

## Persistence And Events

Validation retries are not synthetic bookkeeping. They are part of runtime history.

That means:

- one physical call creates one `provider_calls` row
- semantic validation retries increment `semantic_attempt_index`
- transport retries increment `transport_attempt_index`
- every provider event correlates back to the physical row through `provider_call_id`

## Safety

The platform must not rely on prompt-text parsing heuristics or loose JSON probing.

Raw secrets, credentials, and unsafe payloads must not be persisted in provider-call metadata or
provider events.
