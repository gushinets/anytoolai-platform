# OpenAPI

<!-- Generated file. Do not edit by hand. -->
Canonical source: anytoolai_platform_api.openapi.generate.build_openapi_schema().

API title: AnytoolAI Platform API

Version: 0.1.0

## Implemented operations

| Method | Path | Operation ID | Responses |
|---|---|---|---|
| GET | /health | health_health_get | 200 |
| GET | /v1/atom-lab/atoms | list_atoms_v1_atom_lab_atoms_get | 200, 401, 422, 503 |
| GET | /v1/atom-lab/atoms/{atom_id} | get_atom_v1_atom_lab_atoms__atom_id__get | 200, 401, 404, 422, 503 |
| GET | /v1/atom-lab/models | list_models_v1_atom_lab_models_get | 200, 401, 422, 503 |
| POST | /v1/atom-lab/models/refresh | request_model_refresh_v1_atom_lab_models_refresh_post | 202, 401, 422, 503 |
| GET | /v1/atom-lab/presets | list_presets_v1_atom_lab_presets_get | 200, 401, 422, 503 |
| POST | /v1/atom-lab/presets | create_preset_v1_atom_lab_presets_post | 201, 401, 409, 422, 503 |
| GET | /v1/atom-lab/presets/{preset_id}/versions | list_preset_versions_v1_atom_lab_presets__preset_id__versions_get | 200, 401, 404, 422, 503 |
| POST | /v1/atom-lab/presets/{preset_id}/versions | create_preset_version_v1_atom_lab_presets__preset_id__versions_post | 201, 401, 404, 409, 422, 503 |
| GET | /v1/atom-lab/presets/{preset_id}/versions/{version} | get_preset_version_v1_atom_lab_presets__preset_id__versions__version__get | 200, 401, 404, 422, 503 |
| GET | /v1/atom-lab/presets/{preset_id}/versions/{version}/export | export_preset_version_v1_atom_lab_presets__preset_id__versions__version__export_get | 200, 401, 404, 422, 503 |
| GET | /v1/atom-lab/runs | list_runs_v1_atom_lab_runs_get | 200, 401, 422, 503 |
| POST | /v1/atom-lab/runs | start_run_v1_atom_lab_runs_post | 202, 401, 404, 409, 413, 422, 429, 503 |
| GET | /v1/atom-lab/runs/{run_id} | get_run_v1_atom_lab_runs__run_id__get | 200, 401, 404, 422, 503 |
| POST | /v1/client-events | post_client_event_v1_client_events_post | 200, 404, 409, 422 |
| POST | /v1/demo/runs | start_demo_run_v1_demo_runs_post | 200, 401, 409, 422, 429, 503 |
| POST | /v1/handoffs | create_handoff_v1_handoffs_post | 200, 404, 409, 422 |
| GET | /v1/handoffs/{handoff_token} | get_handoff_v1_handoffs__handoff_token__get | 200, 404, 422 |
| POST | /v1/handoffs/{handoff_token}/accept | accept_handoff_v1_handoffs__handoff_token__accept_post | 200, 404, 409, 410, 422, 429 |
| POST | /v1/handoffs/{handoff_token}/decline | decline_handoff_v1_handoffs__handoff_token__decline_post | 200, 404, 409, 410, 422 |
| POST | /v1/identity/guest | create_guest_identity_v1_identity_guest_post | 200 |
| GET | /v1/products/{product_id}/quota | get_product_quota_v1_products__product_id__quota_get | 200, 404, 422 |
| GET | /v1/products/{product_id}/runtime-config | get_runtime_config_v1_products__product_id__runtime_config_get | 200, 404, 422 |
| POST | /v1/products/{product_id}/scenarios/{scenario_id}/start | start_scenario_v1_products__product_id__scenarios__scenario_id__start_post | 200, 404, 409, 422, 429 |
| GET | /v1/results/{result_artifact_id} | get_result_artifact_v1_results__result_artifact_id__get | 200, 404, 422 |
| GET | /v1/scenario-sessions/{scenario_session_id} | get_scenario_session_v1_scenario_sessions__scenario_session_id__get | 200, 404, 422 |
| POST | /v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id} | post_next_action_v1_scenario_sessions__scenario_session_id__next_actions__next_action_id__post | 200, 404, 409, 422 |

## Component schemas

- AtomLabAtomId
- AtomLabAtomResponse
- AtomLabDebugArtifactResponse
- AtomLabErrorDetailResponse
- AtomLabErrorResponse
- AtomLabFieldErrorResponse
- AtomLabModelRefreshResponse
- AtomLabModelResponse
- AtomLabModelsResponse
- AtomLabPresetCreatedResponse
- AtomLabPresetExportResponse
- AtomLabPresetListResponse
- AtomLabPresetNextVersionRequest
- AtomLabPresetSummaryResponse
- AtomLabPresetVersionListResponse
- AtomLabPresetVersionRequest
- AtomLabPresetVersionResponse
- AtomLabPresetVersionSummaryResponse
- AtomLabProviderCallDiagnosticResponse
- AtomLabRunAcceptedResponse
- AtomLabRunDetailResponse
- AtomLabRunDiagnosticsResponse
- AtomLabRunListResponse
- AtomLabRunRuntimeIdsResponse
- AtomLabRunStatus
- AtomLabRunSummaryResponse
- AtomLabSchemaRefsResponse
- AtomLabVersionedSchemaRefResponse
- ClientEventRequest
- ClientEventResponse
- DemoRunRequest
- ErrorDetailResponse
- ErrorResponse
- FrontendType
- GuestIdentityResponse
- HTTPValidationError
- HandoffAcceptRequest
- HandoffCreateRequest
- HandoffCreateResponse
- HandoffPreviewResponse
- HandoffStatus
- ModelCatalogCompatibility
- ModelCatalogReason
- ModelCatalogRefreshStatus
- ProviderCallStatus
- QuotaDimension
- QuotaPeriod
- QuotaStateResponse
- QuotaUnit
- ReasoningEffort
- ResultArtifactResponse
- RuntimeConfigResponse
- RuntimeFrontendResponse
- RuntimeQuotaSummaryResponse
- RuntimeRendererHintResponse
- RuntimeScenarioResponse
- ScenarioNextActionRequest
- ScenarioSessionResponse
- ScenarioSessionStatus
- ScenarioStartRequest
- ScenarioStartResponse
- ValidationError
- WebClientEventType
