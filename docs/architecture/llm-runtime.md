# LLM Runtime

This document is the repository-local source of truth for how AnytoolAI uses PydanticAI and LiteLLM in MVP-A.

The accepted decision is:

```text
Use both PydanticAI and LiteLLM.
Use LiteLLM as an in-process SDK, not LiteLLM Proxy, for MVP-A.
Keep both libraries behind AnytoolAI-owned gateway/executor interfaces.
```

This document exists so future agents do not need chat history to reconstruct the split.

## Runtime path

```text
WorkflowRunner
  -> ActionRunner
    -> StructuredLlmActionExecutor
      -> PydanticAI structured action run
        -> AnytoolAI ProviderGateway
          -> LiteLLM SDK acompletion(...)
            -> external model provider
```

The public platform contract is AnytoolAI-owned. Product bundles and extensions must never instantiate PydanticAI agents, call LiteLLM directly, or import provider SDKs.

## Responsibility split

| Concern | Owner | Rule |
|---|---|---|
| Workflow execution | AnytoolAI | `WorkflowRunner` remains the sequential MVP runner. |
| Action execution | AnytoolAI | `ActionRunner` calls registered executors by action type/config. |
| Structured LLM action ergonomics | PydanticAI | Use inside `StructuredLlmActionExecutor` only. |
| Typed output validation retry | PydanticAI | Validation retries are semantic retries, not transport retries. |
| Final output contract | AnytoolAI | `StructuredOutputValidator` final-validates before artifact persistence. |
| Provider/model abstraction | LiteLLM SDK | Provider calls use LiteLLM SDK through ProviderGateway. |
| Transport retries | AnytoolAI ProviderGateway loop over LiteLLM SDK | Each physical attempt is explicit and logged. |
| LiteLLM hidden retries | Disabled in MVP-A | Call LiteLLM SDK with `num_retries=0` per physical attempt. |
| Fallback/routing surface | LiteLLM SDK, later | Do not enable fallback until provider-call accounting and cost caps are proven. |
| Provider call ledger | AnytoolAI | One `platform.provider_calls` row per ProviderGateway physical attempt. |
| Action-level usage summary | PydanticAI result metadata | Store only as action summary, never as the canonical provider call ledger. |
| Artifacts/events/quota/handoff | AnytoolAI | Domain runtime state is never delegated to an LLM library. |
| Product-specific semantics | MVP-B configs/bundles | Never put Freelancer meaning in platform-core. |

## Retry policy

Do not pass one ambiguous `max_retries` to both libraries.

Provider policy must split retry budgets by failure type:

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

- transport failures include timeout, network, provider 5xx, and rate-limit failures;
- validation failures include invalid JSON, schema mismatch, and output validator failure;
- validation retries may create new provider attempts;
- AnytoolAI enforces the hard cap before each physical attempt;
- PydanticAI fallback models are not used while LiteLLM owns fallback/routing;
- LiteLLM SDK hidden retries stay disabled in MVP-A so the provider-call ledger is deterministic.

## Provider call granularity

`platform.provider_calls` is a gateway ledger, not a PydanticAI summary.

One row means:

```text
one AnytoolAI ProviderGateway physical attempt
```

Not:

```text
one PydanticAI agent run
one workflow step
one logical LiteLLM call with hidden SDK retries
```

Each provider call row should record at least:

```text
tenant_id
region
product_id
frontend_id
scenario_session_id
job_id
action_run_id
workflow_id
workflow_version
step_id
provider_policy_ref
gateway_backend = litellm_sdk
gateway_model
provider
model
semantic_attempt_index
transport_attempt_index
physical_call_index
status
failure_kind
error_code
http_status
input_tokens
output_tokens
total_tokens
estimated_cost
latency_ms
litellm_response_id
pydantic_run_id
started_at
completed_at
metadata
```

PydanticAI usage can be stored in `action_runs.metadata.llm_usage_summary`, but it must not replace per-attempt `provider_calls` rows.

## Structured-output ownership

PydanticAI owns structured-output generation inside the executor:

- `output_type` / typed output binding;
- output validators;
- validation retry/reflection;
- native/tool/prompted structured-output mode selection where supported.

LiteLLM does not independently enforce a second JSON schema for the same action. If PydanticAI chooses a provider-native schema transport, the gateway may pass that through to LiteLLM, but AnytoolAI must not configure a conflicting LiteLLM `response_format` separately.

AnytoolAI still owns final validation because artifacts, user-safe errors, and action contracts are platform behavior. The final validator persists raw provider output for debugging and normalized output for downstream steps.

## In-process SDK decision

MVP-A uses LiteLLM SDK in-process.

Benefits:

- fewer deployable services;
- simple local development;
- provider abstraction without introducing a gateway server;
- easier MVP harness and quick-check path.

Constraints:

- ProviderGateway owns physical attempt accounting;
- LiteLLM SDK calls use `num_retries=0` in MVP mode;
- any SDK callback behavior is treated as auxiliary telemetry, not as the source of truth;
- shared clients/model adapters are cached and closed through application lifecycle hooks.

Scale path:

- LiteLLM Proxy may replace the in-process SDK later if centralized keys, distributed rate limits, proxy-level budgets, or cross-service gateway logs become necessary.
- The AnytoolAI `ProviderGateway` interface must make that replacement local to the provider layer.

## Model string coupling

LiteLLM-format model strings are allowed only in provider policy/model registry files.

Allowed:

```yaml
provider_policy_ref: structured_fast_v1
```

```yaml
id: structured_fast_v1
gateway_backend: litellm_sdk
model_ref: fast_structured_primary
gateway_model: anthropic/claude-sonnet-4-20250514
```

Not allowed in product/action configs:

```yaml
gateway_model: anthropic/claude-sonnet-4-20250514
```

Product configs reference `provider_policy_ref`. If LiteLLM is replaced later, only provider policy/model registry entries should need migration.

## Client lifecycle

Do not create clients, providers, models, or agents inside every `agent.run`.

Cache by stable configuration keys:

```text
provider_policy_ref
model_ref
output_schema_version
action_config_id
```

Never cache run-specific data in model/agent objects:

```text
scenario_session_id
job_id
action_run_id
guest_id
user input
artifact IDs
```

Run-specific data travels through execution context/dependencies.

## Telemetry

There are three different logging surfaces:

1. AnytoolAI domain logging: `event_log`, `action_runs`, `provider_calls`, `artifacts`.
2. LiteLLM SDK telemetry/callbacks: provider-facing operational metadata.
3. PydanticAI instrumentation: structured action trace/debug data.

MVP-A production default:

```text
AnytoolAI domain logging: on
LiteLLM SDK callback telemetry: optional helper, not source of truth
PydanticAI external tracing/Logfire: off unless explicitly enabled for dev/evals
```

Avoid double telemetry in production. Correlation identifiers must be passed through the stack:

```text
scenario_session_id
job_id
action_run_id
workflow_id
step_id
provider_policy_ref
physical_call_index
pydantic_run_id
litellm_response_id
```

## Dependencies and pinning

Use slim dependency surfaces and pin hot-path libraries.

MVP-A dependency intent:

```text
pydantic-ai-slim with only required extras
litellm
pydantic 2.x pinned by the backend lockfile
```

Rules:

- use `uv add`, not manual lockfile edits;
- avoid the full PydanticAI meta-package unless a required provider path proves it necessary;
- keep PydanticAI and LiteLLM imports behind the gateway/executor boundary;
- dependency upgrades must include structured-output and provider-call accounting smoke tests.

## Import boundary

Allowed imports:

```text
packages/backend/platform-core/**/providers/**
  may import litellm

packages/backend/platform-actions/**/structured_llm_executor/**
  may import pydantic_ai
```

Forbidden everywhere else unless this document and the architecture validator are updated in the same PR:

```text
pydantic_ai
litellm
openai
anthropic
google.genai
cohere
mistralai
```

Extensions and product bundles must use platform contracts only.

## Acceptance tests to add with implementation

Before the LLM runtime slice is considered complete:

- retry accounting: one validation retry plus one transport retry does not exceed `max_physical_provider_calls_per_action`;
- hidden retry guard: LiteLLM SDK is called with `num_retries=0` in MVP mode;
- provider-call granularity: every ProviderGateway physical attempt creates one `provider_calls` row;
- structured-output ownership: PydanticAI owns validation retry and AnytoolAI final-validates artifacts;
- import boundary: forbidden LLM/provider imports fail architecture validation outside allowed modules;
- client lifecycle: repeated action runs reuse cached clients/model adapters;
- telemetry duplication: production config enables only one external infra telemetry path.
