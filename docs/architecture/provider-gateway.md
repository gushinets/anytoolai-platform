# Provider Gateway

All model/provider calls go through Provider Gateway.

Provider Gateway is an AnytoolAI-owned boundary. It may use LiteLLM SDK internally in MVP-A, but product bundles, action configs, frontend code, and Chrome Extensions must not call LiteLLM or provider SDKs directly.

## MVP-A implementation decision

MVP-A uses:

```text
ProviderGateway
  -> LiteLLM SDK in-process
    -> external provider
```

MVP-A does not run LiteLLM Proxy. Proxy remains the scale path for centralized keys, distributed rate limits, central budgets, or cross-service gateway logs.

## Responsibilities

Provider Gateway responsibilities:

- provider policy resolution;
- provider/model lookup from policy/model registry;
- timeout enforcement;
- transport retry loop around LiteLLM SDK calls;
- fallback policy surface when configured later;
- provider call logging;
- token/cost metadata extraction;
- latency metadata;
- user-safe provider errors;
- hard cap enforcement for physical provider attempts.

Provider Gateway does not own semantic structured-output validation. That belongs to `StructuredLlmActionExecutor` / PydanticAI plus the final AnytoolAI `StructuredOutputValidator`.

## Minimum provider policy fields

```text
provider_policy_id
provider
model
temperature
timeout_seconds
retry_policy.transport.owner
retry_policy.transport.max_attempts
retry_policy.transport.litellm_num_retries_per_attempt
retry_policy.validation.owner
retry_policy.validation.max_attempts
retry_policy.hard_limits.max_physical_provider_calls_per_action
fallback_policy optional
structured_output_mode
```

Current MVP-A kernel config keeps provider/model routing in provider policy entries. Product and action
configs reference `provider_policy_ref`; they do not carry provider/model strings or LiteLLM request
settings.

## Retry ownership

Do not pass a single `max_retries` value into multiple layers.

```text
Transport retry owner: provider_gateway_litellm_sdk
Validation retry owner: pydantic_ai
Hard cap owner: AnytoolAI ProviderGateway
```

MVP-A calls LiteLLM SDK with:

```text
num_retries=0
```

Each physical ProviderGateway attempt creates one `platform.provider_calls` row. Hidden LiteLLM SDK retries are disabled so the ledger stays deterministic.

Config validation must reject old retry shapes such as flat `max_retries` and must fail startup if
`retry_policy.hard_limits.max_physical_provider_calls_per_action` is missing.

Outside provider policy/model registry ownership, config validation must reject raw provider/model
and LiteLLM request fields such as `provider`, `model`, `temperature`, `timeout_seconds`,
`max_retries`, `response_format`, `response_schema`, and `litellm_*`.

## Provider call logging

Even before billing, each physical provider attempt must log:

- tenant and region dimensions;
- product and frontend dimensions;
- scenario, job, workflow, step, and action-run dimensions where available;
- provider policy reference;
- gateway backend;
- provider;
- model;
- input tokens;
- output tokens;
- total tokens when available;
- latency in milliseconds;
- estimated cost when available;
- success/failure;
- failure kind and safe error code when failed;
- semantic validation attempt index;
- transport attempt index;
- physical call index.

PydanticAI usage summaries can be stored on action-run metadata, but they do not replace `platform.provider_calls` rows.

## Import boundary

Direct provider SDK imports outside Provider Gateway/provider adapters are forbidden.

Allowed only in provider boundary code:

```text
litellm
openai
anthropic
google.genai
@google/genai
cohere
mistralai
```

`pydantic_ai` is not a provider boundary dependency. It is allowed only in the structured LLM executor boundary under `platform-actions`.
