# OpenAPI

Generated-doc mirror of the minimal MVP-A API surface from `docs/product-specs/mvp-scope-source-of-truth.md`.

## Guest / Quota / Email

```text
POST /v1/identity/guest
GET  /v1/products/{product_id}/quota
POST /v1/email-captures
POST /v1/paywall-intents
```

## Scenario Runtime

```text
GET  /v1/products/{product_id}/runtime-config
POST /v1/products/{product_id}/scenarios/{scenario_id}/start
GET  /v1/scenario-sessions/{scenario_session_id}
POST /v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id}
```

## Jobs / Artifacts

```text
GET /v1/jobs/{job_id}
GET /v1/artifacts/{artifact_id}
GET /v1/results/{artifact_id}
```

## Handoff

```text
POST /v1/handoffs
GET  /v1/handoffs/{handoff_token}
POST /v1/handoffs/{handoff_token}/accept
POST /v1/handoffs/{handoff_token}/decline
```

## Events

```text
POST /v1/client-events
```

This is the minimum API required for Platform Kernel validation. Product-specific backend endpoints are not part of MVP-B unless a kernel contract is explicitly changed first.
