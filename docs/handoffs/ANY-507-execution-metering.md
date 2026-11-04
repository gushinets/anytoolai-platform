# ANY-507 mechanism handoff to ANY-766

Implementation baseline: stage 1 `805110b7`, stage 2 `98c92121`, stage 3 `02639ec7`, stage 4
`6b83e7b2`. Stage-5 tests/procedure are the accompanying working-tree change; no reviewed PR/SHA
or production activation is claimed. Pin the reviewed final SHA before ANY-766 consumes this
handoff. The [execution plan](../exec-plans/active/ANY-507-implementation-plan.md#10-stage-5-checkpoint--2026-11-04)
records actual gates and limitations. [ANY-766](https://linear.app/paveldik/issue/ANY-766)
owns the consuming integration.

## Implemented Core contract

All paths below are relative to
`packages/backend/platform-core/src/anytoolai_platform_core/`:

- `quotas/models.py`: frozen `ExecutionOwner`, `PaidAllowance`, `ExecutionCandidate`,
  `ExecutionReplayIdentity`, `ExecutionReservation`, `ExecutionAcceptance`, `ConsumptionReadback`,
  `FinalExecutionResult` and `ConsumptionTransition`. Closed owner/replay/reservation states are
  Core enums. `ExecutionAcceptance` extends the frontend-safe scenario snapshot with internal
  `reservation` (absent on legacy/unmetered replay) and `is_replay`.
- `quotas/execution_service.py:ExecutionReservationService.reserve_execution(self, session,
  owner, execution, quota_input) -> ExecutionAcceptance`. Inputs are `ExecutionOwner`,
  `ExecutionCandidate` and `QuotaValidation | PaidAllowance`. Normal callers use scenario/handoff
  orchestration, which creates candidate session/job and uses the same caller-owned Session.
- `scenarios/service.py:ScenarioRuntimeService.start_session(...) -> ExecutionAcceptance`
  adds keyword-only `execution_owner=None`, `paid_allowance=None` and `idempotency_key=None` to
  the existing scoped product/scenario/frontend/input arguments. Paid starts require a key.
- `ScenarioRuntimeService.find_execution_replay(self, session, owner, replay_identity,
  request_hash) -> ExecutionAcceptance | None`. It must receive the runtime's own Session.
  A matching replay returns the original bucket and execution, including terminal failure;
  mismatched meaning raises `IdempotencyKeyConflictError`. Use
  `scenarios/service.py:compute_idempotency_request_hash` with the trusted identity; allowance ID
  and access revision do not enter that hash. Never use guest lookup with `guest_id=NULL`.
- `handoffs/service.py:HandoffService.accept(self, token, command, *, execution_owner=None,
  paid_allowance=None) -> HandoffAccepted`. Its runtime calls `create_linked_session` with those
  same trusted arguments. Namespace `handoff` uses the stable runtime handoff ID. Accepted replay
  checks owner before returning original linkage, even after token TTL. Deferred acceptance has
  no job or reservation; temporary occupied capacity leaves consent/token retryable.
- `quotas/finalization.py:finalize_success(session, job_id, final_result, *, config_registry)
  -> ConsumptionTransition` and `release_execution(session, job_id) -> ConsumptionTransition`.
  `FinalExecutionResult(job, artifact)` retains the immutable validated final candidate and ID.
- `quotas/readback.py:read_consumption(session, owner, bucket: str)
  -> ConsumptionReadback | None`. **`bucket` is the original usage-row ID, not allowance ID.**
  Resolve paid IDs through `quotas/execution_repository.py:PaidAllowanceUsageRepository`.
  Owner/bucket records and aware `read_at` accompany the seven counter fields. A read creates
  nothing; unknown/foreign means `None`, storage errors propagate.

ANY-766 supplies deployment-derived scope and an authenticated canonical Portal UUID owner.
Body/source `user_id` grants no authority. Core checks owner/scope/product, registry metric/unit
and strict integer Q in `0…2^53−1`; first acceptance freezes owner/product/metric/unit/quantity
for the scoped allowance ID. A different owner or changed tuple conflicts without changing usage.
Same ID retains history; a new ID gets a separate bucket. ANY-766 selects the scenario's expected
metric and verifies current grant/freshness; a registry enabled flag cannot revoke accepted usage.

## Transactions and integration attachment

The caller owns outer commit/rollback. Acceptance's savepoint covers session, job, original bucket,
reservation, reserved increment and events. Concurrent replay losers discard all candidate writes.
Admission uses `FOR NO KEY UPDATE`; terminal writers lock `job → scenario → reservation → bucket`.
No HTTP/provider I/O belongs under admission locks.

ANY-766 authenticates and fetches snapshots before admission, attempts owner replay before
mandatory refresh, locks its scoped user/floor, repeats replay, reserves for a new execution,
then performs its final locked revision/time check **after waiting for admission locks**. Denial
must roll back the whole acceptance. The existing caller-rejection tests prove this mechanism;
actual AccessSnapshot expiry/floor/cache races belong to ANY-766 integration acceptance.

Canonical publication, succeeded job, allowed running-scenario completion, reserved decrement,
used increment, consumed reservation and events share one transaction. The full Result API
validation boundary is reused. Normal runner success and rollback/unknown-commit recovery call
the same finalizer; immutable success recovery is registered before finalization. Losing or
repeated terminal decisions cannot publish after release, charge twice, overwrite an independently
terminal scenario or report a second exhaustion edge. Legacy jobs are never charged again.

ANY-766 adds an explicit transactional exhaustion-outbox write from the returned
`ConsumptionTransition.became_exhausted` in this shared success orchestration **before the same
outer commit**, covering both normal and recovery paths. No second debit path or callback framework
is supplied here. `applied=False` means an earlier decision, with no new transition/exhaustion edge.
Failure/cancellation/poison/orphan paths release the original reserve; JobLease owns liveness.
Do not release on elapsed time or automatically requeue an unknown outcome.

## Readback fixtures and deployment

[Counter fixtures](../../tests/fixtures/execution_metering/readback.json) are internal facts for a
typed paid TEST-ONLY allowance with Q=1, unit `run`; they are not paid HTTP DTOs or metric approval.
`test_any766_handoff_readback_fixtures_match_paid_storage` exercises them against real PostgreSQL:
unknown bucket → unobserved, active reserve → busy, canonical success → exhausted.
Owner/bucket/read time are intentionally supplied by the actual read rather than synthetic wire IDs.

`used = legacy_used + successful_used`; `remaining = max(Q-used, 0)`;
`available = max(Q-used-reserved, 0)`. Paid legacy contribution is zero. Guest historical usage is
retained verbatim, never refunded or relabelled successful. Busy is retryable without a paywall;
exhaustion is final used reaching Q. New cycles never move old jobs/replay to a different bucket.

Migration head is `0017`, following storage preparation at `0016`. It reconciles guest historical
usage against consumed reservations without changing total usage, active reserves or results. Use the
[quiesce/backup/migrate/rollback procedure](../../infra/deployment/execution-metering-cutover.md).
Storage preparation can preserve nonterminal history; **application cutover requires a successful
full queue drain**. After new reservations exist, old-code rollback requires consistent backup
restore. ANY-766 owns paid HTTP, access ingestion/floor/cache/invalidation, usage/exhaustion delivery,
real Portal integration and joint acceptance; Portal predecessor readiness does not gate this
independent mechanism evidence.

## Reproduce verification

Set `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` to an isolated PostgreSQL maintenance database whose
test role can create/drop disposable databases; never point it at production. Use the repository's
managed Python environment (bootstrap with `quick-check --bootstrap-only` if needed):

```bash
python scripts/agent/runner.py doctor
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py postgresql-check
python scripts/agent/runner.py full-check
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py generate-docs --check
```

The PostgreSQL gate discovers all marked tests, including `test_execution_cutover.py` and the
readback fixture test. The stage-5 run uses PostgreSQL 18.6 and Python 3.12.13. Its actual pass/fail
counts, canonical atoms/Compose evidence and activation blockers live in the plan checkpoint.
`atoms-proof` additionally requires isolated API/worker/PostgreSQL with deterministic providers;
use the existing credential-free Compose setup, then the canonical runner command. Keep its scope
separate from live-provider or Portal acceptance.
