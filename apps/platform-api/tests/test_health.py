from __future__ import annotations

import asyncio
from http import HTTPStatus
from pathlib import Path
import sys

import httpx

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_CORE_SRC = REPO_ROOT / "packages" / "backend" / "platform-core" / "src"
PLATFORM_API_SRC = REPO_ROOT / "apps" / "platform-api" / "src"

for src_path in (PLATFORM_CORE_SRC, PLATFORM_API_SRC):
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from anytoolai_platform_api.main import create_app


async def _get_health() -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/health")


def test_health_contract_shape() -> None:
    response = asyncio.run(_get_health())

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}
