# Execution Plan: ANY-147 Worker Lease Recovery

## Status

- State: completed
- Owner: agent
- Created: 2026-08-03
- Last updated: 2026-08-13
- Review date: 2026-08-13
- Next action: none; repository implementation and validation merged in PR #48. External metadata
  reminders are not repository completion criteria.
- Blocker: none

## Goal

A `running` job whose worker crashes, is OOM-killed, or is rolling-restarted (`docker stop` /
`compose down` / k8s eviction sending `SIGTERM`) must not stay `running` forever. It must be
detected and terminalized without relying on a wall-clock TTL, since jobs can legitimately run
for seconds or for a full day.

## Scope

### In scope

- Postgres session-scoped advisory lock as a per-job lease, held on a dedicated connection for
  the lifetime of `handle()`.
- A reconciliation sweep that non-blockingly probes `running` jobs' locks and terminalizes
  orphans as `failed` / `worker_lease_lost`, no auto-retry.
- Real `SIGTERM` graceful drain in `main.py` (finish in-flight job, take no more), gated for
  platforms without `add_signal_handler` support (Windows).
- Resource cleanup (`dispose()`) for the dedicated lease engine, both in the production
  shutdown path and in the Postgres test suite.
- Focused entrypoint coverage for the SIGTERM-registration gating.

### Out of scope

- Wall-clock TTL/heartbeat lease (rejected design — see Decision log).
- `claimed_by` observability column and its migration (explicitly excluded from MVP by the
  team lead).
- Fencing tokens for the residual race described below (accepted, logged, not auto-fixed).
- Auto-retry of orphaned jobs.

## Relevant docs

- `docs/architecture/job-lifecycle.md`
- `docs/handoffs/worker-cancellation-recovery.md`

## Contracts touched

- API: none
- DB: none (no new columns/migrations — liveness is derived from the live Postgres session
  state, not a stored timestamp)
- Config: none
- Events: `worker.orphaned_jobs_terminated`, `worker.job_completed_after_lease_lost` (new log
  events); existing `workflow.failed` path reused for orphan terminalization
- Frontend: none

## Implementation steps

- [x] `lease.py`: `JobLease` protocol (`acquire`/`release`/`probe_orphaned`/
  `probe_orphaned_batch`/`dispose`), `AdvisoryJobLease` (Postgres, 64-bit key derived from
  `job_id`, dedicated `AUTOCOMMIT` connection per held lock), `NullJobLease` (no-op on
  SQLite), `build_job_lease(engine)` gated on `engine.dialect.name`.
- [x] Claim flow: lock acquired before the `created -> running` conditional claim commits;
  `pg_try_advisory_lock` returning false means another worker already owns the row (skip, not
  an error).
- [x] `reconciliation.py`: `OrphanedRunningJobReconciler.reconcile_once()` — keyset-cursor
  pagination over `running` jobs (`(started_at, id)`, same-pass wrap-around) so a fleet with
  more in-flight jobs than the sweep limit doesn't starve out later rows; batched
  `probe_orphaned_batch` (one connection per sweep pass, not one per job).
- [x] `handlers/run_workflow.py`: lease acquire/release wired around `handle()`, covering
  transaction-commit failures (not just the transaction body) via a `nonlocal` flag so a
  failure there can't leak the lease; `terminate_orphaned_job(job_id)` reuses the existing
  `_persist_running_failure` core; residual-race log added (see Decision log).
- [x] `worker.py` / `main.py`: `Worker.request_shutdown()`/`run_forever()` drains on
  `SIGTERM` only (`SIGINT` unchanged); sweep runs once before the loop and on every idle
  iteration; `_register_sigterm_handler()` catches `NotImplementedError` on platforms without
  signal-handler support and is called inside the same `try/finally` that disposes the
  worker, so a registration failure can't leak the built worker's resources.
- [x] `composition.py` / `transactions.py`: `engine_from_session_factory()` recovers the raw
  `Engine` from a `session_factory` so the lease can open its own connections; `build_worker()`
  public signature unchanged.
- [x] Postgres integration tests: `test_worker_lease_recovery_postgresql.py` — orphan recovery
  after a dead lease connection, positive control (live lease is never touched regardless of
  elapsed time), real-subprocess `SIGTERM` drain.
- [x] Unit tests in `test_worker_boot.py`: fake `JobLease`/reconciler coverage for
  acquire/release ordering, skip-on-lock-miss, sweep termination, drain-then-stop.
- [x] Focused entrypoint coverage in `test_main.py`: `_register_sigterm_handler` swallows
  `NotImplementedError`, and `run()` still disposes the worker when registration fails or
  `run_forever()` raises.
- [x] `docs/handoffs/worker-cancellation-recovery.md`: replaced the stale "no lease or other
  recovery mechanism" line with a description of the advisory-lock lease and sweep.
- [x] `infra/compose/docker-compose.yml`: `stop_grace_period` on `platform-worker` so Compose
  gives the graceful-drain path a realistic window before `SIGKILL`.
- [x] Reconcile repository completion after PR #48 merged; PR-description and Linear wording were
      non-repo reminders and do not keep the implementation plan active.

## Validation

- [x] `python scripts/agent/runner.py quick-check`
- [x] `python scripts/agent/runner.py validate-configs`
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `uv run pytest -m postgresql` across `apps/platform-worker/tests` and
  `packages/backend/platform-core/tests` against a real `postgres:16`
- [x] `python scripts/agent/runner.py full-check` (last run by the user directly, green)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-03 | Rejected a TTL/heartbeat lease column in favor of a Postgres advisory lock. | Any fixed TTL either kills a legitimately long-running job or is too slow to catch a dead worker; correctness must not depend on guessing job duration. |
| 2026-08-03 | Lock is acquired **before** the `created -> running` claim commits, not after. | Closes a gap between claim and lease-acquisition where a job could be `running` with no lock held yet, defeating the sweep. `pg_try_advisory_lock=false` in this position means "another worker already has it" — skip, not an error. |
| 2026-08-03 | Orphaned jobs terminalize to `failed`/`worker_lease_lost`, no auto-retry. | Side effects inside workflow/provider calls are not guaranteed idempotent — same principle already used for cooperative cancellation (`running -> canceled`, not re-queue). |
| 2026-08-03 | Accepted a known residual race: if the lease connection alone drops (e.g. a Postgres restart) while the rest of the worker process survives and finishes the job, the sweep may have already marked it `failed` by the time `mark_succeeded` runs, and the real success is lost (logged via `worker.job_completed_after_lease_lost`, not auto-fixed). | This is a much narrower window than a full worker crash, and any lease scheme has an analogous edge; a fencing-token fix is out of scope for this pass. |
| 2026-08-03 | `claimed_by` observability column dropped from scope. | Team lead: not needed for MVP correctness; can be added later purely for ops visibility without touching the lease/reconciliation design. |
| 2026-08-03 | Gated `add_signal_handler` registration behind a `try/except NotImplementedError`, moved inside the worker's cleanup `try/finally`. | Team-lead review: Windows' event loop does not implement `add_signal_handler` at all, and the original placement registered the handler before the `try/finally`, so a registration failure leaked the just-built worker's resources. |
| 2026-08-03 | `run_forever()`'s idle-backoff condition also checks `result.status is JobStatus.created`, not just `result is None`. | Second-pass review: `next_message()` has no `FOR UPDATE`, so two workers can pick the same `created` candidate; the loser's `_claim()` returns that job's still-`created` record (not `None`) once it loses the advisory-lock race, and the old `if result is None:` check let that fall into the "made progress" branch, spinning the loop hot with no backoff. |
| 2026-08-03 | Confirmed via standalone repro (outside pytest) that `uv run` 0.11.19 (the Dockerfile-pinned version) correctly forwards `SIGTERM` to its Python child in every case tested, including through the real `anytoolai-platform-worker` console-script entry point. | Second-pass review flagged this as unverified since the existing subprocess test bypasses `uv run` entirely; a 2s test warm-up before sending the signal looked like a forwarding failure (exit 143) but was actually the Python process not yet reaching its own `add_signal_handler()` call, not a `uv` bug. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-03 | Implemented the advisory-lock lease, reconciliation sweep, SIGTERM drain, and full Postgres/unit test coverage; ran a self-review pass and fixed a lease leak on transaction-commit failure, a connection leak in `acquire()` on exception, added `dispose()` resource cleanup, batched orphan probing, and keyset-cursor sweep pagination. | Address team-lead review. |
| 2026-08-03 | Team-lead review returned two merge-blocking (P2) findings — Windows signal-handler crash/resource leak in `main.py`, and this exec plan missing entirely (repo policy requires one under `docs/exec-plans/active/`, and code comments pointed at the untracked `plans/ANY-147.md`) — plus two P3 hardening items (Compose `stop_grace_period`, stale cancellation-recovery handoff doc). | Fix `main.py`'s signal-registration gating with focused tests, add this plan, retarget the two dangling comment references, add `stop_grace_period`, and update the handoff doc. |
| 2026-08-03 | Fixed all four items from the team lead's review pass above; second review pass found a real hot-loop bug (`_claim()` losing a claim race returns the still-`created` `JobRecord`, not `None`, so `run_forever()`'s `if result is None:` backoff branch was skipped entirely) plus a genuine test-coverage gap (the SIGTERM subprocess test bypassed `uv run`, the actual PID-1 command in production) and a resource-hygiene gap (9 `build_worker()` call sites across three Postgres-marked test files never called `dispose()`). | Fix the hot-loop bug in `worker.py`, add a real `uv run`-wrapped SIGTERM test, add `dispose()` at the 9 sites, and add a defensive (currently unreachable) guard against a silent double-`acquire()` in `lease.py`. |
| 2026-08-03 | Fixed the hot-loop bug (`run_forever()` now backs off on `result.status is JobStatus.created` too, with a regression test). Added `test_real_console_entrypoint_under_uv_run_exits_cleanly_on_sigterm`, which launches the literal `uv run --project apps/platform-worker --no-sync anytoolai-platform-worker` command against a real provisioned Postgres. First attempt (2s warm-up before SIGTERM) failed with exit 143 -- empirically confirmed via standalone repro scripts that `uv run` (0.11.19) *does* correctly forward SIGTERM to its Python child in every case (this was never a `uv` bug); the failure was that `main.py`'s `_register_sigterm_handler()` call happens only after `WorkerSettings.from_env()`/`build_worker()` complete, and 2s wasn't reliably enough for that config/engine-construction work to finish before the signal arrived, so Python's default SIGTERM disposition (immediate termination) fired first. Fixed by giving the test 6s of warm-up. Added `dispose()` at all 9 previously-missing call sites (7 in `test_worker_boot.py`, 1 each in `test_handoffs_api.py`/`test_scenario_runtime_api.py`). Added a defensive raise in `AdvisoryJobLease.acquire()` for a same-job double-acquire (not reachable today, cheap to guard). Validated against a real `postgres:16` via Docker Compose: full `-m postgresql` run (`packages/backend/platform-core`, `platform-actions`, `apps/platform-api`, `apps/platform-worker`) and `quick-check`, both clean. | None outstanding from this round. |

## Open questions

None repo-side.

## Follow-up debt

- Fencing-token fix for the residual lease-connection-drops-but-worker-survives race
  (currently logged, not auto-corrected).
- `claimed_by` ops-observability column, if wanted later — explicitly out of MVP scope.
