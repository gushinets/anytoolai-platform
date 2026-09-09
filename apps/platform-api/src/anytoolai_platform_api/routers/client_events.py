from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends

from anytoolai_platform_api.dependencies import (
    get_config_registry,
    get_session_factory,
    get_settings,
)
from anytoolai_platform_api.errors import ApiError, platform_error_to_api_error
from anytoolai_platform_api.schemas import ClientEventRequest, ClientEventResponse, ErrorResponse
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.client_events import ClientEventService
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.transactions import transaction_boundary

router = APIRouter(tags=["client-events"])

CLIENT_EVENT_RESPONSE_EXAMPLE = {
    "event_id": "web_evt_123",
    "event_type": "web.product_viewed",
}

SAFE_422_EXAMPLE = {
    "error": {
        "code": "client_event_type_not_allowed",
        "message": "Event type is not part of the v1 client-event allowlist.",
        "request_id": "req_123",
    }
}

SAFE_404_EXAMPLE = {
    "error": {
        "code": "guest_identity_not_found",
        "message": "Guest identity not found.",
        "request_id": "req_123",
    }
}

SAFE_409_EXAMPLE = {
    "error": {
        "code": "client_event_id_conflict",
        "message": "event_id was already used to record a different client event.",
        "request_id": "req_123",
    }
}


@router.post(
    "/v1/client-events",
    response_model=ClientEventResponse,
    summary="Record an allowlisted client analytics event",
    responses={
        200: {
            "description": (
                "Event was durably recorded (or already existed for this event_id -- "
                "duplicate delivery is idempotent)."
            ),
            "content": {"application/json": {"example": CLIENT_EVENT_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe response when the supplied guest identity or scenario session is unknown.",
            "content": {"application/json": {"example": SAFE_404_EXAMPLE}},
        },
        409: {
            "model": ErrorResponse,
            "description": (
                "The supplied event_id was already used to record a client event with "
                "different content (event type, correlation, or properties)."
            ),
            "content": {"application/json": {"example": SAFE_409_EXAMPLE}},
        },
        422: {
            "model": ErrorResponse,
            "description": (
                "Safe response for an unknown event type, an invalid product/frontend "
                "combination, a disallowed property, or a missing/oversized identifier."
            ),
            "content": {"application/json": {"example": SAFE_422_EXAMPLE}},
        },
    },
)
def post_client_event(
    request: Annotated[ClientEventRequest, Body()],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ClientEventResponse:
    with transaction_boundary(session_factory) as session:
        try:
            envelope = _client_event_service(session=session, registry=registry).record(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                event_id=request.event_id,
                event_type=request.event_type,
                product_id=request.product_id,
                frontend_id=request.frontend_id,
                web_session_id=request.web_session_id,
                guest_id=request.guest_id,
                user_id=request.user_id,
                scenario_session_id=request.scenario_session_id,
                properties=request.properties,
            )
        except PlatformError as exc:
            raise _to_api_error(exc) from exc
    return ClientEventResponse(event_id=envelope.event_id, event_type=envelope.event_type)


def _client_event_service(
    *,
    session: Any,
    registry: ConfigRegistry,
) -> ClientEventService:
    return ClientEventService(
        config_registry=registry,
        guest_repository=GuestIdentityRepository(session),
        scenario_session_repository=ScenarioSessionRepository(session),
        event_emitter=EventEmitter(EventLogRepository(session)),
    )


def _status_code_for_platform_error(error: PlatformError) -> int:
    if error.code in {
        "guest_identity_not_found",
        "scenario_session_not_found",
    }:
        return 404
    if error.code == "client_event_id_conflict":
        return 409
    if error.code in {
        "client_event_type_not_allowed",
        "client_event_id_invalid",
        "client_event_web_session_id_invalid",
        "client_event_product_invalid",
        "client_event_frontend_invalid",
        "client_event_property_invalid",
    }:
        return 422
    return 500


def _to_api_error(error: PlatformError) -> ApiError:
    return platform_error_to_api_error(
        error, status_code=_status_code_for_platform_error(error)
    )
