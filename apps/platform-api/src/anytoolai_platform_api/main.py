from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_api.errors import (
    REQUEST_ID_HEADER,
    ApiError,
    api_error_handler,
    unhandled_exception_handler,
)
from anytoolai_platform_api.routers.health import router as health_router
from anytoolai_platform_api.routers.runtime_config import router as runtime_config_router

CORS_ORIGINS_ENV = "ANYTOOLAI_API_CORS_ORIGINS"
CHROME_EXTENSION_ORIGIN_REGEX = r"^chrome-extension://[a-p]{32}$"


def create_app(
    config_root: Path | None = None,
    *,
    database_url: str | None = None,
) -> FastAPI:
    runtime = build_runtime(config_root, database_url=database_url)
    app = FastAPI(title="AnytoolAI Platform API", version="0.1.0")
    app.state.runtime = runtime

    _install_cors(app)
    _install_request_context(app)
    _install_error_handlers(app)

    app.include_router(health_router)
    app.include_router(runtime_config_router)
    return app


def _install_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_configured_cors_origins(),
        allow_origin_regex=CHROME_EXTENSION_ORIGIN_REGEX,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )


def _configured_cors_origins() -> list[str]:
    raw_origins = os.getenv(CORS_ORIGINS_ENV, "")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def _install_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid4().hex}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def _install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


app = create_app()
