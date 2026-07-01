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

### `GET /v1/products/{product_id}/runtime-config`

Returns frontend-safe runtime metadata for a configured product.

Safe response fields:

- `product_id`
- `frontend_ids`
- `frontends[].frontend_id`, `frontends[].type`, `frontends[].enabled`
- `scenario_ids`
- `scenarios[].scenario_id`, `scenarios[].version`
- `scenarios[].allowed_next_actions`
- `scenarios[].input_renderer_hint`
- `scenarios[].output_renderer_hint`
- `quota_summary`
- `allowed_ui_capabilities`

The response must not include prompt text, system prompts, prompt refs, provider policy IDs,
provider names, model names, internal file paths, storage locations, or secrets.

Example `200` response:

```json
{
  "product_id": "kernel_demo",
  "frontend_ids": ["kernel_demo_ce", "web_mirror"],
  "frontends": [
    {"frontend_id": "kernel_demo_ce", "type": "chrome_extension", "enabled": true},
    {"frontend_id": "web_mirror", "type": "web", "enabled": true}
  ],
  "scenario_ids": [
    "kernel_demo.single_action_smoke_v1",
    "kernel_demo.multi_step_workflow_smoke_v1",
    "kernel_demo.quota_exhausted_smoke_v1",
    "kernel_demo.handoff_smoke_source_v1",
    "kernel_demo.handoff_smoke_target_v1"
  ],
  "scenarios": [
    {
      "scenario_id": "kernel_demo.single_action_smoke_v1",
      "version": 1,
      "allowed_next_actions": ["copy_result", "create_handoff"],
      "input_renderer_hint": {
        "renderer": "json_schema",
        "schema_ref": "kernel_demo.generic_text_input_v1",
        "schema_version": 1
      },
      "output_renderer_hint": {
        "renderer": "json_schema",
        "schema_ref": "kernel_demo.extract_output_v1",
        "schema_version": 1
      }
    }
  ],
  "quota_summary": {
    "quota_policy_id": "kernel_demo.guest_quota_v1",
    "unit": "scenario_run",
    "limit_count": 3,
    "period": "lifetime"
  },
  "allowed_ui_capabilities": [
    "capture_email",
    "continue_to_target",
    "copy_result",
    "create_handoff",
    "render_input",
    "render_output",
    "view_paywall"
  ]
}
```

Unknown products return a safe `404` error shape that does not echo the requested product ID:

```json
{
  "error": {
    "code": "product_not_found",
    "message": "Product not found",
    "request_id": "req_123"
  }
}
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
