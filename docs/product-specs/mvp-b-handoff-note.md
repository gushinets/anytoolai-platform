# MVP-B Handoff Note

Written for the team starting `B01` (`ANY-32`, Freelancer Product Template And Bundle Loader) and
the products after it. This is the `A22c` (`ANY-25`) DoD deliverable: what MVP-A1 proves, what is
allowed and forbidden, and where to look before writing product code.

## What is proven

- The platform kernel (workflow runner, action runner, provider gateway, scenario/event/quota/
  handoff modules) runs 11 generic atoms and composite workflows without any Freelancer-specific
  code, per the MVP-A1 release gate (`ANY-5`, `docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`).
- `packages/backend/product-platforms/freelancer-suite/` already loads as a real
  `ProductBundle` depending only on `anytoolai_platform_sdk` — see `bundle.py` and
  `tests/test_bundle_loads.py`. This is a working, tested example of the shape your product bundle
  should take, not a hypothetical.
- Architecture boundaries are enforced twice: `python scripts/agent/runner.py
  validate-architecture` (CI-gated) and `pytest tests/architecture` (10+ test files). Both are
  green on `main` today.

## What is allowed

- Product configs, prompts, schemas, workflows, and action configs under your bundle's
  `products/<name>/` config roots.
- A `provider_policy_ref` from `configs/kernel/provider_policies.yaml` (add a new one there if you
  need different model/temperature/retry settings — never hardcode a model string elsewhere).
- A dedicated Chrome Extension per product, built on shared `packages/frontend/ce-kit`.
- Registering your bundle in `apps/platform-api` composition.

Follow the step-by-step in `docs/product-specs/add-product-recipe.md`.

## What is forbidden

- Any change to `packages/backend/platform-core` or `packages/backend/platform-actions` to make a
  product work. If the kernel is missing something, that is a kernel bug or a new generic atom —
  file it against MVP-A.
- Product-specific `apps/platform-api` routes. Every endpoint stays parameterized on
  `{product_id}`; only the platform's own `kernel_demo` smoke product is a named exception
  (`/demo*` routes in `apps/platform-api/src/anytoolai_platform_api/routers/demo.py`).
- Prompts, `prompt_ref`, or `provider_policy_ref` values inside a Chrome Extension.
- Direct `litellm`, `pydantic_ai`, `openai`, `anthropic`, `google.genai`, `cohere`, or `mistralai`
  imports anywhere outside the Provider Gateway/adapter layer (`litellm`, provider SDKs) or the
  structured LLM executor (`pydantic_ai`).
- Freelancer product vocabulary (`FreelancerProfile`, `Proposal`, `Brief`, `Upwork`, etc. — full
  list in `docs/architecture/platform-boundaries.md`) inside `platform-core`.

## Where the enforcement lives

- `docs/architecture/platform-boundaries.md` — allowed/forbidden vocabulary and ownership split.
- `docs/product-specs/add-product-recipe.md` — the step-by-step to add a product.
- `scripts/agent/validate_architecture.py` and `tests/architecture/` — the tests that fail your PR
  if you cross a boundary, including the two added for this audit
  (`test_no_product_specific_endpoints.py`,
  `test_litellm_model_strings_stay_in_provider_config.py`) and the JS/TS-side checks this audit
  strengthened: `test_no_direct_provider_calls_outside_gateway.py` now also fails on a direct
  provider SDK import from a Chrome Extension or web package
  (`test_no_direct_provider_js_sdk_imports`) or a raw HTTP call to a provider API host
  (`test_no_direct_provider_api_host_references`), and `test_no_prompts_inside_extensions.py` now
  also fails on a real `{ role: "system", ... }` message shape or an `instructions` /
  `systemInstruction` / `system` payload, not just the literal
  `prompt_ref`/`provider_policy_ref`/`system prompt` tokens. All of these resolve string values
  through one shared static resolver (`tests/architecture/static_string_resolution.py`), so a
  constant defined in another module, a `+` concatenation, an f-string, or a `${NAME}` template
  literal is checked as the string it builds — splitting a forbidden value across constants or
  files does not get past a gate.
  `test_no_product_specific_endpoints.py` checks against a static list of known product names —
  add your new product's name to it when you register the bundle (recipe step 6), don't rely on it
  catching an unlisted product automatically.

## Known allowed exceptions

- `apps/platform-api/.../routers/demo.py` hardcodes `product_id="kernel_demo"`. `kernel_demo` is
  the platform's own smoke product (MVP-A1/A2 proof), not a Freelancer product, so this is not a
  precedent for hardcoding a real product id into a route.

No other exceptions exist today. If your product genuinely needs one, it must be a documented
kernel bugfix, agreed with the platform team, not a silent workaround.
