from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

ATOM_LAB_API_PATH_PREFIX = "/v1/atom-lab"


def apply_atom_lab_cache_policy(request: Request, response: Response) -> None:
    path = request.url.path
    if path == ATOM_LAB_API_PATH_PREFIX or path.startswith(f"{ATOM_LAB_API_PATH_PREFIX}/"):
        response.headers["Cache-Control"] = "no-store"
