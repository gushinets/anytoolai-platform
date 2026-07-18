from __future__ import annotations

from typing import Any
from typing import Annotated

from fastapi import APIRouter, Body, Depends

from anytoolai_platform_api.dependencies import (
    get_config_registry,
    get_session_factory,
    get_settings,
)
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.schemas import (
    ErrorResponse,
    ScenarioNextActionRequest,
    ScenarioSessionResponse,
    ScenarioStartRequest,
    ScenarioStartResponse,
)
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.scenarios.models import ScenarioSessionSnapshot
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioRuntimeService, ScenarioSessionService
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.repository import JobRepository

router = APIRouter(tags=["scenario-runtime"])

START_RESPONSE_EXAMPLE = {
    "scenario_session_id": "scenario_session_123",
    "job_id": "job_123",
    "status": "started",
    "allowed_next_actions": [],
    "result_artifact_id": None,
}

SESSION_RESPONSE_EXAMPLE = {
    "scenario_session_id": "scenario_session_123",
    "job_id": "job_123",
    "status": "completed",
    "current_checkpoint_id": "result_ready",
    "allowed_next_actions": ["copy_result", "create_handoff"],
    "result_artifact_id": "artifact_123",
}

SAFE_404_EXAMPLE = {
    "error": {
        "code": "scenario_not_found",
        "message": "Scenario not found.",
        "request_id": "req_123",
    }
}

SAFE_409_EXAMPLE = {
    "error": {
        "code": "scenario_checkpoint_conflict",
        "message": "Scenario checkpoint no longer matches the requested action.",
        "request_id": "req_123",
    }
}

SAFE_422_EXAMPLE = {
    "error": {
        "code": "scenario_input_invalid",
        "message": "Scenario input must be a JSON object.",
        "request_id": "req_123",
    }
}


@router.post(
    "/v1/products/{product_id}/scenarios/{scenario_id}/start",
    response_model=ScenarioStartResponse,
    summary="Create a scenario session and queue workflow execution",
    responses={
        200: {
            "description": "Stable queue-and-return response for CE polling.",
            "content": {"application/json": {"example": START_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe response when the scenario is unknown for the product.",
            "content": {"application/json": {"example": SAFE_404_EXAMPLE}},
        },
        422: {
            "model": ErrorResponse,
            "description": "Safe validation response for unsupported frontend or invalid input.",
            "content": {"application/json": {"example": SAFE_422_EXAMPLE}},
        },
    },
)
def start_scenario(
    product_id: str,
    scenario_id: str,
    request: Annotated[ScenarioStartRequest, Body()],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScenarioStartResponse:
    with transaction_boundary(session_factory) as session:
        snapshot = _wrap_platform_errors(
            lambda: _runtime_service(session=session, registry=registry).start_session(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                product_id=product_id,
                scenario_id=scenario_id,
                frontend_id=request.frontend_id,
                input_payload=request.input,
                guest_id=request.guest_id,
                user_id=request.user_id,
                source_frontend_instance_id=request.source_frontend_instance_id,
            )
        )
    return ScenarioStartResponse.model_validate(_start_response_payload(snapshot))


@router.get(
    "/v1/scenario-sessions/{scenario_session_id}",
    response_model=ScenarioSessionResponse,
    summary="Get frontend-safe scenario session state",
    responses={
        200: {
            "description": "Frontend-safe session snapshot for polling.",
            "content": {"application/json": {"example": SESSION_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe response when the scenario session is unknown.",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "scenario_session_not_found",
                            "message": "Scenario session not found.",
                            "request_id": "req_123",
                        }
                    }
                }
            },
        },
    },
)
def get_scenario_session(
    scenario_session_id: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScenarioSessionResponse:
    with transaction_boundary(session_factory) as session:
        snapshot = _wrap_platform_errors(
            lambda: _runtime_service(
                session=session,
                registry=registry,
            ).get_session_snapshot(
                scenario_session_id,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            )
        )
    return ScenarioSessionResponse.model_validate(_session_response_payload(snapshot))


@router.post(
    "/v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id}",
    response_model=ScenarioSessionResponse,
    summary="Validate and record a frontend next-action click",
    responses={
        200: {
            "description": "Validated next action with the current safe session snapshot.",
            "content": {"application/json": {"example": SESSION_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe response when the scenario session is unknown.",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "scenario_session_not_found",
                            "message": "Scenario session not found.",
                            "request_id": "req_123",
                        }
                    }
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": "Safe response for stale checkpoint or disallowed action.",
            "content": {"application/json": {"example": SAFE_409_EXAMPLE}},
        },
    },
)
def post_next_action(
    scenario_session_id: str,
    next_action_id: str,
    request: Annotated[ScenarioNextActionRequest, Body()],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ScenarioSessionResponse:
    with transaction_boundary(session_factory) as session:
        snapshot = _wrap_platform_errors(
            lambda: _runtime_service(
                session=session,
                registry=registry,
            ).record_next_action(
                scenario_session_id,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                next_action_id=next_action_id,
                checkpoint_id=request.checkpoint_id,
            )
        )
    return ScenarioSessionResponse.model_validate(_session_response_payload(snapshot))


def _runtime_service(
    *,
    session,
    registry: ConfigRegistry,
) -> ScenarioRuntimeService:
    event_emitter = EventEmitter(EventLogRepository(session))
    session_repository = ScenarioSessionRepository(session)
    return ScenarioRuntimeService(
        config_registry=registry,
        session_repository=session_repository,
        session_service=ScenarioSessionService(session_repository, event_emitter),
        job_repository=JobRepository(session),
        event_emitter=event_emitter,
    )


def _start_response_payload(snapshot: ScenarioSessionSnapshot) -> dict[str, object]:
    return {
        "scenario_session_id": snapshot.scenario_session_id,
        "job_id": snapshot.job_id,
        "status": snapshot.status.value,
        "allowed_next_actions": list(snapshot.allowed_next_actions),
        "result_artifact_id": snapshot.result_artifact_id,
    }


def _session_response_payload(snapshot: ScenarioSessionSnapshot) -> dict[str, object]:
    payload = _start_response_payload(snapshot)
    payload["current_checkpoint_id"] = snapshot.current_checkpoint_id
    return payload


def _status_code_for_platform_error(error: PlatformError) -> int:
    if error.code in {"scenario_not_found", "scenario_session_not_found"}:
        return 404
    if error.code in {
        "scenario_checkpoint_conflict",
        "scenario_checkpoint_not_actionable",
        "scenario_next_action_not_allowed",
    }:
        return 409
    if error.code in {
        "scenario_frontend_invalid",
        "scenario_input_invalid",
    }:
        return 422
    return 500


def _to_api_error(error: PlatformError) -> ApiError:
    return ApiError(
        status_code=_status_code_for_platform_error(error),
        code=error.code,
        message=str(error),
    )


def _wrap_platform_errors(callable_):
    try:
        return callable_()
    except PlatformError as exc:
        raise _to_api_error(exc) from exc
