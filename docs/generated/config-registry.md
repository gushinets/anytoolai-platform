# Config Registry

Generated-doc mirror of MVP-A config definitions.

Definitions live in YAML/Markdown and are loaded from the repo. Runtime editing through admin UI is not part of MVP-A.

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

## Validation Rules

- All YAML configs validate before runtime startup.
- Broken references fail startup.
- Product scenario references must exist in scenario config.
- Scenario workflow references must exist in workflow config.
- Workflow steps must reference existing action configs.
- Action configs must reference known action types.
- Action configs must include `prompt_ref` and `provider_policy_ref`.
- Frontends must not choose prompt/provider/model.
