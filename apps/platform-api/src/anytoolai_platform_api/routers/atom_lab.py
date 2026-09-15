from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

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
)
from anytoolai_platform_api.errors import AtomLabApiError
from anytoolai_platform_api.schemas import (
    AtomLabAtomResponse,
    AtomLabErrorResponse,
    AtomLabModelRefreshResponse,
    AtomLabModelResponse,
    AtomLabModelsResponse,
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
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

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


router.include_router(protected_router)
