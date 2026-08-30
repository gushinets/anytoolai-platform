from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime, time
from pathlib import Path
from threading import Lock
from typing import Annotated, Any

import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeBootstrapResult
from anytoolai_platform_api.dependencies import get_runtime, get_settings
from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.schemas import DemoRunRequest, ErrorResponse, ScenarioStartResponse
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityService
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioRuntimeService, ScenarioSessionService
from anytoolai_platform_core.storage.db import jobs_table, scenario_sessions_table
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from fastapi import APIRouter, Body, Depends, Header
from fastapi.responses import FileResponse

router = APIRouter(tags=["stakeholder-demo"])

_ASSET_ROOT = Path(__file__).resolve().parents[1] / "static" / "demo"
_DEMO_ACCESS_CODE_ENV = "ANYTOOLAI_DEMO_ACCESS_CODE"
_LIVE_CANARY_TOKEN_ENV = "ANYTOOLAI_LIVE_CANARY_TOKEN"
_PRODUCT_ID = "kernel_demo"
_FRONTEND_ID = "web_mirror"
_DAILY_LIMIT = 50
_MAX_SOURCE_TEXT_LENGTH = 4_000
_START_LOCK = Lock()


@dataclass(frozen=True)
class DemoDefinition:
    scenario_id: str
    include_analysis_fields: bool = False


_DEMO_DEFINITIONS = {
    "analyze": DemoDefinition(
        scenario_id="kernel_demo.composite_analyze_and_clarify_live_smoke_v1",
        include_analysis_fields=True,
    ),
    "evaluate": DemoDefinition(
        scenario_id="kernel_demo.composite_evaluate_match_live_smoke_v1",
    ),
    "write": DemoDefinition(
        scenario_id="kernel_demo.composite_shape_and_write_live_smoke_v1",
    ),
}
_ALLOWLISTED_SCENARIO_IDS = tuple(
    definition.scenario_id for definition in _DEMO_DEFINITIONS.values()
)
_ANALYZE_FIELDS = [
    {
        "name": "deadline",
        "type": "string",
        "description": "Project deadline mentioned in the text.",
        "required": True,
    },
    {
        "name": "budget",
        "type": "string",
        "description": "Budget mentioned in the text.",
        "required": False,
    },
    {
        "name": "deliverables",
        "type": "array_of_strings",
        "description": "Deliverables mentioned in the text.",
        "required": False,
    },
]


@router.get("/demo", include_in_schema=False)
def get_demo_page() -> FileResponse:
    return FileResponse(_ASSET_ROOT / "index.html", media_type="text/html; charset=utf-8")


@router.get("/demo/demo.css", include_in_schema=False)
def get_demo_styles() -> FileResponse:
    return FileResponse(_ASSET_ROOT / "demo.css", media_type="text/css; charset=utf-8")


@router.get("/demo/demo.js", include_in_schema=False)
def get_demo_script() -> FileResponse:
    return FileResponse(
        _ASSET_ROOT / "demo.js",
        media_type="application/javascript; charset=utf-8",
    )


@router.post(
    "/v1/demo/runs",
    response_model=ScenarioStartResponse,
    summary="Start an allowlisted stakeholder demo workflow",
    responses={
        401: {"model": ErrorResponse, "description": "Demo access denied."},
        409: {"model": ErrorResponse, "description": "Another demo run is active."},
        422: {"model": ErrorResponse, "description": "Demo input is invalid."},
        429: {"model": ErrorResponse, "description": "Daily demo limit exhausted."},
        503: {"model": ErrorResponse, "description": "Demo runtime is unavailable."},
    },
)
def start_demo_run(
    request: Annotated[DemoRunRequest, Body()],
    runtime: Annotated[RuntimeBootstrapResult, Depends(get_runtime)],
    settings: Annotated[Settings, Depends(get_settings)],
    access_code: Annotated[str | None, Header(alias="X-Demo-Access-Code")] = None,
) -> ScenarioStartResponse:
    configured_access_code = os.getenv(_DEMO_ACCESS_CODE_ENV, "")
    live_canary_token = os.getenv(_LIVE_CANARY_TOKEN_ENV, "")
    if not configured_access_code.strip() or not live_canary_token.strip():
        raise _demo_error(503, "demo_unavailable", "Demo is unavailable.")
    if access_code is None or not _access_codes_match(access_code, configured_access_code):
        raise _demo_error(401, "demo_access_denied", "Demo access denied.")

    definition = _DEMO_DEFINITIONS.get(request.demo_id)
    source_text = request.source_text.strip()
    if definition is None or not source_text or len(source_text) > _MAX_SOURCE_TEXT_LENGTH:
        raise _demo_error(422, "demo_input_invalid", "Demo input is invalid.")

    session_factory = runtime.storage.session_factory
    if session_factory is None:
        raise _demo_error(503, "demo_unavailable", "Demo is unavailable.")

    try:
        with _START_LOCK, transaction_boundary(session_factory) as session:
            if _has_active_demo_job(
                session,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            ):
                raise _demo_error(
                    409,
                    "demo_busy",
                    "Another demo run is already active.",
                )
            if (
                _accepted_demo_count_today(
                    session,
                    tenant_id=settings.default_tenant_id,
                    region=settings.default_region,
                )
                >= _DAILY_LIMIT
            ):
                raise _demo_error(
                    429,
                    "demo_daily_limit_exhausted",
                    "Demo daily limit exhausted.",
                )

            event_emitter = EventEmitter(EventLogRepository(session))
            guest = GuestIdentityService(
                GuestIdentityRepository(session),
                event_emitter,
            ).create_guest(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            )
            snapshot = _runtime_service(
                session=session,
                runtime=runtime,
                event_emitter=event_emitter,
            ).start_session(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                product_id=_PRODUCT_ID,
                scenario_id=definition.scenario_id,
                frontend_id=_FRONTEND_ID,
                input_payload=_runtime_input(definition, source_text),
                guest_id=guest.id,
                live_canary_token=live_canary_token,
            )
    except ApiError:
        raise
    except (PlatformError, sa.exc.SQLAlchemyError) as exc:
        raise _demo_error(503, "demo_unavailable", "Demo is unavailable.") from exc

    return ScenarioStartResponse(
        scenario_session_id=snapshot.scenario_session_id,
        job_id=snapshot.job_id,
        status=snapshot.status.value,
        allowed_next_actions=list(snapshot.allowed_next_actions),
        result_artifact_id=snapshot.result_artifact_id,
    )


def _runtime_input(
    definition: DemoDefinition,
    source_text: str,
) -> dict[str, object]:
    payload: dict[str, object] = {"source_text": source_text}
    if definition.include_analysis_fields:
        payload.update(fields=_ANALYZE_FIELDS, strict=False)
    return payload


def _runtime_service(
    *,
    session: Any,
    runtime: RuntimeBootstrapResult,
    event_emitter: EventEmitter,
) -> ScenarioRuntimeService:
    scenario_repository = ScenarioSessionRepository(session)
    return ScenarioRuntimeService(
        config_registry=runtime.config_registry,
        session_repository=scenario_repository,
        session_service=ScenarioSessionService(scenario_repository, event_emitter),
        job_repository=JobRepository(session),
        event_emitter=event_emitter,
        quota_service=GuestQuotaService(
            config_registry=runtime.config_registry,
            quota_repository=QuotaUsageRepository(session),
            guest_repository=GuestIdentityRepository(session),
            event_emitter=event_emitter,
        ),
    )


def _demo_scope_filters(
    *,
    tenant_id: str,
    region: str,
) -> tuple[sa.ColumnElement[bool], ...]:
    return (
        scenario_sessions_table.c.tenant_id == tenant_id,
        scenario_sessions_table.c.region == region,
        scenario_sessions_table.c.product_id == _PRODUCT_ID,
        scenario_sessions_table.c.frontend_id == _FRONTEND_ID,
        scenario_sessions_table.c.scenario_id.in_(_ALLOWLISTED_SCENARIO_IDS),
    )


def _has_active_demo_job(
    session: Any,
    *,
    tenant_id: str,
    region: str,
) -> bool:
    statement = (
        sa.select(jobs_table.c.id)
        .select_from(
            jobs_table.join(
                scenario_sessions_table,
                jobs_table.c.scenario_session_id == scenario_sessions_table.c.id,
            )
        )
        .where(
            *_demo_scope_filters(tenant_id=tenant_id, region=region),
            jobs_table.c.status.in_((JobStatus.created, JobStatus.running)),
        )
        .limit(1)
    )
    return session.execute(statement).scalar_one_or_none() is not None


def _accepted_demo_count_today(
    session: Any,
    *,
    tenant_id: str,
    region: str,
) -> int:
    now = datetime.now(UTC)
    utc_day_start = datetime.combine(now.date(), time.min, tzinfo=UTC)
    statement = (
        sa.select(sa.func.count())
        .select_from(scenario_sessions_table)
        .where(
            *_demo_scope_filters(tenant_id=tenant_id, region=region),
            scenario_sessions_table.c.created_at >= utc_day_start,
        )
    )
    return int(session.execute(statement).scalar_one())


def _demo_error(status_code: int, code: str, message: str) -> ApiError:
    return ApiError(status_code=status_code, code=code, message=message)


def _access_codes_match(provided: str, configured: str) -> bool:
    return hmac.compare_digest(provided.encode("utf-8"), configured.encode("utf-8"))
