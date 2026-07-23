# Structured Output

Structured output is split across the structured LLM execution layer and a platform-owned
finalization layer around `ProviderGateway`.

MVP-A supports:

- input schema validation at the action boundary
- structured provider output validation against JSON Schema
- validation retry on invalid JSON or schema mismatch
- raw provider output debug artifact persistence
- normalized structured artifact persistence
- standardized safe failures

## Ownership

`ProviderGateway` remains the transport and provider-call/event boundary.

Responsibility split:

- LiteLLM: transport/router only
- PydanticAI: structured generation, output validation, and validation retry inside `platform-actions`
- AnytoolAI `platform-core`: final parse, object-only enforcement, final JSON Schema validation,
  normalization to dict, structured artifact persistence, raw debug artifact persistence, and safe
  structured-output validation errors
- `ProviderGateway`: provider-call persistence, provider events, policy resolution, and hard call limits

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
  ->
AnytoolAI final parse/validate/normalize
  ->
structured artifact or raw debug artifact
```

If the provider output is invalid:

- PydanticAI owns the validation retry loop
- each retry still produces a new physical provider call through the gateway
- each physical call gets its own `provider_calls` row
- after retry exhaustion, the platform preserves the last raw provider output as a debug artifact
  and raises one safe `structured_output_validation_failed` error

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
- successful final validation creates a `structured_output` artifact
- final validation failure creates a `structured_output_debug_raw` artifact
- canonical `action_runs.output_artifact_id` may point only to a real `structured_output` artifact;
  debug raw artifacts stay debug-only and must not become the canonical result pointer
- consumers that cross a trust boundary after persistence, including handoff creation, revalidate
  the complete mutable artifact body against its declared workflow output schema before deriving a
  mapped subset

## Safety

The platform must not rely on prompt-text parsing heuristics or loose JSON probing.

Raw secrets, credentials, and unsafe payloads must not be persisted in provider-call metadata or
provider events.

Raw provider output must not appear in safe user-facing validation errors. It is preserved only in
the debug artifact path for platform debugging.

## Provider Schema Ownership

PydanticAI owns the structured-output schema/retry path for structured actions.

LiteLLM / `ProviderGateway` must not independently enforce a second conflicting schema transport for
the same action. `response_schema` stays on AnytoolAI DTOs for platform validation context, and the
LiteLLM adapter may pass that schema forward as model-facing message guidance, but it does not
inject an additional `response_format` validation path in MVP-A.
