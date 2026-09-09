# Add-Product Recipe

How to add an MVP-B product without touching `platform-core`, `platform-actions`, or
`apps/platform-api` route code. This is the practical handoff criterion from `A22c` (`ANY-25`):
a real product ships through configs, prompts, and schemas. A dedicated Chrome Extension is
optional backlog, not required by the bundle contract (`ANY-32`) — `apps/web-mirror`'s shared web
mirror is the default client surface.

See `docs/architecture/platform-boundaries.md` for the allowed/forbidden vocabulary this recipe
must stay inside, and `tests/architecture/` for the tests that enforce it.

## Steps

1. **Bundle package.** Add a package under `packages/backend/product-platforms/<suite>/` that
   depends only on `anytoolai_platform_sdk`. Subclass `ProductBundle`
   (`packages/backend/platform-sdk/src/anytoolai_platform_sdk/bundle.py`) with a `bundle_id` and a
   `config_roots() -> list[Path]` that resolves each product directory relative to your bundle's
   own installed package via the inherited `self._package_dir()` helper — never a bare relative
   string, and never dependent on the caller's current working directory. See
   `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/bundle.py`
   for the class shape (it imports nothing from `platform-core`, `platform-actions`, or
   `platform-api`); as of `ANY-32` it returns `[]` until a product issue (starting with
   `ANY-227`/ProposalAI) adds a real product directory.
2. **Config roots.** Under the bundle's `products/<product_name>/` config root, add the
   product's `product.yaml`, `frontends.yaml`, `action_configs.yaml`, `workflows.yaml`,
   `scenarios.yaml`, `prompts.yaml`, `schemas.yaml`, and any product-scoped
   `quotas.yaml`/`handoffs.yaml`/`analytics.yaml` — the same YAML/Markdown-defines-behavior model
   platform-core already uses for its own atoms and workflows. `apps/platform-api/bootstrap.py`
   passes every composed bundle's `config_roots()` straight through to platform-core's
   product-neutral `ConfigLoader` (its `extra_product_roots` parameter), which validates your
   product against the same duplicate-id and cross-reference checks as `configs/kernel`'s own
   products — see `apps/platform-api/tests/test_bundle_composition.py` for the loader's
   required-evidence suite (happy path, missing-root, duplicate-id in both orderings, invalid
   cross-reference) against a minimal test-only fixture bundle.
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
6. **Register the bundle.** Wire the new bundle into the production default bundle list used by
   every runtime composition boundary that needs your product's config: `apps/platform-api/bootstrap.py`'s
   `build_runtime`, `apps/platform-worker/composition.py`'s `build_worker`, and
   `scripts/agent/validate_configs.py`. These are the only modules allowed to import a
   product-platforms package (see `tests/architecture/test_freelancer_suite_import_boundary.py`);
   keep their default bundle lists identical, or the API and worker can disagree on which product
   configs exist. This does not add product-specific routes: every platform-api endpoint stays
   parameterized on `{product_id}` (`tests/architecture/test_no_product_specific_endpoints.py`).
   That test's forbidden-term list is a static backstop of known/candidate Freelancer product
   names, not a general proof and not tied to what is actually implemented. Add your new product's
   name to `FORBIDDEN_PRODUCT_PATH_TERMS` in that test file too, so a future accidental hardcode of
   *this* product's path also fails the gate.
7. **Chrome Extension (optional).** The bundle contract does not require a dedicated CE
   (`ANY-32`); the shared web mirror (`apps/web-mirror`) is the default client surface for a new
   product's web pages and result renderers. If the product still needs a standalone CE, build it
   on shared `packages/frontend/ce-kit` (transport, storage, identity, quota, start, polling,
   result, handoff helpers) with no prompts, no provider/model selection, and no workflow logic —
   it only calls the platform API and renders results.
8. **Verify the boundary, not just the feature.** Run `python scripts/agent/runner.py
   validate-architecture` and `pytest tests/architecture` before calling the product done. A green
   architecture gate is part of the product's definition of done, not a one-time audit.

## What never changes

- `packages/backend/platform-core` and `packages/backend/platform-actions` source.
- Workflow runner, action runner, provider gateway, scenario/event/quota/handoff kernel modules.
- `apps/platform-api` route shapes (only bundle registration changes).

If a product needs a kernel change to ship, that is a kernel bug or a new generic atom — file it
against MVP-A, do not special-case the product into platform-core.
