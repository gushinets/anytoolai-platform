from dataclasses import asdict
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated

from anytoolai_platform_api.dependencies import get_config_registry
from anytoolai_platform_api.manifest_auth import PortalPrincipal, authorize_manifest_read
from anytoolai_platform_api.schemas import CapabilityManifestResponse, ErrorResponse
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.products.capabilities import project_capability_manifest
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/internal/v1", tags=["capability-manifest"])


@router.get(
    "/capability-manifest",
    response_model=CapabilityManifestResponse,
    responses={
        status: {"model": ErrorResponse}
        for status in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.UNPROCESSABLE_ENTITY,
            HTTPStatus.INTERNAL_SERVER_ERROR,
            HTTPStatus.SERVICE_UNAVAILABLE,
        )
    },
)
def get_capability_manifest(
    principal: Annotated[PortalPrincipal, Depends(authorize_manifest_read)],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
) -> CapabilityManifestResponse:
    manifest = project_capability_manifest(
        registry, tenant_id=principal.tenant_id, region=principal.region
    )
    return CapabilityManifestResponse(
        **asdict(manifest),
        manifest_version=manifest.manifest_version,
        generated_at=datetime.now(UTC),
    )
