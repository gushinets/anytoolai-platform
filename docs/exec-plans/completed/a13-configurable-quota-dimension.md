# Execution Plan: A13 Configurable Quota Dimension

## Status

- State: completed
- Owner: agent
- Created: 2026-07-22
- Completed: 2026-07-22
- Review date: 2026-07-22
- Next action: run the PostgreSQL concurrency test on a Docker-enabled host or with a disposable
  PostgreSQL maintenance database URL.
- Blocker: system `python scripts/agent/runner.py doctor` reports missing Python modules in the
  global interpreter; validation used `uv`. PostgreSQL runtime was not available locally.

## Goal

Fix the A13 quota-dimension contract so quota scope comes from repo policy config instead of being
hard-coded to product scope. Support product-wide guest quota and scenario-specific guest quota
counters while keeping backend enforcement at accepted scenario start.

## Research Summary

- Reviewed docs: `ARCHITECTURE.md`, `docs/index.md`, MVP scope/kernel specs, `docs/core-beliefs.md`,
  platform boundaries, package layering, LLM runtime, quota model, config model, runtime storage,
  event taxonomy, scenario-session model, job lifecycle, frontend boundaries, and the A13 plan.
- Inspected code: quota models/service/repository, SDK quota contract, config loader/registry,
  kernel quota config, scenario start service, identity/quota router, runtime config projection,
  API schemas, storage metadata, Alembic migrations, and A13 quota/scenario/config/storage/API
  tests.
- Previous behavior was hard-coded around
  `tenant_id + region + guest_id + product_id + quota_policy_id + period_key`.
- `ScenarioRuntimeService.start_session()` already passed the concrete `scenario_id` into
  `GuestQuotaService.consume_for_accepted_start()` before session/job creation, so the enforcement
  point remained correct.

## Decisions

- Add required quota policy dimension values: `product` and `scenario`.
- Resolve one persisted `dimension_key` from policy at runtime:
  - `product` -> `dimension_key = product_id`, `scenario_id = null`;
  - `scenario` -> `dimension_key = scenario_id`, `scenario_id = scenario_id`.
- Keep operational scoping by `tenant_id` and `region`; keep product/policy/period in the unique
  key so the minimum guest/product contract remains explicit.
- Avoid nullable columns in the uniqueness path; PostgreSQL NULL semantics must not weaken
  concurrency protection.
- Expose quota dimension in frontend-safe runtime config/quota state and quota event properties.
- Keep quota independent from provider calls, provider retries, PydanticAI, LiteLLM, and telemetry.

## Completed

- [x] Added `QuotaDimension` to SDK/core models and required `dimension` in quota config.
- [x] Added storage metadata and migration support for `quota_dimension`, `dimension_key`, and
  persisted `scenario_id`.
- [x] Updated quota repository lookup/ensure/unique race handling to use resolved dimensions.
- [x] Updated quota service check/consume/state/event paths to resolve dimensions from policy.
- [x] Updated API/runtime config schemas and payloads with frontend-safe dimension fields.
- [x] Added tests for product-wide sharing, scenario-specific counters, config validation, storage
  uniqueness, and quota events.
- [x] Updated architecture/docs/A13 plan and generated docs.
- [x] Ran focused quota/config/API/storage checks, docs validation, slow SQLite stress coverage,
  PostgreSQL guard, architecture validation, and quick-check.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/test_contract_field_compatibility.py packages/backend/platform-sdk/tests/test_contracts_importable.py packages/backend/platform-core/tests/unit/test_config_loader.py packages/backend/platform-core/tests/unit/test_quota_service.py packages/backend/platform-core/tests/unit/test_runtime_storage.py apps/platform-api/tests/test_identity_quota_api.py apps/platform-api/tests/test_runtime_config.py apps/platform-api/tests/test_scenario_runtime_api.py -q --basetemp .quick-check-tmp/a13-quota-dimension-focused`
- [x] `uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_stress.py -m slow -q --basetemp .quick-check-tmp/a13-quota-dimension-stress`
- [x] `uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q --basetemp .quick-check-tmp/a13-quota-dimension-pg-guard`
  skipped because no `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was provided.
- [x] `uv run python scripts/agent/runner.py validate-docs`
- [x] `uv run python scripts/agent/runner.py generate-docs --check`
- [x] `uv run python scripts/agent/runner.py validate-architecture`
- [x] `PYTEST_ADDOPTS='--basetemp .quick-check-tmp/a13-quota-dimension-quickcheck-2' python scripts/agent/runner.py quick-check`

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-22 | Completed docs/code research and wrote implementation plan. | Implement and validate. |
| 2026-07-22 | Implemented configurable product/scenario quota dimensions and validated the fast path. | Run PostgreSQL production-semantics coverage when a disposable PostgreSQL database is available. |
