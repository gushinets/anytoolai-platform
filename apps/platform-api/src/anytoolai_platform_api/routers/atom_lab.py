from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import re
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

from anytoolai_platform_actions.structured_llm.cross_validation import (
    ValidatorRefNotFoundError,
    build_input_validator,
)
from anytoolai_platform_api.atom_lab.access import require_atom_lab_access
from anytoolai_platform_api.atom_lab.catalog import (
    AtomLabCatalogConfigError,
    build_atom_catalog,
    get_atom_catalog_entry,
)
from anytoolai_platform_api.bootstrap import RuntimeBootstrapResult
from anytoolai_platform_api.dependencies import (
    get_atom_lab_run_settings,
    get_atom_lab_session_factory,
    get_config_registry,
    get_model_catalog_settings,
    get_runtime,
    get_settings,
)
from anytoolai_platform_api.errors import AtomLabApiError
from anytoolai_platform_api.schemas import (
    AtomLabAtomResponse,
    AtomLabErrorResponse,
    AtomLabModelRefreshResponse,
    AtomLabModelResponse,
    AtomLabModelsResponse,
    AtomLabPresetCreatedResponse,
    AtomLabPresetExportResponse,
    AtomLabPresetListResponse,
    AtomLabPresetNextVersionRequest,
    AtomLabPresetSummaryResponse,
    AtomLabPresetVersionListResponse,
    AtomLabPresetVersionRequest,
    AtomLabPresetVersionResponse,
    AtomLabPresetVersionSummaryResponse,
    AtomLabRunAcceptedResponse,
    AtomLabRunDetailResponse,
    AtomLabRunListResponse,
    AtomLabRunRequest,
)
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.actions.runner import ActionInputValidationError
from anytoolai_platform_core.atom_lab.models import (
    ATOM_LAB_MODEL_PREFIX,
    AtomLabPresetIdentityRecord,
    AtomLabPresetVersionRecord,
    is_addressable_atom_lab_model,
)
from anytoolai_platform_core.atom_lab.repository import (
    AtomLabPresetRepository,
    AtomLabRunRepository,
    PresetAtomMismatchError,
    PresetSourceRunError,
    PresetVersionConflictError,
)
from anytoolai_platform_core.atom_lab.service import (
    AtomLabActiveRunLimitError,
    AtomLabDailyLimitError,
    AtomLabIdempotencyConflictError,
    AtomLabRunAdmissionRequest,
    AtomLabRunHistoryService,
    AtomLabRunService,
)
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.providers.catalog_repository import (
    ModelCatalogRepository,
    ModelCatalogState,
)
from anytoolai_platform_core.providers.catalog_settings import ModelCatalogSettings
from anytoolai_platform_core.providers.models import (
    ModelCatalogCompatibility,
    ModelCatalogRefreshStatus,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, DisconnectionError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as DatabaseTimeoutError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["atom-lab"])
protected_router = APIRouter(
    prefix="/v1/atom-lab",
    tags=["atom-lab"],
    dependencies=[Depends(require_atom_lab_access)],
)

_ASSET_ROOT = Path(__file__).resolve().parents[1] / "static" / "atom_lab"
_ERROR_RESPONSES = {
    401: {"model": AtomLabErrorResponse, "description": "Atom Lab access denied."},
    422: {"model": AtomLabErrorResponse, "description": "Atom Lab request validation failed."},
    503: {"model": AtomLabErrorResponse, "description": "Atom Lab is not configured."},
}
_PRESET_PAGE_DEFAULT = 20
_PRESET_PAGE_MAX = 100
_PRESET_CURSOR_PARTS = 2
_PRESET_ID_MAX_LENGTH = 128
_POSTGRESQL_INTEGER_MAX = 2_147_483_647
_IDEMPOTENCY_KEY_MAX_LENGTH = 128
_RUN_PAGE_DEFAULT = 20
_RUN_PAGE_MAX = 100
_RUN_CURSOR_MAX_LENGTH = 1024
_RUN_CURSOR_PARTS = 3
_RUN_CURSOR_VERSION = "runs-v1"
_RUN_ID_MAX_LENGTH = 128
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")


def require_atom_lab_run_access(
    access_code: Annotated[str | None, Header(alias="X-Atom-Lab-Access-Code")] = None,
) -> None:
    try:
        require_atom_lab_access(access_code)
    except AtomLabApiError as exc:
        code = "access_denied" if exc.status_code == HTTPStatus.UNAUTHORIZED else "lab_unavailable"
        raise AtomLabApiError(status_code=exc.status_code, code=code, message=exc.message) from exc


run_router = APIRouter(
    prefix="/v1/atom-lab",
    tags=["atom-lab"],
    dependencies=[Depends(require_atom_lab_run_access)],
)


def get_atom_lab_run_session_factory(
    runtime: Annotated[RuntimeBootstrapResult, Depends(get_runtime)],
) -> Any:
    try:
        return get_atom_lab_session_factory(runtime)
    except AtomLabApiError as exc:
        raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "lab_unavailable") from exc


def _run_error(status: HTTPStatus, code: str, path: str | None = None) -> AtomLabApiError:
    return AtomLabApiError(
        status_code=status,
        code=code,
        message="Запуск Atom Lab не может быть принят.",
        field_errors=[] if path is None else [_field_error(path)],
    )


async def _read_run_payload(
    request: Request,
    settings: Annotated[Settings, Depends(get_atom_lab_run_settings)],
) -> AtomLabRunRequest:
    # No FastAPI Body parameter: authentication and the stream bound precede JSON parsing.
    key = request.headers.get("Idempotency-Key")
    if key is None or not key.strip() or len(key) > _IDEMPOTENCY_KEY_MAX_LENGTH:
        raise _run_error(HTTPStatus.UNPROCESSABLE_ENTITY, "input_invalid", "Idempotency-Key")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > settings.atom_lab_run_body_max_bytes:
            raise _run_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large")
        raw.extend(chunk)
    try:
        payload = AtomLabRunRequest.model_validate_json(raw)
        _run_input_bytes(payload)
        payload.prompt.encode("utf-8")
    except ValidationError as exc:
        # Only expose this fixed, trusted path; never echo attacker-controlled locations.
        path = (
            "preset_ref.preset_id"
            if any(error["loc"] == ("preset_ref", "preset_id") for error in exc.errors())
            else None
        )
        raise _run_error(HTTPStatus.UNPROCESSABLE_ENTITY, "input_invalid", path) from exc
    except (ValueError, UnicodeError, RecursionError) as exc:
        # Validation locations can contain attacker-controlled object keys; omit them here.
        raise _run_error(HTTPStatus.UNPROCESSABLE_ENTITY, "input_invalid") from exc
    if _contains_nul(payload.input):
        raise _run_error(HTTPStatus.UNPROCESSABLE_ENTITY, "input_invalid", "input")
    if "\x00" in payload.prompt:
        raise _run_error(HTTPStatus.UNPROCESSABLE_ENTITY, "input_invalid", "prompt")
    if not payload.prompt.strip():
        raise _run_error(HTTPStatus.UNPROCESSABLE_ENTITY, "input_invalid", "prompt")
    return payload


def _contains_nul(value: Any) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, dict):
        return any(_contains_nul(key) or _contains_nul(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_nul(item) for item in value)
    return False


def _run_input_bytes(payload: AtomLabRunRequest) -> bytes:
    return json.dumps(
        payload.input,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _validate_run_sizes(payload: AtomLabRunRequest, settings: Settings) -> None:
    if len(_run_input_bytes(payload)) > settings.atom_lab_run_input_max_bytes:
        raise _run_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large", "input")
    if len(payload.prompt.encode("utf-8")) > settings.atom_lab_run_prompt_max_bytes:
        raise _run_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "payload_too_large", "prompt")


def _run_request_schema() -> dict[str, Any]:
    # The manually bounded body still exposes its actual Pydantic contract in OpenAPI.
    schema = AtomLabRunRequest.model_json_schema()
    definitions = schema.pop("$defs", {})

    def inline(value: Any) -> Any:
        if isinstance(value, dict):
            if "$ref" in value:
                return inline(definitions[value["$ref"].rsplit("/", 1)[-1]])
            return {key: inline(item) for key, item in value.items()}
        if isinstance(value, list):
            return [inline(item) for item in value]
        return value

    return inline(schema)


@run_router.post(
    "/runs",
    status_code=HTTPStatus.ACCEPTED,
    response_model=AtomLabRunAcceptedResponse,
    responses={
        **_ERROR_RESPONSES,
        **{status: {"model": AtomLabErrorResponse} for status in (404, 409, 429)},
        413: {
            "model": AtomLabErrorResponse,
            "description": "Atom Lab payload is too large.",
        },
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": _run_request_schema()}},
        }
    },
)
def start_run(
    payload: Annotated[AtomLabRunRequest, Depends(_read_run_payload)],
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    settings: Annotated[Settings, Depends(get_atom_lab_run_settings)],
    catalog_settings: Annotated[ModelCatalogSettings, Depends(get_model_catalog_settings)],
    session_factory: Annotated[Any, Depends(get_atom_lab_run_session_factory)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)],
) -> AtomLabRunAcceptedResponse:
    try:
        with transaction_boundary(session_factory) as session:
            state = ModelCatalogRepository(session).get(catalog_settings.account_scope)
            model = (
                next(
                    (
                        item
                        for item in state.items
                        if item.model_id == payload.model_id.removeprefix(ATOM_LAB_MODEL_PREFIX)
                    ),
                    None,
                )
                if state
                else None
            )
            admission = AtomLabRunAdmissionRequest(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                atom_id=payload.atom_id.value,
                input_payload=payload.input,
                prompt=payload.prompt,
                model_id=payload.model_id,
                reasoning_effort=payload.reasoning_effort,
                capability_snapshot_id=state.snapshot_id if state and state.snapshot_id else "",
                capability_provenance=model.provenance if model else {},
                idempotency_key=idempotency_key,
                preset_id=payload.preset_ref.preset_id if payload.preset_ref else None,
                preset_version=payload.preset_ref.version if payload.preset_ref else None,
            )

            def validate() -> None:
                _validate_run_sizes(payload, settings)
                if not os.getenv("ANYTOOLAI_LIVE_CANARY_TOKEN", "").strip():
                    raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "lab_unavailable")
                _validate_run_contract(payload, registry)
                if state is None or state.snapshot_id is None:
                    raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "catalog_unavailable")
                if (
                    not is_addressable_atom_lab_model(payload.model_id)
                    or model is None
                    or model.compatibility is not ModelCatalogCompatibility.compatible
                ):
                    raise _run_error(
                        HTTPStatus.UNPROCESSABLE_ENTITY, "model_not_allowed", "model_id"
                    )
                if payload.reasoning_effort is not None and (
                    model.reasoning_supported is not True
                    or model.allowed_reasoning_efforts is None
                    or payload.reasoning_effort not in model.allowed_reasoning_efforts
                ):
                    raise _run_error(
                        HTTPStatus.UNPROCESSABLE_ENTITY, "reasoning_not_allowed", "reasoning_effort"
                    )
                _validate_run_preset(payload, registry, AtomLabPresetRepository(session), settings)

            result = AtomLabRunService(
                session=session,
                config_registry=registry,
                daily_limit=settings.atom_lab_run_daily_limit,
                active_limit=settings.atom_lab_run_active_limit,
            ).start(admission, validate=validate)
    except (
        OperationalError,
        InterfaceError,
        DisconnectionError,
        DatabaseTimeoutError,
        DBAPIError,
    ) as exc:
        logger.warning(
            "atom_lab.run_database_error",
            extra={
                "event": "atom_lab.run_database_error",
                "error_code": "lab_unavailable",
                "exception_type": type(exc).__name__,
            },
        )
        raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "lab_unavailable") from exc
    except AtomLabIdempotencyConflictError as exc:
        raise _run_error(HTTPStatus.CONFLICT, exc.code) from exc
    except (AtomLabActiveRunLimitError, AtomLabDailyLimitError) as exc:
        raise _run_error(HTTPStatus.TOO_MANY_REQUESTS, exc.code) from exc
    except (LookupError, ValueError) as exc:
        raise _run_error(HTTPStatus.CONFLICT, "contract_unavailable") from exc
    return AtomLabRunAcceptedResponse(
        run_id=result.run_id,
        scenario_session_id=result.scenario_session_id,
        job_id=result.job_id,
        status=result.status,
    )


@run_router.get("/runs", response_model=AtomLabRunListResponse, responses=_ERROR_RESPONSES)
def list_runs(
    session_factory: Annotated[Any, Depends(get_atom_lab_run_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=_RUN_PAGE_MAX)] = _RUN_PAGE_DEFAULT,
    cursor: Annotated[str | None, Query(max_length=_RUN_CURSOR_MAX_LENGTH)] = None,
) -> AtomLabRunListResponse:
    before = _decode_run_cursor(cursor) if cursor is not None else None
    try:
        with transaction_boundary(session_factory) as session:
            rows = AtomLabRunRepository(session).history_in_scope(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                limit=limit + 1,
                before=before,
            )
            page = rows[:limit]
            service = AtomLabRunHistoryService(session)
            return AtomLabRunListResponse(
                items=[service.summary(row) for row in page],
                next_cursor=(
                    _encode_run_cursor(page[-1].run.created_at, page[-1].run.id)
                    if len(rows) > limit
                    else None
                ),
            )
    except (OperationalError, InterfaceError, DisconnectionError, DatabaseTimeoutError) as exc:
        raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "lab_unavailable") from exc
    except DBAPIError as exc:
        if not exc.connection_invalidated:
            raise
        raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "lab_unavailable") from exc


def _run_not_found() -> AtomLabApiError:
    return AtomLabApiError(
        status_code=HTTPStatus.NOT_FOUND,
        code="lab_resource_not_found",
        message="Ресурс Atom Lab не найден.",
    )


def _is_valid_run_id(run_id: str) -> bool:
    return len(run_id) <= _RUN_ID_MAX_LENGTH and _RUN_ID_PATTERN.fullmatch(run_id) is not None


def _read_run_id(run_id: str) -> str:
    # Router authentication runs first; invalid path IDs must not reach a database driver.
    if not _is_valid_run_id(run_id):
        raise _run_not_found()
    return run_id


@run_router.get(
    "/runs/{run_id}",
    response_model=AtomLabRunDetailResponse,
    responses={**_ERROR_RESPONSES, 404: {"model": AtomLabErrorResponse}},
)
def get_run(
    run_id: Annotated[str, Depends(_read_run_id)],
    session_factory: Annotated[Any, Depends(get_atom_lab_run_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AtomLabRunDetailResponse:
    try:
        with transaction_boundary(session_factory) as session:
            rows = AtomLabRunRepository(session).history_in_scope(
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
                run_id=run_id,
                limit=1,
            )
            if not rows:
                raise _run_not_found()
            return AtomLabRunDetailResponse.model_validate(
                AtomLabRunHistoryService(session).detail(rows[0])
            )
    except (OperationalError, InterfaceError, DisconnectionError, DatabaseTimeoutError) as exc:
        raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "lab_unavailable") from exc
    except DBAPIError as exc:
        if not exc.connection_invalidated:
            raise
        raise _run_error(HTTPStatus.SERVICE_UNAVAILABLE, "lab_unavailable") from exc


def _encode_run_cursor(created_at: datetime, run_id: str) -> str:
    raw = json.dumps([_RUN_CURSOR_VERSION, created_at.isoformat(), run_id], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_run_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        if len(cursor) > _RUN_CURSOR_MAX_LENGTH:
            raise ValueError
        value = json.loads(_decode_urlsafe_base64(cursor))
        if (
            not isinstance(value, list)
            or len(value) != _RUN_CURSOR_PARTS
            or value[0] != _RUN_CURSOR_VERSION
            or not isinstance(value[1], str)
            or not isinstance(value[2], str)
            or not _is_valid_run_id(value[2])
        ):
            raise ValueError
        created_at = datetime.fromisoformat(value[1])
        if created_at.utcoffset() is None:
            raise ValueError
        return created_at.astimezone(UTC), value[2]
    except (
        ValueError,
        TypeError,
        OverflowError,
        UnicodeError,
        RecursionError,
        binascii.Error,
    ) as exc:
        raise AtomLabApiError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="invalid_cursor",
            message="Курсор списка недействителен.",
            field_errors=[_field_error("cursor")],
        ) from exc


def _validate_run_contract(payload: AtomLabRunRequest, registry: ConfigRegistry) -> None:
    try:
        atom = get_atom_catalog_entry(registry, payload.atom_id.value)
    except AtomLabCatalogConfigError as exc:
        raise _run_error(HTTPStatus.CONFLICT, "contract_unavailable") from exc
    if atom is None:
        raise _run_error(HTTPStatus.NOT_FOUND, "atom_not_found")
    try:
        validate_json_schema(instance=payload.input, schema=atom.input_schema)
        _validate_semantic_input(registry, atom.action_type, payload.input)
    except (JsonSchemaValidationError, ActionInputValidationError) as exc:
        raise _run_error(HTTPStatus.UNPROCESSABLE_ENTITY, "input_invalid", "input") from exc
    except AtomLabApiError as exc:
        raise _run_error(HTTPStatus.CONFLICT, "contract_unavailable") from exc


def _validate_run_preset(
    payload: AtomLabRunRequest,
    registry: ConfigRegistry,
    repository: AtomLabPresetRepository,
    settings: Settings,
) -> None:
    if payload.preset_ref is None:
        return
    preset = repository.get_version(
        payload.preset_ref.preset_id,
        payload.preset_ref.version,
        tenant_id=settings.default_tenant_id,
        region=settings.default_region,
    )
    if preset is None:
        raise _preset_not_found()
    atom = get_atom_catalog_entry(registry, payload.atom_id.value)
    if atom is None:
        raise _run_error(HTTPStatus.CONFLICT, "contract_unavailable")
    expected = (
        payload.atom_id.value,
        atom.base_action_config_id,
        atom.prompt_ref,
        atom.schema_refs.input.schema_ref,
        atom.schema_refs.input.version,
        atom.schema_refs.output.schema_ref,
        atom.schema_refs.output.version,
    )
    actual = (
        preset.atom_id,
        preset.base_action_config_id,
        preset.prompt_ref,
        preset.input_schema_ref,
        preset.input_schema_version,
        preset.output_schema_ref,
        preset.output_schema_version,
    )
    if actual != expected:
        raise _run_error(HTTPStatus.CONFLICT, "preset_mismatch", "preset_ref")


@router.get("/atom-lab", include_in_schema=False)
def get_atom_lab_page() -> FileResponse:
    return FileResponse(_ASSET_ROOT / "index.html", media_type="text/html; charset=utf-8")


@router.get("/atom-lab/atom_lab.css", include_in_schema=False)
def get_atom_lab_styles() -> FileResponse:
    return FileResponse(_ASSET_ROOT / "atom_lab.css", media_type="text/css; charset=utf-8")


@router.get("/atom-lab/atom_lab.js", include_in_schema=False)
def get_atom_lab_script() -> FileResponse:
    return FileResponse(
        _ASSET_ROOT / "atom_lab.js", media_type="application/javascript; charset=utf-8"
    )


@protected_router.get(
    "/atoms",
    response_model=list[AtomLabAtomResponse],
    responses=_ERROR_RESPONSES,
)
def list_atoms(
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
) -> tuple[AtomLabAtomResponse, ...]:
    try:
        return build_atom_catalog(registry)
    except AtomLabCatalogConfigError as exc:
        raise _catalog_unavailable() from exc


@protected_router.get(
    "/atoms/{atom_id}",
    response_model=AtomLabAtomResponse,
    responses={
        **_ERROR_RESPONSES,
        404: {"model": AtomLabErrorResponse, "description": "Atom not found."},
    },
)
def get_atom(
    atom_id: str,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
) -> AtomLabAtomResponse:
    try:
        atom = get_atom_catalog_entry(registry, atom_id)
    except AtomLabCatalogConfigError as exc:
        raise _catalog_unavailable() from exc
    if atom is None:
        raise AtomLabApiError(
            status_code=HTTPStatus.NOT_FOUND,
            code="atom_not_found",
            message="Атом не найден.",
        )
    return atom


@protected_router.get(
    "/models",
    response_model=AtomLabModelsResponse,
    responses=_ERROR_RESPONSES,
)
def list_models(
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[ModelCatalogSettings, Depends(get_model_catalog_settings)],
) -> AtomLabModelsResponse:
    now = utc_now()
    with transaction_boundary(session_factory) as session:
        state = ModelCatalogRepository(session).get(settings.account_scope)
    return _models_response(state, now=now)


@protected_router.post(
    "/models/refresh",
    status_code=HTTPStatus.ACCEPTED,
    response_model=AtomLabModelRefreshResponse,
    responses=_ERROR_RESPONSES,
)
def request_model_refresh(
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[ModelCatalogSettings, Depends(get_model_catalog_settings)],
) -> AtomLabModelRefreshResponse:
    now = utc_now()
    with transaction_boundary(session_factory) as session:
        state = ModelCatalogRepository(session).request_refresh(
            settings.account_scope,
            now=now,
        )
    response = _models_response(state, now=now)
    return AtomLabModelRefreshResponse(
        snapshot_id=response.snapshot_id,
        last_success_at=response.last_success_at,
        stale=response.stale,
        refresh_status=response.refresh_status,
        error=response.error,
    )


@protected_router.post(
    "/presets",
    status_code=HTTPStatus.CREATED,
    response_model=AtomLabPresetCreatedResponse,
    responses={**_ERROR_RESPONSES, 409: {"model": AtomLabErrorResponse}},
)
def create_preset(
    payload: AtomLabPresetVersionRequest,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AtomLabPresetCreatedResponse:
    _validate_preset_payload(payload, registry, settings)
    now = utc_now()
    identity = AtomLabPresetIdentityRecord(
        tenant_id=settings.default_tenant_id,
        region=settings.default_region,
        atom_id=payload.atom_id.value,
        created_at=now,
        updated_at=now,
    )
    version = _preset_version_record(
        identity.id,
        1,
        payload,
        tenant_id=identity.tenant_id,
        region=identity.region,
        created_at=now,
    )
    try:
        with transaction_boundary(session_factory) as session:
            stored = AtomLabPresetRepository(session).create(identity, version)
    except PresetSourceRunError as exc:
        raise _preset_source_invalid() from exc
    return AtomLabPresetCreatedResponse(
        preset_id=stored.preset_id,
        version=stored.version,
        created_at=stored.created_at,
    )


@protected_router.get(
    "/presets",
    response_model=AtomLabPresetListResponse,
    responses=_ERROR_RESPONSES,
)
def list_presets(
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=_PRESET_PAGE_MAX)] = _PRESET_PAGE_DEFAULT,
    cursor: str | None = None,
) -> AtomLabPresetListResponse:
    before = _decode_preset_cursor(cursor) if cursor is not None else None
    with transaction_boundary(session_factory) as session:
        rows = AtomLabPresetRepository(session).list_presets(
            tenant_id=settings.default_tenant_id,
            region=settings.default_region,
            before=before,
            limit=limit + 1,
        )
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = _encode_preset_cursor(last.created_at, last.preset_id)
    return AtomLabPresetListResponse(
        items=[
            AtomLabPresetSummaryResponse.model_validate(row, from_attributes=True) for row in page
        ],
        next_cursor=next_cursor,
    )


@protected_router.post(
    "/presets/{preset_id}/versions",
    status_code=HTTPStatus.CREATED,
    response_model=AtomLabPresetCreatedResponse,
    responses={
        **_ERROR_RESPONSES,
        404: {"model": AtomLabErrorResponse},
        409: {"model": AtomLabErrorResponse},
    },
)
def create_preset_version(
    preset_id: str,
    payload: AtomLabPresetNextVersionRequest,
    registry: Annotated[ConfigRegistry, Depends(get_config_registry)],
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AtomLabPresetCreatedResponse:
    _validate_preset_payload(payload, registry, settings)
    version = _preset_version_record(
        preset_id,
        payload.base_version + 1,
        payload,
        tenant_id=settings.default_tenant_id,
        region=settings.default_region,
        created_at=utc_now(),
    )
    try:
        with transaction_boundary(session_factory) as session:
            stored = AtomLabPresetRepository(session).add_version(
                version,
                base_version=payload.base_version,
            )
    except LookupError as exc:
        raise _preset_not_found() from exc
    except PresetVersionConflictError as exc:
        raise AtomLabApiError(
            status_code=HTTPStatus.CONFLICT,
            code="preset_version_conflict",
            message="Пресет уже содержит более новую версию.",
        ) from exc
    except PresetAtomMismatchError as exc:
        raise _preset_contract_invalid("atom_id") from exc
    except PresetSourceRunError as exc:
        raise _preset_source_invalid() from exc
    return AtomLabPresetCreatedResponse(
        preset_id=stored.preset_id,
        version=stored.version,
        created_at=stored.created_at,
    )


@protected_router.get(
    "/presets/{preset_id}/versions",
    response_model=AtomLabPresetVersionListResponse,
    responses={**_ERROR_RESPONSES, 404: {"model": AtomLabErrorResponse}},
)
def list_preset_versions(
    preset_id: str,
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=_PRESET_PAGE_MAX)] = _PRESET_PAGE_DEFAULT,
    cursor: str | None = None,
) -> AtomLabPresetVersionListResponse:
    before_version = _decode_version_cursor(cursor) if cursor is not None else None
    with transaction_boundary(session_factory) as session:
        repository = AtomLabPresetRepository(session)
        if (
            repository.get_identity(
                preset_id,
                tenant_id=settings.default_tenant_id,
                region=settings.default_region,
            )
            is None
        ):
            raise _preset_not_found()
        rows = repository.list_versions(
            preset_id,
            tenant_id=settings.default_tenant_id,
            region=settings.default_region,
            before_version=before_version,
            limit=limit + 1,
        )
    page = rows[:limit]
    next_cursor = _encode_version_cursor(page[-1].version) if len(rows) > limit else None
    return AtomLabPresetVersionListResponse(
        items=[
            AtomLabPresetVersionSummaryResponse(
                preset_id=row.preset_id,
                version=row.version,
                name=row.name,
                description=row.description,
                atom_id=row.atom_id,
                created_at=row.created_at,
            )
            for row in page
        ],
        next_cursor=next_cursor,
    )


@protected_router.get(
    "/presets/{preset_id}/versions/{version}",
    response_model=AtomLabPresetVersionResponse,
    responses={**_ERROR_RESPONSES, 404: {"model": AtomLabErrorResponse}},
)
def get_preset_version(
    preset_id: str,
    version: int,
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AtomLabPresetVersionResponse:
    stored = _get_preset_version(session_factory, settings, preset_id, version)
    return _preset_version_response(stored)


@protected_router.get(
    "/presets/{preset_id}/versions/{version}/export",
    response_model=AtomLabPresetExportResponse,
    responses={**_ERROR_RESPONSES, 404: {"model": AtomLabErrorResponse}},
)
def export_preset_version(
    preset_id: str,
    version: int,
    session_factory: Annotated[Any, Depends(get_atom_lab_session_factory)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AtomLabPresetExportResponse:
    stored = _get_preset_version(session_factory, settings, preset_id, version)
    detail = _preset_version_response(stored)
    configuration = AtomLabPresetVersionRequest.model_validate(
        detail.model_dump(exclude={"preset_id", "version", "created_at"})
    )
    return AtomLabPresetExportResponse(
        preset_id=preset_id,
        version=version,
        configuration=configuration,
    )


def _models_response(state: ModelCatalogState | None, *, now: datetime) -> AtomLabModelsResponse:
    if state is None:
        return AtomLabModelsResponse(
            items=[],
            snapshot_id=None,
            last_success_at=None,
            stale=True,
            refresh_status=ModelCatalogRefreshStatus.pending,
            error="Каталог моделей ещё не загружен.",
        )
    return AtomLabModelsResponse(
        items=[
            AtomLabModelResponse(
                model_id=item.model_id,
                compatibility=item.compatibility,
                reason=item.reason,
                reasoning_supported=item.reasoning_supported,
                allowed_reasoning_efforts=(
                    None
                    if item.allowed_reasoning_efforts is None
                    else list(item.allowed_reasoning_efforts)
                ),
                provenance={key: dict(value) for key, value in item.provenance.items()},
            )
            for item in state.items
        ],
        snapshot_id=state.snapshot_id,
        last_success_at=state.last_success_at,
        stale=state.is_stale(now),
        refresh_status=state.refresh_status(now),
        error=(
            state.last_error
            if state.last_error is not None
            else "Каталог моделей ещё не загружен."
            if state.snapshot_id is None
            else None
        ),
    )


def _catalog_unavailable() -> AtomLabApiError:
    return AtomLabApiError(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        code="atom_lab_catalog_unavailable",
        message="Каталог Atom Lab недоступен.",
    )


def _validate_preset_payload(
    payload: AtomLabPresetVersionRequest,
    registry: ConfigRegistry,
    settings: Settings,
) -> None:
    try:
        atom = get_atom_catalog_entry(registry, payload.atom_id.value)
    except AtomLabCatalogConfigError as exc:
        raise _catalog_unavailable() from exc
    if atom is None:
        raise _preset_contract_invalid("atom_id")

    expected_refs = atom.schema_refs.model_dump(mode="json")
    field_errors = _validate_required_preset_text(payload)
    if payload.base_action_config_id != atom.base_action_config_id:
        field_errors.append(_field_error("base_action_config_id"))
    if payload.prompt_ref != atom.prompt_ref:
        field_errors.append(_field_error("prompt_ref"))
    if payload.schema_refs.model_dump(mode="json") != expected_refs:
        field_errors.append(_field_error("schema_refs"))
    if not is_addressable_atom_lab_model(payload.model_id):
        field_errors.append(_field_error("model_id"))

    field_errors.extend(_validate_fixed_fields(payload))

    field_errors.extend(
        _validate_example_input(
            payload.example_input,
            registry=registry,
            action_type=atom.action_type,
            input_schema=atom.input_schema,
            max_bytes=settings.atom_lab_preset_example_input_max_bytes,
        )
    )

    if field_errors:
        raise AtomLabApiError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="preset_contract_invalid",
            message="Конфигурация пресета не соответствует контракту атома.",
            field_errors=field_errors,
        )


def _validate_required_preset_text(
    payload: AtomLabPresetVersionRequest,
) -> list[dict[str, str]]:
    return [
        _field_error(field_name)
        for field_name, value in (("name", payload.name), ("prompt", payload.prompt))
        if not value.strip()
    ]


def _validate_example_input(
    example_input: dict[str, Any],
    *,
    registry: ConfigRegistry,
    action_type: str,
    input_schema: dict[str, Any],
    max_bytes: int,
) -> list[dict[str, str]]:
    try:
        serialized = json.dumps(
            example_input,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, UnicodeEncodeError):
        return [_field_error("example_input")]
    if len(serialized) > max_bytes:
        return [_field_error("example_input")]

    try:
        validate_json_schema(instance=example_input, schema=input_schema)
    except JsonSchemaValidationError as exc:
        suffix = ".".join(str(part) for part in exc.absolute_path)
        path = "example_input" if not suffix else f"example_input.{suffix}"
        return [_field_error(path)]

    try:
        _validate_semantic_input(registry, action_type, example_input)
    except ActionInputValidationError:
        return [_field_error("example_input")]
    return []


def _validate_semantic_input(
    registry: ConfigRegistry,
    action_type: str,
    input_payload: dict[str, Any],
) -> None:
    action_definition = registry.get_action_definition(action_type)
    if action_definition is None:
        raise _catalog_unavailable()
    try:
        input_validator = build_input_validator(action_definition)
    except ValidatorRefNotFoundError as exc:
        raise _catalog_unavailable() from exc
    if input_validator is not None:
        input_validator.validate(input_payload=input_payload)


def _validate_fixed_fields(
    payload: AtomLabPresetVersionRequest,
) -> list[dict[str, str]]:
    field_errors: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, field_name in enumerate(payload.fixed_fields):
        path = f"fixed_fields.{index}"
        if not field_name or "." in field_name or field_name not in payload.example_input:
            field_errors.append(_field_error(path))
        if field_name in seen:
            field_errors.append(_field_error("fixed_fields"))
        seen.add(field_name)
    return field_errors


def _preset_version_record(
    preset_id: str,
    version: int,
    payload: AtomLabPresetVersionRequest,
    *,
    tenant_id: str,
    region: str,
    created_at: datetime,
) -> AtomLabPresetVersionRecord:
    return AtomLabPresetVersionRecord(
        preset_id=preset_id,
        version=version,
        name=payload.name,
        description=payload.description,
        atom_id=payload.atom_id.value,
        base_action_config_id=payload.base_action_config_id,
        input_schema_ref=payload.schema_refs.input.schema_ref,
        input_schema_version=payload.schema_refs.input.version,
        output_schema_ref=payload.schema_refs.output.schema_ref,
        output_schema_version=payload.schema_refs.output.version,
        prompt=payload.prompt,
        prompt_ref=payload.prompt_ref,
        model_id=payload.model_id,
        reasoning_effort=payload.reasoning_effort,
        fixed_fields=tuple(payload.fixed_fields),
        example_input=payload.example_input,
        tenant_id=tenant_id,
        region=region,
        source_run_id=payload.source_run_id,
        created_at=created_at,
    )


def _get_preset_version(
    session_factory: Any,
    settings: Settings,
    preset_id: str,
    version: int,
) -> AtomLabPresetVersionRecord:
    with transaction_boundary(session_factory) as session:
        stored = AtomLabPresetRepository(session).get_version(
            preset_id,
            version,
            tenant_id=settings.default_tenant_id,
            region=settings.default_region,
        )
    if stored is None:
        raise _preset_not_found()
    return stored


def _preset_version_response(
    stored: AtomLabPresetVersionRecord,
) -> AtomLabPresetVersionResponse:
    return AtomLabPresetVersionResponse(
        preset_id=stored.preset_id,
        version=stored.version,
        created_at=stored.created_at,
        name=stored.name,
        description=stored.description,
        atom_id=stored.atom_id,
        base_action_config_id=stored.base_action_config_id,
        schema_refs={
            "input": {
                "schema_ref": stored.input_schema_ref,
                "version": stored.input_schema_version,
            },
            "output": {
                "schema_ref": stored.output_schema_ref,
                "version": stored.output_schema_version,
            },
        },
        prompt=stored.prompt,
        prompt_ref=stored.prompt_ref,
        model_id=stored.model_id,
        reasoning_effort=stored.reasoning_effort,
        fixed_fields=list(stored.fixed_fields),
        example_input=stored.example_input,
        source_run_id=stored.source_run_id,
    )


def _preset_not_found() -> AtomLabApiError:
    return AtomLabApiError(
        status_code=HTTPStatus.NOT_FOUND,
        code="preset_not_found",
        message="Пресет или его версия не найдены.",
    )


def _preset_source_invalid() -> AtomLabApiError:
    return AtomLabApiError(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        code="preset_source_run_invalid",
        message="Исходный запуск не соответствует конфигурации пресета.",
        field_errors=[_field_error("source_run_id")],
    )


def _preset_contract_invalid(path: str) -> AtomLabApiError:
    return AtomLabApiError(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        code="preset_contract_invalid",
        message="Конфигурация пресета не соответствует контракту атома.",
        field_errors=[_field_error(path)],
    )


def _field_error(path: str) -> dict[str, str]:
    return {"path": path, "message": "Недопустимое значение."}


def _encode_preset_cursor(created_at: datetime, preset_id: str) -> str:
    raw = json.dumps([created_at.isoformat(), preset_id], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_preset_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        value = json.loads(_decode_urlsafe_base64(cursor))
        if (
            not isinstance(value, list)
            or len(value) != _PRESET_CURSOR_PARTS
            or not isinstance(value[0], str)
            or not isinstance(value[1], str)
            or not value[1]
            or len(value[1]) > _PRESET_ID_MAX_LENGTH
        ):
            raise ValueError
        created_at = datetime.fromisoformat(value[0])
        if created_at.utcoffset() is None:
            raise ValueError
        return created_at.astimezone(UTC), value[1]
    except (
        ValueError,
        TypeError,
        OverflowError,
        UnicodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as exc:
        raise AtomLabApiError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="invalid_cursor",
            message="Курсор списка недействителен.",
            field_errors=[_field_error("cursor")],
        ) from exc


def _encode_version_cursor(version: int) -> str:
    return base64.urlsafe_b64encode(str(version).encode("ascii")).decode("ascii").rstrip("=")


def _decode_version_cursor(cursor: str) -> int:
    try:
        raw_version = _decode_urlsafe_base64(cursor).decode("ascii")
        version = int(raw_version)
        if str(version) != raw_version or version < 1 or version > _POSTGRESQL_INTEGER_MAX:
            raise ValueError
        return version
    except (ValueError, UnicodeError, binascii.Error) as exc:
        raise AtomLabApiError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="invalid_cursor",
            message="Курсор списка недействителен.",
            field_errors=[_field_error("cursor")],
        ) from exc


def _decode_urlsafe_base64(value: str) -> bytes:
    if re.fullmatch(r"[A-Za-z0-9_-]+={0,2}", value) is None:
        raise ValueError
    unpadded = value.rstrip("=")
    padded = unpadded + "=" * (-len(unpadded) % 4)
    if value not in {unpadded, padded}:
        raise ValueError
    decoded = base64.b64decode(padded.encode("ascii"), altchars=b"-_", validate=True)
    canonical = base64.urlsafe_b64encode(decoded).decode("ascii").rstrip("=")
    if canonical != unpadded:
        raise ValueError
    return decoded


router.include_router(protected_router)
router.include_router(run_router)
