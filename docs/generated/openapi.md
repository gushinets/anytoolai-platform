# OpenAPI

<!-- Generated file. Do not edit by hand. -->
Canonical source: anytoolai_platform_api.main.create_app().openapi().

API title: AnytoolAI Platform API

Version: 0.1.0

## Implemented operations

| Method | Path | Operation ID | Responses |
|---|---|---|---|
| GET | /health | health_health_get | 200 |
| POST | /v1/handoffs | create_handoff_v1_handoffs_post | 200, 404, 409, 422 |
| GET | /v1/handoffs/{handoff_token} | get_handoff_v1_handoffs__handoff_token__get | 200, 404, 422 |
| POST | /v1/handoffs/{handoff_token}/accept | accept_handoff_v1_handoffs__handoff_token__accept_post | 200, 404, 409, 410, 422, 429 |
| POST | /v1/handoffs/{handoff_token}/decline | decline_handoff_v1_handoffs__handoff_token__decline_post | 200, 404, 409, 410, 422 |
| POST | /v1/identity/guest | create_guest_identity_v1_identity_guest_post | 200 |
| GET | /v1/products/{product_id}/quota | get_product_quota_v1_products__product_id__quota_get | 200, 404, 422 |
| GET | /v1/products/{product_id}/runtime-config | get_runtime_config_v1_products__product_id__runtime_config_get | 200, 404, 422 |
| POST | /v1/products/{product_id}/scenarios/{scenario_id}/start | start_scenario_v1_products__product_id__scenarios__scenario_id__start_post | 200, 404, 422, 429 |
| GET | /v1/scenario-sessions/{scenario_session_id} | get_scenario_session_v1_scenario_sessions__scenario_session_id__get | 200, 404, 422 |
| POST | /v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id} | post_next_action_v1_scenario_sessions__scenario_session_id__next_actions__next_action_id__post | 200, 404, 409, 422 |

## Component schemas

- ErrorDetailResponse
- ErrorResponse
- GuestIdentityResponse
- HTTPValidationError
- HandoffAcceptRequest
- HandoffCreateRequest
- HandoffCreateResponse
- HandoffPreviewResponse
- QuotaStateResponse
- RuntimeConfigResponse
- RuntimeFrontendResponse
- RuntimeQuotaSummaryResponse
- RuntimeRendererHintResponse
- RuntimeScenarioResponse
- ScenarioNextActionRequest
- ScenarioSessionResponse
- ScenarioStartRequest
- ScenarioStartResponse
- ValidationError
