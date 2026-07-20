from __future__ import annotations

import asyncio
from dataclasses import replace
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.scenarios.checkpoints import (
    FAILED_CHECKPOINT_ID,
    PROCESSING_CHECKPOINT_ID,
    RESULT_READY_CHECKPOINT_ID,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioSessionService
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    guest_quota_usage_table,
    jobs_table,
    provider_calls_table,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_worker.composition import build_worker
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


def _build_session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    main_db = tmp_path / "api-main.sqlite3"
    platform_db = tmp_path / "api-platform.sqlite3"
    engine = sa.create_engine(
        _sqlite_url(main_db),
        future=True,
        connect_args={"timeout": 30.0},
    )

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        dbapi_connection.execute("PRAGMA busy_timeout = 30000")
        dbapi_connection.execute(
            f"ATTACH DATABASE '{platform_db.resolve().as_posix()}' AS platform"
        )

    alembic_config = Config()
    alembic_config.set_main_option(
        "script_location", str(REPO_ROOT / "migrations" / "platform")
    )
    alembic_config.set_main_option("sqlalchemy.url", _sqlite_url(main_db))

    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")

    return build_session_factory(engine)


def _create_test_app(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
):
    with transaction_boundary(session_factory) as session:
        GuestIdentityRepository(session).create(
            GuestIdentityRecord(
                id="guest_demo",
                tenant_id="anytoolai",
                region="default",
            )
        )
    app = create_app(config_root=CONFIG_ROOT)
    app.state.runtime = replace(
        app.state.runtime,
        storage=RuntimeStorageDependencies(session_factory=session_factory),
    )
    return app


async def _request(
    app,
    method: str,
    path: str,
    *,
    json: Any | None = None,
    request_id: str = "req_scenario_runtime_test",
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(
            method,
            path,
            json=json,
            headers={"X-Request-ID": request_id},
        )


def _start_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "frontend_id": "kernel_demo_ce",
        "guest_id": "guest_demo",
        "input": {"source_text": "deadline budget deliverables"},
    }
    payload.update(overrides)
    return payload


def _mark_running(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    *,
    scenario_session_id: str,
    job_id: str,
) -> None:
    with transaction_boundary(session_factory) as session:
        job = JobRepository(session).claim_created(job_id)
        assert job is not None
        scenario = ScenarioSessionRepository(session).get_in_scope(
            scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario is not None
        ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        ).mark_running(scenario)


def _mark_completed(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    *,
    scenario_session_id: str,
    job_id: str,
) -> str:
    with transaction_boundary(session_factory) as session:
        job = JobRepository(session).get(job_id)
        assert job is not None
        scenario = ScenarioSessionRepository(session).get_in_scope(
            scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario is not None
        if job.status is JobStatus.created:
            claimed_job = JobRepository(session).claim_created(job.id)
            assert claimed_job is not None
            job = claimed_job
            ScenarioSessionService(
                ScenarioSessionRepository(session),
                EventEmitter(EventLogRepository(session)),
            ).mark_running(scenario)
            scenario = ScenarioSessionRepository(session).get_in_scope(
                scenario_session_id,
                tenant_id="anytoolai",
                region="default",
            )
            assert scenario is not None

        artifact = ArtifactRepository(session).create(
            ArtifactRecord(
                tenant_id=job.tenant_id,
                region=job.region,
                product_id=job.product_id,
                frontend_id=job.frontend_id,
                scenario_session_id=job.scenario_session_id,
                job_id=job.id,
                artifact_type="structured_output",
                status=ArtifactStatus.stored,
                content_json={"ok": True},
            )
        )
        succeeded_job = JobRepository(session).mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=artifact.id,
                completed_at=artifact.created_at,
            )
        )
        ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        ).mark_completed(replace(scenario, completed_at=succeeded_job.completed_at))
        return artifact.id


def _mark_failed(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    *,
    scenario_session_id: str,
    job_id: str,
) -> None:
    with transaction_boundary(session_factory) as session:
        job = JobRepository(session).get(job_id)
        assert job is not None
        scenario = ScenarioSessionRepository(session).get_in_scope(
            scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario is not None
        if job.status is JobStatus.created:
            claimed_job = JobRepository(session).claim_created(job.id)
            assert claimed_job is not None
            job = claimed_job
            ScenarioSessionService(
                ScenarioSessionRepository(session),
                EventEmitter(EventLogRepository(session)),
            ).mark_running(scenario)
            scenario = ScenarioSessionRepository(session).get_in_scope(
                scenario_session_id,
                tenant_id="anytoolai",
                region="default",
            )
            assert scenario is not None

        failed_job = JobRepository(session).mark_failed(
            replace(
                job,
                status=JobStatus.failed,
                error_code="workflow_execution_failed",
                error_message_safe="Workflow execution failed.",
            )
        )
        ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        ).mark_failed(
            replace(scenario, completed_at=failed_job.completed_at),
            error_code="workflow_execution_failed",
        )


def test_start_scenario_creates_session_and_linked_job(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(guest_id="guest_demo"),
        )
    )

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data == {
        "scenario_session_id": data["scenario_session_id"],
        "job_id": data["job_id"],
        "status": "started",
        "allowed_next_actions": [],
        "result_artifact_id": None,
    }

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get_in_scope(
            data["scenario_session_id"],
            tenant_id="anytoolai",
            region="default",
        )
        job = JobRepository(session).get(data["job_id"])

    assert scenario is not None
    assert scenario.metadata["input"] == {"source_text": "deadline budget deliverables"}
    assert scenario.current_checkpoint_id == PROCESSING_CHECKPOINT_ID
    assert job is not None
    assert job.scenario_session_id == data["scenario_session_id"]
    assert job.product_id == scenario.product_id
    assert job.frontend_id == scenario.frontend_id


def test_start_scenario_consumes_guest_quota_and_returns_exhausted_on_n_plus_one(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    successes = [
        asyncio.run(
            _request(
                app,
                "POST",
                "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
                json=_start_payload(),
                request_id=f"req_quota_success_{index}",
            )
        )
        for index in range(3)
    ]
    exhausted = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(),
            request_id="req_quota_exhausted",
        )
    )

    assert [response.status_code for response in successes] == [HTTPStatus.OK] * 3
    assert exhausted.status_code == HTTPStatus.TOO_MANY_REQUESTS
    assert exhausted.json() == {
        "error": {
            "code": "quota_exhausted",
            "message": "Guest quota exhausted.",
            "request_id": "req_quota_exhausted",
        }
    }

    with transaction_boundary(session_factory) as session:
        scenario_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()
        job_count = session.execute(
            sa.select(sa.func.count()).select_from(jobs_table)
        ).scalar_one()
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).order_by(
                    event_log_table.c.timestamp,
                    event_log_table.c.event_id,
                )
            ).scalars()
        )

    assert scenario_count == 3
    assert job_count == 3
    assert event_types.count("quota.consumed") == 3
    assert event_types.count("quota.exhausted") == 1


def test_start_scenario_requires_valid_guest_identity_for_quota_product(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    missing_guest = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(guest_id=None),
            request_id="req_missing_guest_start",
        )
    )
    unknown_guest = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(guest_id="guest_missing"),
            request_id="req_unknown_guest_start",
        )
    )

    assert missing_guest.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert missing_guest.json() == {
        "error": {
            "code": "guest_identity_required",
            "message": "Guest identity is required for this product.",
            "request_id": "req_missing_guest_start",
        }
    }
    assert unknown_guest.status_code == HTTPStatus.NOT_FOUND
    assert unknown_guest.json() == {
        "error": {
            "code": "guest_identity_not_found",
            "message": "Guest identity not found.",
            "request_id": "req_unknown_guest_start",
        }
    }

    with transaction_boundary(session_factory) as session:
        scenario_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()
        job_count = session.execute(
            sa.select(sa.func.count()).select_from(jobs_table)
        ).scalar_one()
        event_types = list(session.execute(sa.select(event_log_table.c.event_type)).scalars())

    assert scenario_count == 0
    assert job_count == 0
    assert "quota.consumed" not in event_types


def test_parallel_start_scenario_consumes_quota_exactly_to_limit(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    async def start_parallel_requests() -> list[httpx.Response]:
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
                        headers={"X-Request-ID": f"req_parallel_start_{index}"},
                    )
                    for index in range(4)
                ]
            )

    responses = asyncio.run(start_parallel_requests())
    status_codes = [response.status_code for response in responses]

    assert status_codes.count(HTTPStatus.OK) == 3
    assert status_codes.count(HTTPStatus.TOO_MANY_REQUESTS) == 1
    exhausted_response = next(
        response for response in responses if response.status_code == HTTPStatus.TOO_MANY_REQUESTS
    )
    assert exhausted_response.json()["error"]["code"] == "quota_exhausted"

    with transaction_boundary(session_factory) as session:
        scenario_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()
        job_count = session.execute(
            sa.select(sa.func.count()).select_from(jobs_table)
        ).scalar_one()
        usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).order_by(
                    event_log_table.c.timestamp,
                    event_log_table.c.event_id,
                )
            ).scalars()
        )

    assert scenario_count == 3
    assert job_count == 3
    assert usage["used_count"] == 3
    assert usage["limit_count"] == 3
    assert event_types.count("quota.consumed") == 3
    assert event_types.count("quota.exhausted") == 1


def test_start_scenario_returns_safe_404_for_unknown_or_unattached_scenario(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.missing_v1/start",
            json=_start_payload(),
        )
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "error": {
            "code": "scenario_not_found",
            "message": "Scenario not found.",
            "request_id": "req_scenario_runtime_test",
        }
    }
    assert "kernel_demo.missing_v1" not in response.text


def test_start_scenario_rejects_invalid_frontend_and_input_shape(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    invalid_frontend = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(frontend_id="unknown_frontend"),
        )
    )
    invalid_input = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(input=["not", "an", "object"]),
            request_id="req_invalid_input",
        )
    )

    assert invalid_frontend.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid_frontend.json()["error"]["code"] == "scenario_frontend_invalid"
    assert invalid_input.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert invalid_input.json() == {
        "error": {
            "code": "scenario_input_invalid",
            "message": "Scenario input must be a JSON object.",
            "request_id": "req_invalid_input",
        }
    }


def test_get_scenario_session_returns_started_and_running_snapshots(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    started_response = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(),
        )
    )
    started = started_response.json()

    queued = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
        )
    )

    _mark_running(
        session_factory,
        scenario_session_id=started["scenario_session_id"],
        job_id=started["job_id"],
    )
    running = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
            request_id="req_running",
        )
    )

    assert queued.status_code == HTTPStatus.OK
    assert queued.json() == {
        "scenario_session_id": started["scenario_session_id"],
        "job_id": started["job_id"],
        "status": "started",
        "current_checkpoint_id": PROCESSING_CHECKPOINT_ID,
        "allowed_next_actions": [],
        "result_artifact_id": None,
    }
    assert running.status_code == HTTPStatus.OK
    assert running.json() == {
        "scenario_session_id": started["scenario_session_id"],
        "job_id": started["job_id"],
        "status": "running",
        "current_checkpoint_id": PROCESSING_CHECKPOINT_ID,
        "allowed_next_actions": [],
        "result_artifact_id": None,
    }


def test_get_scenario_session_returns_completed_snapshot(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    started = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(),
        )
    ).json()

    artifact_id = _mark_completed(
        session_factory,
        scenario_session_id=started["scenario_session_id"],
        job_id=started["job_id"],
    )

    response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
        )
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "scenario_session_id": started["scenario_session_id"],
        "job_id": started["job_id"],
        "status": "completed",
        "current_checkpoint_id": RESULT_READY_CHECKPOINT_ID,
        "allowed_next_actions": ["copy_result", "create_handoff"],
        "result_artifact_id": artifact_id,
    }


def test_start_then_real_worker_execution_preserves_a12_runtime_correlation(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    started = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(guest_id="guest_demo", user_id="user_demo"),
        )
    ).json()

    worker = build_worker(
        session_factory=session_factory,
        config_root=CONFIG_ROOT,
        provider_adapters={"fake": FakeProviderAdapter(FIXTURE_ROOT)},
    )
    processed = asyncio.run(worker.process_next_job())
    assert processed is not None
    assert processed.id == started["job_id"]
    assert processed.status is JobStatus.succeeded
    assert processed.result_artifact_id is not None

    response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
            request_id="req_vertical_poll",
        )
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "scenario_session_id": started["scenario_session_id"],
        "job_id": started["job_id"],
        "status": "completed",
        "current_checkpoint_id": RESULT_READY_CHECKPOINT_ID,
        "allowed_next_actions": ["copy_result", "create_handoff"],
        "result_artifact_id": processed.result_artifact_id,
    }

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get_in_scope(
            started["scenario_session_id"],
            tenant_id="anytoolai",
            region="default",
        )
        job = JobRepository(session).get(started["job_id"])
        action_run = session.execute(
            sa.select(action_runs_table).where(action_runs_table.c.job_id == started["job_id"])
        ).mappings().one()
        provider_call = session.execute(
            sa.select(provider_calls_table).where(
                provider_calls_table.c.job_id == started["job_id"]
            )
        ).mappings().one()
        artifacts = list(
            session.execute(
                sa.select(artifacts_table)
                .where(artifacts_table.c.job_id == started["job_id"])
                .order_by(artifacts_table.c.created_at, artifacts_table.c.id)
            ).mappings()
        )
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.scenario_session_id == started["scenario_session_id"])
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert scenario is not None
    assert scenario.status.value == "completed"
    assert scenario.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert job is not None
    assert job.scenario_session_id == started["scenario_session_id"]
    assert job.product_id == scenario.product_id
    assert job.frontend_id == scenario.frontend_id
    assert job.result_artifact_id == processed.result_artifact_id

    assert action_run["scenario_session_id"] == started["scenario_session_id"]
    assert provider_call["scenario_session_id"] == started["scenario_session_id"]
    assert provider_call["job_id"] == started["job_id"]
    assert provider_call["action_run_id"] == action_run["id"]
    assert all(artifact["scenario_session_id"] == started["scenario_session_id"] for artifact in artifacts)
    assert any(artifact["id"] == processed.result_artifact_id for artifact in artifacts)
    result_artifact = next(
        artifact for artifact in artifacts if artifact["id"] == processed.result_artifact_id
    )
    assert result_artifact["job_id"] == started["job_id"]
    assert result_artifact["scenario_session_id"] == started["scenario_session_id"]

    event_types = [event_row["event_type"] for event_row in events]
    assert {
        "scenario.started",
        "workflow.started",
        "action.started",
        "provider.request_started",
        "provider.request_succeeded",
        "artifact.created",
        "action.succeeded",
        "workflow.succeeded",
        "scenario.checkpoint_reached",
        "scenario.completed",
    }.issubset(event_types)
    for event_row in events:
        if event_row["job_id"] is not None:
            assert event_row["job_id"] == started["job_id"]


def test_get_scenario_session_returns_failed_snapshot(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    started = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(),
        )
    ).json()

    _mark_failed(
        session_factory,
        scenario_session_id=started["scenario_session_id"],
        job_id=started["job_id"],
    )

    response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
        )
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "scenario_session_id": started["scenario_session_id"],
        "job_id": started["job_id"],
        "status": "failed",
        "current_checkpoint_id": FAILED_CHECKPOINT_ID,
        "allowed_next_actions": [],
        "result_artifact_id": None,
    }


def test_get_scenario_session_returns_failed_checkpoint_for_preclaim_canceled_job(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    started = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(),
        )
    ).json()

    with transaction_boundary(session_factory) as session:
        canceled_job = JobRepository(session).cancel_created(started["job_id"])
        assert canceled_job is not None
        scenario = ScenarioSessionRepository(session).get_in_scope(
            started["scenario_session_id"],
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario is not None
        assert scenario.current_checkpoint_id == PROCESSING_CHECKPOINT_ID

    response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
            request_id="req_preclaim_cancel",
        )
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "scenario_session_id": started["scenario_session_id"],
        "job_id": started["job_id"],
        "status": "failed",
        "current_checkpoint_id": FAILED_CHECKPOINT_ID,
        "allowed_next_actions": [],
        "result_artifact_id": None,
    }


def test_next_action_validates_checkpoint_and_emits_event(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    started = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(),
        )
    ).json()
    artifact_id = _mark_completed(
        session_factory,
        scenario_session_id=started["scenario_session_id"],
        job_id=started["job_id"],
    )

    success = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/copy_result",
            json={"checkpoint_id": RESULT_READY_CHECKPOINT_ID},
        )
    )
    stale = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/copy_result",
            json={"checkpoint_id": FAILED_CHECKPOINT_ID},
            request_id="req_stale",
        )
    )
    disallowed = asyncio.run(
        _request(
            app,
            "POST",
            f"/v1/scenario-sessions/{started['scenario_session_id']}/next-actions/view_paywall",
            json={"checkpoint_id": RESULT_READY_CHECKPOINT_ID},
            request_id="req_disallowed",
        )
    )

    assert success.status_code == HTTPStatus.OK
    assert success.json() == {
        "scenario_session_id": started["scenario_session_id"],
        "job_id": started["job_id"],
        "status": "completed",
        "current_checkpoint_id": RESULT_READY_CHECKPOINT_ID,
        "allowed_next_actions": ["copy_result", "create_handoff"],
        "result_artifact_id": artifact_id,
    }
    assert stale.status_code == HTTPStatus.CONFLICT
    assert stale.json()["error"]["code"] == "scenario_checkpoint_conflict"
    assert disallowed.status_code == HTTPStatus.CONFLICT
    assert disallowed.json()["error"]["code"] == "scenario_next_action_not_allowed"

    with transaction_boundary(session_factory) as session:
        event_row = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "client.next_action_clicked"
            )
        ).mappings().one()

    assert event_row["scenario_session_id"] == started["scenario_session_id"]
    assert event_row["job_id"] == started["job_id"]
    assert event_row["properties"] == {
        "checkpoint_id": RESULT_READY_CHECKPOINT_ID,
        "next_action_id": "copy_result",
    }


def test_get_scenario_session_returns_safe_404(tmp_path: Path) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    response = asyncio.run(
        _request(app, "GET", "/v1/scenario-sessions/scenario_session_missing")
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["error"]["code"] == "scenario_session_not_found"
    assert "scenario_session_missing" not in response.text


def test_get_scenario_session_returns_safe_404_for_persisted_scenario_version_mismatch(
    tmp_path: Path,
) -> None:
    session_factory = _build_session_factory(tmp_path)
    app = _create_test_app(session_factory)

    started = asyncio.run(
        _request(
            app,
            "POST",
            "/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
            json=_start_payload(),
        )
    ).json()

    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).get_in_scope(
            started["scenario_session_id"],
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario is not None
        ScenarioSessionRepository(session).update(
            replace(scenario, scenario_version=scenario.scenario_version + 1),
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
        )

    response = asyncio.run(
        _request(
            app,
            "GET",
            f"/v1/scenario-sessions/{started['scenario_session_id']}",
            request_id="req_scenario_version_missing",
        )
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json() == {
        "error": {
            "code": "scenario_not_found",
            "message": "Scenario not found.",
            "request_id": "req_scenario_version_missing",
        }
    }
    assert "single_action_smoke_v1" not in response.text


def test_openapi_contains_scenario_runtime_endpoints() -> None:
    app = create_app(config_root=CONFIG_ROOT)
    openapi = app.openapi()

    start_operation = openapi["paths"][
        "/v1/products/{product_id}/scenarios/{scenario_id}/start"
    ]["post"]
    get_operation = openapi["paths"]["/v1/scenario-sessions/{scenario_session_id}"]["get"]
    next_action_operation = openapi["paths"][
        "/v1/scenario-sessions/{scenario_session_id}/next-actions/{next_action_id}"
    ]["post"]

    assert (
        start_operation["responses"]["200"]["content"]["application/json"]["example"]["status"]
        == "started"
    )
    assert (
        start_operation["responses"]["404"]["content"]["application/json"]["examples"][
            "guest_not_found"
        ]["value"]["error"]["code"]
        == "guest_identity_not_found"
    )
    assert (
        start_operation["responses"]["422"]["content"]["application/json"]["examples"][
            "guest_required"
        ]["value"]["error"]["code"]
        == "guest_identity_required"
    )
    assert (
        start_operation["responses"]["429"]["content"]["application/json"]["example"]["error"][
            "code"
        ]
        == "quota_exhausted"
    )
    assert (
        get_operation["responses"]["200"]["content"]["application/json"]["example"][
            "current_checkpoint_id"
        ]
        == "result_ready"
    )
    assert (
        next_action_operation["responses"]["409"]["content"]["application/json"]["example"][
            "error"
        ]["code"]
        == "scenario_checkpoint_conflict"
    )
