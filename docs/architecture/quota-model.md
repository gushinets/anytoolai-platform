# Quota Model

MVP-A uses guest quota instead of billing.

## A13 status

A13 is **backend-complete, integration pending**. The backend owns guest identity persistence,
quota policy resolution, quota state, quota consumption, standardized API errors, and quota events.
CE-kit currently has real local guest-id creation/persistence only; the real shared CE-kit
`getQuota()` and `startScenario()` HTTP clients are deferred to A16.

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
- email capture and paywall intent are recorded.

For A13, an accepted scenario start means the A12 queue-and-return start flow has passed product,
scenario, frontend, input, and workflow validation and will commit:

```text
quota consumed
-> scenario_sessions row with status=started and checkpoint=processing
-> linked jobs row with status=created
```

If quota is exhausted, no scenario session or job is created and the API returns
`quota_exhausted`.

Immediate handoff acceptance uses the same quota contract. A rejected target start must leave the
quota usage dimension and the `quota.checked` / `quota.exhausted` audit pair durable, return safe
HTTP 429, and create no target session or job. Because handoff acceptance has already made a
conditional accept claim inside its transaction, it cannot commit that transaction the way the
ordinary scenario-start router does. The quota service therefore registers an exhaustion-only
rollback recovery callback: after rollback it re-ensures the same usage dimension and re-emits the
same checked/exhausted pair in an independent transaction. It never consumes quota during recovery.
The handoff failure transaction then records `failed` with safe `quota_exhausted`.

API behavior:

- `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` returns `429` with
  `quota_exhausted` when the backend rejects the start for exhausted quota;
- the rejected start is not visible as a half-created session or job to the frontend;
- missing guest identity for a quota-protected product returns frontend-safe `422`;
- unknown guest identity for a quota-protected product returns frontend-safe `404`.
- `GET /v1/products/{product_id}/quota?guest_id={guest_id}` returns product-wide quota state for
  product-dimension policies; scenario-dimension policies require `scenario_id` so the backend can
  identify the counter.

Concurrency proof:

- the fast suite keeps SQLite/ASGI coverage for local regression speed;
- PostgreSQL is the production source of truth for quota consume semantics;
- `apps/platform-api/tests/test_quota_concurrency_postgresql.py` is the PostgreSQL-backed
  integration check for concurrent accepted starts and `N+1` exhaustion behavior.

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
