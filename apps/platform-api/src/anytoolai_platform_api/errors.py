from __future__ import annotations

from anytoolai_platform_core.common.errors import PlatformError
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

REQUEST_ID_HEADER = "X-Request-ID"


class ApiError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def platform_error_to_api_error(error: PlatformError, *, status_code: int) -> ApiError:
    """Builds the ApiError shape shared by every router's PlatformError -> HTTP mapping.

    Each router still owns its own `PlatformError.code -> status_code` table (those encode
    router-specific business rules and must not be conflated into one shared table), but the
    construction of the resulting ApiError itself was independently duplicated three times.
    """
    return ApiError(status_code=status_code, code=error.code, message=str(error))


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return _error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _error_response(
        request,
        status_code=500,
        code="internal_server_error",
        message="Internal server error",
    )


async def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del exc
    return _error_response(
        request,
        status_code=422,
        code="request_validation_failed",
        message="Request validation failed.",
    )


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    request_id = request_id_from(request)
    response = JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )
    response.headers[REQUEST_ID_HEADER] = request_id
    return response


def request_id_from(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))
