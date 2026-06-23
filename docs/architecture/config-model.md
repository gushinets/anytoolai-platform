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
- `max_retries`
- `structured_output_mode`

Frontend must not see system prompts or choose prompt versions.

Config validation must run in CI and before runtime startup. Broken references must fail startup.
Missing owned files and missing explicit fields must fail validation with structured diagnostics.

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
- quota unit: `scenario_run`
- quota period: `lifetime`
- scenario session status: `started`, `waiting_for_user`, `running`, `completed`, `failed`, `expired`
- job status: `created`, `running`, `succeeded`, `failed`, `canceled`
- handoff status: `created`, `viewed`, `accepted`, `declined`, `consumed`, `expired`, `failed`

Future frontend types such as mobile clients should be added by extending `FrontendType`, updating
tests, and then allowing configs to use the new value. Future human-input job states require the
same enum update plus separate runtime work for persistence, timeout handling, APIs, and events.
