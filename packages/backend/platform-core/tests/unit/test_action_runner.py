from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import event

from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.executor import ActionExecutorResponse
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.actions.runner import (
    ActionInputValidationError,
    ActionRunService,
    ActionRunner,
)
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    provider_calls_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    main_db = tmp_path / "action-runner-main.sqlite3"
    platform_db = tmp_path / "action-runner-platform.sqlite3"
    engine = sa.create_engine(_sqlite_url(main_db), future=True)

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
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

    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


def _context(
    *,
    step_id: str,
    action_type: str,
    action_config_id: str,
    workflow_version: int | None = 1,
) -> ExecutionContext:
    return ExecutionContext(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        workflow_id="kernel_demo.extract_detect_report_v1",
        workflow_version=workflow_version,
        step_id=step_id,
        guest_id="guest_demo",
        user_id="user_demo",
        action_type=action_type,
        action_config_id=action_config_id,
    )


class AlwaysFailFakeAdapter:
    async def complete(self, request: Any) -> Any:
        del request
        raise RuntimeError("provider exploded with secret_token=abc123")


class GenericExecutor:
    executor_id = "structured_llm"

    async def execute(self, request: Any, *, session: Any) -> ActionExecutorResponse:
        del request, session
        return ActionExecutorResponse(
            structured_output={"title": "Generic Summary", "fields": ["budget"]},
            metadata={"structured_output_artifact_id": "artifact_generic"},
        )


def _event_rows(session: sa.orm.Session) -> list[dict[str, Any]]:
    return list(
        session.execute(
            sa.select(event_log_table).order_by(
                event_log_table.c.timestamp,
                event_log_table.c.event_id,
            )
        ).mappings()
    )


def _build_runner(
    session: sa.orm.Session,
    *,
    fake_adapter: Any | None = None,
) -> ActionRunner:
    registry = build_config_registry(CONFIG_ROOT)
    emitter = EventEmitter(EventLogRepository(session))
    artifact_service = ArtifactService(ArtifactRepository(session), emitter)
    gateway = ProviderGateway(
        {"fake": fake_adapter or FakeProviderAdapter(FIXTURE_ROOT)},
        policy_resolver=ProviderPolicyResolver(registry),
        provider_call_repository=ProviderCallRepository(session),
        event_emitter=emitter,
    )
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=gateway,
        artifact_service=artifact_service,
    )
    return ActionRunner(
        session=session,
        config_registry=registry,
        action_run_service=ActionRunService(ActionRunRepository(session), emitter),
        executors={executor.executor_id: executor},
        artifact_repository=ArtifactRepository(session),
    )


def test_action_runner_executes_extract_structured_fields_and_persists_context(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.extract_structured_fields",
                "kernel_demo.extract_structured_fields_v1",
                {"source_text": "deadline budget deliverables"},
                _context(
                    step_id="extract",
                    action_type="text.extract_structured_fields",
                    action_config_id="kernel_demo.extract_structured_fields_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        artifact = session.execute(sa.select(artifacts_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "title": "Kernel Demo Source Summary",
        "fields": ["deadline", "budget", "deliverables"],
    }
    assert result.output_artifact_id == artifact["id"]
    assert action_run["status"].value == "succeeded"
    assert action_run["output_artifact_id"] == artifact["id"]
    assert action_run["metadata"]["workflow_version"] == 1
    assert action_run["metadata"]["guest_id"] == "guest_demo"
    assert action_run["metadata"]["user_id"] == "user_demo"
    assert artifact["action_run_id"] == action_run["id"]
    assert artifact["metadata"]["schema_ref"] == "kernel.schemas.extract_output_v1"
    assert provider_call["action_run_id"] == action_run["id"]
    assert provider_call["workflow_version"] == 1
    assert [row["event_type"] for row in events] == [
        "action.started",
        "provider.request_started",
        "provider.request_succeeded",
        "artifact.created",
        "action.succeeded",
    ]
    assert all(row["tenant_id"] == "tenant_demo" for row in events)
    assert all(row["region"] == "eu-central" for row in events)
    assert events[0]["guest_id"] == "guest_demo"
    assert events[0]["user_id"] == "user_demo"
    assert events[0]["workflow_version"] == 1
    assert events[1]["provider_policy_ref"] == "default_fake_provider_v1"
    assert events[2]["provider_call_id"] == provider_call["id"]
    assert events[3]["artifact_id"] == artifact["id"]
    assert events[4]["action_run_id"] == action_run["id"]


def test_action_runner_executes_detect_issues_atom_through_generic_path(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        result = asyncio.run(
            runner.run(
                "text.detect_issues_by_taxonomy",
                "kernel_demo.detect_issues_v1",
                {
                    "source_text": "We need this soon.",
                    "taxonomy": ["timeline", "scope", "requirements"],
                },
                _context(
                    step_id="detect_issues",
                    action_type="text.detect_issues_by_taxonomy",
                    action_config_id="kernel_demo.detect_issues_v1",
                ),
            )
        )

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "issues": [
            {
                "severity": "high",
                "issue": "Timeline is underspecified",
            }
        ]
    }


def test_action_runner_marks_failed_on_provider_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session, fake_adapter=AlwaysFailFakeAdapter())

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables"},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        events = _event_rows(session)

    assert exc_info.value.error_code == "provider_request_failed"
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "provider_request_failed"
    assert [row["event_type"] for row in events] == [
        "action.started",
        "provider.request_started",
        "provider.request_failed",
        "action.failed",
    ]


def test_action_runner_marks_failed_on_input_validation_error(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        with pytest.raises(ActionInputValidationError) as exc_info:
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"unexpected": "shape"},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                    ),
                )
            )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        provider_call_count = session.execute(
            sa.select(sa.func.count()).select_from(provider_calls_table)
        ).scalar_one()
        events = _event_rows(session)

    assert exc_info.value.code == "action_input_validation_failed"
    assert action_run["status"].value == "failed"
    assert action_run["error_code"] == "action_input_validation_failed"
    assert provider_call_count == 0
    assert [row["event_type"] for row in events] == [
        "action.started",
        "action.failed",
    ]
    assert events[0]["workflow_version"] == 1
    assert events[1]["workflow_version"] == 1


def test_action_runner_allows_executor_responses_without_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        registry = build_config_registry(CONFIG_ROOT)
        emitter = EventEmitter(EventLogRepository(session))
        runner = ActionRunner(
            session=session,
            config_registry=registry,
            action_run_service=ActionRunService(ActionRunRepository(session), emitter),
            executors={GenericExecutor.executor_id: GenericExecutor()},
            artifact_repository=ArtifactRepository(session),
        )

        result = asyncio.run(
            runner.run(
                "text.extract_structured_fields",
                "kernel_demo.extract_structured_fields_v1",
                {"source_text": "deadline budget deliverables"},
                _context(
                    step_id="extract",
                    action_type="text.extract_structured_fields",
                    action_config_id="kernel_demo.extract_structured_fields_v1",
                ),
            )
        )
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "title": "Generic Summary",
        "fields": ["budget"],
    }
    assert result.output_artifact_id == "artifact_generic"
    assert result.provider_policy_ref is None
    assert result.provider is None
    assert result.model is None
    assert action_run["metadata"]["llm_response_metadata"] == {
        "structured_output_artifact_id": "artifact_generic"
    }
    assert "provider" not in action_run["metadata"]
    assert "model" not in action_run["metadata"]


def test_action_runner_rejects_missing_workflow_version_before_creating_action_run(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_runner(session)

        with pytest.raises(ValueError, match="workflow_version"):
            asyncio.run(
                runner.run(
                    "text.extract_structured_fields",
                    "kernel_demo.extract_structured_fields_v1",
                    {"source_text": "deadline budget deliverables"},
                    _context(
                        step_id="extract",
                        action_type="text.extract_structured_fields",
                        action_config_id="kernel_demo.extract_structured_fields_v1",
                        workflow_version=None,
                    ),
                )
            )
        action_run_count = session.execute(
            sa.select(sa.func.count()).select_from(action_runs_table)
        ).scalar_one()
        event_count = session.execute(
            sa.select(sa.func.count()).select_from(event_log_table)
        ).scalar_one()

    assert action_run_count == 0
    assert event_count == 0
