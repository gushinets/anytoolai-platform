from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import asdict
from datetime import timedelta
from http import HTTPStatus

import httpx
import pytest
import sqlalchemy as sa
from anytoolai_platform_api.dependencies import (
    get_atom_lab_run_settings,
    get_config_registry,
    get_settings,
)
from anytoolai_platform_api.schemas import AtomLabRunDetailResponse
from anytoolai_platform_api.settings import Settings
from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.atom_lab.repository import AtomLabRunRepository
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.providers.models import ProviderCallRecord, ProviderCallStatus
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    atom_lab_runs_table,
    jobs_table,
    model_catalog_state_table,
    provider_calls_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary
from pydantic import ValidationError
from test_atom_lab_runs import ACCESS_CODE, MODEL_ID, _error, _factory, _payload, _post
from test_atom_lab_runs import app as app  # noqa: PLC0414 -- register the shared pytest fixture

DIAGNOSTIC_PAGE_SIZE = 100
LARGE_CALL_COUNT = 105
DEBUG_TEXT_MAX_BYTES = 8192
LONG_TEST_ID_TEXT_LENGTH = 256
DIAGNOSTIC_MARKER_SEPARATORS = (
    "\n", "\t", "\u00a0", "\u2003", "\u202e", "\x01", "\x1b[31m", "\x9b31m", r"\n", r"\t",
)


def _get(app, path="", *, access=ACCESS_CODE):
    async def request():
        headers = {} if access is None else {"X-Atom-Lab-Access-Code": access}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/v1/atom-lab/runs" + path, headers=headers)

    return asyncio.run(request())


def _start(app, key="history-1"):
    response = _post(app, _payload(), key=key)
    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    with transaction_boundary(_factory(app)) as session:
        return AtomLabRunRepository(session).get(response.json()["run_id"])


def _state(app, run, job_status, scenario_status="running", **updates):
    with transaction_boundary(_factory(app)) as session:
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == run.job_id)
            .values(status=job_status, **updates)
        )
        session.execute(
            sa.update(scenario_sessions_table)
            .where(scenario_sessions_table.c.id == run.scenario_session_id)
            .values(status=scenario_status)
        )


@pytest.mark.parametrize(
    "job_status,session_status,expected",
    [
        ("created", "running", "queued"),
        ("running", "running", "running"),
        ("succeeded", "completed", "succeeded"),
        ("failed", "failed", "failed"),
        ("canceled", "running", "cancelled"),
        ("created", "expired", "expired"),
        ("running", "expired", "expired"),
        ("succeeded", "expired", "expired"),
        ("failed", "expired", "expired"),
        ("canceled", "expired", "expired"),
    ],
)
def test_admission_replay_uses_same_run_status_as_history(
    app, job_status, session_status, expected,
):
    run = _start(app)
    _state(app, run, job_status, session_status)
    replay = _post(app, _payload(), key="history-1")
    assert replay.status_code == HTTPStatus.ACCEPTED, replay.text
    assert replay.json() == {
        "run_id": run.id,
        "scenario_session_id": run.scenario_session_id,
        "job_id": run.job_id,
        "status": expected,
    }
    assert _get(app, "/" + run.id).json()["status"] == expected
    assert _get(app).json()["items"][0]["status"] == expected


def test_admission_schema_shares_history_status_contract(app):
    schemas = app.openapi()["components"]["schemas"]
    accepted_status = schemas["AtomLabRunAcceptedResponse"]["properties"]["status"]
    assert accepted_status == {"$ref": "#/components/schemas/AtomLabRunStatus"}
    assert schemas["AtomLabRunStatus"]["enum"] == [
        "queued", "running", "succeeded", "failed", "expired", "cancelled",
    ]


def _runtime(app, run, *, success=True, calls=((1, 1),), confirmed_model=None):
    scope = {
        key: getattr(run, key)
        for key in (
            "tenant_id",
            "region",
            "product_id",
            "frontend_id",
            "scenario_session_id",
            "job_id",
        )
    }
    action = ActionRunRecord(
        **scope,
        workflow_id=run.workflow_id,
        step_id=run.step_id,
        action_type=run.action_type,
        action_config_id=run.action_config_id,
        status=ActionRunStatus.succeeded if success else ActionRunStatus.failed,
        error_code=None if success else "structured_output_validation_failed",
    )
    artifact = ArtifactRecord(
        **scope,
        action_run_id=action.id,
        artifact_type="structured_output" if success else "structured_output_debug_raw",
        status=ArtifactStatus.stored if success else ArtifactStatus.failed,
        content_json={"original": [None, False, 0]} if success else None,
        content_text=None if success else "private raw output sk-secret",
        metadata={} if success else {"error_code": "structured_output_validation_failed"},
    )
    with transaction_boundary(_factory(app)) as session:
        session.execute(
            sa.insert(action_runs_table).values(
                **{**asdict(action), "output_artifact_id": artifact.id}
            )
        )
        session.execute(sa.insert(artifacts_table).values(**asdict(artifact)))
        for index, (semantic, transport) in enumerate(calls, 1):
            call = ProviderCallRecord(
                **scope,
                action_run_id=action.id,
                workflow_id=run.workflow_id,
                workflow_version=run.workflow_version,
                step_id=run.step_id,
                action_type=run.action_type,
                action_config_id=run.action_config_id,
                provider_policy_ref=run.provider_policy_ref,
                provider="openai",
                model=MODEL_ID,
                gateway_backend="litellm",
                gateway_model=MODEL_ID,
                semantic_attempt_index=semantic,
                transport_attempt_index=transport,
                physical_call_index=index,
                status=ProviderCallStatus.succeeded,
                metadata={
                    "response_metadata": {"litellm": {"actual_model": confirmed_model}},
                    "prompt": "private prompt",
                    "authorization": "sk-secret",
                },
            )
            session.execute(sa.insert(provider_calls_table).values(**asdict(call)))
    now = utc_now()
    _state(
        app,
        run,
        "succeeded" if success else "failed",
        started_at=now,
        completed_at=now + timedelta(seconds=2),
        result_artifact_id=artifact.id,
        error_code=None if success else "structured_output_validation_failed",
        error_message_safe="unsafe upstream prompt sk-secret",
    )
    return action, artifact


def test_expired_session_keeps_terminal_precedence_and_hides_stored_result(app):
    """Catches a late successful job reviving an independently expired scenario."""
    run = _start(app)
    _runtime(app, run, success=True)
    _state(app, run, "succeeded", "expired")

    detail = _get(app, "/" + run.id)
    assert detail.status_code == HTTPStatus.OK, detail.text
    assert detail.json()["status"] == "expired"
    assert detail.json()["result"] is None

    listing = _get(app)
    assert listing.status_code == HTTPStatus.OK, listing.text
    assert listing.json()["items"][0]["status"] == "expired"


@pytest.mark.parametrize("path", ["", "/missing", "?limit=bad&cursor=bad"])
def test_history_authentication_precedes_validation_and_lookup(app, path, monkeypatch):
    _error(_get(app, path, access=None), 401, "access_denied")
    monkeypatch.delenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE")
    _error(_get(app, path), 503, "lab_unavailable")


def test_history_scope_and_unknown_ids_are_protected(app):
    run = _start(app)
    app.dependency_overrides[get_settings] = lambda: Settings(default_tenant_id="other")
    assert _get(app).json() == {"items": [], "next_cursor": None}
    _error(_get(app, "/" + run.id), 404, "lab_resource_not_found")
    _error(_get(app, "/missing"), 404, "lab_resource_not_found")
    app.dependency_overrides[get_settings] = lambda: Settings(default_region="other")
    _error(_get(app, "/" + run.id), 404, "lab_resource_not_found")


@pytest.mark.parametrize(
    "path",
    ["/run%00id", "/" + "x" * 129, "/run%20id", "/run%5Cid", "/run%0Aid", "/не-id"],
)
def test_history_rejects_unsafe_detail_ids_after_auth_and_before_sql(app, path):
    with transaction_boundary(_factory(app)) as session:
        engine = session.get_bind().engine
    statements = []

    def observe_sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    sa.event.listen(engine, "before_cursor_execute", observe_sql)
    try:
        _error(_get(app, "/missing"), 404, "lab_resource_not_found")
        assert statements, "A valid opaque ID should exercise the observed database"
        statements.clear()
        _error(_get(app, path, access=None), 401, "access_denied")
        _error(_get(app, path), 404, "lab_resource_not_found")
        assert statements == [], "Malformed run identifiers must never reach the database"
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe_sql)


@pytest.mark.parametrize(
    ("job", "scenario", "expected"),
    [
        ("created", "started", "queued"),
        ("running", "running", "running"),
        ("succeeded", "completed", "succeeded"),
        ("failed", "failed", "failed"),
        ("created", "expired", "expired"),
        ("canceled", "failed", "failed"),
    ],
)
def test_history_projects_lifecycle_without_fabricating_nullable_values(
    app, job, scenario, expected
):
    run = _start(app)
    _state(app, run, job, scenario)
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert set(body) == {
        "run_id",
        "status",
        "snapshot",
        "runtime_ids",
        "result",
        "diagnostics",
        "created_at",
        "started_at",
        "finished_at",
    }
    assert body["status"] == expected
    assert body["runtime_ids"] == {
        "scenario_session_id": run.scenario_session_id,
        "job_id": run.job_id,
        "action_run_id": None,
        "artifact_id": None,
    }
    assert body["started_at"] is None and body["finished_at"] is None
    assert body["result"] is None
    assert _get(app).json()["items"][0]["status"] == expected


def test_history_keyset_remains_stable_with_tied_times_and_new_insert(app):
    stamp = utc_now()
    runs = []
    for index in range(3):
        run = _start(app, f"run-{index}")
        _state(app, run, "succeeded")
        runs.append(run)
    with transaction_boundary(_factory(app)) as session:
        session.execute(sa.update(atom_lab_runs_table).values(created_at=stamp))
    first = _get(app, "?limit=2")
    assert first.status_code == HTTPStatus.OK, first.text
    page = first.json()
    expected = sorted([run.id for run in runs], reverse=True)
    assert [item["run_id"] for item in page["items"]] == expected[:2]
    assert set(page) == {"items", "next_cursor"}
    assert "snapshot" not in page["items"][0]
    _start(app, "inserted-later")
    second = _get(app, "?limit=2&cursor=" + page["next_cursor"]).json()
    assert [item["run_id"] for item in second["items"]] == expected[2:]
    assert second["next_cursor"] is None


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "limit=invalid",
        "cursor=" + "x" * 1025,
        "cursor=%%%",
        "cursor=" + base64.urlsafe_b64encode(b'["2026-01-01","id"]').decode(),
        "cursor=" + base64.urlsafe_b64encode(b'["2026-01-01T00:00:00Z",true]').decode(),
    ],
)
def test_history_rejects_invalid_pagination_without_echo(app, query):
    response = _get(app, "?" + query)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
    assert set(response.json()) == {"error", "request_id"}
    assert query not in response.text


def test_history_reads_immutable_snapshot_and_normalized_result_after_registry_drift(app):
    run = _start(app)
    action, artifact = _runtime(app, run, confirmed_model="gpt-confirmed-2026")

    def unavailable():
        raise AssertionError("history must not resolve current definitions")

    app.dependency_overrides[get_config_registry] = unavailable
    with transaction_boundary(_factory(app)) as session:
        session.execute(sa.delete(model_catalog_state_table))
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["snapshot"] == run.snapshot_payload()
    assert body["result"] == artifact.content_json
    assert body["runtime_ids"]["action_run_id"] == action.id
    assert body["runtime_ids"]["artifact_id"] == artifact.id
    assert body["diagnostics"]["response_model_id"] == "gpt-confirmed-2026"
    assert body["diagnostics"]["requested_model_id"] == MODEL_ID
    assert "requested_model" not in body["diagnostics"]
    assert "response_model" not in body["diagnostics"]
    call = body["diagnostics"]["provider_calls"][0]
    assert call["response_model_id"] == "gpt-confirmed-2026"
    assert "response_model" not in call
    assert body["diagnostics"]["requested_reasoning_effort"] == "high"
    expected_duration_ms = 2000
    assert body["diagnostics"]["duration_ms"] == expected_duration_ms
    assert body["diagnostics"]["succeeded_first_attempt"] is True
    assert _get(app, "/" + run.id).json() == body


def test_history_keeps_retry_dimensions_and_provider_confirmation_distinct(app):
    run = _start(app)
    _runtime(app, run, calls=((1, 1), (1, 2), (2, 1), (2, 1)))
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK, response.text
    diagnostics = response.json()["diagnostics"]
    assert {
        key: diagnostics[key]
        for key in ("validation_attempts", "transport_attempts", "physical_calls")
    } == {"validation_attempts": 2, "transport_attempts": 3, "physical_calls": 4}
    assert diagnostics["response_model_id"] is None
    assert diagnostics["succeeded_first_attempt"] is False
    assert [call["physical_call_index"] for call in diagnostics["provider_calls"]] == [1, 2, 3, 4]
    assert all(call["response_model_id"] is None for call in diagnostics["provider_calls"])
    assert "reasoning_effort" not in diagnostics["provider_calls"][0]


def test_failed_debug_output_is_safe_diagnostics_never_result(app):
    run = _start(app)
    _, artifact = _runtime(app, run, success=False)
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK, response.text
    body = response.json()
    assert body["result"] is None
    diagnostics = body["diagnostics"]
    assert diagnostics["error_code"] == "structured_output_validation_failed"
    assert diagnostics["debug_artifacts"][0]["artifact_id"] == artifact.id
    assert diagnostics["succeeded_first_attempt"] is None
    assert "sk-secret" not in response.text
    assert "private raw output" not in response.text
    assert "unsafe upstream" not in response.text


@pytest.mark.parametrize("tag", [None, "different-run"])
def test_history_never_exposes_untagged_or_other_run_debug_text(app, tag):
    """Catches serving an ordinary or incorrectly linked raw debug artifact as lab text."""
    run = _start(app)
    _, artifact = _runtime(app, run, success=False)
    with transaction_boundary(_factory(app)) as session:
        session.execute(sa.update(artifacts_table).where(
            artifacts_table.c.id == artifact.id
        ).values(content_text="ordinary private output", metadata={
            "atom_lab_run_id": tag, "atom_lab_debug_version": 1,
        }))
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK
    debug, = response.json()["diagnostics"]["debug_artifacts"]
    assert debug["raw_output_text"] is None
    assert "ordinary private output" not in response.text


@pytest.mark.parametrize(
    ("raw_text", "expected", "truncated", "redacted"),
    [
        ("字" * 3000, "字" * 2730, True, False),
        ("ｉｎｖａｌｉｄ\ttext\n}", "ｉｎｖａｌｉｄ\ttext\n}", False, False),
        ("invalid\x00\x1b\r\u202etext\n\tend", "invalidtext\n\tend", False, True),
        ("invalid\x9b31m text\x9b0m", "invalid text", False, True),
        ("api\x00_key=private-value", "[redacted]", False, True),
        ("valid-looking-prefix " * 500 + "Bearer private-value", "[redacted]", False, True),
        (
            "-----BEGIN EC PRIVATE KEY-----\nYWJj\n-----END EC PRIVATE KEY-----",
            "[redacted]", False, True,
        ),
        ('{"private_key":"private-value"}', "[redacted]", False, True),
        ('{"privateKey":"private-value"}', "[redacted]", False, True),
        ('{"PRIVATE--KEY":"private-value"}', "[redacted]", False, True),
        ("<thinking>private internal content</thinking>", "[redacted]", False, True),
        (r'{"api\tkey":"private-value"}', "[redacted]", False, True),
        ("Here is sk-\nabcdefghijklmnopqrst", "[redacted]", False, True),
        ("Here is s\tk-abcdefghijklmnopqrst", "[redacted]", False, True),
        (
            "Here is eyJ\nhbGciOiJub25lIn0.cGF5bG9hZA.c2lnbmF0dXJl",
            "[redacted]", False, True,
        ),
        (
            "Here is e\tyJhbGciOiJub25lIn0.cGF5bG9hZA.c2lnbmF0dXJl",
            "[redacted]", False, True,
        ),
        (
            "Here is e\x9b31myJhbGciOiJub25lIn0.cGF5bG9hZA.c2lnbmF0dXJl",
            "[redacted]", False, True,
        ),
        ("Here is sk-\u202e\tabcdefghijklmnopqrst", "[redacted]", False, True),
        ("rea\x9b31msoning_content: private deliberation", "[redacted]", False, True),
        *[
            (
                f'{{"rea{separator}soning_content":"private internal content"}}',
                "[redacted]", False, True,
            )
            for separator in DIAGNOSTIC_MARKER_SEPARATORS
        ],
        *[
            (f'{{"pr{separator}ivate_k{separator}ey":"private-value"}}', "[redacted]", False, True)
            for separator in DIAGNOSTIC_MARKER_SEPARATORS
        ],
        *[
            (
                f'<t{separator}hinking>private internal content</t{separator}hinking>',
                "[redacted]", False, True,
            )
            for separator in DIAGNOSTIC_MARKER_SEPARATORS
        ],
    ],
    ids=lambda value: (
        "large-text"
        if isinstance(value, str) and len(value) > LONG_TEST_ID_TEXT_LENGTH
        else None
    ),
)
def test_history_bounds_and_sanitizes_tagged_diagnostics_at_read_boundary(
    app, raw_text, expected, truncated, redacted,
):
    """Catches unbounded/unsafe migrated debug content crossing the protected response boundary."""
    run = _start(app)
    _, artifact = _runtime(app, run, success=False)
    with transaction_boundary(_factory(app)) as session:
        session.execute(sa.update(artifacts_table).where(
            artifacts_table.c.id == artifact.id
        ).values(content_text=raw_text, metadata={
            "atom_lab_run_id": run.id, "atom_lab_debug_version": 1,
        }))
    assert _get(app, "/" + run.id, access=None).status_code == HTTPStatus.UNAUTHORIZED
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK
    debug, = response.json()["diagnostics"]["debug_artifacts"]
    assert debug["raw_output_text"] == expected
    assert debug["truncated"] is truncated
    assert debug["redacted"] is redacted
    assert len(debug["raw_output_text"].encode("utf-8")) <= DEBUG_TEXT_MAX_BYTES
    assert response.json()["result"] is None


@pytest.mark.parametrize(
    "artifact_type,artifact_status",
    [
        ("structured_output_debug_raw", "failed"),
        ("workflow_result", "stored"),
        ("structured_output", "failed"),
    ],
)
def test_success_status_cannot_promote_noncanonical_artifact(app, artifact_type, artifact_status):
    run = _start(app)
    _, artifact = _runtime(app, run)
    with transaction_boundary(_factory(app)) as session:
        session.execute(
            sa.update(artifacts_table)
            .where(artifacts_table.c.id == artifact.id)
            .values(artifact_type=artifact_type, status=artifact_status)
        )
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK, response.text
    assert response.json()["result"] is None


def test_history_diagnostics_are_bounded_but_counts_are_complete(app):
    run = _start(app)
    _runtime(app, run, calls=tuple((index, 1) for index in range(1, LARGE_CALL_COUNT + 1)))
    response = _get(app, "/" + run.id)
    assert response.status_code == HTTPStatus.OK, response.text
    diagnostics = response.json()["diagnostics"]
    assert len(diagnostics["provider_calls"]) == DIAGNOSTIC_PAGE_SIZE
    assert diagnostics["provider_calls_truncated"] is True
    assert diagnostics["physical_calls"] == LARGE_CALL_COUNT
    assert diagnostics["validation_attempts"] == LARGE_CALL_COUNT


def test_history_default_and_maximum_page_sizes(app):
    settings = Settings(
        atom_lab_run_daily_limit=200, atom_lab_run_active_limit=200
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_atom_lab_run_settings] = lambda: settings
    for index in range(101):
        _start(app, f"page-{index}")
    default_page_size = 20
    maximum_page_size = 100
    default_page = _get(app).json()
    assert len(default_page["items"]) == default_page_size
    assert default_page["next_cursor"] is not None
    maximum_page = _get(app, "?limit=100").json()
    assert len(maximum_page["items"]) == maximum_page_size
    final_page = _get(app, "?cursor=" + maximum_page["next_cursor"]).json()
    assert len(final_page["items"]) == 1
    assert final_page["next_cursor"] is None


def test_history_requires_server_owned_lab_session_scope(app):
    run = _start(app)
    with transaction_boundary(_factory(app)) as session:
        session.execute(
            sa.update(scenario_sessions_table)
            .where(scenario_sessions_table.c.id == run.scenario_session_id)
            .values(metadata={})
        )
    assert _get(app).json() == {"items": [], "next_cursor": None}
    _error(_get(app, "/" + run.id), 404, "lab_resource_not_found")


@pytest.mark.parametrize(
    "timestamp,run_id",
    [
        ("2026-01-01", "valid_id"),
        ("invalid", "valid_id"),
        ("2026-01-01T00:00:00Z", True),
        ("2026-01-01T00:00:00Z", "id\nsecret"),
        ("2026-01-01T00:00:00Z", "x" * 129),
    ],
)
def test_history_cursor_rejects_invalid_typed_payload(app, timestamp, run_id):
    cursor = base64.urlsafe_b64encode(json.dumps(["runs-v1", timestamp, run_id]).encode()).decode()
    _error(_get(app, "?cursor=" + cursor), 422, "invalid_cursor")


def test_history_debug_artifact_diagnostics_are_explicitly_truncated(app):
    run = _start(app)
    _, artifact = _runtime(app, run, success=False)
    with transaction_boundary(_factory(app)) as session:
        for index in range(DIAGNOSTIC_PAGE_SIZE):
            session.execute(
                sa.insert(artifacts_table).values(**{**asdict(artifact), "id": f"debug-{index}"})
            )
    diagnostics = _get(app, "/" + run.id).json()["diagnostics"]
    assert len(diagnostics["debug_artifacts"]) == DIAGNOSTIC_PAGE_SIZE
    assert diagnostics["debug_artifacts_truncated"] is True


def test_history_response_contract_rejects_unknown_status_and_extra_fields(app):
    run = _start(app)
    body = _get(app, "/" + run.id).json()
    with pytest.raises(ValidationError):
        AtomLabRunDetailResponse.model_validate({**body, "status": "imagined"})
    with pytest.raises(ValidationError):
        AtomLabRunDetailResponse.model_validate({**body, "prompt": "unexpected"})


def test_history_does_not_use_artifacts_from_another_scope(app):
    run = _start(app)
    _, artifact = _runtime(app, run)
    with transaction_boundary(_factory(app)) as session:
        session.execute(
            sa.update(artifacts_table)
            .where(artifacts_table.c.id == artifact.id)
            .values(tenant_id="other")
        )
    assert _get(app, "/" + run.id).json()["result"] is None
