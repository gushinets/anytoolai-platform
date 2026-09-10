from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import Annotated

from anytoolai_platform_api.atom_lab.access import require_atom_lab_access
from anytoolai_platform_api.atom_lab.catalog import (
    AtomLabCatalogConfigError,
    build_atom_catalog,
    get_atom_catalog_entry,
)
from anytoolai_platform_api.dependencies import get_config_registry
from anytoolai_platform_api.errors import AtomLabApiError
from anytoolai_platform_api.schemas import AtomLabAtomResponse, AtomLabErrorResponse
from anytoolai_platform_core.config.registry import ConfigRegistry
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


def _catalog_unavailable() -> AtomLabApiError:
    return AtomLabApiError(
        status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        code="atom_lab_catalog_unavailable",
        message="Каталог Atom Lab недоступен.",
    )


router.include_router(protected_router)
