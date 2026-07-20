# Execution Plan: A13 PostgreSQL Concurrency And CE Scope

## Status

- State: active
- Owner: agent
- Created: 2026-07-20
- Last updated: 2026-07-20
- Review date: 2026-07-20
- Next action: run `apps/platform-api/tests/test_quota_concurrency_postgresql.py` against a
  disposable PostgreSQL database.
- Blocker: Docker daemon is unavailable in this environment and no
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was provided, so PostgreSQL-specific execution could not
  be completed locally.

## Decision

**A13 remains backend-complete; CE-kit quota/start HTTP integration remains deferred to A16.**

The current patch will not implement the central CE-kit Platform API client because that would widen
scope into the explicitly deferred A16 frontend/runtime-client work. A13 will continue to expose only
real `createGuestIdentity()` local persistence in CE-kit.

## Reviewed

- Docs: quota model, frontend boundaries, scenario-session model, job lifecycle, runtime storage,
  LLM runtime, MVP-A/MVP scope specs, A13 active plan, A13 follow-up completed plan, worktree runtime
  docs.
- Backend/API: quota service/repository, scenario runtime service/router, identity/quota router,
  transaction boundary, storage metadata and migrations, API bootstrap.
- Frontend: CE-kit `createGuestIdentity()`, `startScenario()`, `getQuota()`, package exports.
- Tests/tooling: SQLite Alembic/ASGI scenario runtime tests, slow SQLite stress test, runner
  worktree Compose commands, PostgreSQL compose file.

## Complete Now

- Add a PostgreSQL-only integration test that runs through the real API transaction path when
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is provided.
- Make the test explicitly verify first `N` accepted starts, `N+1` `429 quota_exhausted`, no double
  consumption, and post-factum session/job/quota/event consistency under concurrent starts.
- Guard the PostgreSQL test so it only runs against a clearly disposable test database.
- Update docs/specs/plans to state that SQLite concurrency coverage is not production proof and the
  PostgreSQL test is the production-semantics check.
- Keep CE-kit start/quota helpers deferred and document only guest identity persistence as real in
  A13.

## Deferred To A16

- Real CE-kit `getQuota()` and `startScenario()` HTTP clients.
- Guest-id propagation from local CE storage into scenario-start calls.
- Typed CE handling for `429 quota_exhausted`, `422`, polling, and normalized API errors.
- CE-kit integration tests for guest create + quota + scenario start.

## Validation Plan

- [x] API/quota-focused tests.
- [ ] PostgreSQL test against a live disposable PostgreSQL database.
- [x] PostgreSQL test guard executed and reported explicit skip without
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`.
- [x] Docs validation and generated-docs check.
- [x] Frontend typecheck/build because CE-kit scope files remain in play.
- [x] Canonical quick-check.

## PostgreSQL Test Command

```powershell
$env:ANYTOOLAI_POSTGRES_TEST_DATABASE_URL = "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres"
uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_postgresql.py -m "slow and postgresql" -q
```

The SQLite/ASGI stress test remains available outside the quick-check fast path:

```powershell
uv run python -m pytest apps/platform-api/tests/test_quota_concurrency_stress.py -m slow -q
```

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-20 | Added the PostgreSQL-backed API quota concurrency test, clarified that CE-kit quota/start remain deferred, documented PostgreSQL as the production concurrency proof, and validated the runnable fast suite. Docker Compose startup failed locally because the Docker daemon was unavailable. | Run the PostgreSQL test on a Docker-enabled host or with `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` pointing at a disposable PostgreSQL maintenance DB. |
