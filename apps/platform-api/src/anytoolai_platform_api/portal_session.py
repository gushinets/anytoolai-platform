"""Portal's scoped identity adapter. No user directory, guest fallback or identity cache."""

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from http.client import HTTPException
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener
from urllib.request import Request as UrlRequest
from uuid import UUID

from anytoolai_platform_api.dependencies import get_settings
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.quotas.models import ExecutionOwner, ExecutionOwnerKind
from fastapi import Depends, Request
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError

PORTAL_TIMEOUT_SECONDS = 2
PORTAL_MAX_RESPONSE_BYTES = 16 * 1024
DELEGATION_TTL_SECONDS = 30 * 60
PORTAL_CLOCK_BUDGET_SECONDS = 5
IDENTITY_FAILURE_CODES = frozenset(
    {
        "kernel_delegation_expired",
        "kernel_parent_authority_invalid",
        "kernel_session_code_invalid",
    }
)


def _utc_wire_timestamp(value: object) -> object:
    if (
        not isinstance(value, str)
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)",
            value,
        )
        is None
    ):
        raise ValueError("Expected an RFC3339 UTC timestamp")
    return value


def _version_one(value: object) -> object:
    if type(value) is not int or value != 1:
        raise ValueError("Expected integer version 1")
    return value


WireTimestamp = Annotated[datetime, BeforeValidator(_utc_wire_timestamp)]
VersionOne = Annotated[Literal[1], BeforeValidator(_version_one)]
WireUserId = Annotated[
    str, Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
]


class PortalExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$", repr=False)
    code_verifier: str = Field(pattern=r"^[A-Za-z0-9._~-]{43,128}$", repr=False)


class PortalExchangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: VersionOne
    access_token: str = Field(min_length=43, max_length=512, repr=False)
    token_type: Literal["Bearer"]
    tenant_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    user_id: WireUserId
    expires_at: WireTimestamp


class PortalIntrospectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    schema_version: VersionOne
    tenant_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    user_id: WireUserId
    valid_until: WireTimestamp


@dataclass(frozen=True)
class PortalUserPrincipal:
    owner: ExecutionOwner
    valid_until: datetime


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: UrlRequest, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


def _unavailable() -> ApiError:
    return ApiError(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        code="portal_identity_unavailable",
        message="Portal identity is unavailable.",
    )


def _expired() -> ApiError:
    return ApiError(
        status_code=HTTPStatus.UNAUTHORIZED,
        code="kernel_delegation_expired",
        message="Portal delegation has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )


class PortalSessionClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _post(self, operation: Literal["exchange", "introspect"], payload: dict[str, str]) -> bytes:
        settings = self.settings
        if not settings.portal_base_url or settings.portal_access_service_token is None:
            raise _unavailable()
        request = UrlRequest(
            settings.portal_base_url + "/internal/v1/kernel-sessions/" + operation,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer "
                + settings.portal_access_service_token.get_secret_value(),
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-store",
            },
            method="POST",
        )
        # Never forward secrets through redirects or environment-selected proxies.
        opener = build_opener(ProxyHandler({}), _NoRedirect())
        try:
            with opener.open(request, timeout=PORTAL_TIMEOUT_SECONDS) as response:
                if response.status != HTTPStatus.OK:
                    raise _unavailable()
                content = response.read(PORTAL_MAX_RESPONSE_BYTES + 1)
        except HTTPError as error:
            try:
                with error:
                    content = error.read(PORTAL_MAX_RESPONSE_BYTES + 1)
            except (OSError, HTTPException):
                raise _unavailable() from None
            if error.code == HTTPStatus.UNAUTHORIZED and len(content) <= PORTAL_MAX_RESPONSE_BYTES:
                self._identity_failure(content, operation)
            raise _unavailable() from None
        except (URLError, TimeoutError, OSError, HTTPException):
            raise _unavailable() from None
        if len(content) > PORTAL_MAX_RESPONSE_BYTES:
            raise _unavailable()
        return content

    @staticmethod
    def _identity_failure(content: bytes, operation: str) -> None:
        try:
            body = json.loads(content)
        except (ValueError, UnicodeError):
            return
        detail = body.get("detail") if isinstance(body, dict) else None
        code = detail.get("code") if isinstance(detail, dict) else None
        allowed = (
            IDENTITY_FAILURE_CODES
            if operation == "exchange"
            else IDENTITY_FAILURE_CODES - {"kernel_session_code_invalid"}
        )
        if isinstance(code, str) and code in allowed:
            raise ApiError(
                status_code=HTTPStatus.UNAUTHORIZED,
                code=code,
                message="Portal identity is no longer valid.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def _require_scope(self, tenant_id: str, region: str) -> None:
        if (tenant_id, region) != (self.settings.default_tenant_id, self.settings.default_region):
            raise _unavailable()

    def exchange(self, payload: PortalExchangeRequest) -> PortalExchangeResponse:
        try:
            response = PortalExchangeResponse.model_validate_json(
                self._post("exchange", payload.model_dump())
            )
        except ValidationError:
            raise _unavailable() from None
        self._require_scope(response.tenant_id, response.region)
        now = datetime.now(UTC)
        if response.expires_at <= now:
            raise _expired()
        if response.expires_at > now + timedelta(
            seconds=DELEGATION_TTL_SECONDS + PORTAL_CLOCK_BUDGET_SECONDS
        ):
            raise _unavailable()
        return response

    def introspect(self, token: str) -> PortalUserPrincipal:
        try:
            response = PortalIntrospectionResponse.model_validate_json(
                self._post("introspect", {"access_token": token})
            )
        except ValidationError:
            raise _unavailable() from None
        self._require_scope(response.tenant_id, response.region)
        now = datetime.now(UTC)
        if response.valid_until <= now:
            raise _expired()
        if response.valid_until > now + timedelta(
            seconds=DELEGATION_TTL_SECONDS + PORTAL_CLOCK_BUDGET_SECONDS
        ):
            raise _unavailable()
        return PortalUserPrincipal(
            owner=ExecutionOwner(
                response.tenant_id,
                response.region,
                ExecutionOwnerKind.portal_user,
                str(UUID(response.user_id)),
            ),
            valid_until=response.valid_until,
        )


def get_portal_session_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PortalSessionClient:
    return PortalSessionClient(settings)


def authenticate_portal_user(
    request: Request, client: Annotated[PortalSessionClient, Depends(get_portal_session_client)]
) -> PortalUserPrincipal:
    headers = request.headers.getlist("authorization")
    scheme, _, token = (headers[0] if len(headers) == 1 else "").partition(" ")
    if (
        scheme.lower() != "bearer"
        or re.fullmatch(r"[A-Za-z0-9._~+/-]{43,512}={0,2}", token) is None
    ):
        raise ApiError(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="portal_identity_required",
            message="Portal identity is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return client.introspect(token)
