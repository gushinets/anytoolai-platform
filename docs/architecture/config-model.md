# Config Model

In MVP-A definitions live in YAML/Markdown and runtime state lives in PostgreSQL.

Definitions:

- product
- frontend
- scenario
- workflow
- action definition
- action configuration
- prompt
- provider policy
- quota policy
- handoff definition

Source of truth in MVP-A:

```text
Product / Scenario / Workflow / Action Config / Prompt = repo config.
Runtime state / Events / Artifacts / Sessions = database.
```

Registry ownership is explicit and read-only:

- `product.yaml` owns product identity, platform, scenario list, and explicit `quota_policy_ref`.
- `frontends.yaml` is required for every product and is the only allowed source of frontend definitions.
- `analytics.yaml` is optional; when analytics are configured it is the only allowed source of analytics definitions.
- `prompts.yaml` owns prompt ids and prompt asset paths for each product.
- `schemas.yaml` owns schema ids and schema asset paths for kernel and product-local schemas.
- Loader-level silent fallback, hidden merge, and hidden default behavior are not allowed for registry-owned definitions.

Prompt registry entries live in repo manifests plus Markdown assets and must expose:

- `prompt_ref`
- version
- `template_path`
- input variables
- `output_schema_ref`

Schema registry entries live in repo manifests plus JSON assets and must expose:

- `schema_ref`
- version
- `file_path`

Provider policy entries must explicitly declare:

- `temperature`
- `timeout_seconds`
- `retry_policy`
- `structured_output_mode`

See the provider policy section below and
`packages/backend/platform-sdk/src/anytoolai_platform_sdk/contracts/provider.py`:
retry configuration belongs under `retry_policy`, and old flat retry fields such
as `max_retries` are invalid.

Frontend must not see system prompts or choose prompt versions.

Config validation must run in CI and before runtime startup. Broken references must fail startup.
Missing owned files and missing explicit fields must fail validation with structured diagnostics.

## Provider policy ownership

Provider/model routing and transport settings belong to provider policy or model-registry-owned files
only.

Current MVP-A provider policies expose:

- `provider_policy_ref`
- `provider`
- `model`
- `temperature`
- `timeout_seconds`
- `retry_policy.transport.owner`
- `retry_policy.transport.max_attempts`
- `retry_policy.transport.litellm_num_retries_per_attempt`
- `retry_policy.validation.owner`
- `retry_policy.validation.max_attempts`
- `retry_policy.hard_limits.max_physical_provider_calls_per_action`
- `fallback_policy` optional
- `structured_output_mode`

MVP-A rules:

- `retry_policy.transport.owner` must be `provider_gateway_litellm_sdk`
- `retry_policy.validation.owner` must be `pydantic_ai`
- `retry_policy.transport.litellm_num_retries_per_attempt` must be exactly `0`
- old flat retry fields such as `max_retries` are invalid

Product, frontend, scenario, workflow, action, and prompt-owned configs must not define raw
provider/model/LiteLLM request fields such as `provider`, `model`, `temperature`,
`timeout_seconds`, `max_retries`, `response_format`, `response_schema`, or `litellm_*`.
Those configs may reference `provider_policy_ref` where the runtime contract allows it.

## Public contract models

Public DTOs live in `packages/backend/platform-sdk/src/anytoolai_platform_sdk/contracts`.
They are the shared boundary for backend composition, CE kit usage, and web mirror/runtime-config
shapes. Internal `platform-core` models may use a different implementation, but must keep the
same field names and enum values for the same concepts.

A01 defines these public models:

- `ProductDefinition`
- `FrontendDefinition`
- `ScenarioDefinition`
- `WorkflowDefinition`
- `WorkflowStepDefinition`
- `ActionDefinition`
- `ActionConfiguration`
- `PromptRef`
- `ProviderPolicy`
- `QuotaPolicy`
- `HandoffDefinition`
- `EventEnvelope`

All public DTOs include:

- `schema_version`, defaulting to `1`;
- `metadata`, a JSON object for non-contract annotations.

Unknown top-level fields are rejected. Future optional annotations belong under `metadata` until
they are promoted to explicit contract fields.

## Current enum values

Enums are closed per SDK version. Adding a value is an explicit additive contract update with docs
and tests.

- frontend type: `chrome_extension`, `web`
- action executor: `structured_llm`
- structured output mode: `json_schema`
- transport retry owner: `provider_gateway_litellm_sdk`
- validation retry owner: `pydantic_ai`
- quota unit: `scenario_run`
- quota period: `lifetime`
- scenario session status: `started`, `waiting_for_user`, `running`, `completed`, `failed`, `expired`
- job status: `created`, `running`, `succeeded`, `failed`, `canceled`
- handoff status: `created`, `viewed`, `accepted`, `declined`, `consumed`, `expired`, `failed`

Future frontend types such as mobile clients should be added by extending `FrontendType`, updating
tests, and then allowing configs to use the new value. Future human-input job states require the
same enum update plus separate runtime work for persistence, timeout handling, APIs, and events.
