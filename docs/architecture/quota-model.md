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

API behavior:

- `POST /v1/products/{product_id}/scenarios/{scenario_id}/start` returns `429` with
  `quota_exhausted` when the backend rejects the start for exhausted quota;
- the rejected start is not visible as a half-created session or job to the frontend;
- missing guest identity for a quota-protected product returns frontend-safe `422`;
- unknown guest identity for a quota-protected product returns frontend-safe `404`.

Concurrency proof:

- the fast suite keeps SQLite/ASGI coverage for local regression speed;
- PostgreSQL is the production source of truth for quota consume semantics;
- `apps/platform-api/tests/test_quota_concurrency_postgresql.py` is the PostgreSQL-backed
  integration check for concurrent accepted starts and `N+1` exhaustion behavior.

The quota dimension currently supported by the config contract is:

```text
tenant_id + region + guest_id + product_id + quota_policy_id + period_key
```

`product.quota_policy_ref` resolves the quota policy from repo config. The current config contract
does not expose a scenario-level quota dimension.

The MVP-A conversion path is:

```text
guest usage -> quota exhausted -> email capture -> waitlist/paywall intent -> early access
```

Implementing guest quota only in frontend is an architecture error.
