# Agent Review Checklist

## Architecture

- [ ] No forbidden imports.
- [ ] No product-specific logic in platform-core.
- [ ] No prompts in extensions.
- [ ] No direct provider calls outside Provider Gateway.

## Contracts

- [ ] Input/output schemas updated.
- [ ] OpenAPI updated if API changed.
- [ ] Config refs validated.
- [ ] Product scenario refs exist in scenario config.
- [ ] Action configs include `prompt_ref` and `provider_policy_ref`.
- [ ] DB migration added if runtime schema changed.

## Runtime

- [ ] `scenario_session_id` is preserved.
- [ ] Events emitted for important transitions.
- [ ] Event log includes product_id, frontend_id, and scenario_session_id where applicable.
- [ ] Artifacts created for workflow results.
- [ ] User-safe errors returned.

## Product boundary

- [ ] `kernel_demo` remains smoke-only and not a user product.
- [ ] MVP-B product meaning stays in product configs/prompts/schemas/renderers/CE wrappers.
- [ ] MVP-B changes do not require `platform-core` changes.

## Validation

- [ ] `just quick-check`
- [ ] `just validate-configs`
- [ ] `just validate-architecture`
- [ ] Relevant smoke test
