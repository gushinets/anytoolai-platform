"""ANY-227 (B02a) required-evidence coverage for the ProposalAI product bundle and workflow.

Every case here goes through the real application composition path
(anytoolai_platform_api.bootstrap.build_runtime, via create_app) and the real worker
(anytoolai_platform_worker.composition.build_worker) against a SQLite-backed runtime -- not a
hand-rolled ConfigLoader or WorkflowRunner call -- so a passing test here is direct evidence that
ProposalAI's bundle, workflow, and A06 wiring work end to end without any Platform Core or
mapping-DSL change.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.storage.db import provider_calls_table
from anytoolai_platform_core.storage.transactions import SessionFactory, transaction_boundary
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_worker.composition import build_worker

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
GUEST_ID = "guest_proposal_ai_test"

# `session_factory` (SQLite-backed) comes from apps/platform-api/tests/conftest.py -- shared with
# test_demo_api.py, the only other suite that needs the same SQLite-backed setup.


@pytest.fixture
def app(session_factory: SessionFactory):
    with transaction_boundary(session_factory) as session:
        GuestIdentityRepository(session).create(
            GuestIdentityRecord(id=GUEST_ID, tenant_id="anytoolai", region="default")
        )
    application = create_app(config_root=CONFIG_ROOT)
    application.state.runtime = replace(
        application.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return application


async def _request(
    app: Any,
    method: str,
    path: str,
    *,
    json: Any | None = None,
    request_id: str = "req_proposal_ai_test",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": request_id},
        )


def _start(app: Any, *, input_payload: dict[str, Any], request_id: str = "req_start") -> httpx.Response:
    return asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/proposal_ai/scenarios/proposal_ai.generate_v1/start",
            json={
                "frontend_id": "web_mirror",
                "guest_id": GUEST_ID,
                "input": input_payload,
            },
            request_id=request_id,
        )
    )


def _build_worker(app: Any, session_factory: SessionFactory):
    # Reuses the app's already-loaded config_registry instead of re-parsing configs/kernel from
    # scratch a second time per test.
    return build_worker(
        session_factory=session_factory,
        config_registry=app.state.runtime.config_registry,
        provider_adapters={"fake": FakeProviderAdapter(FIXTURE_ROOT)},
    )


def _provider_call_count(session_factory: SessionFactory, *, job_id: str) -> int:
    with transaction_boundary(session_factory) as session:
        return session.execute(
            sa.select(sa.func.count())
            .select_from(provider_calls_table)
            .where(provider_calls_table.c.job_id == job_id)
        ).scalar_one()


def test_proposal_ai_happy_path_invokes_a06_once_and_produces_canonical_artifact(
    app: Any,
    session_factory: SessionFactory,
) -> None:
    started = _start(
        app,
        input_payload={
            "task_text": "Build a 5-page marketing site for a local bakery within two weeks.",
            "freelancer_positioning": "Freelance web designer with 4 years building small-business sites.",
        },
    ).json()

    worker = _build_worker(app, session_factory)
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.id == started["job_id"]
    assert processed.status is JobStatus.succeeded
    assert processed.result_artifact_id is not None
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 1

    session_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
            request_id="req_session",
        )
    )
    assert session_response.status_code == HTTPStatus.OK
    assert session_response.json()["allowed_next_actions"] == ["copy_result"]

    result_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/results/{processed.result_artifact_id}",
            request_id="req_result",
        )
    )
    assert result_response.status_code == HTTPStatus.OK
    result_body = result_response.json()
    assert result_body["workflow_id"] == "proposal_ai.generate_v1"
    assert result_body["schema_ref"] == "kernel.schemas.compose_persuasive_text_output_v1"
    assert set(result_body["output"]) == {"text"}
    assert isinstance(result_body["output"]["text"], str)
    assert 1 <= len(result_body["output"]["text"]) <= 4000


def test_proposal_ai_weak_but_non_empty_input_still_passes_schema_and_completes(
    app: Any,
    session_factory: SessionFactory,
) -> None:
    """Proves the *schema* accepts a vague-but-non-empty task/positioning pair and the workflow
    runs it to completion -- it does not exercise the `.weak_input.json` fixture itself.
    `FakeProviderAdapter` always resolves by `action_config_id` in the real runtime path (it never
    receives a `fixture_key`), so this and the happy-path test necessarily resolve the same
    fixture; the weak-input fixture's own content is asserted separately, at the config level, in
    test_proposal_ai_product.py (see exec-plan Design decision 4)."""
    started = _start(
        app,
        input_payload={
            "task_text": "Need some help with a website.",
            "freelancer_positioning": "I build websites.",
        },
        request_id="req_start_weak",
    ).json()

    worker = _build_worker(app, session_factory)
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.succeeded
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 1


@pytest.mark.parametrize(
    "invalid_input",
    [
        {"task_text": "", "freelancer_positioning": "I build websites."},
        {"task_text": "   ", "freelancer_positioning": "I build websites."},
        {"task_text": "Build a site.", "freelancer_positioning": ""},
    ],
)
def test_proposal_ai_rejects_empty_or_whitespace_required_fields_before_provider_execution(
    app: Any,
    session_factory: SessionFactory,
    invalid_input: dict[str, Any],
) -> None:
    started = _start(app, input_payload=invalid_input, request_id="req_start_invalid").json()

    worker = _build_worker(app, session_factory)
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert processed.error_code == "workflow_input_validation_failed"
    assert processed.result_artifact_id is None
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 0
