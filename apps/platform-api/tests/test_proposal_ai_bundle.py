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
import json
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
from anytoolai_platform_core.providers.models import ProviderResponse, ResolvedProviderRequest
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


def _start(
    app: Any, *, input_payload: dict[str, Any], request_id: str = "req_start"
) -> dict[str, Any]:
    response = asyncio.run(
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
    assert response.status_code == HTTPStatus.OK, response.text
    return response.json()


class _FixedFixtureProviderAdapter(FakeProviderAdapter):
    """Test-only: forces a specific fixture_key regardless of what action_config_id the real
    pipeline would resolve. In production, FakeProviderAdapter._fixture_key_for() only ever falls
    back to action_config_id -- a real workflow run has no way to pick a *second* fixture for the
    same action config. This lets a test pin a worker run to a specific checked-in fixture file
    (e.g. the weak-input variant) so the run's own output can be asserted against it, without any
    change to product or platform runtime code."""

    def __init__(self, fixture_root: Path, *, fixture_key: str) -> None:
        super().__init__(fixture_root)
        self._forced_fixture_key = fixture_key

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        return await super().complete(replace(request, fixture_key=self._forced_fixture_key))


def _build_worker(app: Any, session_factory: SessionFactory, *, provider_adapters=None):
    # Reuses the app's already-loaded config_registry instead of re-parsing configs/kernel from
    # scratch a second time per test.
    return build_worker(
        session_factory=session_factory,
        config_registry=app.state.runtime.config_registry,
        provider_adapters=provider_adapters or {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
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
            "freelancer_positioning": (
                "Freelance web designer with 4 years building small-business sites."
            ),
        },
    )

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


def test_proposal_ai_resolves_through_the_bare_default_worker_provider_adapters(
    app: Any,
    session_factory: SessionFactory,
) -> None:
    """Code review finding: every other test here builds its worker through `_build_worker`,
    which always injects an explicit `provider_adapters` override -- masking that
    `build_worker()`'s *bare* default (no override at all) is what a real running
    apps/platform-worker process actually uses. ProposalAI's action config resolves to provider
    `fake` (`default_fake_provider_v1`), and `build_default_provider_adapters()`'s own
    `FakeProviderAdapter()` only ever searches the shared, kernel-level
    `tests/fixtures/provider/fake_provider_outputs/` directory -- exactly where ProposalAI's
    fixtures live (see Design decision 5 in the exec plan for why they stay there rather than
    under `products/proposal_ai/`: making the *default*, zero-override composition resolve a
    product-local fixture is not achievable without either violating
    `test_no_direct_provider_adapter_imports_outside_provider_boundary` or changing Platform
    Core, and ANY-227 forbids the latter outright). This proves the true default composition --
    config_root and zero other overrides, exactly what apps/platform-worker/composition.py's own
    production entrypoint uses -- resolves ProposalAI's fixture with no special-casing at all."""
    _start(
        app,
        input_payload={
            "task_text": "Build a 5-page marketing site for a local bakery within two weeks.",
            "freelancer_positioning": (
                "Freelance web designer with 4 years building small-business sites."
            ),
        },
        request_id="req_start_default_adapters",
    )

    worker = build_worker(session_factory=session_factory, config_root=CONFIG_ROOT)
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.succeeded
    assert processed.result_artifact_id is not None


def test_proposal_ai_weak_but_non_empty_input_still_passes_schema_and_completes(
    app: Any,
    session_factory: SessionFactory,
) -> None:
    """Proves the *schema* accepts a vague-but-non-empty task/positioning pair and the workflow
    runs it to completion via the pipeline's natural fixture resolution (by `action_config_id`,
    which is always the happy fixture here -- see
    test_proposal_ai_weak_input_end_to_end_produces_the_checked_in_weak_fixture_artifact below for
    a run that actually exercises `.weak_input.json`)."""
    started = _start(
        app,
        input_payload={
            "task_text": "Need some help with a website.",
            "freelancer_positioning": "I build websites.",
        },
        request_id="req_start_weak",
    )

    worker = _build_worker(app, session_factory)
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.succeeded
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 1


def test_proposal_ai_weak_input_end_to_end_produces_the_checked_in_weak_fixture_artifact(
    app: Any,
    session_factory: SessionFactory,
) -> None:
    """Code review finding: the real pipeline can never select the weak-input fixture on its own
    (FakeProviderAdapter only ever resolves fixture_key from action_config_id), so nothing proved
    the checked-in `.weak_input.json` fixture is actually reachable end to end -- it could be
    wrong (as it once was) while every other test still passed. `_FixedFixtureProviderAdapter`
    pins this one worker run to that fixture (test-only, no product/platform runtime change), and
    the result is asserted against the fixture file's own content -- not a hardcoded copy of it."""
    weak_fixture_key = "proposal_ai.compose_persuasive_text_v1.weak_input"
    expected_text = json.loads(
        (FIXTURE_ROOT / f"{weak_fixture_key}.json").read_text(encoding="utf-8")
    )["response_json"]["text"]

    _start(
        app,
        input_payload={
            "task_text": "Need some help with a website.",
            "freelancer_positioning": "I build websites.",
        },
        request_id="req_start_weak_pinned",
    )

    worker = _build_worker(
        app,
        session_factory,
        provider_adapters={
            "fake": _FixedFixtureProviderAdapter(FIXTURE_ROOT, fixture_key=weak_fixture_key)
        },
    )
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.succeeded
    assert processed.result_artifact_id is not None

    result_response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/results/{processed.result_artifact_id}",
            request_id="req_result_weak_pinned",
        )
    )
    assert result_response.status_code == HTTPStatus.OK
    assert result_response.json()["output"] == {"text": expected_text}


@pytest.mark.parametrize(
    "invalid_input",
    [
        {"task_text": "", "freelancer_positioning": "I build websites."},
        {"task_text": "   ", "freelancer_positioning": "I build websites."},
        {"task_text": "Build a site.", "freelancer_positioning": ""},
        # Code review finding: `task_text`/`freelancer_positioning` are a `required trimmed
        # string` per ANY-227 -- non-blank but padded values must not reach A06 untrimmed either.
        {"task_text": "  Build a site.  ", "freelancer_positioning": "I build websites."},
        {"task_text": "Build a site.", "freelancer_positioning": "I build websites.\n"},
    ],
)
def test_proposal_ai_rejects_invalid_required_field_values_before_provider_execution(
    app: Any,
    session_factory: SessionFactory,
    invalid_input: dict[str, Any],
) -> None:
    started = _start(app, input_payload=invalid_input, request_id="req_start_invalid")

    worker = _build_worker(app, session_factory)
    processed = asyncio.run(worker.process_next_job())
    worker.dispose()

    assert processed is not None
    assert processed.status is JobStatus.failed
    assert processed.error_code == "workflow_input_validation_failed"
    assert processed.result_artifact_id is None
    assert _provider_call_count(session_factory, job_id=started["job_id"]) == 0
