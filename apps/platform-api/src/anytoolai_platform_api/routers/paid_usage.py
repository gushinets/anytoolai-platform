"""Read actual ANY-507 counters without establishing buckets or requiring current grants."""

from http import HTTPStatus
from typing import Annotated, Literal

from anytoolai_platform_api.dependencies import get_session_factory
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.manifest_auth import (
    PortalPermission,
    PortalPrincipal,
    authenticate_portal,
)
from anytoolai_platform_api.paid_access import PAID_RUNTIME_ERROR_RESPONSES, require_portal_user
from anytoolai_platform_api.portal_session import (
    PortalUserPrincipal,
    WireUserId,
)
from anytoolai_platform_core.quotas.execution_repository import PaidAllowanceUsageRepository
from anytoolai_platform_core.quotas.models import (
    MAX_ALLOWANCE_QUANTITY,
    ExecutionOwner,
    ExecutionOwnerKind,
)
from anytoolai_platform_core.quotas.readback import consumption_from_bucket
from anytoolai_platform_core.storage.transactions import SessionFactory
from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPBearer
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(tags=["paid-usage"], responses=PAID_RUNTIME_ERROR_RESPONSES)
AllowanceIds = Annotated[list[WireUserId], Query(min_length=1, max_length=100)]
Counter = Annotated[int, Field(strict=True, ge=0, le=MAX_ALLOWANCE_QUANTITY)]


class UnobservedUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowance_id: WireUserId
    status: Literal["unobserved"] = "unobserved"


class ObservedUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowance_id: WireUserId
    status: Literal["observed"] = "observed"
    product_id: str = Field(min_length=1)
    metric_key: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    quantity: Counter
    successful_used: Counter
    reserved: Counter
    remaining: Counter
    available: Counter
    read_at: AwareDatetime


class PaidUsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    tenant_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    user_id: WireUserId
    items: list[Annotated[ObservedUsage | UnobservedUsage, Field(discriminator="status")]] = Field(
        min_length=1, max_length=100
    )


def _read(
    factory: SessionFactory,
    owner: ExecutionOwner,
    allowance_ids: list[str],
    *,
    product_id: str | None = None,
) -> PaidUsageResponse:
    if len(set(allowance_ids)) != len(allowance_ids):
        raise ApiError(
            status_code=422, code="usage_query_invalid", message="Allowance IDs must be distinct."
        )
    items: list[ObservedUsage | UnobservedUsage] = []
    try:
        # No commit, locks, inserts or source/config lookups on a historical read.
        with factory() as session:
            repository = PaidAllowanceUsageRepository(session)
            for identity in allowance_ids:
                bucket = repository.get_owned_allowance(owner, identity)
                if bucket is None or (
                    product_id is not None and bucket.allowance.product_id != product_id
                ):
                    items.append(UnobservedUsage(allowance_id=identity))
                    continue
                state = consumption_from_bucket(owner, bucket)
                binding = bucket.allowance
                items.append(
                    ObservedUsage(
                        allowance_id=identity,
                        product_id=binding.product_id,
                        metric_key=binding.metric_key,
                        unit=binding.unit,
                        quantity=state.quantity,
                        successful_used=state.successful_used,
                        reserved=state.reserved,
                        remaining=state.remaining,
                        available=state.available,
                        read_at=state.read_at,
                    )
                )
    except SQLAlchemyError:
        raise ApiError(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            code="paid_usage_unavailable",
            message="Usage is unavailable.",
        ) from None
    return PaidUsageResponse(
        tenant_id=owner.tenant_id,
        region=owner.region,
        user_id=owner.owner_id,
        items=items,
    )


@router.get(
    "/internal/v1/usage/{user_id}",
    response_model=PaidUsageResponse,
    summary="Read actual usage for 1–100 distinct allowances",
)
def internal_paid_usage(
    user_id: WireUserId,
    tenant_id: Annotated[str, Query(min_length=1)],
    region: Annotated[str, Query(min_length=1)],
    allowance_id: AllowanceIds,
    request: Request,
    principal: Annotated[PortalPrincipal, Depends(authenticate_portal)],
    factory: Annotated[SessionFactory, Depends(get_session_factory)],
) -> PaidUsageResponse:
    if (
        PortalPermission.USAGE_READ not in principal.permissions
        or (tenant_id, region) != (principal.tenant_id, principal.region)
        or request.query_params.getlist("tenant_id") != [tenant_id]
        or request.query_params.getlist("region") != [region]
    ):
        raise ApiError(
            status_code=HTTPStatus.FORBIDDEN,
            code="paid_usage_forbidden",
            message="Usage access is forbidden.",
        )
    return _read(
        factory,
        ExecutionOwner(tenant_id, region, ExecutionOwnerKind.portal_user, user_id),
        allowance_id,
    )


@router.get(
    "/v1/products/{product_id}/paid-usage",
    response_model=PaidUsageResponse,
    summary="Read owned current or historical paid usage",
    dependencies=[Depends(HTTPBearer(scheme_name="PortalDelegatedBearer", auto_error=False))],
)
def public_paid_usage(
    product_id: str,
    allowance_id: AllowanceIds,
    principal: Annotated[PortalUserPrincipal, Depends(require_portal_user)],
    factory: Annotated[SessionFactory, Depends(get_session_factory)],
) -> PaidUsageResponse:
    return _read(factory, principal.owner, allowance_id, product_id=product_id)
