# Execution Plan: A06 API Bootstrap And Runtime Config Endpoint

## Status

- State: active
- Owner: mixed
- Created: 2026-06-22
- Last updated: 2026-06-22

## Goal

Wire the FastAPI composition root to config registry and runtime storage bootstrap, then expose a frontend-safe runtime config endpoint for product surfaces.

## Scope

### In scope

- Bootstrap kernel configs before API serving.
- Wire config registry and optional runtime storage dependencies through `apps/platform-api`.
- Add request context, safe API errors, and basic CORS handling for web and Chrome Extension surfaces.
- Add `GET /v1/products/{product_id}/runtime-config`.
- Return only frontend-safe runtime metadata: product ID, frontend IDs, scenario IDs, enabled frontends/scenarios, input/output renderer hints, quota summary, and allowed UI capabilities.
- Explicitly exclude prompt text, system prompts, provider policy/model, internal file paths, and secrets from the response.
- Add httpx API tests and generated OpenAPI markdown.

### Out of scope

- Scenario start.
- Jobs.
- Auth.
- Provider execution.

## Relevant docs

- `AGENTS.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/generated/openapi.md`

## Contracts touched

- API: `GET /v1/products/{product_id}/runtime-config`
- Runtime bootstrap: app-level registry and optional storage dependency container
- Config: read-only registry projection only
- DB: no schema changes
- Frontend: runtime-config consumers receive only frontend-safe metadata and renderer hints

## Acceptance criteria

- Unknown product returns a safe `404` that does not leak internal config identifiers beyond the requested `product_id` slot.
- Invalid startup config prevents API serving by failing app creation before requests are accepted.
- OpenAPI contains the runtime-config endpoint and example response.

## Definition of done

- API tests run through `httpx`.
- Generated OpenAPI is updated in `docs/generated/openapi.md`.
- Runtime-config response shape is explicitly safe for frontend consumption.

## Repo impact

- `apps/platform-api/src`
- `packages/backend/platform-core/src/anytoolai_platform_core/bootstrap`
- `docs/generated/openapi.md`

## Implementation steps

- [x] Add a frontend-safe runtime config projection in `platform-core/bootstrap`.
- [x] Extend API bootstrap to carry registry and optional storage dependencies.
- [x] Bootstrap configs during `create_app()` so invalid config fails before serving requests.
- [x] Add request ID context, CORS handling, and safe error response handling.
- [x] Add response schemas, OpenAPI example, and runtime-config router.
- [x] Add httpx API tests for success, safe `404`, startup failure, CORS preflight, and OpenAPI.
- [x] Update generated OpenAPI markdown.
- [ ] Re-run the repo validation slice after unrelated `platform-core` config-loader failures are resolved on this branch/base.

## Validation

- [x] Local slice: `.quick-check-venv\Scripts\python.exe -m pytest -q apps/platform-api/tests`
- [x] Local slice: `python -m py_compile` for touched API/core files
- [x] Baseline command attempted: `python scripts/agent/quick_check.py`
- [ ] `python scripts/agent/quick_check.py` green end-to-end
- [ ] `uv run python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-22 | Put the projection in `platform-core/bootstrap`, not product-specific code. | The API needs product-neutral runtime metadata from the registry without importing product bundles. |
| 2026-06-22 | Return schema refs/version hints instead of schema bodies. | The endpoint should guide renderers without exposing larger internal config documents. |
| 2026-06-22 | Keep storage wiring optional unless `ANYTOOLAI_DATABASE_URL` is set. | This slice does not start scenarios or jobs, but the composition root should still be ready for runtime storage. |
| 2026-06-22 | Treat prompt text, provider selection details, internal paths, and secrets as forbidden response data. | Frontend surfaces need runtime metadata only, not backend execution internals. |
| 2026-06-22 | Fix only the shared config error path needed for startup-failure validation; leave broader config-loader API/test cleanup out of A06. | The API acceptance test needs invalid config to raise a stable `RegistryLoadError`, but the remaining registry helper/test mismatches are separate work. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-22 | Audited the branch against A06. The runtime bootstrap, dependency wiring, CORS, request ID propagation, safe error handler, runtime-config router, and `docs/generated/openapi.md` were already present. | Validate the branch against the actual acceptance criteria and fix only what is still blocking A06. |
| 2026-06-22 | Fixed the shared config error path so invalid config cleanly fails `create_app()` with `RegistryLoadError`, and tightened the API test to assert the OpenAPI example payloads for `200` and safe `404`. | Keep A06 scoped to the API slice; log the remaining unrelated `platform-core` test failures separately. |
| 2026-06-22 | `.quick-check-venv\Scripts\python.exe -m pytest -q apps/platform-api/tests` passed. `python -m py_compile` for touched files passed. `python scripts/agent/quick_check.py` still fails, but now only on unrelated `platform-core` config-loader registry helper/test expectations. | Leave repo-wide green as an external blocker for this task unless those base failures are assigned separately. |

## Open questions

- Should this plan move to `completed/` once A06-only review is accepted, or stay active until unrelated `platform-core` quick-check failures are resolved on the branch/base?

## Assignee notes

- The endpoint should return only frontend-safe runtime metadata: IDs, enabled frontends/scenarios, renderer hints, quota summary, and allowed UI capabilities.
- Do not expose prompt text, system prompts, provider policy/model, internal file paths, or secrets in the response body or OpenAPI example.
- Keep the API behavior product-neutral. The runtime projection belongs in `platform-core/bootstrap`, while `apps/platform-api` stays the composition and transport layer.
- A startup-failure test already exists in `apps/platform-api/tests/test_startup_config_validation.py`; use it as the acceptance check for invalid config preventing serving.
- If CORS and extension-origin handling are already present locally, preserve and extend them rather than adding a second mechanism.
- `just doctor` is not available in the current shell, so task validation used the documented Python fallbacks and the managed `.quick-check-venv`.

## Follow-up debt

- Move the plan to `completed/` after final validation is green.
- If repo-level checks continue to fail, split unrelated `platform-core` config-loader fixes into a separate task so A06 can be reviewed on its own merits. Current remaining failures are the missing `ConfigRegistry.get_action_config()` compatibility helper, missing `RegistryLoadError.errors` aggregation field, and a config-loader test expectation that `product.scenarios` is a tuple.
