# Quota Model

MVP-A uses guest quota instead of billing.

## A13 status

A13 is **backend-complete**. The backend owns guest identity persistence, quota policy resolution,
quota state, quota consumption, standardized API errors, and quota events. CE-kit's shared
`getQuota()` and `startScenario()` HTTP clients in the MVP-A2 A15 slice (ANY-8/ANY-170/ANY-171)
are real, propagate the opaque guest id, and handle `429 quota_exhausted`.

Rules:

- quota enforcement is backend-owned;
- check quota before accepting a scenario start;
- resolve quota scope from the repo-configured quota policy dimension;
- consume quota on accepted scenario start, in the same transaction that creates the started
  scenario session and linked created job;
- do not consume quota on frontend clicks or intent;
- failed workflow execution after an accepted start does not refund quota in A13;
- quota exhausted returns standardized state;
- quota state is independent from provider calls, transport retries, PydanticAI validation retries,
  LiteLLM telemetry, and provider usage/cost accounting;
- email capture and paywall intent are recorded;
- (ANY-150) a scenario start submitted with the same `Idempotency-Key` header, tenant, region,
  product, scenario, and `guest_id` as an already-accepted start replays that start's snapshot and
  does not consume quota again, even under concurrent duplicate submission.

For A13, an accepted scenario start means the A12 queue-and-return start flow has passed product,
scenario, frontend, input, and workflow validation and will commit:

```text
scenario_sessions row with status=started and checkpoint=processing (insert-or-select on
  Idempotency-Key, see ANY-150 below)
-> quota consumed (only when this call actually inserted the row -- a replay never reaches this step)
-> linked jobs row with status=created
```

If quota is exhausted, the whole request transaction rolls back: any `scenario_sessions` row this
specific call inserted (an ANY-150 keyed insert-or-select can insert before quota runs) disappears
with it, and the API returns `quota_exhausted`. No scenario session or job is ever left committed for
a rejected start.

Immediate handoff acceptance and the ordinary `/start` router share the same rollback-and-recover
shape for quota exhaustion. A rejected start must leave the quota usage dimension and the
`quota.checked` / `quota.exhausted` audit pair durable, return safe HTTP 429, and leave no target
session or job committed. Neither router commits its transaction on `quota_exhausted` -- both let the
error propagate out of `transaction_boundary`, which rolls the transaction back. The quota service
therefore registers an exhaustion-only rollback recovery callback before raising: after rollback it
re-ensures the same usage dimension and re-emits the same checked/exhausted pair in an independent
transaction (`storage/transactions.py`'s `register_rollback_recovery_callback`).

For handoffs, the accepted claim establishes quota-rejection ownership when target quota evaluation
discovers exhaustion under the handoff lifecycle advisory lock. That PostgreSQL session-level lock
survives the accepting transaction rollback and is released only after recovery callbacks complete.
The handoff quota callback is critical: the owning accept request cannot return
`429 quota_exhausted` if recovery fails to persist the durable `failed` state and audit chain. One
conditional update claims recovery and finalizes `failed` with safe `quota_exhausted`, then emits the
quota pair and `handoff.failed` before commit. A repeated recovery that finds an existing audit pair
returns without duplicating it; a lost terminal CAS without the audit pair is treated as recovery
failure, not a valid 429. Decline and expiry can win only before this ownership point; afterward they
wait and observe `failed`. Recovery never consumes quota, creates a target session/job, runs a
workflow, creates a target artifact, or makes a provider call. The router's later failure call
remains idempotent and does not duplicate the handoff event.

The fast SQLite test suite has a known ceiling here: many concurrent ordinary `/start` losing
requests each spawn an independent non-critical recovery transaction against the same usage row, and
SQLite's ATTACH-schema harness can drop some of those under write contention
(`sqlite3.OperationalError: database is locked`) without changing the primary response path. That
best-effort tolerance applies only to non-critical ordinary `/start` recovery. Immediate handoff
quota recovery is critical: recovery failure prevents returning `429 quota_exhausted`. SQLite does
not provide valid handoff race behavior for advisory-lock ownership, decline/expiry serialization,
or recovery ordering. Production-safe concurrency evidence for handoff quota rejection comes from
`test_quota_concurrency_postgresql.py`, not the SQLite suite.

API behavior:

- `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` returns `429` with
  `quota_exhausted` when the backend rejects the start for exhausted quota;
- the rejected start is not visible as a half-created session or job to the frontend;
- missing guest identity for a quota-protected product returns frontend-safe `422`;
- unknown guest identity for a quota-protected product returns frontend-safe `404`;
- (ANY-150) the same request replayed with the same `Idempotency-Key` returns `200` with the
  original start's snapshot and does not touch quota; the same key reused with a different request
  returns `409 idempotency_key_conflict` before quota is touched -- see
  `docs/architecture/scenario-session-model.md`.
- `GET /v1/products/{product_id}/quota?guest_id={guest_id}` returns product-wide quota state for
  product-dimension policies; scenario-dimension policies require `scenario_id` so the backend can
  identify the counter.

Concurrency proof:

- PostgreSQL is the production source of truth for quota consume semantics;
- PostgreSQL-backed tests are required for quota concurrency, `ON CONFLICT`, row-lock, and
  transaction-isolation proof;
- `apps/platform-api/tests/test_quota_concurrency_postgresql.py` is the PostgreSQL-backed
  integration check for concurrent accepted starts, `N+1` exhaustion behavior, and (ANY-150)
  concurrent duplicate submission under one `Idempotency-Key`.

Quota policy config owns the quota dimension. Supported values:

- `product`: one product-wide quota counter shared by all scenarios under the product;
- `scenario`: one quota counter per `guest_id + product_id + scenario_id`.

The persisted quota uniqueness path is:

```text
tenant_id + region + guest_id + product_id + quota_policy_id + quota_dimension + dimension_key + period_key
```

For product-wide policies, `dimension_key = product_id` and `scenario_id` is not persisted on the
usage row. For scenario-specific policies, `dimension_key = scenario_id` and `scenario_id` is
persisted on the usage row. Quota events include `quota_dimension` and `quota_dimension_key`; for
scenario-specific policies they also include `quota_scenario_id`.

`product.quota_policy_ref` resolves the quota policy from repo config.

The MVP-A conversion path is:

```text
guest usage -> quota exhausted -> email capture -> waitlist/paywall intent -> early access
```

Implementing guest quota only in frontend is an architecture error.

## Periods and windows

Quota periods are `lifetime` and the fixed UTC calendar windows `calendar_day` (UTC day),
`calendar_week` (ISO week, Monday-Sunday) and `calendar_month` (UTC month). Rolling windows are not
supported. `resolve_quota_period(period, now)` computes `period_key` (`lifetime`, `day:2026-09-30`,
`week:2020-W53` using the ISO week-year, `month:2026-09`), `starts_at` and `ends_at` together from one
UTC instant; naive datetimes are rejected.

- The window is resolved once per operation: `validate_accepted_start` stores it in `QuotaValidation`,
  and consume and rollback recovery reuse it; `check_quota` resolves once per request. Only these two
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
