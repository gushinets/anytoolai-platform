from __future__ import annotations

from typing import Annotated, Any

from anytoolai_platform_api.dependencies import (
    get_config_registry,
    get_session_factory,
    get_settings,
)
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.schemas import ErrorResponse, ResultArtifactResponse
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.results.service import ResultArtifactView, ResultService
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.repository import JobRepository
from fastapi import APIRouter, Depends

router = APIRouter(tags=["results"])

RESULT_RESPONSE_EXAMPLE = {
    "result_artifact_id": "artifact_123",
    "scenario_session_id": "scenario_session_123",
    "job_id": "job_123",
    "workflow_id": "kernel_demo.single_action_extract_v1",
    "workflow_version": 1,
    "schema_ref": "kernel_demo.extract_output_v1",
    "schema_version": 1,
    "created_at": "2026-01-01T00:00:00Z",
    "output": {"title": "Example", "fields": ["one", "two"]},
}

SAFE_NOT_FOUND_404_EXAMPLE = {
    "error": {
        "code": "result_artifact_not_found",
        "message": "Result artifact not found.",
        "request_id": "req_123",
    }
}

SAFE_UNAVAILABLE_404_EXAMPLE = {
    "error": {
        "code": "result_artifact_unavailable",
        "message": "Result artifact is not available.",
        "request_id": "req_123",
    }
}


@router.get(
    "/v1/results/{result_artifact_id}",
    response_model=ResultArtifactResponse,
    summary="Get a frontend-safe normalized workflow result artifact",
    responses={
        200: {
            "description": "Frontend-safe normalized canonical workflow result.",
            "content": {"application/json": {"example": RESULT_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": (
                "Safe response when the artifact is unknown, out of tenant/region scope, "
                "or is not an available canonical frontend-safe result (raw/debug artifact, "
                "unfinished job, or a schema/version mismatch)."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "not_found": {
                            "summary": "Artifact is unknown or out of scope.",
                            "value": SAFE_NOT_FOUND_404_EXAMPLE,
                        },
                        "unavailable": {
                            "summary": "Artifact is not a canonical frontend-safe result.",
                            "value": SAFE_UNAVAILABLE_404_EXAMPLE,
                        },
                    }
                }
            },
        },
    },
)
def get_result_artifact(
    result_artifact_id: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResultArtifactResponse:
    with transaction_boundary(session_factory) as session:
        try:
            view = ResultService(
                config_registry=registry,
                artifact_repository=ArtifactRepository(session),
                job_repository=JobRepository(session),
            ).get_result(
                result_artifact_id,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            )
        except PlatformError as exc:
            raise _to_api_error(exc) from exc
    return ResultArtifactResponse.model_validate(_result_response_payload(view))


def _result_response_payload(view: ResultArtifactView) -> dict[str, object]:
    return {
        "result_artifact_id": view.artifact_id,
        "scenario_session_id": view.scenario_session_id,
        "job_id": view.job_id,
        "workflow_id": view.workflow_id,
        "workflow_version": view.workflow_version,
        "schema_ref": view.schema_ref,
        "schema_version": view.schema_version,
        "created_at": view.created_at,
        "output": view.output,
    }


def _to_api_error(error: PlatformError) -> ApiError:
    status_code = (
        404
        if error.code in {"result_artifact_not_found", "result_artifact_unavailable"}
        else 500
    )
    return ApiError(status_code=status_code, code=error.code, message=str(error))
