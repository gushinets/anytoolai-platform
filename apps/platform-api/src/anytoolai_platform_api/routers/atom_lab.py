from __future__ import annotations

import base64
import binascii
import json
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
from anytoolai_platform_api.dependencies import (
    get_atom_lab_session_factory,
    get_config_registry,
    get_model_catalog_settings,
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
)
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.actions.runner import ActionInputValidationError
from anytoolai_platform_core.atom_lab.models import (
    AtomLabPresetIdentityRecord,
    AtomLabPresetVersionRecord,
    is_addressable_atom_lab_model,
)
from anytoolai_platform_core.atom_lab.repository import (
    AtomLabPresetRepository,
    PresetAtomMismatchError,
    PresetSourceRunError,
    PresetVersionConflictError,
)
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.providers.catalog_repository import (
    ModelCatalogRepository,
    ModelCatalogState,
)
from anytoolai_platform_core.providers.catalog_settings import ModelCatalogSettings
from anytoolai_platform_core.providers.models import ModelCatalogRefreshStatus
from anytoolai_platform_core.storage.transactions import transaction_boundary
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json_schema

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
    _validate_preset_payload(payload, registry)
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
            AtomLabPresetSummaryResponse.model_validate(row, from_attributes=True)
            for row in page
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
    _validate_preset_payload(payload, registry)
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
        if repository.get_identity(
            preset_id,
            tenant_id=settings.default_tenant_id,
            region=settings.default_region,
        ) is None:
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
) -> None:
    try:
        atom = get_atom_catalog_entry(registry, payload.atom_id.value)
    except AtomLabCatalogConfigError as exc:
        raise _catalog_unavailable() from exc
    if atom is None:
        raise _preset_contract_invalid("atom_id")

    expected_refs = atom.schema_refs.model_dump(mode="json")
    field_errors: list[dict[str, str]] = []
    if payload.base_action_config_id != atom.base_action_config_id:
        field_errors.append(_field_error("base_action_config_id"))
    if payload.prompt_ref != atom.prompt_ref:
        field_errors.append(_field_error("prompt_ref"))
    if payload.schema_refs.model_dump(mode="json") != expected_refs:
        field_errors.append(_field_error("schema_refs"))
    if not is_addressable_atom_lab_model(payload.model_id):
        field_errors.append(_field_error("model_id"))

    field_errors.extend(_validate_fixed_fields(payload))

    try:
        validate_json_schema(instance=payload.example_input, schema=atom.input_schema)
    except JsonSchemaValidationError as exc:
        suffix = ".".join(str(part) for part in exc.absolute_path)
        path = "example_input" if not suffix else f"example_input.{suffix}"
        field_errors.append(_field_error(path))
    else:
        try:
            _validate_semantic_input(registry, atom.action_type, payload.example_input)
        except ActionInputValidationError:
            field_errors.append(_field_error("example_input"))

    if field_errors:
        raise AtomLabApiError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="preset_contract_invalid",
            message="Конфигурация пресета не соответствует контракту атома.",
            field_errors=field_errors,
        )


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
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        if (
            not isinstance(value, list)
            or len(value) != _PRESET_CURSOR_PARTS
            or not isinstance(value[0], str)
            or not isinstance(value[1], str)
            or not value[1]
        ):
            raise ValueError
        created_at = datetime.fromisoformat(value[0])
        if created_at.utcoffset() is None:
            raise ValueError
        return created_at.astimezone(UTC), value[1]
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error) as exc:
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
        padded = cursor + "=" * (-len(cursor) % 4)
        version = int(base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii"))
        if version < 1:
            raise ValueError
        return version
    except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise AtomLabApiError(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            code="invalid_cursor",
            message="Курсор списка недействителен.",
            field_errors=[_field_error("cursor")],
        ) from exc


router.include_router(protected_router)
