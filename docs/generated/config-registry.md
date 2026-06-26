# Config Registry

Generated-doc mirror of MVP-A config definitions.

Definitions live in YAML/Markdown and are loaded from the repo. Runtime editing through admin UI is not part of MVP-A.

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
configs/kernel/action_definitions/
configs/kernel/products/kernel_demo/product.yaml
configs/kernel/products/kernel_demo/frontends.yaml
configs/kernel/products/kernel_demo/scenarios.yaml
configs/kernel/products/kernel_demo/workflows.yaml
configs/kernel/products/kernel_demo/action_configs.yaml
configs/kernel/products/kernel_demo/prompts/
configs/kernel/products/kernel_demo/schemas/
configs/kernel/products/kernel_demo/handoffs.yaml
configs/kernel/products/kernel_demo/quotas.yaml
```

## Ownership And Fallbacks

- `default_tenant.yaml`, `regions.yaml`, and `provider_policies.yaml` are top-level single sources for their definition types.
- Each product directory is loaded from `product.yaml` first, with dedicated child files then loaded for action configs, workflows, scenarios, quotas, handoffs, prompts, and schemas.
- `frontends.yaml` is used when present; otherwise the loader falls back to the `frontends` field in `product.yaml`.
- `analytics.yaml` is used when present; otherwise the loader falls back to the `analytics` field in `product.yaml`.
- `quota_policy_ref` comes from `product.yaml` when set. If it is omitted and `quotas.yaml` defines exactly one quota policy, the loader uses that single quota policy ID as a fallback. If multiple quota policies exist and `product.yaml` omits `quota_policy_ref`, loading fails.
- Prompts are discovered from `products/*/prompts/*.md`, excluding `README.md`.
- Schemas are discovered from both `configs/kernel/schemas/*.json` and `products/*/schemas/*.json`.

## Merge And Override Behavior

- The loader does not silently merge `frontends.yaml` with `product.yaml` frontends. If `frontends.yaml` exists, it replaces the fallback from `product.yaml`.
- The loader does not silently merge `analytics.yaml` with `product.yaml` analytics. If `analytics.yaml` exists, it replaces the fallback from `product.yaml`.
- Cross-reference validation happens only after all configured definitions, prompts, and schemas have been loaded.

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
- Broken references fail startup.
- Product scenario references must exist in scenario config.
- Scenario workflow references must exist in workflow config.
- Workflow steps must reference existing action configs.
- Action configs must reference known action types.
- Action configs must include `prompt_ref` and `provider_policy_ref`.
- Provider policies must use the ADR 0007 split retry shape with explicit transport and validation owners.
- Product, frontend, scenario, workflow, action, and prompt-owned configs must reject raw provider/model/LiteLLM fields such as `provider`, `model`, `temperature`, `timeout_seconds`, `max_retries`, `response_format`, `response_schema`, and `litellm_*`.
- Frontends must not choose prompt/provider/model.
