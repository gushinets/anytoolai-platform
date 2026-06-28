# Config Registry

Generated-doc mirror of MVP-A config definitions.

Definitions live in YAML/Markdown and are loaded from the repo. Runtime editing through admin UI is not part of MVP-A.
Registry-owned definitions must be explicit in repo config. The loader does not apply silent
fallbacks, hidden defaults, or silent merges for owned files or owned fields.

## Load Order

The current loader reads definitions in this order:

1. tenant defaults
2. regions
3. provider policies
4. action definitions
5. products
6. prompts
7. schemas
8. cross-reference validation

## Required Definition Types

- product definition
- frontend definition
- scenario definition
- workflow definition
- action definition
- action configuration
- prompt reference/version
- provider policy
- quota policy
- handoff definition
- event envelope contract

## Kernel Config Paths

```text
configs/kernel/default_tenant.yaml
configs/kernel/regions.yaml
configs/kernel/provider_policies.yaml
configs/kernel/schemas.yaml
configs/kernel/action_definitions/
configs/kernel/products/kernel_demo/product.yaml
configs/kernel/products/kernel_demo/frontends.yaml
configs/kernel/products/kernel_demo/analytics.yaml
configs/kernel/products/kernel_demo/scenarios.yaml
configs/kernel/products/kernel_demo/workflows.yaml
configs/kernel/products/kernel_demo/action_configs.yaml
configs/kernel/products/kernel_demo/prompts.yaml
configs/kernel/products/kernel_demo/prompts/
configs/kernel/products/kernel_demo/schemas.yaml
configs/kernel/products/kernel_demo/schemas/
configs/kernel/products/kernel_demo/handoffs.yaml
configs/kernel/products/kernel_demo/quotas.yaml
```

## Ownership Rules

- `default_tenant.yaml`, `regions.yaml`, `provider_policies.yaml`, and kernel `schemas.yaml` are top-level single sources for their definition types.
- Each product directory is loaded from `product.yaml` first, then from dedicated child files that own frontends, analytics, scenarios, workflows, action configs, handoffs, quotas, prompts, and schemas.
- `frontends.yaml` is required for every product and is the exclusive owner of frontend definitions. `product.yaml` must not embed `frontends`.
- `analytics.yaml` is optional. If it is absent, the product loads with `analytics = {}`. If analytics are configured, `analytics.yaml` is the exclusive owner and `product.yaml` must not embed `analytics`.
- `quota_policy_ref` must be explicit in `product.yaml` whenever `quotas.yaml` defines one or more quota policies. The loader never infers a quota policy from the number of available policies.
- `prompts.yaml` is required for each product and explicitly owns `prompt_ref`, `version`, `template_path`, `input_variables`, and `output_schema_ref`.
- Kernel `schemas.yaml` and product `schemas.yaml` files explicitly own `schema_ref`, `version`, and `file_path`.

## No-Silent-Default Rules

- The loader does not read fallback frontend definitions from `product.yaml`.
- The loader does not read fallback analytics definitions from `product.yaml`.
- The loader does not infer `quota_policy_ref`.
- The loader does not invent provider-policy values for `temperature`, `timeout_seconds`, `max_retries`, or `structured_output_mode`.
- Prompt and schema ids do not come from asset filenames; they come from manifest entries.
- Prompt `output_schema_ref` does not come from action-definition inference; it comes from `prompts.yaml`.
- Cross-reference validation happens only after all configured definitions, prompt manifests/assets, and schema manifests/assets have been loaded.

## Required Fields And Optionality

- Provider policies must explicitly set `provider_policy_id`, `provider`, `model`, `temperature`, `timeout_seconds`, `max_retries`, and `structured_output_mode`.
- Action configs must explicitly set `action_config_id`, `action_type`, `prompt_ref`, and `provider_policy_ref`.
- Prompt manifest entries must explicitly set `prompt_ref`, `version`, `template_path`, `input_variables`, and `output_schema_ref`.
- Schema manifest entries must explicitly set `schema_ref`, `version`, and `file_path`.
- `analytics.yaml` is intentionally optional; the loader treats a missing file as an explicit empty analytics config rather than a fallback to another file.

## Provider Policy Contract

Provider policies are the config-owned source of truth for provider/model routing and retry
ownership in MVP-A.

Current required retry shape:

```yaml
retry_policy:
  transport:
    owner: provider_gateway_litellm_sdk
    max_attempts: <int >= 1>
    litellm_num_retries_per_attempt: 0
  validation:
    owner: pydantic_ai
    max_attempts: <int >= 1>
  hard_limits:
    max_physical_provider_calls_per_action: <int >= 1>
```

Rules:

- `litellm_num_retries_per_attempt` must be exactly `0` in MVP-A.
- Flat retry fields such as `max_retries` are invalid.
- Missing `retry_policy.transport.owner`, `retry_policy.validation.owner`, or
  `retry_policy.hard_limits.max_physical_provider_calls_per_action` fails startup.
- Product/scenario/workflow/action/frontend/prompt-owned configs may reference
  `provider_policy_ref`, but they must not define raw provider/model/LiteLLM request fields.

## Validation Rules

- All YAML configs validate before runtime startup.
- Missing owned files fail startup with structured diagnostics that include `file_path`, `config_id`, `ref_type`, and `ref_value` where applicable.
- Broken references fail startup.
- Product scenario references must exist in scenario config.
- Scenario workflow references must exist in workflow config.
- Workflow steps must reference existing action configs.
- Action configs must reference known action types.
- Action configs must include `prompt_ref` and `provider_policy_ref`.
- Provider policies must use the ADR 0007 split retry shape with explicit transport and validation owners.
- Product, frontend, scenario, workflow, action, and prompt-owned configs must reject raw provider/model/LiteLLM fields such as `provider`, `model`, `temperature`, `timeout_seconds`, `max_retries`, `response_format`, `response_schema`, and `litellm_*`.
- Frontends must not choose prompt/provider/model.
