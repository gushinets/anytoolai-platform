# ADR 0004: LLM Runtime With PydanticAI And In-Process LiteLLM SDK

## Status

Accepted.

## Context

MVP-A Platform Kernel needs one generic structured LLM executor that can run product-neutral typed actions through prompts, schemas, provider policies, runtime jobs, provider-call logging, artifacts, and event logs.

The library decision must preserve the MVP-A/MVP-B boundary:

- MVP-A owns the platform runtime.
- MVP-B adds product configs, prompts, schemas, workflows, renderers, handoff maps, and thin Chrome Extension wrappers.
- Freelancer product meaning must not enter `platform-core`.
- Provider calls must not bypass Provider Gateway.

The main implementation risk is responsibility overlap. Both PydanticAI and LiteLLM can participate in retries and structured output. If the boundary is vague, retry counts multiply, provider-call logging becomes ambiguous, and product/action code can bypass platform policy.

## Decision

Use both libraries.

```text
PydanticAI = structured action execution and validation retry.
LiteLLM SDK = in-process provider/model access behind Provider Gateway.
AnytoolAI = runtime source of truth, provider-call ledger, artifacts, events, quota, handoff, final validation, import boundaries.
```

Do not run LiteLLM Proxy in MVP-A. The proxy remains the scale path if centralized keys, distributed rate limits, budgets, or cross-service gateway logs become necessary.

Do not rely on PydanticAI usage summaries as the canonical provider-call ledger. `platform.provider_calls` is owned by AnytoolAI ProviderGateway.

## Detailed responsibilities

### PydanticAI owns

- structured LLM action ergonomics inside `StructuredLlmActionExecutor`;
- `output_type` / typed output binding;
- output validators;
- validation retry/reflection;
- action-level usage summary metadata.

### LiteLLM SDK owns

- in-process provider/model abstraction;
- provider API calls;
- provider error surface consumed by ProviderGateway;
- usage/cost metadata extraction where available;
- fallback/routing surface later.

### AnytoolAI owns

- `ProviderGateway` interface and implementation boundary;
- retry policy split;
- physical attempt accounting;
- `platform.provider_calls` rows;
- raw provider output artifacts;
- normalized final output artifacts;
- final `StructuredOutputValidator`;
- domain `event_log`;
- workflow/session/job/action runtime state;
- import boundary enforcement.

## Retry policy

One `ProviderPolicy.max_retries` must not be fed to both libraries.

Provider policy stores split retry budgets:

```yaml
retry_policy:
  transport:
    owner: provider_gateway_litellm_sdk
    max_attempts: 2
    litellm_num_retries_per_attempt: 0
  validation:
    owner: pydantic_ai
    max_attempts: 2
  hard_limits:
    max_physical_provider_calls_per_action: 4
```

Rules:

- transport retries are owned by AnytoolAI ProviderGateway around LiteLLM SDK calls;
- validation retries are owned by PydanticAI;
- LiteLLM SDK hidden retries are disabled in MVP-A with `num_retries=0` per physical attempt;
- AnytoolAI enforces `max_physical_provider_calls_per_action` before every physical call;
- PydanticAI fallback models are not used while LiteLLM owns the fallback/routing surface.

This avoids retry multiplication such as `2 validation attempts * 2 hidden transport retries` becoming four untracked provider hits.

## Provider-call granularity

One `platform.provider_calls` row means:

```text
one AnytoolAI ProviderGateway physical attempt
```

Not:

```text
one PydanticAI agent run
one workflow step
one logical LiteLLM call with hidden retries
```

PydanticAI usage summary may be copied into `action_runs.metadata.llm_usage_summary`, but it is not the source for the provider-call ledger.

## Structured output

PydanticAI owns structured-output generation and validation retries.

LiteLLM must not independently enforce a second conflicting schema. If PydanticAI chooses a provider-native schema transport, ProviderGateway may pass through the resulting provider request shape to LiteLLM, but AnytoolAI must not configure a separate conflicting `response_format` for the same action.

AnytoolAI final-validates before persistence and stores both raw provider output and normalized final output artifacts.

## Import boundary

Allowed:

```text
packages/backend/platform-core/**/providers/**
  may import litellm and provider SDKs.

packages/backend/platform-actions/**/structured_llm/**
  may import pydantic_ai.

packages/backend/platform-actions/**/structured_llm_executor/**
  may import pydantic_ai.
```

Forbidden outside approved boundaries:

```text
pydantic_ai
litellm
openai
anthropic
google.genai
@google/genai
cohere
mistralai
```

Architecture validation must enforce this so product bundles, Chrome Extensions, and arbitrary actions cannot bypass Provider Gateway.

## Consequences

Positive:

- PydanticAI gives typed structured-output ergonomics without owning platform runtime.
- LiteLLM gives broad provider/model support without leaking provider choice into products.
- Provider-call accounting remains deterministic in MVP-A.
- LiteLLM Proxy can be adopted later without changing product/action configs.
- Future agents have a single repo-local decision source.

Negative / accepted tradeoffs:

- More dependencies in the hot path.
- A thin AnytoolAI adapter is required between PydanticAI execution and LiteLLM SDK calls.
- Some LiteLLM SDK retry/fallback features are intentionally disabled until accounting is proven.
- LiteLLM-format model strings create mild lock-in inside provider policy/model registry files.

## Dependency rule

Use slim and pinned dependencies:

```text
pydantic-ai-slim with only required extras
litellm
pydantic 2.x pinned by the backend lockfile
```

Use `uv add`; do not hand-edit `uv.lock`.

## Follow-up implementation requirements

Before the runtime slice is complete, add tests for:

- retry accounting and hard cap enforcement;
- LiteLLM SDK `num_retries=0` in MVP mode;
- one provider-call row per ProviderGateway physical attempt;
- final structured-output validation and artifact persistence;
- import-boundary enforcement;
- client/model adapter lifecycle reuse;
- production telemetry duplication guard.
