"""Request-driven paid authority; network calls never hold database transactions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from http import HTTPStatus
from http.client import HTTPException
from typing import Annotated, Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener
from urllib.request import Request as UrlRequest

import sqlalchemy as sa
from anytoolai_platform_api.dependencies import get_settings
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.portal_session import (
    PORTAL_TIMEOUT_SECONDS,
    PortalSessionClient,
    PortalUserPrincipal,
    WireTimestamp,
    WireUserId,
    _NoRedirect,
    authenticate_portal_user,
    get_portal_session_client,
)
from anytoolai_platform_api.schemas import ErrorResponse
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.quotas.access_coherence import (
    AccessCoherenceRepository,
    database_wall_time,
)
from anytoolai_platform_core.quotas.execution_repository import PaidAllowanceUsageRepository
from anytoolai_platform_core.quotas.models import (
    MAX_ALLOWANCE_QUANTITY,
    ExecutionOwner,
    PaidAllowance,
)
from anytoolai_platform_core.scenarios.ownership import session_owner_matches
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from fastapi import Depends, Request
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

PAID_RUNTIME_ERROR_RESPONSES = {
    status: {"model": ErrorResponse}
    for status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN, HTTPStatus.SERVICE_UNAVAILABLE)
}

SNAPSHOT_SCHEMA_VERSION = 3
SNAPSHOT_MAX_BYTES = 256 * 1024
SNAPSHOT_MAX_AGE_SECONDS = 300


def _version_three(value: object) -> object:
    if type(value) is not int or value != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("Expected integer version 3")
    return value


class Grant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: str = Field(min_length=1)
    valid_until: WireTimestamp | None


class Allowance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowance_id: WireUserId
    product_id: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    quantity: int = Field(strict=True, ge=0, le=MAX_ALLOWANCE_QUANTITY)


class AccessSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Annotated[Literal[3], BeforeValidator(_version_three)]
    consumer_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    consumer_policy_revision: int = Field(strict=True, ge=1, le=2**53 - 1)
    tenant_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    user_id: WireUserId
    access_revision: int = Field(strict=True, ge=0)
    refresh_after: WireTimestamp
    expires_at: WireTimestamp
    grants: list[Grant]
    allowances: list[Allowance]

    @model_validator(mode="after")
    def semantic_checks(self) -> AccessSnapshot:
        products = {grant.product_id for grant in self.grants}
        if (
            len(products) != len(self.grants)
            or len({item.allowance_id for item in self.allowances}) != len(self.allowances)
            or any(item.product_id not in products for item in self.allowances)
            or (self.access_revision == 0 and (self.grants or self.allowances))
            or self.refresh_after > self.expires_at
            or any(
                g.valid_until is not None and g.valid_until < self.expires_at for g in self.grants
            )
        ):
            raise ValueError("Invalid snapshot semantics")
        return self

    def semantic_digest(self) -> str:
        contents = {
            "grants": sorted(
                (g.model_dump(mode="json") for g in self.grants), key=lambda g: g["product_id"]
            ),
            "allowances": sorted(
                (a.model_dump(mode="json") for a in self.allowances),
                key=lambda a: a["allowance_id"],
            ),
        }
        return hashlib.sha256(json.dumps(contents, sort_keys=True).encode()).hexdigest()


def unavailable() -> ApiError:
    return ApiError(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        code="paid_access_unavailable",
        message="Paid access authority is unavailable.",
    )


def forbidden() -> ApiError:
    return ApiError(
        status_code=HTTPStatus.FORBIDDEN,
        code="paid_access_denied",
        message="Paid access is not available for this operation.",
    )


def optional_portal_user(
    request: Request,
    client: Annotated[PortalSessionClient, Depends(get_portal_session_client)],
) -> PortalUserPrincipal | None:
    # Supplying an invalid credential must never select the guest route.
    if not request.headers.getlist("authorization"):
        return None
    return authenticate_portal_user(request, client)


def require_session_owner(
    session: Session,
    session_id: str,
    settings: Settings,
    principal: PortalUserPrincipal | None,
    *,
    code: str = "scenario_session_not_found",
) -> None:
    record = ScenarioSessionRepository(session).get_in_scope(
        session_id, tenant_id=settings.default_tenant_id, region=settings.default_region
    )
    if record is not None and not session_owner_matches(
        session, record, None if principal is None else principal.owner
    ):
        raise ApiError(status_code=HTTPStatus.NOT_FOUND, code=code, message="Resource not found.")


def db_now(session: Session) -> datetime:
    return database_wall_time(session)


def lock_authority(session: Session, owner: ExecutionOwner, consumer_id: str) -> sa.RowMapping:
    return AccessCoherenceRepository(session, owner, consumer_id=consumer_id).lock()


def invalidate(session: Session, owner: ExecutionOwner, revision: int, consumer_id: str) -> None:
    AccessCoherenceRepository(session, owner, consumer_id=consumer_id).invalidate(revision)


def evict(session: Session, owner: ExecutionOwner, consumer_id: str) -> None:
    AccessCoherenceRepository(session, owner, consumer_id=consumer_id).evict()


def install(session: Session, owner: ExecutionOwner, document: AccessSnapshot) -> bool:
    if (document.tenant_id, document.region, document.user_id) != (
        owner.tenant_id,
        owner.region,
        owner.owner_id,
    ):
        raise unavailable()
    repository = AccessCoherenceRepository(session, owner, consumer_id=document.consumer_id)
    row = repository.lock()
    now = db_now(session)
    if (
        document.consumer_policy_revision != row["policy_floor"]
        or document.access_revision < row["revision_floor"]
    ):
        return False
    if document.expires_at <= now or document.expires_at > now + timedelta(
        seconds=SNAPSHOT_MAX_AGE_SECONDS
    ):
        raise unavailable()
    digest = document.semantic_digest()
    if (
        row["snapshot_policy_revision"] == document.consumer_policy_revision
        and row["snapshot_revision"] == document.access_revision
        and row["semantic_digest"] != digest
    ):
        raise unavailable()
    buckets = PaidAllowanceUsageRepository(session)
    for item in document.allowances:
        allowance = PaidAllowance(owner=owner, **item.model_dump())
        existing = buckets.get(
            tenant_id=owner.tenant_id, region=owner.region, allowance_id=item.allowance_id
        )
        # A conflicting frozen tuple refuses only dependent admission, without rewriting history.
        if existing is None or existing.allowance == allowance:
            buckets.ensure_usage(allowance)
    repository.install(
        document.access_revision,
        document.consumer_policy_revision,
        digest,
        document.model_dump(mode="json"),
    )
    return True


class AccessSnapshotClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def fetch(self, owner: ExecutionOwner) -> AccessSnapshot:
        settings = self.settings
        if not settings.portal_base_url or settings.portal_access_service_token is None:
            raise unavailable()
        query = urlencode({"tenant_id": owner.tenant_id, "region": owner.region})
        request = UrlRequest(
            f"{settings.portal_base_url}/internal/v1/access-snapshots/{owner.owner_id}?{query}",
            headers={
                "Authorization": "Bearer "
                + settings.portal_access_service_token.get_secret_value(),
                "Accept": "application/json",
                "Cache-Control": "no-store",
            },
        )
        try:
            with build_opener(ProxyHandler({}), _NoRedirect()).open(
                request, timeout=PORTAL_TIMEOUT_SECONDS
            ) as response:
                if response.status != HTTPStatus.OK:
                    raise unavailable()
                body = response.read(SNAPSHOT_MAX_BYTES + 1)
            if len(body) > SNAPSHOT_MAX_BYTES:
                raise unavailable()
            document = AccessSnapshot.model_validate_json(body)
        except HTTPError as error:
            try:
                error.close()
            except (OSError, HTTPException):
                raise unavailable() from None
            raise unavailable() from None
        except (URLError, TimeoutError, OSError, HTTPException, ValidationError):
            raise unavailable() from None
        if (document.consumer_id, document.tenant_id, document.region, document.user_id) != (
            settings.portal_consumer_id,
            owner.tenant_id,
            owner.region,
            owner.owner_id,
        ):
            raise unavailable()
        return document


def get_snapshot_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessSnapshotClient:
    return AccessSnapshotClient(settings)


def refresh_authority(
    factory: SessionFactory, principal: PortalUserPrincipal, client: AccessSnapshotClient
) -> None:
    owner = principal.owner
    with transaction_boundary(factory) as session:
        repository = AccessCoherenceRepository(session, owner, consumer_id=principal.consumer_id)
        # Commit P before network I/O or admission can fail. A stale in-flight
        # introspection must never restore an older policy, including after restart.
        if not repository.observe_policy(principal.consumer_policy_revision):
            raise unavailable()
        row = repository.read()
        document = (
            None
            if row is None or row["snapshot"] is None
            else AccessSnapshot.model_validate(row["snapshot"])
        )
        if (
            document is not None
            and document.consumer_id == principal.consumer_id
            and document.consumer_policy_revision
            == principal.consumer_policy_revision
            == row["policy_floor"]
            and document.access_revision >= row["revision_floor"]
            and (db_now(session) < min(document.refresh_after, document.expires_at))
        ):
            return
    try:
        fresh = client.fetch(owner)
    except ApiError:
        # Admission under the row lock decides whether old finite authority is still usable.
        return
    if (fresh.consumer_id, fresh.consumer_policy_revision) != (
        principal.consumer_id,
        principal.consumer_policy_revision,
    ):
        raise unavailable()
    with transaction_boundary(factory) as session:
        install(session, owner, fresh)


def eligible_allowance(
    session: Session,
    principal: PortalUserPrincipal,
    registry: ConfigRegistry,
    product_id: str,
    scenario_id: str,
) -> PaidAllowance:
    row = lock_authority(session, principal.owner, principal.consumer_id)
    document = None if row["snapshot"] is None else AccessSnapshot.model_validate(row["snapshot"])
    now = db_now(session)
    if principal.valid_until <= now:
        raise ApiError(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="backend_delegation_expired",
            message="Portal delegation has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if (
        document is None
        or document.consumer_id != principal.consumer_id
        or document.consumer_policy_revision != principal.consumer_policy_revision
        or principal.consumer_policy_revision != row["policy_floor"]
        or document.access_revision < row["revision_floor"]
        or document.expires_at <= now
    ):
        raise unavailable()
    grant = next((g for g in document.grants if g.product_id == product_id), None)
    if grant is None or (grant.valid_until is not None and grant.valid_until <= now):
        raise forbidden()
    scenario = registry.get_scenario(scenario_id)
    if scenario is None or not scenario.paid_metric_key:
        raise forbidden()
    candidates = [
        a
        for a in document.allowances
        if a.product_id == product_id and a.metric_key == scenario.paid_metric_key
    ]
    if len(candidates) != 1:
        raise forbidden()
    return PaidAllowance(owner=principal.owner, **candidates[0].model_dump())
