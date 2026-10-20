# Execution Plan: ANY-680 httpx2/httpcore2 and PydanticAI Security Upgrade

## Status

- State: active
- Owner: agent
- Created: 2026-10-20
- Last updated: 2026-10-20
- Review date: 2026-10-20
- Next action: wait for required CI on PR #188, then confirm Dependabot marks the alerts fixed after merge.
- Blocker: none

## Goal

Close the High httpx2/httpcore2 Dependabot alerts (and related Medium ones) and, by owner decision,
the open `pydantic-ai-slim` alerts, by re-resolving every affected uv lock with `uv`.

## Scope

### In scope

- Raise `pydantic-ai-slim` lower bound to `>=2.53.0` in `pyproject.toml` and
  `packages/backend/platform-actions/pyproject.toml`.
- `uv lock --upgrade-package pydantic-ai-slim --upgrade-package httpx2 --upgrade-package httpcore2`
  for the root, `apps/platform-api`, `apps/platform-worker` and `packages/backend/platform-actions`.
- Record the new PydanticAI decision in `docs/architecture/llm-runtime.md`.

### Out of scope

- `httpx`/`httpcore` (different packages), urllib3/aiohttp (ANY-678/679).
- Using new PydanticAI features; this is a version bump only.

## Resolver outcome

| Package | Before (root / api / worker / actions) | After (all four) |
|---|---|---|
| httpx2 | 2.5.0 / 2.12.0 / 2.5.0 / 2.5.0 | 2.15.1 |
| httpcore2 | 2.5.0 / 2.12.0 / 2.5.0 / 2.5.0 | 2.15.1 |
| pydantic-ai-slim, pydantic-graph | 2.2.0 / 2.40.0 / 2.9.0 / 2.2.0 | 2.58.0 |
| genai-prices | 0.0.67 / 0.1.6 / 0.0.71 / 0.0.67 | 0.1.13 |

`httpx2-jsfetch` is added to three locks; it is Emscripten-only and is not installed on Linux or
Windows. `platform-core` does not contain these packages.

## Reachability

No AnyToolAI code imports `httpx2`, `httpcore2` or `genai_prices`; provider calls go through
ProviderGateway, LiteLLM and `httpx`. Installed `genai_prices` references `httpx2` only in
`update_prices.py`. The PydanticAI web chat UI, `web_fetch`, remote content download,
concurrency-limited models and OTel paths are not used. All alerts are fixed by version.

## Validation

- `uv lock --check` passes in all five projects.
- `quick-check`: 2341 passed; one failure, `test_activation_marker_is_readable_by_non_root_api_user`,
  needs passwordless sudo, which this environment lacks.
- `platform-actions` tests pass with `-W error::DeprecationWarning`.
- Images for `infra/docker/platform-{api,worker}.Dockerfile` rebuilt with `--no-cache`: `httpx2` and
  `httpcore2` 2.15.1, `pydantic-ai-slim` and `pydantic-graph` 2.58.0, `genai-prices` 0.1.13,
  `httpx2-jsfetch` not installed.
- `atoms-proof` on the rebuilt images: 11/11 atoms and 3/3 composite workflows pass.
- `postgresql-check` passes.
- `frontend-check` passes.

## Remaining

- `full-check` end to end: it stops at the `quick-check` sudo failure above, so its product-suite
  steps have not run locally; CI covers them.
- PydanticAI cost comparison after `genai-prices` 0.1.13.
- Required CI on the PR.
