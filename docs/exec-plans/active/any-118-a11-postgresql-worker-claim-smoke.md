# Execution Plan: ANY-118 / A11 PostgreSQL Worker Claim Smoke

## Status

- State: active
- Owner: Codex
- Created: 2026-08-03
- Last updated: 2026-08-03
- Review date: 2026-08-03
- Next action: run the repeated focused PostgreSQL smoke and required PostgreSQL gate with
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` configured, or let the required CI PostgreSQL gate execute
  them.
- Blocker: no local PostgreSQL maintenance URL is configured, so the new smoke can currently only
  be collected as an explicit skip.

## Goal

Prove with a real PostgreSQL database that two independent `platform-worker` instances can contend
for one persisted `created` job, but exactly one worker claims and executes it. Cover both successful
terminalization and safe failure terminalization.

## Scope

### In scope

- PostgreSQL-only worker integration smoke using disposable databases and Alembic `head`.
- Two independent engines/session factories for the same temporary database.
- Real `worker.process_next_job()` poll, claim, handler, runner, provider gateway, and terminal
  persistence paths.
- Documentation of the PostgreSQL worker claim concurrency contract.

### Out of scope

- Changes to the production claim algorithm unless the smoke exposes a bug.
- Leases, heartbeats, external queues, scheduler changes, or worker assignment.
- SQLite evidence for worker claim concurrency.

## Relevant docs

- `docs/architecture/job-lifecycle.md`
- `docs/architecture/runtime-storage.md`
- `docs/tasks/a11-job-lifecycle-and-worker-integration.md`
- `docs/handoffs/a11-job-lifecycle-worker-review-remediation.md`
- `docs/tasks/postgresql-required-gate-coverage.md`

## Contracts touched

- API: none
- DB: PostgreSQL runtime claim behavior, migrated schema verification
- Config: existing `kernel_demo` workflow/action/provider configs only
- Events: workflow/action/provider/artifact/scenario event uniqueness assertions
- Frontend: none

## Implementation steps

- [x] Verify current claim, worker poll, handler, terminalization, recovery, and PostgreSQL test
  infrastructure contracts.
- [x] Add a dedicated PostgreSQL worker claim smoke for success and safe failure contention.
- [x] Update runtime and job lifecycle documentation.
- [x] Add the short ANY-118 task document.
- [x] Run focused PostgreSQL smoke collection where a maintenance database is unavailable and record
  the local blocker truthfully.
- [x] Run focused PostgreSQL smoke where a maintenance database is available and record the result
  truthfully.
- [x] Run repository validation commands that do not require a PostgreSQL maintenance database.
- [x] Harden `postgresql-check` to use a unique workspace-owned pytest basetemp on Windows.

## Validation

- [ ] Repeated focused smoke:
  `uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q`
- [x] Focused smoke with real PostgreSQL maintenance URL:
  `uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q`
  -> user-reported `2 passed` (`.. [100%]`), with only the existing pytest-cache warning.
- [x] Focused smoke collection:
  `uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q`
  -> `2 skipped` because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is unset.
- [x] Worker PostgreSQL suite selection:
  `uv run python -m pytest apps/platform-worker/tests -m "postgresql" -q`
  -> selected the worker PostgreSQL tests; live-DB cases skipped because the maintenance URL is
  unset.
- [ ] Required PostgreSQL gate:
  `uv run python scripts/agent/runner.py postgresql-check`
  -> local result `PGTEST001` because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is unset.
- [x] `uv run python scripts/agent/runner.py validate-configs` -> passed.
- [x] `uv run python scripts/agent/runner.py validate-architecture` -> passed.
- [x] `uv run python scripts/agent/runner.py validate-docs` -> passed.
- [x] `uv run python scripts/agent/runner.py generate-docs --check` -> passed.
- [x] `uv run python -m pytest tests/test_runner.py::test_postgresql_check_uses_marker_driven_backend_roots -q`
  -> passed.
- [x] `python scripts/agent/runner.py quick-check` with workspace `TEMP`/`TMP` -> 215 passed,
  268 deselected, 1 pytest-cache warning.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-03 | Instrument `JobRepository.claim_created()` with a test wrapper instead of replacing it. | The smoke must synchronize the contention while still exercising the real conditional update. |
| 2026-08-03 | Use separate SQLAlchemy engines and session factories per worker. | Independent PostgreSQL connections are the production concurrency contract. |
| 2026-08-03 | Keep CI wiring marker-driven. | `postgresql-check` already selects all `postgresql` tests under worker roots and quick-check excludes `slow`. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-03 | Plan created after inspecting the current worker, claim, handler, runner, migrations, and CI paths. | Add the smoke tests and docs. |
| 2026-08-03 | Added the PostgreSQL contention smoke, runtime docs, index entry, and task doc; non-DB validations pass. | Run the real PostgreSQL smoke with a configured maintenance database or rely on the required CI gate. |
| 2026-08-03 | User reported the focused PostgreSQL smoke passing with a real maintenance URL. | Run the 5x focused loop and the full `postgresql-check` gate. |
| 2026-08-03 | Added a unique `--basetemp` to `postgresql-check` after a Windows pytest temp-root collision. | Retry `postgresql-check` with the configured PostgreSQL maintenance URL. |

## Open questions

- None.

## Follow-up debt

- None expected.
