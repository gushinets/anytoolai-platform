from __future__ import annotations

import asyncio
from http import HTTPStatus
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_core.storage.db import (
    event_log_table,
    guest_quota_usage_table,
    jobs_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary
from test_scenario_runtime_api import (
    _build_session_factory,
    _create_test_app,
    _start_payload,
)


@pytest.mark.slow
def test_parallel_scenario_start_stress_keeps_quota_and_rows_consistent(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)
    request_count = 24

    async def start_many() -> list[httpx.Response]:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await asyncio.gather(
                *[
                    client.post(
                        "/v1/products/kernel_demo/scenarios/"
                        "kernel_demo.single_action_smoke_v1/start",
                        json=_start_payload(),
                        headers={"X-Request-ID": f"req_quota_stress_{index}"},
                    )
                    for index in range(request_count)
                ]
            )

    responses = asyncio.run(start_many())
    status_codes = [response.status_code for response in responses]

    assert status_codes.count(HTTPStatus.OK) == 3
    assert status_codes.count(HTTPStatus.TOO_MANY_REQUESTS) == request_count - 3
    assert all(
        response.json()["error"]["code"] == "quota_exhausted"
        for response in responses
        if response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    )

    with transaction_boundary(session_factory) as session:
        scenario_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()
        job_count = session.execute(
            sa.select(sa.func.count()).select_from(jobs_table)
        ).scalar_one()
        usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()
        event_types = list(session.execute(sa.select(event_log_table.c.event_type)).scalars())

    assert scenario_count == 3
    assert job_count == 3
    assert usage["used_count"] == 3
    assert usage["limit_count"] == 3
    assert event_types.count("quota.consumed") == 3
    assert event_types.count("quota.exhausted") == request_count - 3
