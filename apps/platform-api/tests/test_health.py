from __future__ import annotations

import asyncio
from http import HTTPStatus

import httpx

from anytoolai_platform_api.main import create_app


async def _get_health() -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/health")


def test_health_contract_shape() -> None:
    response = asyncio.run(_get_health())

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}
