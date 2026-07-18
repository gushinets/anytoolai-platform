from __future__ import annotations

from typing import Annotated
from typing import Any

from fastapi import Depends, Request

from anytoolai_platform_api.errors import ApiError
from anytoolai_platform_api.bootstrap import RuntimeBootstrapResult
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.config.registry import ConfigRegistry


def get_settings() -> Settings:
    return Settings()


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
