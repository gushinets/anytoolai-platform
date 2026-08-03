# Execution Plan: ANY-118 / A11 PostgreSQL Worker Claim Smoke

## Status

- State: active
- Owner: Codex
- Created: 2026-08-03
- Last updated: 2026-08-03
- Review date: 2026-08-03
- Next action: push the lease-first follow-up commit to the PR branch.
- Blocker: none. The focused smoke, repeated smoke loop, worker PostgreSQL suite,
  `postgresql-check`, and repository quick-check have passed against the configured local
  PostgreSQL maintenance URL.

## Goal

Prove with a real PostgreSQL database that two independent `platform-worker` instances can contend
for one persisted `created` job, but exactly one worker acquires the advisory lease, claims the job,
and executes it. Cover both successful terminalization and safe failure terminalization.

## Scope

### In scope

- PostgreSQL-only worker integration smoke using disposable databases and Alembic `head`.
- Two independent engines/session factories for the same temporary database.
- Real `worker.process_next_job()` poll, advisory lease, claim, handler, runner, provider gateway,
  and terminal persistence paths.
- Documentation of the PostgreSQL lease-first worker coordination contract.

### Out of scope

- Changes to the production claim algorithm unless the smoke exposes a bug.
- New lease mechanisms, heartbeats, external queues, scheduler changes, or worker assignment.
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
- [x] Address still-valid review comments on schema-qualified Alembic lookup, docs wording,
  success event symmetry, and unsafe-text durability assertions.
- [x] Rebase the smoke against the current lease-first worker contract.
- [x] Move deterministic contention synchronization from repository claim to pre-advisory-lease
  acquisition.
- [x] Update assertions so exactly one lease acquisition and exactly one downstream claim/execution
  are required.
- [x] Update architecture/runtime docs for lease-first coordination.

## Validation

- [x] Repeated focused smoke with real PostgreSQL maintenance URL:
  `for ($i=1; $i -le 5; $i++) { uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }`
  -> 5 consecutive successful runs; each run reported `2 passed`.
- [x] Focused smoke with real PostgreSQL maintenance URL:
  `uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q`
  -> `2 passed`, with only the existing pytest-cache warning.
- [x] Focused smoke collection:
  `uv run python -m pytest apps/platform-worker/tests/test_worker_claim_postgresql.py -m "slow and postgresql" -q`
  -> `2 skipped` because `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` is unset.
- [x] Worker PostgreSQL suite selection:
  `uv run python -m pytest apps/platform-worker/tests -m "postgresql" -q`
  -> selected the worker PostgreSQL tests; live-DB cases skipped because the maintenance URL is
  unset.
- [x] Worker lease/claim/concurrent selection with real PostgreSQL maintenance URL:
  `uv run python -m pytest apps/platform-worker/tests -k "lease or claim or concurrent" -q`
  -> passed with `16 passed, 2 skipped`.
- [x] Worker PostgreSQL suite with real PostgreSQL maintenance URL:
  `uv run python -m pytest apps/platform-worker/tests -m "postgresql" -q`
  -> passed with `34 passed, 2 skipped`.
- [x] Required PostgreSQL gate:
  `uv run python scripts/agent/runner.py postgresql-check`
  -> passed after increasing the local command timeout; selected PostgreSQL-marked tests across
  platform core/actions, platform API, and platform worker roots, with 2 skips.
- [x] `uv run python scripts/agent/runner.py validate-configs` -> passed.
- [x] `uv run python scripts/agent/runner.py validate-architecture` -> passed after the lease-first
  documentation update.
- [x] `uv run python scripts/agent/runner.py validate-docs` -> passed after the lease-first
  documentation update.
- [x] `uv run python scripts/agent/runner.py generate-docs --check` -> `Generated documentation is current`.
- [x] `uv run python -m pytest tests/architecture/test_no_direct_provider_calls_outside_gateway.py -q`
  -> `4 passed` after excluding workspace temp/cache directories from source scanning.
- [x] `uv run python -m pytest tests/test_runner.py::test_postgresql_check_uses_marker_driven_backend_roots -q`
  -> passed.
- [x] `python scripts/agent/runner.py quick-check` with workspace `TEMP`/`TMP` -> 215 passed,
  268 deselected, 1 pytest-cache warning. Rerun after review fixes also passed with the same
  counts.
- [x] `uv run python scripts/agent/runner.py quick-check` with workspace `TEMP`/`TMP` -> first
  5-minute local command timed out before output; rerun exposed architecture scanner failures from
  `.tmp/uv-cache` files; after adding those skip parts, rerun passed with `219 passed, 284
  deselected, 1 warning`.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-03 | Instrument `JobRepository.claim_created()` with a test wrapper instead of replacing it. | The smoke must synchronize the contention while still exercising the real conditional update. |
| 2026-08-03 | Use separate SQLAlchemy engines and session factories per worker. | Independent PostgreSQL connections are the production concurrency contract. |
| 2026-08-03 | Keep CI wiring marker-driven. | `postgresql-check` already selects all `postgresql` tests under worker roots and quick-check excludes `slow`. |
| 2026-08-03 | Synchronize current contention before `JobLease.acquire(...)`, not inside `JobRepository.claim_created(...)`. | The rebased production handler is lease-first; only the advisory lease winner reaches the repository claim, so a two-party post-lease barrier can wait forever. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-03 | Plan created after inspecting the current worker, claim, handler, runner, migrations, and CI paths. | Add the smoke tests and docs. |
| 2026-08-03 | Added the PostgreSQL contention smoke, runtime docs, index entry, and task doc; non-DB validations pass. | Run the real PostgreSQL smoke with a configured maintenance database or rely on the required CI gate. |
| 2026-08-03 | User reported the focused PostgreSQL smoke passing with a real maintenance URL. | Run the 5x focused loop and the full `postgresql-check` gate. |
| 2026-08-03 | Added a unique `--basetemp` to `postgresql-check` after a Windows pytest temp-root collision. | Retry `postgresql-check` with the configured PostgreSQL maintenance URL. |
| 2026-08-03 | Addressed still-valid inline review comments and skipped the invalid public-loser-returns-None request because current handler reloads the job after a lost claim. | Push the follow-up commit to the PR branch. |
| 2026-08-03 | Reproduced `BrokenBarrierError` after rebasing onto the lease-first implementation, then moved the smoke barrier to a test-only `JobLease` wrapper before real advisory acquisition. | Run focused and marker-selected PostgreSQL tests. |

## Open questions

- None.

## Follow-up debt

- None expected.
