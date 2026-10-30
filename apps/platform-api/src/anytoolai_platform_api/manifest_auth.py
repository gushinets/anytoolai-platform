"""Receiver-owned Portal identity; request values can only narrow its authority."""

from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from secrets import compare_digest
from typing import Annotated, Literal

from anytoolai_platform_api.dependencies import get_settings
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.settings import Settings
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

portal_bearer = HTTPBearer(scheme_name="PortalServiceBearer", auto_error=False)


class PortalPermission(StrEnum):
    MANIFEST_READ = "manifest:read"


@dataclass(frozen=True)
class PortalPrincipal:
    tenant_id: str
    region: str
    caller: Literal["portal"] = "portal"
    permissions: frozenset[PortalPermission] = frozenset({PortalPermission.MANIFEST_READ})


def authenticate_portal(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(portal_bearer)],
) -> PortalPrincipal:
    if settings.portal_service_token is None:
        raise ApiError(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            code="manifest_unavailable",
            message="Capability manifest is unavailable.",
        )
    # Evaluate both rotation slots, including the nonmatching empty slot, without short circuit.
    supplied = credentials.credentials.encode("utf-8") if credentials is not None else b""
    current_matches = compare_digest(
        supplied, settings.portal_service_token.get_secret_value().encode("ascii")
    )
    previous = settings.portal_service_token_previous
    previous_matches = compare_digest(
        supplied, previous.get_secret_value().encode("ascii") if previous is not None else b""
    )
    if (
        credentials is None
        or len(request.headers.getlist("authorization")) != 1
        or not (current_matches | (previous is not None and previous_matches))
    ):
        raise ApiError(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="service_unauthorized",
            message="Valid service authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return PortalPrincipal(tenant_id=settings.default_tenant_id, region=settings.default_region)


def authorize_manifest_read(
    request: Request,
    principal: Annotated[PortalPrincipal, Depends(authenticate_portal)],
    tenant_id: str,
    region: str,
) -> PortalPrincipal:
    if (
        principal.caller != "portal"
        or PortalPermission.MANIFEST_READ not in principal.permissions
        or tenant_id != principal.tenant_id
        or region != principal.region
        or len(request.query_params.getlist("tenant_id")) != 1
        or len(request.query_params.getlist("region")) != 1
    ):
        raise ApiError(
            status_code=HTTPStatus.FORBIDDEN,
            code="manifest_forbidden",
            message="Capability manifest access is forbidden.",
        )
    return principal
