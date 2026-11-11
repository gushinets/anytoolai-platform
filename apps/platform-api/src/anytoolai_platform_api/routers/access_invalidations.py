from http import HTTPStatus
from typing import Annotated, Any

from anytoolai_platform_api.dependencies import get_session_factory, get_settings
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.manifest_auth import (
    PortalPermission,
    PortalPrincipal,
    authenticate_portal,
)
from anytoolai_platform_api.paid_access import PAID_RUNTIME_ERROR_RESPONSES, invalidate
from anytoolai_platform_api.portal_session import VersionOne, WireUserId
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from anytoolai_platform_core.storage.transactions import transaction_boundary
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["paid-access"])


class AccessInvalidation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: VersionOne
    tenant_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    user_id: WireUserId
    access_revision: int = Field(strict=True, ge=0)


@router.post(
    "/internal/v1/access-invalidations",
    status_code=HTTPStatus.NO_CONTENT,
    responses=PAID_RUNTIME_ERROR_RESPONSES,
)
def post_access_invalidation(
    payload: AccessInvalidation,
    principal: Annotated[PortalPrincipal, Depends(authenticate_portal)],
    factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    if PortalPermission.ACCESS_INVALIDATE not in principal.permissions or (
        payload.tenant_id,
        payload.region,
    ) != (principal.tenant_id, principal.region):
        raise ApiError(
            status_code=HTTPStatus.FORBIDDEN,
            code="access_invalidation_forbidden",
            message="Access invalidation is forbidden.",
        )
    owner = ExecutionOwner(
        payload.tenant_id, payload.region, ExecutionOwnerKind.portal_user, payload.user_id
    )
    with transaction_boundary(factory) as session:
        invalidate(session, owner, payload.access_revision, settings.portal_consumer_id)
    return Response(status_code=HTTPStatus.NO_CONTENT)
