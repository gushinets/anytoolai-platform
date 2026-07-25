from __future__ import annotations

import logging
import os
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_api.errors import (
    REQUEST_ID_HEADER,
    ApiError,
    api_error_handler,
    request_validation_error_handler,
    unhandled_exception_handler,
)
from anytoolai_platform_api.routers.handoffs import router as handoffs_router
from anytoolai_platform_api.routers.health import router as health_router
from anytoolai_platform_api.routers.identity_quota import router as identity_quota_router
from anytoolai_platform_api.routers.runtime_config import router as runtime_config_router
from anytoolai_platform_api.routers.scenario_runtime import (
    router as scenario_runtime_router,
)
from anytoolai_platform_core.common.logging import (
    bind_log_context,
    configure_json_logging,
    log_event,
    reset_log_context,
)
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

CORS_ORIGINS_ENV = "ANYTOOLAI_API_CORS_ORIGINS"
CHROME_EXTENSION_ORIGIN_REGEX = r"^chrome-extension://[a-p]{32}$"
logger = logging.getLogger(__name__)


def create_app(
    config_root: Path | None = None,
    *,
    database_url: str | None = None,
) -> FastAPI:
    configure_json_logging("platform-api")
    runtime = build_runtime(config_root, database_url=database_url)
    app = FastAPI(title="AnytoolAI Platform API", version="0.1.0")
    app.state.runtime = runtime

    _install_cors(app)
    _install_request_context(app)
    _install_error_handlers(app)

    app.include_router(health_router)
    app.include_router(identity_quota_router)
    app.include_router(handoffs_router)
    app.include_router(runtime_config_router)
    app.include_router(scenario_runtime_router)
    return app


def _install_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_configured_cors_origins(),
        allow_origin_regex=CHROME_EXTENSION_ORIGIN_REGEX,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )


def _configured_cors_origins() -> list[str]:
    raw_origins = os.getenv(CORS_ORIGINS_ENV, "")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


def _install_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid4().hex}"
        request.state.request_id = request_id
        token = bind_log_context(request_id=request_id)
        started = perf_counter()
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            log_event(
                logger,
                "http.request_completed",
                method=request.method,
                path=_safe_request_path(request),
                status_code=response.status_code,
                duration_ms=round((perf_counter() - started) * 1000, 2),
            )
            return response
        except Exception:
            logger.exception(
                "http.request_failed",
                extra={
                    "event": "http.request_failed",
                    "fields": {
                        "method": request.method,
                        "path": _safe_request_path(request),
                        "status_code": 500,
                    },
                },
            )
            raise
        finally:
            reset_log_context(token)


def _install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


def _safe_request_path(request: Request) -> str:
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str):
        return route_path
    return re.sub(
        r"(/v1/handoffs/)[^/]+",
        r"\1{handoff_token}",
        request.url.path,
    )


app = create_app()
