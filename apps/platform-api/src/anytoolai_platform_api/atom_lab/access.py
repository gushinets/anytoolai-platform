from __future__ import annotations

import hmac
import os
from http import HTTPStatus
from typing import Annotated

from anytoolai_platform_api.errors import AtomLabApiError
from fastapi import Header

ATOM_LAB_ACCESS_CODE_ENV = "ANYTOOLAI_ATOM_LAB_ACCESS_CODE"
ATOM_LAB_ACCESS_CODE_HEADER = "X-Atom-Lab-Access-Code"


def require_atom_lab_access(
    access_code: Annotated[str | None, Header(alias=ATOM_LAB_ACCESS_CODE_HEADER)] = None,
) -> None:
    configured_access_code = os.getenv(ATOM_LAB_ACCESS_CODE_ENV, "")
    if not configured_access_code.strip():
        raise AtomLabApiError(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            code="atom_lab_unavailable",
            message="Atom Lab недоступен.",
        )
    if access_code is None or not hmac.compare_digest(
        access_code.encode("utf-8"), configured_access_code.encode("utf-8")
    ):
        raise AtomLabApiError(
            status_code=HTTPStatus.UNAUTHORIZED,
            code="atom_lab_access_denied",
            message="Доступ к Atom Lab запрещён.",
        )
