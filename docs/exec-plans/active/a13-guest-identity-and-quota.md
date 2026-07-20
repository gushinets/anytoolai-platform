# Execution Plan: A13 Guest Identity And Quota

## Status

- State: active
- Scope status: backend-complete, integration pending
- Owner: agent
- Created: 2026-07-20
- Last updated: 2026-07-20
- Review date: 2026-07-20
- Next action: A16 must complete the shared CE-kit Platform API client and full frontend quota
  integration.
- Blocker: none

## Goal

Implement backend-enforced access-lite quota for guest identities.

A13 scope is backend storage, policy resolution, API behavior, event emission, and local CE guest-id
persistence. Full CE-kit quota/start integration is intentionally deferred to A16.

## Research Summary

- Reviewed: `ARCHITECTURE.md`, `docs/index.md`, MVP scope/kernel specs, `docs/core-beliefs.md`,
  platform boundaries/layering, LLM runtime, scenario-session model, job lifecycle, runtime
  storage, event taxonomy, config model, quota model, generated DB/OpenAPI/config docs, and the
  completed A04/A11/A12 execution plans.
- Inspected: A12 scenario runtime router/service, session and job repositories, transaction
  boundary, event emitter/repository/taxonomy, identity/quota placeholders, config loader and
  `product.quota_policy_ref` loading, migrations, API schemas/errors/bootstrap, scenario-runtime
  tests, runtime-config tests, and CE-kit identity/quota placeholders.
- A04 currently owns runtime storage for sessions/jobs/actions/provider calls/artifacts only and
  intentionally left quota out.
- A12 starts scenarios by validating product/scenario/frontend/input/workflow, creating a
  `scenario_sessions` row with `processing`, creating one linked `jobs` row with `created`, then
  committing and returning polling IDs.

## Decisions

- An accepted scenario start is the A12 queue-and-return acceptance that commits both the started
  scenario session and created workflow job.
- Quota is checked and consumed in the same transaction as accepted scenario start, after A12
  config/frontend/input validation and before session/job creation.
- If quota is exhausted, no scenario session or job is created; quota check/exhausted events are
  committed and the API returns standardized `quota_exhausted`.
- Quota policy is resolved from `product.quota_policy_ref`; the current config contract has no
  scenario-level quota dimension, so the required dimension is
  `tenant_id + region + guest_id + product_id + quota_policy_id + period_key`.
- Quota state is independent from workflow success, provider-call ledger rows, PydanticAI
  validation retries, LiteLLM transport attempts, and usage/cost telemetry.

## Implementation Steps

- [x] Implement Alembic `0003` and shared storage tables for `guest_identities` and
  `guest_quota_usage`.
- [x] Implement identity models, repository, and service with opaque guest IDs and `guest.created`
  event emission.
- [x] Implement quota models, repository, and service with check/consume/exhausted behavior and
  transaction-safe conditional updates.
- [x] Add identity and quota API routes and wire them in the FastAPI composition root.
- [x] Inject quota enforcement into `ScenarioRuntimeService.start_session`.
- [x] Add tests for guest create, quota check, consume, exhausted, repeat calls, concurrency, and
  scenario-start integration.
- [x] Update architecture/product/generated docs and refresh generated DB/OpenAPI docs.
- [ ] A16 follow-up: replace CE-kit demo/deferred helpers with real `getQuota()` and
  `startScenario()` HTTP clients, guest-id propagation, typed error handling, and CE integration
  tests.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py packages/backend/platform-core/tests/unit/test_quota_service.py apps/platform-api/tests/test_identity_quota_api.py apps/platform-api/tests/test_scenario_runtime_api.py -q --basetemp .quick-check-tmp/a13-focused`
- [x] `uv run python -m pytest packages/backend/platform-core/tests apps/platform-api/tests -q --basetemp .quick-check-tmp/a13-core-api`
- [x] `uv run python scripts/agent/runner.py validate-docs`
- [x] `uv run python scripts/agent/runner.py generate-docs --check`
- [x] `uv run python scripts/agent/runner.py validate-architecture`
- [x] `uv run python scripts/agent/runner.py quick-check` with `PYTEST_ADDOPTS='--basetemp .quick-check-tmp/a13-quickcheck-runner'`
- [x] Frontend equivalent via Corepack because `pnpm` is not directly on PATH:
  `corepack pnpm install --frozen-lockfile`, `corepack pnpm -r typecheck`,
  `corepack pnpm -r build`
- [ ] PostgreSQL quota concurrency/production-semantics test:
  blocked because Docker was unavailable and no disposable PostgreSQL database URL was provided.

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-20 | Completed mandatory docs/code research, identified the A12 accepted-start boundary, and confirmed `uv run python scripts/agent/runner.py doctor` passes. | Implement storage/domain/API wiring. |
| 2026-07-20 | Implemented guest identity, quota persistence/services, API endpoints, CE guest-id storage helper, scenario-start enforcement, tests, and docs. Canonical quick-check passed with a fresh basetemp override for the known stale pytest temp root; frontend typecheck/build passed through Corepack pnpm. | None. |
| 2026-07-20 | Follow-up clarified A13 as backend-complete with integration pending, added explicit scenario-start `429` OpenAPI metadata, guest `422` API tests, real parallel HTTP start coverage, a slow stress test, and CE-kit deferred-helper comments. | A16 must replace CE-kit demo/deferred start/quota helpers with the real Platform API client and integration tests. |
| 2026-07-20 | Added PostgreSQL-backed quota concurrency integration coverage gated by `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` and clarified that SQLite stress tests are not production proof. Docker CLI was present locally, but the daemon was unavailable during this pass. | Run the PostgreSQL test on a Docker-enabled host or against a disposable PostgreSQL test database. |
