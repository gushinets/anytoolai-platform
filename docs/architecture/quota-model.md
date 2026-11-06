# Quota Model

MVP-A exposes guest quota. ANY-507 also provides typed paid metering internally; paid
HTTP authentication, AccessSnapshot, scenario metric selection and interservice usage remain
ANY-766 responsibilities. See the [shared contract and execution plan](../exec-plans/completed/ANY-507-implementation-plan.md).

## Admission and replay

Ordinary start and immediate handoff share `ExecutionReservationService.reserve_execution`.
The caller owns the SQLAlchemy Session and outer commit. One candidate savepoint contains the
session, created job, original bucket reservation, reserved increment and admission events.
Acceptance requires `used_count + reserved_count < quantity`; it does not debit used quota.
Deferred handoff creates no job or reservation.

Guest buckets use the configured product/scenario dimension and UTC period. Paid buckets use a
scoped allowance ID, immutable owner/product/metric/unit/quantity, and strict integer quantity in
`0…2^53−1`. A new allowance ID creates a separate bucket even when its other terms match. A
historical body/source-session `user_id` is never trusted paid authority. Before first binding,
Core verifies the trusted owner/scope, requested product and session/job/bucket links, product
membership of the metric, and registry unit. One allowance ID within tenant/region binds to one
owner; a changed tuple conflicts without changing usage. ANY-766 selects the scenario's expected
metric and checks grant/freshness; a registry commercial `enabled` flag alone is not paid authority.

`ScenarioRuntimeService.find_execution_replay` is owner-scoped and returns the original session,
job and reservation with `is_replay=True`, without reserving again. Paid starts require a key;
replay namespace is `start` or `handoff` (stable runtime handoff ID). Request hashes exclude
allowance ID/access revision. Legacy guest replay synthesizes no historical reservation. Paid
replay never uses the guest `guest_id=NULL` path. Concurrent losers roll back all candidate writes
before reading the winner.

PostgreSQL admission locks use `FOR NO KEY UPDATE`, avoiding an upgrade deadlock with reservation
FK `KEY SHARE` locks. Locks remain held through the caller's final admission check. Caller rejection
rolls back the complete candidate; it cannot recreate acceptance through rollback recovery.

## Finalization and recovery

`quotas/finalization.py` provides `finalize_success(session, job_id, FinalExecutionResult,
config_registry=...)` and `release_execution(session, job_id)`. Neither commits or rolls back the
caller. Existing-row lock order is `job -> scenario -> reservation -> original bucket`.

The shared Result API availability boundary (`results/validation.py`) validates canonical linkage,
workflow/schema versions, normalized output and recursively forbidden fields. The runner retains
one deep-copied final candidate and artifact ID and registers success recovery before finalization.
An artifact row or successful provider call alone cannot consume quota.

New success requires a running job, active reservation and running scenario. Accessible canonical
result publication, succeeded job, scenario completion, `reserved−1`, `used+1`, consumed reservation
and events commit together. Failure/cancellation releases without debit; partial/debug artifacts do
not qualify as success. A competing terminal scenario wins without publication, debit or restoration
to running. Consumed and released decisions cannot change into each other; repeated terminal calls
return `applied=False` and emit no new transition.

Normal execution and rollback/unknown-commit recovery use this same finalizer. Recovery reads durable
terminal state first; metered final results have no independent artifact-only recovery commit.
Action/provider/debug recovery and causal event backfill remain intact. Preclaim cancellation,
worker cancellation, disabled/poison failure and orphan terminalization share release. JobLease
still determines liveness: elapsed time never releases a live execution or automatically requeues
an unknown outcome. Original guest windows and paid buckets remain attached across calendar/cycle
changes. Legacy jobs retain their earlier debit history and are never charged again.

`ConsumptionTransition(applied, reservation, became_exhausted)` exposes an exhaustion edge only on
an applied consumption. ANY-766 attaches its explicit outbox write before the same outer commit,
including recovery; this stage introduces no outbox or Portal wire.

## Readback and guest HTTP

`quotas/readback.py:read_consumption(session, owner, bucket)` takes an original usage-row ID and
returns `ConsumptionReadback` from one query without writes or locks. Its typed bucket carries the
original guest dimension or paid allowance identity. Unknown/foreign buckets return `None`
(`unobserved`); storage errors propagate. Paid callers resolve allowance IDs through the paid
repository. Reads never create an allowance. The result carries `owner`, the typed original
`bucket`, `quantity`, `used`, `successful_used`, `legacy_used`, `reserved`, `remaining`, `available`
and aware UTC `read_at`. Paid `legacy_used` is always zero.

All readback counters derive from one row snapshot:

```text
used = legacy_used + successful_used
remaining = max(quantity - used, 0)
available = max(quantity - used - reserved, 0)
exhausted = remaining == 0
```

`GET /v1/products/{product_id}/quota?guest_id=...` preserves the guest identity/policy/dimension,
unit/period/limit/used/remaining/exhausted/resets fields. It adds `successful_used_count`,
`legacy_used_count`, `reserved_count`, `available_count` and timezone-aware `read_at`. Historical
used quota is preserved, never refunded or relabelled as successful results. Product policies share
one product counter; scenario policies require `scenario_id`. Empty guest state derives from policy
without creating a usage row. Guest HTTP uses the current configured policy `limit_count`, even
when it differs from the stored guest limit; GET does not synchronize that stored limit. Used,
legacy and reserved counts come from one row, and remaining/available use the configured limit.
HTTP exposes no bucket/reservation/owner internals, prompts or billing state. The paid HTTP branch
and interservice endpoints belong to ANY-766.

With Q=1 and one reservation: used=0, reserved=1, remaining=1, available=0, exhausted=false.
`429 quota_capacity_reserved` is a temporary admission rejection; no candidate execution survives,
no exhaustion/paywall state opens, and handoff consent remains retryable. `429 quota_exhausted`
means final used quota reached quantity. Missing guest identity returns 422; unknown guest returns
404. Accepted keyed replay returns the original execution's current snapshot; changed input returns
409 `idempotency_key_conflict` without reserving.

## Events and clients

- `quota.checked`: quota evaluation.
- `quota.reserved`: actual admission reservation, in the acceptance transaction.
- `quota.consumed`: accessible successful result, in the publication/debit transaction.
- `quota.released`: actual failure/cancellation release, in the terminal transaction.
- `quota.capacity_reserved`: rejected admission while reserves occupy capacity.
- `quota.exhausted`: rejected admission after used quota reached quantity.

Transition events carry owner kind/ID, tenant/region, product/scenario/frontend, session/job, original
bucket and applicable handoff/result dimensions. Paid events include allowance/metric/unit; guest
events include policy/dimension/window. Replay and losing terminal decisions emit no duplicate
reserve/consume/release. Denial audit recovery never recreates session/job/reservation or consumes.
Capacity audit retains the observed counter snapshot across rollback. Exhaustion recovery preserves
the checked/exhausted audit pair. Immediate handoff exhaustion also durably marks failed under its
lifecycle lock; busy capacity leaves the handoff actionable. Handoff audit recovery is critical.

CE-kit parses the expanded DTO and classifies the two 429 codes separately. Shared web refreshes
quota after acceptance, terminal success/release and explicit new-task reads. Temporary busy retry
reuses the prepared start/key or original handoff token and guest. A result-fetch retry only reads
the same result. Advisory quota never replaces an active/completed result. Leaving the page does
not cancel execution: an eventual successful result still consumes its reservation.

## Verification and activation boundary

PostgreSQL suites cover atomic acceptance/finalization/recovery, terminal arbitration and bucket
history; `test_execution_readback_postgresql.py` proves readback, guest HTTP refresh, historical
contribution, scoped unknown/error behavior and transition dimensions. Frontend parser/component
checks cover busy versus exhausted and retry identity. Stage 5 provides the
[quiesce/cutover/rollback procedure](../../infra/deployment/execution-metering-cutover.md) and
[ANY-766 mechanism handoff](../handoffs/ANY-507-execution-metering.md). Actual gate results and
activation limits remain in the plan's stage-5 checkpoint. Never mix old/new admission or workers.

## Periods and windows

Quota periods are `lifetime` and the fixed UTC calendar windows `calendar_day` (UTC day),
`calendar_week` (ISO week, Monday-Sunday) and `calendar_month` (UTC month). Rolling windows are not
supported. `resolve_quota_period(period, now)` computes `period_key` (`lifetime`, `day:2026-09-30`,
`week:2020-W53` using the ISO week-year, `month:2026-09`), `starts_at` and `ends_at` together from one
UTC instant; naive datetimes are rejected.

- The window is resolved once per operation: `validate_accepted_start` stores it in `QuotaValidation`,
  and reservation and rollback recovery reuse it; `check_quota` resolves once per request. Only these two
  entry points read the injectable quota clock.
- A new window selects or creates a new `guest_quota_usage` row through the existing `period_key`
  unique dimension. Nothing is reset and no job or migration is needed.
- `QuotaState.resets_at` (the window's `ends_at`, `null` for `lifetime`) is exposed as `resets_at` on
  `GET /v1/products/{product_id}/quota`. `period_key`, the runtime quota summary and quota events do
  not carry it.
- Changing a policy's period while keeping its `quota_policy_id` gives guests a fresh window;
  switching back to `lifetime` revives the old lifetime row. Historical period rows are not cleaned up.

### Rollout order for a new period

A client that does not know a period value fails `parseRuntimeConfig` and the product does not open.
Before a product YAML switches from `lifetime` to a calendar period: (1) Core/SDK/OpenAPI support the
value, (2) CE-kit and all supported web/extension clients understand it, (3) those clients are
deployed, (4) only then switch the YAML. Never switch a product before every supported client version
understands the new `QuotaPeriod` values.
