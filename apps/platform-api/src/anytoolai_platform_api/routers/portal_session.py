"""Browser code exchange; original Portal bearer never crosses this boundary."""

from http import HTTPStatus
from typing import Annotated

from anytoolai_platform_api.portal_session import (
    PortalExchangeRequest,
    PortalExchangeResponse,
    PortalSessionClient,
    get_portal_session_client,
)
from anytoolai_platform_api.schemas import ErrorResponse
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/v1/portal-session", tags=["portal-session"])


@router.post(
    "/exchange",
    response_model=PortalExchangeResponse,
    responses={
        status: {"model": ErrorResponse}
        for status in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            HTTPStatus.SERVICE_UNAVAILABLE,
        )
    },
)
def exchange_portal_session(
    payload: PortalExchangeRequest,
    client: Annotated[PortalSessionClient, Depends(get_portal_session_client)],
) -> PortalExchangeResponse:
    return client.exchange(payload)
