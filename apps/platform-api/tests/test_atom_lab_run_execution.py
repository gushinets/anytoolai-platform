"""HTTP admission through the real worker/ActionRunner boundary."""

from __future__ import annotations

import asyncio
import json
from http import HTTPStatus

import pytest
from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.atom_lab.repository import AtomLabRunRepository
from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse
from anytoolai_platform_core.storage.transactions import transaction_boundary
from anytoolai_platform_worker.composition import build_worker
from test_atom_lab_history import _get
from test_atom_lab_runs import INPUTS, _factory, _payload, _post
from test_atom_lab_runs import app as app  # noqa: PLC0414 -- shared fixture


@pytest.mark.parametrize("atom_id", INPUTS)
def test_submitted_payload_equals_snapshot_and_action_runner_input(app, monkeypatch, atom_id):
    """Catches HTTP/snapshot/workflow defaults changing omitted/null/false/zero inputs."""
    submitted = _payload(atom_id)
    response = _post(app, submitted)
    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    run_id = response.json()["run_id"]
    factory = _factory(app)
    with transaction_boundary(factory) as session:
        record = AtomLabRunRepository(session).get(run_id)
        assert record is not None
        assert record.input_payload == submitted["input"]

    observed = []

    async def stop_before_external_provider(_executor, request, *, session):
        observed.append(dict(request.input_payload))
        raise RuntimeError("test stops after real ActionRunner input validation")

    monkeypatch.setattr(StructuredLlmActionExecutor, "execute", stop_before_external_provider)
    worker = build_worker(
        session_factory=factory,
        config_registry=app.state.runtime.config_registry,
    )
    try:
        processed = asyncio.run(worker.process_next_job())
    finally:
        worker.dispose()
    assert processed is not None and processed.id == response.json()["job_id"]
    assert observed == [submitted["input"]]
    with transaction_boundary(factory) as session:
        stored = AtomLabRunRepository(session).get(run_id)
        assert stored is not None and stored.input_payload == submitted["input"]


class _FinalAnswerAdapter:
    def __init__(self, output):
        self.output = output

    async def complete(self, request):
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=self.output,
            status=ProviderCallStatus.succeeded,
        )


@pytest.mark.parametrize("success", [True, False])
def test_http_worker_terminal_history_and_idempotent_replay(app, success):
    """Catches terminal response drift or retries admitting another terminal execution."""
    expected = {
        "values": {"date": "2026-09-30"}, "missing_fields": [], "confidence": {"date": 0.9},
    }
    submitted = _payload()
    accepted = _post(app, submitted)
    assert accepted.status_code == HTTPStatus.ACCEPTED
    run_id = accepted.json()["run_id"]
    worker = build_worker(
        session_factory=_factory(app), config_registry=app.state.runtime.config_registry,
        provider_adapters={"litellm": _FinalAnswerAdapter(
            json.dumps(expected) if success else "invalid final answer",
        )},
    )
    try:
        asyncio.run(worker.process_next_job())
        detail = _get(app, "/" + run_id)
        replay = _post(app, submitted)
        assert asyncio.run(worker.process_next_job()) is None
    finally:
        worker.dispose()
    assert detail.status_code == HTTPStatus.OK
    expected_status = "succeeded" if success else "failed"
    assert detail.json()["status"] == expected_status
    assert detail.json()["snapshot"]["input"] == submitted["input"]
    assert replay.status_code == HTTPStatus.ACCEPTED
    assert replay.json() == {**accepted.json(), "status": expected_status}
    assert _get(app, "/" + run_id).json() == detail.json()
    assert _get(app, "/" + run_id, access=None).status_code == HTTPStatus.UNAUTHORIZED
    assert len(_get(app).json()["items"]) == 1
    if success:
        assert detail.json()["result"] == expected
        assert detail.json()["diagnostics"]["succeeded_first_attempt"] is True
    else:
        assert detail.json()["result"] is None
        debug, = detail.json()["diagnostics"]["debug_artifacts"]
        assert debug["raw_output_text"] == "invalid final answer"
        assert debug["truncated"] is False
