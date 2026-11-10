from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from anytoolai_platform_api.dependencies import (
    get_config_registry,
    get_session_factory,
    get_settings,
    require_enabled_product,
)
from anytoolai_platform_api.errors import ApiError, platform_error_to_api_error
from anytoolai_platform_api.paid_access import (
    PAID_RUNTIME_ERROR_RESPONSES,
    AccessSnapshotClient,
    eligible_allowance,
    get_snapshot_client,
    lock_authority,
    optional_portal_user,
    refresh_authority,
    require_session_owner,
)
from anytoolai_platform_api.portal_session import PortalUserPrincipal
from anytoolai_platform_api.schemas import (
    ErrorResponse,
    ScenarioNextActionRequest,
    ScenarioSessionResponse,
    ScenarioStartRequest,
    ScenarioStartResponse,
)
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.quotas.models import PaidAllowance
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import QUOTA_CAPACITY_RESERVED, GuestQuotaService
from anytoolai_platform_core.scenarios.models import ScenarioSessionSnapshot
from anytoolai_platform_core.scenarios.repository import (
    MAX_IDEMPOTENCY_KEY_LENGTH,
    ScenarioSessionRepository,
)
from anytoolai_platform_core.scenarios.runtime_scope import is_public_runtime_session
from anytoolai_platform_core.scenarios.service import ScenarioRuntimeService, ScenarioSessionService
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.repository import JobRepository
from fastapi import APIRouter, Body, Depends, Header

router = APIRouter(tags=["scenario-runtime"])

START_RESPONSE_EXAMPLE = {
    "scenario_session_id": "scenario_session_123",
    "job_id": "job_123",
    "status": "started",
    "allowed_next_actions": [],
    "result_artifact_id": None,
}

SESSION_RESPONSE_EXAMPLE = {
    "scenario_id": "kernel_demo.single_action_smoke_v1",
    "scenario_session_id": "scenario_session_123",
    "job_id": "job_123",
    "status": "completed",
    "current_checkpoint_id": "result_ready",
    "allowed_next_actions": ["copy_result", "create_handoff"],
    "result_artifact_id": "artifact_123",
}

SAFE_404_EXAMPLE = {
    "error": {
        "code": "scenario_not_found",
        "message": "Scenario not found.",
        "request_id": "req_123",
    }
}

SAFE_GUEST_404_EXAMPLE = {
    "error": {
        "code": "guest_identity_not_found",
        "message": "Guest identity not found.",
        "request_id": "req_123",
    }
}

SAFE_409_EXAMPLE = {
    "error": {
        "code": "scenario_checkpoint_conflict",
        "message": "Scenario checkpoint no longer matches the requested action.",
        "request_id": "req_123",
    }
}

SAFE_422_EXAMPLE = {
    "error": {
        "code": "scenario_input_invalid",
        "message": "Scenario input must be a JSON object.",
        "request_id": "req_123",
    }
}

SAFE_GUEST_422_EXAMPLE = {
    "error": {
        "code": "guest_identity_required",
        "message": "Guest identity is required for this product.",
        "request_id": "req_123",
    }
}

SAFE_IDEMPOTENCY_KEY_INVALID_422_EXAMPLE = {
    "error": {
        "code": "idempotency_key_invalid",
        "message": f"Idempotency-Key must be at most {MAX_IDEMPOTENCY_KEY_LENGTH} characters.",
        "request_id": "req_123",
    }
}

SAFE_429_EXAMPLE = {
    "error": {
        "code": "quota_exhausted",
        "message": "Guest quota exhausted.",
        "request_id": "req_123",
    }
}

SAFE_CAPACITY_RESERVED_429_EXAMPLE = {
    "error": {
        "code": QUOTA_CAPACITY_RESERVED,
        "message": "Quota capacity is temporarily reserved.",
        "request_id": "req_123",
    }
}

SAFE_IDEMPOTENCY_CONFLICT_409_EXAMPLE = {
    "error": {
        "code": "idempotency_key_conflict",
        "message": "Idempotency-Key was already used with a different request.",
        "request_id": "req_123",
    }
}


@router.post(
    "/v1/products/{product_id}/scenarios/{scenario_id}/start",
    response_model=ScenarioStartResponse,
    summary="Create a scenario session and queue workflow execution",
    responses={
        **PAID_RUNTIME_ERROR_RESPONSES,
        200: {
            "description": "Stable queue-and-return response for CE polling.",
            "content": {"application/json": {"example": START_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": (
                "Safe response when the scenario is unknown for the product or the supplied "
                "guest identity is unknown."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "scenario_not_found": {
                            "summary": "Scenario is unknown for the product.",
                            "value": SAFE_404_EXAMPLE,
                        },
                        "guest_not_found": {
                            "summary": "Supplied guest identity is unknown.",
                            "value": SAFE_GUEST_404_EXAMPLE,
                        },
                    }
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": (
                "Idempotency-Key was reused with a request whose scope or input does not "
                "match the original request. No new scenario session is created and quota "
                "is not consumed; retry with a new Idempotency-Key or the original request."
            ),
            "content": {"application/json": {"example": SAFE_IDEMPOTENCY_CONFLICT_409_EXAMPLE}},
        },
        422: {
            "model": ErrorResponse,
            "description": (
                "Safe validation response for unsupported frontend, invalid input, missing "
                "guest identity, or an oversized Idempotency-Key."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_input": {
                            "summary": "Scenario input is not a JSON object.",
                            "value": SAFE_422_EXAMPLE,
                        },
                        "guest_required": {
                            "summary": "Quota-protected product requires guest_id.",
                            "value": SAFE_GUEST_422_EXAMPLE,
                        },
                        "idempotency_key_invalid": {
                            "summary": "Idempotency-Key exceeds the maximum length.",
                            "value": SAFE_IDEMPOTENCY_KEY_INVALID_422_EXAMPLE,
                        },
                    }
                }
            },
        },
        429: {
            "model": ErrorResponse,
            "description": (
                "Quota exhausted or capacity temporarily reserved. The rejected start leaves "
                "no scenario session, job or reservation. A temporary reserve does not mean "
                "the allowance is exhausted."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "quota_exhausted": {"value": SAFE_429_EXAMPLE},
                        "quota_capacity_reserved": {"value": SAFE_CAPACITY_RESERVED_429_EXAMPLE},
                    }
                }
            },
        },
    },
)
def start_scenario(
    product_id: str,
    scenario_id: str,
    request: Annotated[ScenarioStartRequest, Body()],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
    principal: Annotated[PortalUserPrincipal | None, Depends(optional_portal_user)],
    snapshot_client: Annotated[AccessSnapshotClient, Depends(get_snapshot_client)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    live_canary_token: Annotated[str | None, Header(alias="X-Live-Canary-Token")] = None,
) -> ScenarioStartResponse:
    values = dict(
        tenant_id=settings.default_tenant_id,
        region=settings.default_region,
        product_id=product_id,
        scenario_id=scenario_id,
        frontend_id=request.frontend_id,
        input_payload=request.input,
        guest_id=request.guest_id,
        user_id=request.user_id,
        source_frontend_instance_id=request.source_frontend_instance_id,
        idempotency_key=idempotency_key,
        live_canary_token=live_canary_token,
        execution_owner=None if principal is None else principal.owner,
    )
    try:
        if principal is not None:
            # Replay precedes refresh, sales flags and all mutable admission configuration.
            try:
                with transaction_boundary(session_factory) as session:
                    runtime = _runtime_service(
                        session=session, registry=registry, paid_admission=_needs_refresh
                    )
                    snapshot = runtime.start_session(**values)
                return ScenarioStartResponse.model_validate(_start_response_payload(snapshot))
            except _RefreshRequired:
                refresh_authority(session_factory, principal, snapshot_client)
        with transaction_boundary(session_factory) as session:
            if principal is not None:
                lock_authority(session, principal.owner)

            def admit_paid_start(product: str, scenario: str) -> PaidAllowance:
                if principal is None:
                    raise RuntimeError("Paid admission requires a trusted principal")
                require_enabled_product(product, settings)
                return eligible_allowance(session, principal, registry, product, scenario)

            runtime = _runtime_service(
                session=session,
                registry=registry,
                paid_admission=None if principal is None else admit_paid_start,
            )
            if principal is None:
                require_enabled_product(product_id, settings)
            snapshot = runtime.start_session(**values)
            if not snapshot.is_replay and principal is not None:
                # Resample database wall time after every bucket/reservation wait.
                eligible_allowance(session, principal, registry, product_id, scenario_id)
    except PlatformError as exc:
        raise _to_api_error(exc) from exc
    return ScenarioStartResponse.model_validate(_start_response_payload(snapshot))


class _RefreshRequired(Exception):
    pass


def _needs_refresh(product_id: str, scenario_id: str) -> PaidAllowance:
    raise _RefreshRequired()


@router.get(
    "/v1/scenario-sessions/{scenario_session_id}",
    response_model=ScenarioSessionResponse,
    summary="Get frontend-safe scenario session state",
    responses={
        **PAID_RUNTIME_ERROR_RESPONSES,
        200: {
            "description": "Frontend-safe session snapshot for polling.",
            "content": {"application/json": {"example": SESSION_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe response when the scenario session is unknown.",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "scenario_session_not_found",
                            "message": "Scenario session not found.",
                            "request_id": "req_123",
                        }
                    }
                }
            },
        },
    },
)
def get_scenario_session(
    scenario_session_id: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
    principal: Annotated[PortalUserPrincipal | None, Depends(optional_portal_user)],
) -> ScenarioSessionResponse:
    with transaction_boundary(session_factory) as session:
        require_session_owner(session, scenario_session_id, settings, principal)
        _require_public_session(
            ScenarioSessionRepository(session),
            scenario_session_id,
            tenant_id=settings.default_tenant_id,
            region=settings.default_region,
        )
        snapshot = _wrap_platform_errors(
            lambda: _runtime_service(
                session=session,
                registry=registry,
            ).get_session_snapshot(
                scenario_session_id,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            )
        )
    return ScenarioSessionResponse.model_validate(_session_response_payload(snapshot))


@router.post(
    "/v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id}",
    response_model=ScenarioSessionResponse,
    summary="Validate and record a frontend next-action click",
    responses={
        **PAID_RUNTIME_ERROR_RESPONSES,
        200: {
            "description": "Validated next action with the current safe session snapshot.",
            "content": {"application/json": {"example": SESSION_RESPONSE_EXAMPLE}},
        },
        404: {
            "model": ErrorResponse,
            "description": "Safe response when the scenario session is unknown.",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "scenario_session_not_found",
                            "message": "Scenario session not found.",
                            "request_id": "req_123",
                        }
                    }
                }
            },
        },
        409: {
            "model": ErrorResponse,
            "description": "Safe response for stale checkpoint or disallowed action.",
            "content": {"application/json": {"example": SAFE_409_EXAMPLE}},
        },
    },
)
def post_next_action(
    scenario_session_id: str,
    next_action_id: str,
    request: Annotated[ScenarioNextActionRequest, Body()],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
    principal: Annotated[PortalUserPrincipal | None, Depends(optional_portal_user)],
) -> ScenarioSessionResponse:
    with transaction_boundary(session_factory) as session:
        require_session_owner(session, scenario_session_id, settings, principal)
        _require_public_session(
            ScenarioSessionRepository(session),
            scenario_session_id,
            tenant_id=settings.default_tenant_id,
            region=settings.default_region,
        )
        snapshot = _wrap_platform_errors(
            lambda: _runtime_service(
                session=session,
                registry=registry,
            ).record_next_action(
                scenario_session_id,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                next_action_id=next_action_id,
                checkpoint_id=request.checkpoint_id,
            )
        )
    return ScenarioSessionResponse.model_validate(_session_response_payload(snapshot))


def _runtime_service(
    *,
    session,
    registry: ConfigRegistry,
    paid_admission: Callable[[str, str], PaidAllowance] | None = None,
) -> ScenarioRuntimeService:
    event_emitter = EventEmitter(EventLogRepository(session))
    session_repository = ScenarioSessionRepository(session)
    return ScenarioRuntimeService(
        config_registry=registry,
        paid_admission=paid_admission,
        session_repository=session_repository,
        session_service=ScenarioSessionService(session_repository, event_emitter),
        job_repository=JobRepository(session),
        event_emitter=event_emitter,
        quota_service=GuestQuotaService(
            config_registry=registry,
            quota_repository=QuotaUsageRepository(session),
            guest_repository=GuestIdentityRepository(session),
            event_emitter=event_emitter,
        ),
    )


def _start_response_payload(snapshot: ScenarioSessionSnapshot) -> dict[str, object]:
    return {
        "scenario_session_id": snapshot.scenario_session_id,
        "job_id": snapshot.job_id,
        "status": snapshot.status.value,
        "allowed_next_actions": list(snapshot.allowed_next_actions),
        "result_artifact_id": snapshot.result_artifact_id,
    }


def _session_response_payload(snapshot: ScenarioSessionSnapshot) -> dict[str, object]:
    payload = _start_response_payload(snapshot)
    payload["current_checkpoint_id"] = snapshot.current_checkpoint_id
    payload["scenario_id"] = snapshot.scenario_id
    return payload


def _status_code_for_platform_error(error: PlatformError) -> int:
    if error.code in {
        "guest_identity_not_found",
        "scenario_not_found",
        "scenario_session_not_found",
    }:
        return 404
    if error.code in {
        "scenario_checkpoint_conflict",
        "scenario_checkpoint_not_actionable",
        "scenario_next_action_not_allowed",
        "idempotency_key_conflict",
        "paid_allowance_conflict",
    }:
        return 409
    if error.code in {"quota_exhausted", QUOTA_CAPACITY_RESERVED}:
        return 429
    if error.code in {
        "guest_identity_required",
        "scenario_frontend_invalid",
        "scenario_input_invalid",
        "idempotency_key_invalid",
        "idempotency_key_required",
        "execution_owner_invalid",
        "paid_allowance_invalid",
    }:
        return 422
    return 500


def _to_api_error(error: PlatformError) -> ApiError:
    return platform_error_to_api_error(error, status_code=_status_code_for_platform_error(error))


def _wrap_platform_errors(callable_):
    try:
        return callable_()
    except PlatformError as exc:
        raise _to_api_error(exc) from exc


def _require_public_session(
    repository: ScenarioSessionRepository,
    scenario_session_id: str,
    *,
    tenant_id: str,
    region: str,
) -> None:
    record = repository.get_in_scope(
        scenario_session_id,
        tenant_id=tenant_id,
        region=region,
    )
    if record is not None and not is_public_runtime_session(record):
        raise ApiError(
            status_code=404,
            code="scenario_session_not_found",
            message="Scenario session not found.",
        )
