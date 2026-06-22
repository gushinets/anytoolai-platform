# Provider Gateway

All model/provider calls go through Provider Gateway.

Provider Gateway responsibilities:

- provider policy resolution;
- async request orchestration;
- timeout handling;
- retries;
- fallback policy when configured;
- structured output mode;
- provider call logging;
- token/cost metadata;
- latency metadata;
- user-safe provider errors.

## Allowed runtime path

Runtime code must use:

```text
action/runtime code -> ProviderGateway -> provider adapter protocol -> concrete adapter
```

Direct provider adapter imports outside `platform-core/providers` are forbidden. Actions, workflow
runtime, and other execution code must not bypass the gateway to call provider adapters directly.

## Async provider contract

The runtime provider path uses async DTOs:

- `ProviderRequest`
  - runtime dimensions such as `scenario_session_id`, `job_id`, `action_run_id`,
    `action_config_id`, and `provider_policy_id`
  - input payload as `prompt` plus optional `messages`
  - safe request metadata, `fixture_key`, and optional correlation/request ids
- `ResolvedProviderRequest`
  - the adapter-facing request after `ProviderPolicy` resolution
  - includes resolved `provider`, `model`, `temperature`, `timeout_seconds`, `max_retries`, and
    `structured_output_mode`
- `ProviderResponse`
  - `output_text`
  - success/failure status
  - token usage
  - latency
  - estimated cost when known
  - safe response/error metadata

Concrete adapters implement one shared async interface and remain implementation details behind the
gateway.

## Dependency shape

`ProviderGateway` supports two persistence wiring modes:

- explicit `provider_call_repository` injection
- caller-owned SQLAlchemy `session` passed to `request(...)`, with the gateway constructing
  `ProviderCallRepository(session)`

For runtime event emission, `ProviderGateway` may also receive the shared `event_emitter`
dependency. Provider request events must go through that shared emitter, not through an ad-hoc
provider-specific event path.

This preserves the explicit transaction-boundary pattern from runtime storage. The gateway does not
own commits and does not introduce hidden commit behavior.

The gateway currently exposes:

- async `request(...)` for the current provider-runtime path
- sync `execute(...)` as a compatibility seam for event-log/runtime service tests that still use the
  earlier provider execution shape

Minimum provider policy fields:

```text
provider
model
temperature
timeout_seconds
max_retries
fallback_policy optional
structured_output_mode
```

Even before billing, provider calls must log:

- provider;
- model;
- input tokens;
- output tokens;
- latency in milliseconds;
- estimated cost;
- success/failure.

## Provider call persistence

The gateway persists `platform.provider_calls` rows for both success and failure paths while keeping
transaction ownership with the caller.

Persisted data includes:

- resolved provider policy id, provider, and model
- runtime dimensions through `action_run_id`
- result status
- token counts when available
- latency and estimated cost when available
- safe error type/message for failures
- safe metadata for timeout, retry, request id, correlation id, fixture selection, and response
  annotations

The gateway must not persist secrets, raw credentials, or large unsafe payloads such as raw prompt
bodies.

Required event dimensions gate persistence for provider calls. If required dimensions such as
`tenant_id` or `region` are missing or blank, the gateway must not write a `provider_calls` row.

When the shared event emitter is configured, the gateway should emit:

- `provider.request_started`
- `provider.request_succeeded`
- `provider.request_failed`

If required event dimensions are invalid, event emission should fail fast and provider-call
persistence should not proceed.

## Fake provider behavior

The fake provider is deterministic and selects fixtures by request metadata, not prompt text.

Selection order:

1. explicit `fixture_key`
2. `request.metadata["fixture_key"]`
3. `action_config_id`
4. `request.metadata["action_config_id"]`

Fixture files live in `tests/fixtures/provider/fake_provider_outputs/`.

## Failure safety

Gateway failures must use safe platform-facing error codes.

Current behavior:

- use `PlatformError.code` when the underlying exception is a platform error
- use `provider_request_timed_out` for timeout failures
- use `provider_request_failed` for other provider failures

The gateway may still keep the underlying exception type for internal metadata, but persisted
failure rows and surfaced safe errors should use the safe platform error code.
