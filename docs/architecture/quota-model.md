# Quota Model

MVP-A uses guest quota instead of billing.

## A13 status

A13 is **backend-complete**. The backend owns guest identity persistence, quota policy resolution,
quota state, quota consumption, standardized API errors, and quota events. CE-kit's shared
`getQuota()` and `startScenario()` HTTP clients (A15, ANY-8/ANY-170/ANY-171) are real, propagate
the opaque guest id, and handle `429 quota_exhausted`.

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

Immediate handoff acceptance and the ordinary `/start` router now share the same rollback-and-recover
contract for quota exhaustion. A rejected start must leave the quota usage dimension and the
`quota.checked` / `quota.exhausted` audit pair durable, return safe HTTP 429, and leave no target
session or job committed. Neither router commits its transaction on `quota_exhausted` -- both let the
error propagate out of `transaction_boundary`, which rolls the transaction back. The quota service
therefore registers an exhaustion-only rollback recovery callback before raising: after rollback it
re-ensures the same usage dimension and re-emits the same checked/exhausted pair in an independent
transaction (`storage/transactions.py`'s `register_rollback_recovery_callback`). For handoffs, that
independent transaction also uses one conditional update to claim recovery and finalize `failed` with
safe `quota_exhausted`, then emits the quota pair and `handoff.failed` before commit; for an ordinary
scenario start there is no handoff row to finalize, so the callback only re-ensures the usage
dimension and re-emits the checked/exhausted pair. A losing concurrent recovery performs no writes.
There is no committed pre-terminal reservation window, so neither process interruption nor a
competing transition can leave a stuck or mixed state. Recovery never consumes quota. The router's
later failure call remains idempotent and does not duplicate the handoff event.

The fast SQLite test suite has a known ceiling here: many concurrent losing requests each spawn an
independent recovery transaction against the same usage row, and SQLite's ATTACH-schema harness can
drop some of those under write contention (`sqlite3.OperationalError: database is locked`) even
though the recovery callback's own failure-handling is designed to tolerate exactly this (a failing
callback never masks the real response -- see `transaction_boundary`). The financial invariant (exact
consumed-quota count, exact session/job row count) is never affected, only the secondary
`quota.exhausted` audit-event count under heavy concurrency; `test_quota_concurrency_stress.py`
documents this bound. Production-safe concurrency evidence for this comes from
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
