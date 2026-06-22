# Execution Plan: A06 API Bootstrap And Runtime Config Endpoint

## Status

- State: active
- Owner: agent
- Created: 2026-06-22
- Last updated: 2026-06-22

## Goal

Wire the FastAPI composition root to config registry and runtime storage bootstrap, then expose a frontend-safe runtime config endpoint for product surfaces.

## Scope

### In scope

- Bootstrap kernel configs before API serving.
- Wire config registry and storage dependencies through `apps/platform-api`.
- Add request context and a safe API error shape.
- Add `GET /v1/products/{product_id}/runtime-config`.
- Return product/frontend/scenario IDs, renderer hints, quota summary, and allowed UI capabilities.
- Exclude prompt text, system prompts, provider policy/model, internal paths, and secrets.
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

## Implementation steps

- [x] Add a frontend-safe runtime config projection in `platform-core/bootstrap`.
- [x] Extend API bootstrap to carry registry and optional storage dependencies.
- [x] Add request ID context, CORS handling, and safe error response handling.
- [x] Add response schemas and runtime-config router.
- [x] Add httpx API tests for success, safe 404, CORS preflight, and OpenAPI.
- [x] Update generated OpenAPI markdown.

## Validation

- [x] Local slice: `pytest -q apps/platform-api/tests`
- [x] Local slice: `python -m py_compile` for touched API/core files
- [ ] Full repo: blocked locally because the sandbox cannot resolve `github.com` for cloning.
- [ ] `uv run python scripts/agent/runner.py full-check`: pending CI/local repo environment.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-22 | Put the projection in `platform-core/bootstrap`, not product-specific code. | The API needs product-neutral runtime metadata from the registry without importing product bundles. |
| 2026-06-22 | Return schema refs/version hints instead of schema bodies. | The endpoint should guide renderers without exposing larger internal config documents. |
| 2026-06-22 | Keep storage wiring optional unless `ANYTOOLAI_DATABASE_URL` is set. | This slice does not start scenarios or jobs, but the composition root should still be ready for runtime storage. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-22 | Implemented the API bootstrap, runtime-config endpoint, tests, and generated OpenAPI doc update. | Open PR and let repository CI run full validation. |

## Open questions

None.
