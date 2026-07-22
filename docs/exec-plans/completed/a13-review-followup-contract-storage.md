# Execution Plan: A13 Review Follow-Up Contract And Storage

## Status

- State: completed
- Owner: agent
- Created: 2026-07-21
- Completed: 2026-07-21
- Review date: 2026-07-21
- Next action: run the PostgreSQL concurrency test on a Docker-enabled host or with a disposable
  PostgreSQL maintenance database URL.
- Blocker: Docker/PostgreSQL runtime was not available locally for production-semantics execution.

## Goal

Verify the current review findings against the branch, fix only still-valid gaps, and keep A13/A16
scope alignment intact.

## Verified Findings

- SQLite/ASGI stress concurrency used the shared scenario runtime test session factory without a
  SQLite busy timeout.
- Scenario start mapped unknown guest identity to `422`; the intended frontend-safe contract
  distinguishes missing guest identity as `422` from unknown guest identity as `404`.
- Quota polling called `check_quota()` with persistence and `quota.checked` event emission, so GET
  polling could create usage rows and append events.
- `guest_quota_usage` lacked a guest identity foreign key in both migration and shared metadata.
- `QuotaUsageRepository.ensure_usage()` caught all `IntegrityError` values instead of only the
  expected unique-dimension insert race.
- The named docs had stale wording for the unknown-identity contract, runtime storage inventory,
  repository count, PostgreSQL validation status, and one compound adjective.

## Completed

- [x] Added the SQLite busy timeout to the affected session factory.
- [x] Made quota polling read-only by adding/using non-persisting, non-emitting quota check options.
- [x] Aligned unknown guest identity handling to `404` for scenario start and docs/OpenAPI/tests.
- [x] Added the `guest_quota_usage.guest_id` foreign key in migration and metadata.
- [x] Restricted `ensure_usage()` `IntegrityError` suppression to the expected unique-dimension
  race.
- [x] Applied the requested documentation and execution-plan wording updates.
- [x] Ran focused API/quota/storage tests, docs validation, generated-docs check, quick-check, and
  the PostgreSQL test guard.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_quota_service.py packages/backend/platform-core/tests/unit/test_runtime_storage.py apps/platform-api/tests/test_identity_quota_api.py apps/platform-api/tests/test_scenario_runtime_api.py apps/platform-api/tests/test_quota_concurrency_stress.py -m "not postgresql" -q --basetemp .quick-check-tmp/a13-review-followup`
- [x] `uv run python scripts/agent/runner.py validate-docs`
- [x] `uv run python scripts/agent/runner.py generate-docs --check`
- [x] `PYTEST_ADDOPTS='--basetemp .quick-check-tmp/a13-review-followup-quickcheck' python scripts/agent/runner.py quick-check`
- [x] `uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q --basetemp .quick-check-tmp/a13-review-followup-pg-guard`
  skipped because no `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was provided.

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-21 | Created plan after verifying the findings against current code/docs. | Implement the minimal patch and validate. |
| 2026-07-21 | Completed the minimal code/docs fixes and validation. | Run PostgreSQL production-semantics coverage when a disposable PostgreSQL database is available. |
