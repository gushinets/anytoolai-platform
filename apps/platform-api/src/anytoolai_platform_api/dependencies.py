from __future__ import annotations

from http import HTTPStatus
from typing import Annotated, Any

from anytoolai_platform_api.bootstrap import RuntimeBootstrapResult
from anytoolai_platform_api.errors import ApiError, AtomLabApiError
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.providers.catalog_settings import ModelCatalogSettings
from fastapi import Depends, Request
from pydantic import ValidationError


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def require_enabled_product(
    product_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    if settings.enabled_product_ids is not None and product_id not in settings.enabled_product_ids:
        raise ApiError(
            status_code=HTTPStatus.NOT_FOUND,
            code="product_not_found",
            message="Product not found",
        )
    return product_id


def get_atom_lab_run_settings() -> Settings:
    try:
        return Settings.from_env()
    except ValidationError as exc:
        raise AtomLabApiError(
            status_code=503,
            code="lab_unavailable",
            message="Запуск Atom Lab не может быть принят.",
        ) from exc


def get_runtime(request: Request) -> RuntimeBootstrapResult:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise RuntimeError("Platform runtime is missing")
    return runtime


def get_config_registry(
    runtime: Annotated[RuntimeBootstrapResult, Depends(get_runtime)],
) -> ConfigRegistry:
    return runtime.config_registry


def get_session_factory(
    runtime: Annotated[RuntimeBootstrapResult, Depends(get_runtime)],
) -> Any:
    session_factory = runtime.storage.session_factory
    if session_factory is None:
        raise ApiError(
            status_code=503,
            code="runtime_storage_unavailable",
            message="Runtime storage is unavailable.",
        )
    return session_factory


def get_model_catalog_settings(
    runtime: Annotated[RuntimeBootstrapResult, Depends(get_runtime)],
) -> ModelCatalogSettings:
    return runtime.model_catalog_settings


def get_atom_lab_session_factory(
    runtime: Annotated[RuntimeBootstrapResult, Depends(get_runtime)],
) -> Any:
    session_factory = runtime.storage.session_factory
    if session_factory is None:
        raise AtomLabApiError(
            status_code=503,
            code="runtime_storage_unavailable",
            message="Runtime storage is unavailable.",
        )
    return session_factory
