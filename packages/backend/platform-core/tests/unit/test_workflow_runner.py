from __future__ import annotations

import asyncio
from collections import Counter
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.executor import ActionExecutorResponse
from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.actions.runner import ActionRunService, ActionRunner
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.models import ProviderResponse, ProviderUsage
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import (
    action_runs_table,
    artifacts_table,
    event_log_table,
    jobs_table,
    provider_calls_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import (
    SequentialWorkflowRunner,
    WorkflowJobService,
)
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "workflow-main.sqlite3"
    platform_db = tmp_path / "workflow-platform.sqlite3"
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

    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(runtime_engine: sa.Engine) -> sa.orm.sessionmaker[sa.orm.Session]:
    return build_session_factory(runtime_engine)


@pytest.fixture
def config_registry() -> ConfigRegistry:
    return build_config_registry(CONFIG_ROOT)


def _base_context() -> ExecutionContext:
    return ExecutionContext(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        guest_id="guest_demo",
        user_id="user_demo",
    )


def _event_rows(session: sa.orm.Session) -> list[dict[str, Any]]:
    return list(session.execute(sa.select(event_log_table)).mappings())


def _event_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(row["event_type"]) for row in rows)


def _event_by_type(rows: list[dict[str, Any]], event_type: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["event_type"] == event_type]


class RecordingExecutor:
    executor_id = "structured_llm"

    def __init__(self, outputs_by_step: dict[str, dict[str, Any]]) -> None:
        self.outputs_by_step = outputs_by_step
        self.inputs_by_step: dict[str, list[dict[str, Any]]] = {}

    async def execute(self, request: Any, *, session: Any) -> ActionExecutorResponse:
        del session
        self.inputs_by_step.setdefault(request.step_id, []).append(dict(request.input_payload))
        return ActionExecutorResponse(
            structured_output=self.outputs_by_step[request.step_id],
        )


class FailOnceThenSucceedAdapter:
    def __init__(self) -> None:
        self.call_count = 0
        self._delegate = FakeProviderAdapter(FIXTURE_ROOT)

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("provider exploded with secret_token=abc123")
        return await self._delegate.complete(request)


class AlwaysFailAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        del request
        raise RuntimeError("provider exploded with secret_token=abc123")


class ExplodingActionRunner:
    async def run(
        self,
        action_type: str,
        action_config_id: str,
        input_payload: dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        del action_type, action_config_id, input_payload, context
        raise RuntimeError("workflow exploded with secret_token=abc123")


def _build_recording_workflow_runner(
    session: sa.orm.Session,
    *,
    executor: RecordingExecutor,
) -> SequentialWorkflowRunner:
    registry = build_config_registry(CONFIG_ROOT)
    emitter = EventEmitter(EventLogRepository(session))
    action_runner = ActionRunner(
        session=session,
        config_registry=registry,
        action_run_service=ActionRunService(ActionRunRepository(session), emitter),
        executors={executor.executor_id: executor},
        artifact_repository=ArtifactRepository(session),
    )
    return SequentialWorkflowRunner(
        session=session,
        config_registry=registry,
        job_service=WorkflowJobService(JobRepository(session), emitter),
        action_runner=action_runner,
        artifact_service=ArtifactService(ArtifactRepository(session), emitter),
        event_emitter=emitter,
    )


def _build_structured_workflow_runner(
    session: sa.orm.Session,
    *,
    adapter: Any | None = None,
) -> SequentialWorkflowRunner:
    registry = build_config_registry(CONFIG_ROOT)
    emitter = EventEmitter(EventLogRepository(session))
    gateway = ProviderGateway(
        {"fake": adapter or FakeProviderAdapter(FIXTURE_ROOT)},
        policy_resolver=ProviderPolicyResolver(registry),
        provider_call_repository=ProviderCallRepository(session),
        event_emitter=emitter,
    )
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=gateway,
        artifact_service=ArtifactService(ArtifactRepository(session), emitter),
    )
    action_runner = ActionRunner(
        session=session,
        config_registry=registry,
        action_run_service=ActionRunService(ActionRunRepository(session), emitter),
        executors={executor.executor_id: executor},
        artifact_repository=ArtifactRepository(session),
    )
    return SequentialWorkflowRunner(
        session=session,
        config_registry=registry,
        job_service=WorkflowJobService(JobRepository(session), emitter),
        action_runner=action_runner,
        artifact_service=ArtifactService(ArtifactRepository(session), emitter),
        event_emitter=emitter,
    )


def _build_workflow_runner_with_action_runner(
    session: sa.orm.Session,
    *,
    action_runner: Any,
) -> SequentialWorkflowRunner:
    registry = build_config_registry(CONFIG_ROOT)
    emitter = EventEmitter(EventLogRepository(session))
    return SequentialWorkflowRunner(
        session=session,
        config_registry=registry,
        job_service=WorkflowJobService(JobRepository(session), emitter),
        action_runner=action_runner,
        artifact_service=ArtifactService(ArtifactRepository(session), emitter),
        event_emitter=emitter,
    )


def test_workflow_runner_executes_single_step_workflow_and_creates_final_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_structured_workflow_runner(session)

        result = asyncio.run(
            runner.run(
                "kernel_demo.single_action_extract_v1",
                {"source_text": "deadline budget deliverables"},
                _base_context(),
            )
        )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        artifacts = list(session.execute(sa.select(artifacts_table)).mappings())
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "title": "Kernel Demo Source Summary",
        "fields": ["deadline", "budget", "deliverables"],
    }
    assert job["status"].value == "succeeded"
    assert job["result_artifact_id"] == result.result_artifact_id
    assert action_run["status"].value == "succeeded"
    assert provider_call["status"].value == "succeeded"
    assert len(artifacts) == 2
    final_artifact = next(artifact for artifact in artifacts if artifact["id"] == result.result_artifact_id)
    assert final_artifact["job_id"] == job["id"]
    assert final_artifact["action_run_id"] is None
    assert final_artifact["metadata"]["artifact_role"] == "workflow_result"
    assert _event_counts(events) == Counter(
        {
            "workflow.started": 1,
            "workflow.step_started": 1,
            "action.started": 1,
            "provider.request_started": 1,
            "provider.request_succeeded": 1,
            "artifact.created": 2,
            "action.succeeded": 1,
            "workflow.step_succeeded": 1,
            "workflow.succeeded": 1,
        }
    )


def test_workflow_runner_executes_multi_step_workflow_with_input_and_output_mappings(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    executor = RecordingExecutor(
        {
            "extract": {"title": "Extracted", "fields": ["deadline", "budget"]},
            "detect_issues": {"issues": [{"severity": "high", "issue": "Timeline risk"}]},
            "generate_report": {
                "headline": "Report",
                "summary": "Structured workflow complete",
            },
        }
    )
    with transaction_boundary(session_factory) as session:
        runner = _build_recording_workflow_runner(session, executor=executor)

        result = asyncio.run(
            runner.run(
                "kernel_demo.extract_detect_report_v1",
                {
                    "source_text": "deadline budget deliverables",
                    "taxonomy": ["timeline", "scope"],
                },
                _base_context(),
            )
        )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_runs = list(
            session.execute(
                sa.select(action_runs_table).order_by(action_runs_table.c.created_at, action_runs_table.c.id)
            ).mappings()
        )
        artifacts = list(session.execute(sa.select(artifacts_table)).mappings())

    assert result.status.value == "succeeded"
    assert executor.inputs_by_step["extract"][0] == {
        "source_text": "deadline budget deliverables",
    }
    assert executor.inputs_by_step["detect_issues"][0] == {
        "source_text": "deadline budget deliverables",
        "taxonomy": ["timeline", "scope"],
    }
    assert executor.inputs_by_step["generate_report"][0] == {
        "source_text": "deadline budget deliverables",
        "extracted": {"title": "Extracted", "fields": ["deadline", "budget"]},
        "issues": {"issues": [{"severity": "high", "issue": "Timeline risk"}]},
    }
    assert [row["step_id"] for row in action_runs] == ["extract", "detect_issues", "generate_report"]
    assert all(row["status"].value == "succeeded" for row in action_runs)
    assert len(artifacts) == 1
    assert result.output_payload == {
        "headline": "Report",
        "summary": "Structured workflow complete",
    }
    assert job["metadata"]["workflow_state"]["context"]["workflow_output"] == result.output_payload
    assert job["metadata"]["workflow_state"]["context"]["extracted"] == {
        "title": "Extracted",
        "fields": ["deadline", "budget"],
    }
    assert job["metadata"]["workflow_state"]["context"]["detected_issues"] == [
        {"severity": "high", "issue": "Timeline risk"}
    ]


def test_workflow_runner_skips_step_and_records_reason(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    executor = RecordingExecutor(
        {
            "extract": {"title": "Extracted", "fields": ["deadline", "budget"]},
            "optional_extract": {"title": "Optional", "fields": ["ignored"]},
        }
    )
    with transaction_boundary(session_factory) as session:
        runner = _build_recording_workflow_runner(session, executor=executor)

        result = asyncio.run(
            runner.run(
                "kernel_demo.conditional_skip_extract_v1",
                {
                    "source_text": "deadline budget deliverables",
                    "run_optional_step": False,
                },
                _base_context(),
            )
        )
        action_runs = list(
            session.execute(
                sa.select(action_runs_table).order_by(action_runs_table.c.created_at, action_runs_table.c.id)
            ).mappings()
        )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert list(executor.inputs_by_step) == ["extract"]
    assert [row["status"].value for row in action_runs] == ["succeeded", "skipped"]
    skipped = next(row for row in action_runs if row["step_id"] == "optional_extract")
    assert "falsy value" in skipped["metadata"]["skip_reason"]
    assert job["metadata"]["workflow_state"]["steps"]["optional_extract"]["status"] == "skipped"
    assert "falsy value" in job["metadata"]["workflow_state"]["steps"]["optional_extract"]["skip_reason"]
    skipped_events = _event_by_type(events, "workflow.step_skipped")
    assert len(skipped_events) == 1
    assert "falsy value" in skipped_events[0]["properties"]["skip_reason"]


def test_workflow_runner_retries_step_without_mixing_provider_retry_layers(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    adapter = FailOnceThenSucceedAdapter()
    with transaction_boundary(session_factory) as session:
        runner = _build_structured_workflow_runner(session, adapter=adapter)

        result = asyncio.run(
            runner.run(
                "kernel_demo.retry_extract_v1",
                {"source_text": "deadline budget deliverables"},
                _base_context(),
            )
        )
        action_runs = list(
            session.execute(
                sa.select(action_runs_table).order_by(action_runs_table.c.created_at, action_runs_table.c.id)
            ).mappings()
        )
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(provider_calls_table.c.created_at, provider_calls_table.c.id)
            ).mappings()
        )
        step_events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert adapter.call_count == 2
    assert [row["status"].value for row in action_runs] == ["failed", "succeeded"]
    assert len(provider_calls) == 2
    assert all(row["transport_attempt_index"] == 1 for row in provider_calls)
    assert all(row["physical_call_index"] == 1 for row in provider_calls)
    step_succeeded = _event_by_type(step_events, "workflow.step_succeeded")
    assert len(step_succeeded) == 1
    assert step_succeeded[0]["properties"]["attempt_count"] == 2


def test_workflow_runner_stops_after_failed_step(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_structured_workflow_runner(session, adapter=AlwaysFailAdapter())

        with pytest.raises(
            ProviderGatewayExecutionError,
            match="\\[redacted provider error\\]",
        ):
            asyncio.run(
                runner.run(
                    "kernel_demo.extract_detect_report_v1",
                    {
                        "source_text": "deadline budget deliverables",
                        "taxonomy": ["timeline", "scope"],
                    },
                    _base_context(),
                )
            )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_runs = list(session.execute(sa.select(action_runs_table)).mappings())
        events = _event_rows(session)

    assert job["status"].value == "failed"
    assert job["error_code"] == "workflow_execution_failed"
    assert job["error_message_safe"] == "Workflow execution failed."
    assert job["completed_at"] is not None
    assert job["result_artifact_id"] is None
    assert [row["step_id"] for row in action_runs] == ["extract"]
    assert _event_by_type(events, "workflow.step_failed")[0]["properties"]["step_id"] == "extract"
    assert not _event_by_type(events, "workflow.step_succeeded")
    assert _event_by_type(events, "workflow.failed")


def test_workflow_runner_latest_action_run_id_uses_ordered_timestamp_columns(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_recording_workflow_runner(
            session,
            executor=RecordingExecutor({"extract": {"title": "Extracted"}}),
        )
        repository = ActionRunRepository(session)
        created_at = utc_now()

        earlier = repository.create(
            ActionRunRecord(
                tenant_id="tenant_demo",
                region="eu-central",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                scenario_session_id="scenario_session_demo",
                job_id="job_demo",
                workflow_id="kernel_demo.single_action_extract_v1",
                step_id="extract",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                status=ActionRunStatus.failed,
                created_at=created_at,
                started_at=created_at,
            )
        )
        later = repository.create(
            ActionRunRecord(
                tenant_id="tenant_demo",
                region="eu-central",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                scenario_session_id="scenario_session_demo",
                job_id="job_demo",
                workflow_id="kernel_demo.single_action_extract_v1",
                step_id="extract",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                status=ActionRunStatus.failed,
                created_at=created_at,
                started_at=created_at + timedelta(microseconds=1),
            )
        )

        latest_id = runner._latest_action_run_id("job_demo", "extract")

    assert latest_id == later.id
    assert latest_id != earlier.id


def test_workflow_runner_persists_generic_safe_message_for_unknown_exceptions(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        runner = _build_workflow_runner_with_action_runner(
            session,
            action_runner=ExplodingActionRunner(),
        )

        with pytest.raises(RuntimeError):
            asyncio.run(
                runner.run(
                    "kernel_demo.single_action_extract_v1",
                    {"source_text": "deadline budget deliverables"},
                    _base_context(),
                )
            )
        job = session.execute(sa.select(jobs_table)).mappings().one()

    assert job["status"].value == "failed"
    assert job["error_code"] == "workflow_execution_failed"
    assert job["error_message_safe"] == "Workflow execution failed."
    assert "secret_token" not in job["error_message_safe"]


def test_workflow_runner_persists_failed_state_when_exception_escapes_transaction_boundary(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with pytest.raises(RuntimeError):
        with transaction_boundary(session_factory) as session:
            runner = _build_workflow_runner_with_action_runner(
                session,
                action_runner=ExplodingActionRunner(),
            )
            asyncio.run(
                runner.run(
                    "kernel_demo.single_action_extract_v1",
                    {"source_text": "deadline budget deliverables"},
                    _base_context(),
                )
            )

    with transaction_boundary(session_factory) as session:
        job = session.execute(sa.select(jobs_table)).mappings().one()
        events = _event_rows(session)

    assert job["status"].value == "failed"
    assert job["error_code"] == "workflow_execution_failed"
    assert job["error_message_safe"] == "Workflow execution failed."
    assert job["completed_at"] is not None
    assert _event_counts(events) == Counter({"workflow.failed": 1})
    assert _event_by_type(events, "workflow.failed")[0]["job_id"] == job["id"]
