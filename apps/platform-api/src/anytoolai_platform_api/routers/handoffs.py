from __future__ import annotations

from typing import Annotated, Any

from anytoolai_platform_api.dependencies import (
    get_config_registry,
    get_session_factory,
    get_settings,
)
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.schemas import (
    ErrorResponse,
    HandoffAcceptRequest,
    HandoffCreateRequest,
    HandoffCreateResponse,
    HandoffPreviewResponse,
)
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.handoffs.models import (
    AcceptHandoffCommand,
    CreateHandoffCommand,
    HandoffPreview,
)
from anytoolai_platform_core.handoffs.payloads import HandoffPayloadBuilder
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.handoffs.service import HandoffAcceptanceExecutionError, HandoffService
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioRuntimeService, ScenarioSessionService
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.repository import JobRepository
from fastapi import APIRouter, Body, Depends

router = APIRouter(prefix="/v1/handoffs", tags=["handoffs"])


@router.post(
    "",
    response_model=HandoffCreateResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_handoff(
    request: Annotated[HandoffCreateRequest, Body()],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HandoffCreateResponse:
    with transaction_boundary(session_factory) as session:
        try:
            created = _service(session, registry).create_handoff(
                CreateHandoffCommand(
                    tenant_id=settings.default_tenant_id,
                    region=settings.default_region,
                    handoff_definition_id=request.handoff_definition_id,
                    source_scenario_session_id=request.source_scenario_session_id,
                    source_artifact_id=request.source_artifact_id,
                )
            )
        except PlatformError as exc:
            raise _api_error(exc) from exc
    return HandoffCreateResponse(
        handoff_id=created.preview.handoff_id,
        handoff_token=created.handoff_token,
        status=created.preview.status.value,
        expires_at=created.preview.expires_at,
    )


@router.get(
    "/{handoff_token}",
    response_model=HandoffPreviewResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_handoff(
    handoff_token: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HandoffPreviewResponse:
    with transaction_boundary(session_factory) as session:
        try:
            preview = _service(session, registry).get_preview(
                handoff_token,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            )
        except PlatformError as exc:
            raise _api_error(exc) from exc
    return _preview_response(preview)


@router.post(
    "/{handoff_token}/accept",
    response_model=HandoffPreviewResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
def accept_handoff(
    handoff_token: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Annotated[HandoffAcceptRequest | None, Body()] = None,
) -> HandoffPreviewResponse:
    accepted = None
    deferred_error: ApiError | None = None
    command = request or HandoffAcceptRequest()
    try:
        with transaction_boundary(session_factory) as session:
            try:
                accepted = _service(session, registry).accept(
                    handoff_token,
                    AcceptHandoffCommand(
                        tenant_id=settings.default_tenant_id,
                        region=settings.default_region,
                        guest_id=command.guest_id,
                        source_frontend_instance_id=command.source_frontend_instance_id,
                    ),
                )
            except PlatformError as exc:
                deferred_error = _api_error(exc)
    except HandoffAcceptanceExecutionError as exc:
        with transaction_boundary(session_factory) as failure_session:
            _service(failure_session, registry).mark_failed(
                exc.handoff_id,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                error_code=exc.error_code,
            )
        raise ApiError(
            status_code=429 if exc.error_code == "quota_exhausted" else 500,
            code=exc.error_code,
            message=(
                "Guest quota exhausted."
                if exc.error_code == "quota_exhausted"
                else "Handoff acceptance failed."
            ),
        ) from exc
    if deferred_error is not None:
        raise deferred_error
    if accepted is None:
        raise RuntimeError("handoff accept did not produce a response")
    return _preview_response(accepted.preview)


@router.post(
    "/{handoff_token}/decline",
    response_model=HandoffPreviewResponse,
    responses={
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        410: {"model": ErrorResponse},
    },
)
def decline_handoff(
    handoff_token: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HandoffPreviewResponse:
    preview = None
    deferred_error: ApiError | None = None
    with transaction_boundary(session_factory) as session:
        try:
            preview = _service(session, registry).decline(
                handoff_token,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            )
        except PlatformError as exc:
            deferred_error = _api_error(exc)
    if deferred_error is not None:
        raise deferred_error
    if preview is None:
        raise RuntimeError("handoff decline did not produce a response")
    return _preview_response(preview)


def _service(session: Any, registry: ConfigRegistry) -> HandoffService:
    emitter = EventEmitter(EventLogRepository(session))
    sessions = ScenarioSessionRepository(session)
    jobs = JobRepository(session)
    guests = GuestIdentityRepository(session)
    quota = GuestQuotaService(
        config_registry=registry,
        quota_repository=QuotaUsageRepository(session),
        guest_repository=guests,
        event_emitter=emitter,
    )
    scenario_runtime = ScenarioRuntimeService(
        config_registry=registry,
        session_repository=sessions,
        session_service=ScenarioSessionService(sessions, emitter),
        job_repository=jobs,
        event_emitter=emitter,
        quota_service=quota,
    )
    return HandoffService(
        config_registry=registry,
        repository=HandoffRepository(session),
        payload_builder=HandoffPayloadBuilder(
            config_registry=registry,
            session_repository=sessions,
            job_repository=jobs,
            artifact_repository=ArtifactRepository(session),
        ),
        scenario_runtime=scenario_runtime,
        scenario_repository=sessions,
        guest_repository=guests,
        event_emitter=emitter,
    )


def _preview_response(preview: HandoffPreview) -> HandoffPreviewResponse:
    return HandoffPreviewResponse(
        handoff_id=preview.handoff_id,
        status=preview.status.value,
        source_product_id=preview.source_product_id,
        source_product_display_name=preview.source_product_display_name,
        target_product_id=preview.target_product_id,
        target_product_display_name=preview.target_product_display_name,
        target_scenario_id=preview.target_scenario_id,
        preview=preview.preview,
        expires_at=preview.expires_at,
        target_scenario_session_id=preview.target_scenario_session_id,
        target_job_id=preview.target_job_id,
    )


def _api_error(error: PlatformError) -> ApiError:
    if error.code in {"handoff_not_found", "handoff_source_invalid"}:
        status = 404
    elif error.code == "handoff_expired":
        status = 410
    elif error.code == "quota_exhausted":
        status = 429
    else:
        status = 409
    return ApiError(status_code=status, code=error.code, message=str(error))
