# ANY-118 / A11 follow-up: PostgreSQL Worker Claim Smoke

## References

- Original task: `ANY-31`
- Follow-up source: `gushinets/anytoolai-platform#24`
- Parent task doc: `docs/tasks/a11-job-lifecycle-and-worker-integration.md`

## Problem

The A11 worker lifecycle had DB-backed claim and idempotency coverage, but the production
concurrency contract is PostgreSQL. SQLite tests do not prove PostgreSQL transaction behavior,
independent connections, row visibility, or conditional updates under contention. Multiple
`platform-worker` processes are not preassigned jobs; they compete through the database claim.

## Implementation summary

- Added an opt-in PostgreSQL smoke for two independent workers contending for one persisted
  `created` job.
- The smoke provisions a unique disposable PostgreSQL database through `provision_database(...)`,
  applies real Alembic migrations to `head`, and verifies the migrated runtime tables exist.
- Each worker uses its own SQLAlchemy engine and session factory against the same database.
- A test-only barrier wraps the real `JobRepository.claim_created(...)` method so both workers reach
  the production claim boundary before the real conditional update runs.
- The success case proves exactly one claim, runner invocation, provider call, action run, final
  result artifact chain, and `succeeded` terminal state.
- The failure case proves exactly one claim and runner/provider invocation, safe
  `provider_request_failed` fields, no unsafe provider text in durable safe fields, and `failed`
  terminal state.

## Test cases

- `test_two_postgresql_workers_claim_one_job_success_once`
- `test_two_postgresql_workers_claim_one_job_failure_once`

Both tests reload final state from a fresh session and assert no duplicate workflow/action/provider
terminal event chain was emitted. Worker attribution is established separately through the claim,
runner, and provider invocation records; event-log rows do not carry worker identity.

## CI wiring

The tests are marked `postgresql` and `slow`, so they stay outside `quick-check` and are selected by
the required backend PostgreSQL gate:

```powershell
uv run python scripts/agent/runner.py postgresql-check
```

That command selects all `postgresql` tests under platform core/actions, platform API, and platform
worker roots. No individual node ID was added.

## Local execution

The smoke intentionally does not use a mock database, SQLite, or `metadata.create_all()`. It proves
PostgreSQL transaction and conditional-update behavior, so it requires a real PostgreSQL maintenance
database URL:

```powershell
$env:ANYTOOLAI_POSTGRES_TEST_DATABASE_URL = "postgresql+psycopg://anytoolai:anytoolai@127.0.0.1:5432/postgres"
uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q
```

If that environment variable is unset, `provision_database(...)` skips the tests locally. That skip
is not evidence that the smoke passed; it only confirms the test is opt-in until PostgreSQL is
available. CI sets the maintenance URL in the required PostgreSQL job.

## Validation results

Record concrete command results in
`docs/exec-plans/active/any-118-a11-postgresql-worker-claim-smoke.md` during implementation. Local
PostgreSQL execution requires `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`; when that URL is unavailable,
the smoke must not be treated as locally completed.
