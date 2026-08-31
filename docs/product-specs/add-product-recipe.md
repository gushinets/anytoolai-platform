# Add-Product Recipe

How to add an MVP-B product without touching `platform-core`, `platform-actions`, or
`apps/platform-api` route code. This is the practical handoff criterion from `A22c` (`ANY-25`):
a real product ships through configs, prompts, schemas, and a CE wrapper only.

See `docs/architecture/platform-boundaries.md` for the allowed/forbidden vocabulary this recipe
must stay inside, and `tests/architecture/` for the tests that enforce it.

## Steps

1. **Bundle package.** Add a package under `packages/backend/product-platforms/<suite>/` that
   depends only on `anytoolai_platform_sdk`. Implement `ProductBundle` with a `bundle_id` and
   `config_roots()` listing the product's config directories. See
   `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/bundle.py`
   for the working example — it is 17 lines and imports nothing from `platform-core`,
   `platform-actions`, or `platform-api`.
2. **Config roots.** Under the bundle's `products/<product_name>/` config root, add the
   product's workflow definition, action configs, and any product-scoped events/handoff maps —
   the same YAML/Markdown-defines-behavior model platform-core already uses for its own atoms and
   workflows.
3. **Prompts.** Add prompt files under the bundle (e.g. `shared/prompts/`), referenced from action
   configs by `prompt_ref`. Prompts never live in `platform-core`, `platform-actions`, or in any
   extension.
4. **Schemas.** Add strict input/output JSON schemas for the product's structured LLM actions
   alongside the prompts. `platform-actions`' `StructuredLlmActionExecutor` validates against
   these; it does not know product schema content ahead of time.
5. **Provider policy.** Reuse an existing `provider_policy_ref` from
   `configs/kernel/provider_policies.yaml`, or add a new named policy there if the product needs
   different model/temperature/retry settings. Provider policy refs and LiteLLM-format model
   strings live only in `configs/kernel/provider_policies.yaml` and
   `configs/kernel/litellm_router.yaml` — never hardcoded in bundle or action code
   (`tests/architecture/test_litellm_model_strings_stay_in_provider_config.py`).
6. **Register the bundle.** Wire the new bundle into `apps/platform-api` composition (the only
   place allowed to know both platform runtime and product bundles). This does not add
   product-specific routes: every platform-api endpoint stays parameterized on `{product_id}`
   (`tests/architecture/test_no_product_specific_endpoints.py`). That test's forbidden-term list
   only names the 8 Freelancer Suite products that exist today — it is a backstop, not a general
   proof. Add your new product's name to `FORBIDDEN_PRODUCT_PATH_TERMS` in that test file too, so
   a future accidental hardcode of *this* product's path also fails the gate.
7. **Chrome Extension.** Build a separate CE for the product using shared `packages/frontend/ce-kit`
   (transport, storage, identity, quota, start, polling, result, handoff helpers). The extension
   contains no prompts, no provider/model selection, and no workflow logic — it calls the platform
   API and renders results.
8. **Verify the boundary, not just the feature.** Run `python scripts/agent/runner.py
   validate-architecture` and `pytest tests/architecture` before calling the product done. A green
   architecture gate is part of the product's definition of done, not a one-time audit.

## What never changes

- `packages/backend/platform-core` and `packages/backend/platform-actions` source.
- Workflow runner, action runner, provider gateway, scenario/event/quota/handoff kernel modules.
- `apps/platform-api` route shapes (only bundle registration changes).

If a product needs a kernel change to ship, that is a kernel bug or a new generic atom — file it
against MVP-A, do not special-case the product into platform-core.
