# Execution Plan: A13 PostgreSQL Concurrency And CE Scope

## Status

- State: completed
- Owner: agent
- Created: 2026-07-20
- Last updated: 2026-08-05
- Review date: 2026-07-20
- Next action: none repo-side; canonical `postgresql-check` runs in the backend PostgreSQL CI job.
- Blocker: none

## Decision

**A13 remains backend-complete; ANY-170 delivered the CE client foundation, and ANY-171 owns the
deferred real quota/start/polling integration.**

The current patch will not implement the central CE-kit Platform API client because that would widen
scope into the explicitly deferred ANY-171 frontend/runtime-client work. A13 will continue to expose only
real `createGuestIdentity()` local persistence in CE-kit.

## Reviewed

- Docs: quota model, frontend boundaries, scenario-session model, job lifecycle, runtime storage,
  LLM runtime, MVP-A/MVP scope specs, A13 active plan, A13 follow-up completed plan, worktree runtime
  docs.
- Backend/API: quota service/repository, scenario runtime service/router, identity/quota router,
  transaction boundary, storage metadata and migrations, API bootstrap.
- Frontend: CE-kit `createGuestIdentity()`, `startScenario()`, `getQuota()`, package exports.
- Tests/tooling: legacy non-PostgreSQL scenario runtime coverage, runner worktree Compose
  commands, PostgreSQL compose file.

## Complete Now

- Add a PostgreSQL-only integration test that runs through the real API transaction path when
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is provided.
- Make the test explicitly verify first `N` accepted starts, `N+1` `429 quota_exhausted`, no double
  consumption, and post-factum session/job/quota/event consistency under concurrent starts.
- Guard the PostgreSQL test so it only runs against a clearly disposable test database.
- Update docs/specs/plans to state that PostgreSQL tests are the only supported production-semantics
  check.
- Keep CE-kit start/quota helpers deferred and document only guest identity persistence as real in
  A13.

## Follow-up Debt Owned By ANY-171

- Real CE-kit `getQuota()` and `startScenario()` HTTP clients.
- Guest-id propagation from local CE storage into scenario-start calls.
- Typed CE handling for `429 quota_exhausted`, `422`, polling, and normalized API errors.
- CE-kit integration tests for guest create + quota + scenario start.

## Validation Plan

- [x] API/quota-focused tests.
- [x] PR #54 required CI ran the canonical `python scripts/agent/runner.py postgresql-check`
  successfully against a live PostgreSQL service.
- [x] Dedicated GitHub Actions job provisions PostgreSQL and runs the production-dialect quota
  concurrency test.
- Historical local PostgreSQL test-guard run skipped without
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`; it is not counted as successful validation.
- [x] Docs validation and generated-docs check.
- [x] Frontend typecheck/build because CE-kit scope files remain in play.
- [x] Canonical quick-check.
- [x] PR #54's canonical PostgreSQL CI run revalidated the scenario-dimension quota assertions
  after the July 28 policy-limit cleanup.

## PostgreSQL Test Command

```powershell
$env:ANYTOOLAI_POSTGRES_TEST_DATABASE_URL = "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres"
uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q
```

Legacy non-PostgreSQL concurrency harnesses have been removed from the supported test path.

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-20 | Added the PostgreSQL-backed API quota concurrency test, clarified that CE-kit quota/start remain deferred, documented PostgreSQL as the production concurrency proof, and validated the runnable fast suite. Docker Compose startup failed locally because the Docker daemon was unavailable. | Run the PostgreSQL test on a Docker-enabled host or with `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` pointing at a disposable PostgreSQL maintenance DB. |
| 2026-07-22 | Added a dedicated backend CI job with a PostgreSQL service that runs `apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql"` against a disposable database URL. | Confirm the new workflow job is configured as a required check for PRs. |
| 2026-07-28 | Tightened the scenario-dimension PostgreSQL quota test so it explicitly reads `kernel_demo.guest_quota_v1`, asserts the policy exists, derives `scenario_quota_limit` from `policy.limit_count`, and still drives the scenario-scoped override through the existing registry mutation helper. | Re-run the PostgreSQL slow test plus `quick-check` and record whether local validation can execute or skips for missing PostgreSQL configuration. |
| 2026-07-28 | Ran the requested PostgreSQL pytest command locally with a repo-local `UV_CACHE_DIR`; the test module skipped because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was unset. `python scripts/agent/runner.py quick-check` passed. | Re-run the PostgreSQL slow test against a disposable PostgreSQL maintenance database URL to complete live-dialect validation. |
| 2026-08-05 | PR #54's required CI completed the canonical PostgreSQL check against a live service. Reassigned the separately deferred CE integration to ANY-171. | None for A13. |
