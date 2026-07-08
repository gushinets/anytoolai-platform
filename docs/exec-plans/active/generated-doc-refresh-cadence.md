# Execution Plan: Generated Doc Refresh Cadence

## Status

- State: active
- Owner: agent

## Goal

Keep generated repository docs aligned with current schema, API, config, action, and event contracts.

## Context

Weekly doc gardening on 2026-07-08 found generated docs present and useful, but refresh ownership is still manual. `apps/platform-api/src/anytoolai_platform_api/openapi/generate.py` is placeholder-level, and `docs/generated/openapi.md` can drift from the API surface unless refresh steps are made explicit.

## Tasks

- [ ] Confirm the intended generated-doc entrypoint in `scripts/agent/generate-docs.sh`.
- [ ] Refresh `docs/generated/*.md` from current config, storage, event, action, and API sources.
- [ ] Replace or document the placeholder OpenAPI generation helper.
- [ ] Add a lightweight validation check that fails when generated docs are stale, if practical.
- [ ] Run `python scripts/agent/runner.py validate-configs`, `python scripts/agent/runner.py validate-architecture`, and `python scripts/agent/quick_check.py`.
