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

LiteLLM router deployment config is separate from the ConfigRegistry load order. It lives in
`configs/kernel/litellm_router.yaml` and is consumed by provider-adapter bootstrap, not by the
registry loader.

Provider policies remain the owner of platform intent, including:

- provider selection
- model-group selection
- timeout policy
- structured-output mode
- nested retry policy

LiteLLM router config remains the owner of deployments, routing, credentials, and provider-specific
transport settings.

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
configs/kernel/litellm_router.yaml
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
- `litellm_router.yaml` is a top-level provider deployment/routing config file and is intentionally
  separate from provider policies. Provider policies describe platform intent; LiteLLM router config
  describes deployment/model-group routing.
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

## Validation Rules

- All YAML configs validate before runtime startup.
- Broken references fail startup.
- Product scenario references must exist in scenario config.
- Scenario workflow references must exist in workflow config.
- Workflow steps must reference existing action configs.
- Action configs must reference known action types.
- Action configs must include `prompt_ref` and `provider_policy_ref`.
- Frontends must not choose prompt/provider/model.

## Provider Policy Contract

Provider policies use `provider_policy_ref` and the ADR-0007 nested retry contract.

Current retry shape:

```text
retry_policy.transport.owner
retry_policy.transport.max_attempts
retry_policy.transport.litellm_num_retries_per_attempt

retry_policy.validation.owner
retry_policy.validation.max_attempts

retry_policy.hard_limits.max_physical_provider_calls_per_action
```

Legacy flat fields such as `max_retries` are rejected by the loader.
