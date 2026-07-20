from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from anytoolai_platform_api.dependencies import (
    get_config_registry,
    get_session_factory,
    get_settings,
)
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.schemas import (
    ErrorResponse,
    GuestIdentityResponse,
    QuotaStateResponse,
)
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityService
from anytoolai_platform_core.quotas.models import QuotaState
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService
from anytoolai_platform_core.storage.transactions import transaction_boundary

router = APIRouter(tags=["access-lite"])

GUEST_RESPONSE_EXAMPLE = {"guest_id": "guest_123"}
QUOTA_RESPONSE_EXAMPLE = {
    "guest_id": "guest_123",
    "product_id": "kernel_demo",
    "quota_policy_id": "kernel_demo.guest_quota_v1",
    "unit": "scenario_run",
    "period": "lifetime",
    "limit_count": 3,
    "used_count": 1,
    "remaining_count": 2,
    "exhausted": False,
}


@router.post(
    "/v1/identity/guest",
    response_model=GuestIdentityResponse,
    summary="Create an opaque guest identity",
    responses={
        200: {
            "description": "Frontend-safe opaque guest identifier.",
            "content": {"application/json": {"example": GUEST_RESPONSE_EXAMPLE}},
        },
    },
)
def create_guest_identity(
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GuestIdentityResponse:
    with transaction_boundary(session_factory) as session:
        guest = _identity_service(session).create_guest(
            tenant_id=settings.default_tenant_id,
            region=settings.default_region,
        )
    return GuestIdentityResponse(guest_id=guest.id)


@router.get(
    "/v1/products/{product_id}/quota",
    response_model=QuotaStateResponse,
    summary="Get frontend-safe guest quota state",
    responses={
        200: {
            "description": "Current backend-owned guest quota state.",
            "content": {"application/json": {"example": QUOTA_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe response when product or guest identity is unknown.",
        },
    },
)
def get_product_quota(
    product_id: str,
    guest_id: Annotated[str, Query(min_length=1)],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> QuotaStateResponse:
    with transaction_boundary(session_factory) as session:
        state = _wrap_platform_errors(
            lambda: _quota_service(session=session, registry=registry).check_quota(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                product_id=product_id,
                guest_id=guest_id,
                emit_event=False,
                persist_usage=False,
            )
        )
    return QuotaStateResponse.model_validate(_quota_state_payload(state))


def _identity_service(session: Any) -> GuestIdentityService:
    event_emitter = EventEmitter(EventLogRepository(session))
    return GuestIdentityService(
        GuestIdentityRepository(session),
        event_emitter,
    )


def _quota_service(
    *,
    session: Any,
    registry: ConfigRegistry,
) -> GuestQuotaService:
    return GuestQuotaService(
        config_registry=registry,
        quota_repository=QuotaUsageRepository(session),
        guest_repository=GuestIdentityRepository(session),
        event_emitter=EventEmitter(EventLogRepository(session)),
    )


def _quota_state_payload(state: QuotaState) -> dict[str, object]:
    return {
        "guest_id": state.guest_id,
        "product_id": state.product_id,
        "quota_policy_id": state.quota_policy_id,
        "unit": state.unit.value,
        "period": state.period.value,
        "limit_count": state.limit_count,
        "used_count": state.used_count,
        "remaining_count": state.remaining_count,
        "exhausted": state.exhausted,
    }


def _status_code_for_platform_error(error: PlatformError) -> int:
    if error.code in {
        "guest_identity_not_found",
        "product_not_found",
        "quota_policy_not_configured",
    }:
        return 404
    if error.code == "guest_identity_required":
        return 422
    if error.code == "quota_exhausted":
        return 429
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
