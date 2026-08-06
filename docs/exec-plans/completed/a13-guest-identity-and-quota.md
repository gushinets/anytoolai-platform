# Execution Plan: A13 Guest Identity And Quota

## Status

- State: completed
- Scope status: backend scope complete; frontend integration remains a separate ANY-171 follow-up
- Owner: agent
- Created: 2026-07-20
- Last updated: 2026-08-05
- Review date: 2026-07-20
- Next action: none for A13; ANY-171 owns the remaining frontend quota/start integration.
- Blocker: none

## Goal

Implement backend-enforced access-lite quota for guest identities.

A13 scope is backend storage, policy resolution, API behavior, event emission, and local CE guest-id
persistence. ANY-170 delivered the CE client foundation; ANY-171 owns the deferred real
quota/start/polling integration.

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
- Quota policy is resolved from `product.quota_policy_ref`; policy config declares `dimension:
  product` for shared product-wide counters or `dimension: scenario` for scenario-specific
  counters. The resolved persisted dimension is
  `tenant_id + region + guest_id + product_id + quota_policy_id + quota_dimension + dimension_key
  + period_key`.
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
- Historical local PostgreSQL quota attempt could not run because Docker was unavailable and no
  disposable PostgreSQL database URL was provided; it is not counted as successful validation.
- [x] PR #54 required CI ran the canonical `python scripts/agent/runner.py postgresql-check`
  successfully against PostgreSQL.

## Follow-up Debt

- ANY-171 owns real CE-kit `getQuota()` and `startScenario()` clients, guest-id propagation,
  polling, typed error handling, and integration tests. This is separate from A13's completed
  backend scope.

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-20 | Completed mandatory docs/code research, identified the A12 accepted-start boundary, and confirmed `uv run python scripts/agent/runner.py doctor` passes. | Implement storage/domain/API wiring. |
| 2026-07-20 | Implemented guest identity, quota persistence/services, API endpoints, CE guest-id storage helper, scenario-start enforcement, tests, and docs. Canonical quick-check passed with a fresh basetemp override for the known stale pytest temp root; frontend typecheck/build passed through Corepack pnpm. | None. |
| 2026-07-20 | Follow-up clarified A13 as backend-complete with integration pending, added explicit scenario-start `429` OpenAPI metadata, guest `422` API tests, real parallel HTTP start coverage, a slow stress test, and CE-kit deferred-helper comments. | The separately owned frontend integration remains follow-up work. |
| 2026-07-20 | Added PostgreSQL-backed quota concurrency integration coverage gated by `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` and clarified that only PostgreSQL-backed tests count as production concurrency proof. Docker CLI was present locally, but the daemon was unavailable during this pass. | Run the PostgreSQL test on a Docker-enabled host or against a disposable PostgreSQL test database. |
| 2026-07-22 | Added explicit quota policy dimensions for product-wide and scenario-specific quota counters, persisted resolved dimension keys, and aligned tests/docs with configurable scope. | Run focused validation and refresh generated docs. |
| 2026-08-05 | Recorded ANY-170 as the delivered CE client foundation, assigned deferred real quota/start/polling integration to ANY-171, and reconciled local skips with PR #54's successful canonical PostgreSQL CI evidence. | None for A13. |
