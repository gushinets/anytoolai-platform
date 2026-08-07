from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from anytoolai_platform_actions.structured_llm.cross_validation import (
    DetectIssuesByTaxonomyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
)
from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.executor import ActionExecutorResponse
from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.actions.runner import ActionRunner, ActionRunService
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
from anytoolai_platform_core.providers.models import ProviderResponse
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
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
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError
from anytoolai_platform_core.workflows.errors import (
    WorkflowConditionEvaluationError,
    WorkflowMappingResolutionError,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import (
    SequentialWorkflowRunner,
    WorkflowJobService,
    _emit_recovered_workflow_events,
)
from tests.db_support import provision_database

_EXTRACT_FIELDS = [
    {
        "name": "deadline",
        "type": "string",
        "description": "Project deadline mentioned in the text.",
        "required": True,
    },
    {
        "name": "budget",
        "type": "string",
        "description": "Budget mentioned in the text.",
        "required": False,
    },
    {
        "name": "deliverables",
        "type": "array_of_strings",
        "description": "Deliverables mentioned in the text.",
        "required": False,
    },
]


REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"
pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def runtime_engine() -> Iterator[sa.Engine]:
    with provision_database(
        database_name_prefix="anytoolai_workflow_runner_test",
        skip_reason="PostgreSQL workflow runner coverage",
    ) as (engine, _alembic_config, _database_url):
        yield engine


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
        scenario_chain_id="scenario_chain_demo",
        handoff_id="handoff_demo",
        acquisition_source="kernel_demo_ce",
    )


def _seed_context_scenario(
    session: sa.orm.Session,
    context: ExecutionContext | None = None,
) -> None:
    seeded = context or _base_context()
    ScenarioSessionRepository(session).create(
        ScenarioSessionRecord(
            id=seeded.scenario_session_id or "scenario_session_demo",
            tenant_id=seeded.tenant_id,
            region=seeded.region,
            product_id=seeded.product_id,
            frontend_id=seeded.frontend_id,
            scenario_id="smoke_start",
            scenario_version=1,
            guest_id=seeded.guest_id,
            user_id=seeded.user_id,
            scenario_chain_id=seeded.scenario_chain_id,
        )
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


def _event_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(row["event_type"]) for row in rows)


def _event_types(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row["event_type"]) for row in rows]


def _assert_event_types(
    rows: list[dict[str, Any]],
    expected_event_types: list[str],
) -> None:
    assert _event_types(rows) == expected_event_types


def _assert_strictly_increasing_event_timestamps(rows: list[dict[str, Any]]) -> None:
    for previous, current in zip(rows, rows[1:], strict=False):
        assert previous["timestamp"] < current["timestamp"]


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


class CancelledAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        del request
        raise asyncio.CancelledError()


class UnsafeRawTextProviderAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        raise RuntimeError(
            "provider returned raw prompt="
            f"{request.prompt}; customer_text=deadline budget deliverables"
        )


class FailOnSecondCallAdapter:
    def __init__(self) -> None:
        self.call_count = 0
        self._delegate = FakeProviderAdapter(FIXTURE_ROOT)

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        if self.call_count == 2:
            raise RuntimeError("provider exploded with secret_token=abc123")
        return await self._delegate.complete(request)


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


class ValidationFailingActionRunner:
    async def run(
        self,
        action_type: str,
        action_config_id: str,
        input_payload: dict[str, Any],
        context: ExecutionContext,
    ) -> Any:
        del action_type, action_config_id, input_payload, context
        raise StructuredOutputValidationError(
            reason="schema_mismatch",
            error_type="StructuredOutputSchemaMismatchError",
        )


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
        output_cross_validators={
            "text.extract_structured_fields": ExtractStructuredFieldsCrossValidator(),
            "text.detect_issues_by_taxonomy": DetectIssuesByTaxonomyCrossValidator(),
        },
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
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_structured_workflow_runner(session)

        result = asyncio.run(
            runner.run(
                "kernel_demo.single_action_extract_v1",
                {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                context,
            )
        )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_run = session.execute(sa.select(action_runs_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()
        artifacts = list(session.execute(sa.select(artifacts_table)).mappings())
        events = _event_rows(session)

    assert result.status.value == "succeeded"
    assert result.output_payload == {
        "values": {
            "deadline": "next Friday",
            "budget": "$5,000",
            "deliverables": ["logo", "landing page"],
        },
        "missing_fields": [],
        "confidence": {"deadline": 0.9, "budget": 0.8, "deliverables": 0.7},
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
    workflow_started = _event_by_type(events, "workflow.started")[0]
    workflow_step_started = _event_by_type(events, "workflow.step_started")[0]
    action_started = _event_by_type(events, "action.started")[0]
    provider_started = _event_by_type(events, "provider.request_started")[0]
    artifact_created = _event_by_type(events, "artifact.created")
    workflow_step_succeeded = _event_by_type(events, "workflow.step_succeeded")[0]
    workflow_succeeded = _event_by_type(events, "workflow.succeeded")[0]
    assert workflow_started["guest_id"] == "guest_demo"
    assert workflow_started["user_id"] == "user_demo"
    assert workflow_started["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_started["handoff_id"] == "handoff_demo"
    assert workflow_started["acquisition_source"] == "kernel_demo_ce"
    assert workflow_step_started["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_step_started["handoff_id"] == "handoff_demo"
    assert workflow_step_started["acquisition_source"] == "kernel_demo_ce"
    assert workflow_step_succeeded["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_step_succeeded["handoff_id"] == "handoff_demo"
    assert workflow_step_succeeded["acquisition_source"] == "kernel_demo_ce"
    assert action_started["scenario_chain_id"] == "scenario_chain_demo"
    assert action_started["handoff_id"] == "handoff_demo"
    assert action_started["acquisition_source"] == "kernel_demo_ce"
    assert provider_started["scenario_chain_id"] == "scenario_chain_demo"
    assert provider_started["handoff_id"] == "handoff_demo"
    assert provider_started["acquisition_source"] == "kernel_demo_ce"
    action_artifact_event = next(
        event for event in artifact_created if event["action_run_id"] == action_run["id"]
    )
    final_artifact_event = next(
        event for event in artifact_created if event["artifact_id"] == result.result_artifact_id
    )
    assert action_artifact_event["workflow_id"] == "kernel_demo.single_action_extract_v1"
    assert action_artifact_event["workflow_version"] == 1
    assert action_artifact_event["guest_id"] == "guest_demo"
    assert action_artifact_event["user_id"] == "user_demo"
    assert action_artifact_event["scenario_chain_id"] == "scenario_chain_demo"
    assert action_artifact_event["handoff_id"] == "handoff_demo"
    assert action_artifact_event["acquisition_source"] == "kernel_demo_ce"
    assert action_artifact_event["action_run_id"] == action_run["id"]
    assert final_artifact_event["workflow_id"] == "kernel_demo.single_action_extract_v1"
    assert final_artifact_event["workflow_version"] == 1
    assert final_artifact_event["guest_id"] == "guest_demo"
    assert final_artifact_event["user_id"] == "user_demo"
    assert final_artifact_event["scenario_chain_id"] == "scenario_chain_demo"
    assert final_artifact_event["handoff_id"] == "handoff_demo"
    assert final_artifact_event["acquisition_source"] == "kernel_demo_ce"
    assert final_artifact_event["action_run_id"] is None
    assert workflow_succeeded["guest_id"] == "guest_demo"
    assert workflow_succeeded["user_id"] == "user_demo"
    assert workflow_succeeded["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_succeeded["handoff_id"] == "handoff_demo"
    assert workflow_succeeded["acquisition_source"] == "kernel_demo_ce"


def test_workflow_runner_executes_an_existing_claimed_job_without_duplicate_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_structured_workflow_runner(session)
        repository = JobRepository(session)
        claimed = WorkflowJobService(
            repository,
            EventEmitter(EventLogRepository(session)),
        ).claim_created(
            repository.create(
                JobRecord(
                    tenant_id="tenant_demo",
                    region="eu-central",
                    product_id="kernel_demo",
                    frontend_id="kernel_demo_ce",
                    scenario_session_id="scenario_session_demo",
                    workflow_id="kernel_demo.single_action_extract_v1",
                    workflow_version=1,
                )
            ).id
        )
        assert claimed is not None

        result = asyncio.run(
            runner.run_claimed_job(
                claimed,
                {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                context,
            )
        )
        jobs = list(session.execute(sa.select(jobs_table)).mappings())
        action_runs = list(session.execute(sa.select(action_runs_table)).mappings())
        provider_calls = list(session.execute(sa.select(provider_calls_table)).mappings())
        artifacts = list(session.execute(sa.select(artifacts_table)).mappings())

    assert result.status is JobStatus.succeeded
    assert len(jobs) == 1
    assert jobs[0]["id"] == claimed.id
    assert jobs[0]["status"] is JobStatus.succeeded
    assert jobs[0]["result_artifact_id"] == result.result_artifact_id
    assert action_runs[0]["job_id"] == claimed.id
    assert provider_calls[0]["job_id"] == claimed.id
    assert all(artifact["job_id"] == claimed.id for artifact in artifacts)


def test_workflow_runner_recovers_failed_state_for_existing_claimed_job_after_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)
        repository = JobRepository(session)
        claimed = WorkflowJobService(
            repository,
            EventEmitter(EventLogRepository(session)),
        ).claim_created(
            repository.create(
                JobRecord(
                    tenant_id="tenant_demo",
                    region="eu-central",
                    product_id="kernel_demo",
                    frontend_id="kernel_demo_ce",
                    scenario_session_id="scenario_session_demo",
                    workflow_id="kernel_demo.single_action_extract_v1",
                    workflow_version=1,
                )
            ).id
        )
        assert claimed is not None
        claimed_job_id = claimed.id

    with pytest.raises(ProviderGatewayExecutionError):
        with transaction_boundary(session_factory) as session:
            runner = _build_structured_workflow_runner(session, adapter=AlwaysFailAdapter())
            job = JobRepository(session).get(claimed_job_id)
            assert job is not None
            asyncio.run(
                runner.run_claimed_job(
                    job,
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )

    with transaction_boundary(session_factory) as session:
        job = session.execute(
            sa.select(jobs_table).where(jobs_table.c.id == claimed_job_id)
        ).mappings().one()
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == claimed_job_id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert job["status"] is JobStatus.failed
    assert job["error_code"] == "provider_request_failed"
    assert job["error_message_safe"] == "Provider request failed."
    assert job["metadata"]["workflow_state"]["steps"]["extract"]["status"] == "failed"
    assert job["metadata"]["workflow_state"]["steps"]["extract"]["error_code"] == (
        "provider_request_failed"
    )
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "action.started",
            "provider.request_started",
            "provider.request_failed",
            "action.failed",
            "workflow.step_failed",
            "workflow.failed",
        ],
    )
    _assert_strictly_increasing_event_timestamps(events)
    workflow_step_started = _event_by_type(events, "workflow.step_started")[0]
    action_failed = _event_by_type(events, "action.failed")[0]
    workflow_step_failed = _event_by_type(events, "workflow.step_failed")[0]
    workflow_failed = _event_by_type(events, "workflow.failed")[0]
    assert workflow_step_started["job_id"] == claimed_job_id
    assert workflow_step_started["properties"]["step_id"] == "extract"
    assert workflow_step_failed["job_id"] == claimed_job_id
    assert workflow_step_failed["action_run_id"] == action_failed["action_run_id"]
    assert workflow_step_failed["properties"]["step_id"] == "extract"
    assert workflow_step_failed["properties"]["error_code"] == "provider_request_failed"
    assert workflow_failed["job_id"] == claimed_job_id
    assert workflow_failed["properties"]["error_code"] == "provider_request_failed"


def test_workflow_runner_recovers_canceled_state_for_existing_claimed_job_after_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)
        repository = JobRepository(session)
        claimed = WorkflowJobService(
            repository,
            EventEmitter(EventLogRepository(session)),
        ).claim_created(
            repository.create(
                JobRecord(
                    tenant_id="tenant_demo",
                    region="eu-central",
                    product_id="kernel_demo",
                    frontend_id="kernel_demo_ce",
                    scenario_session_id="scenario_session_demo",
                    workflow_id="kernel_demo.single_action_extract_v1",
                    workflow_version=1,
                )
            ).id
        )
        assert claimed is not None
        claimed_job_id = claimed.id

    with pytest.raises(asyncio.CancelledError):
        with transaction_boundary(session_factory) as session:
            runner = _build_structured_workflow_runner(session, adapter=CancelledAdapter())
            job = JobRepository(session).get(claimed_job_id)
            assert job is not None
            asyncio.run(
                runner.run_claimed_job(
                    job,
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )

    with transaction_boundary(session_factory) as session:
        job = session.execute(
            sa.select(jobs_table).where(jobs_table.c.id == claimed_job_id)
        ).mappings().one()
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == claimed_job_id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert job["status"] is JobStatus.canceled
    assert job["completed_at"] is not None
    assert job["metadata"]["workflow_state"]["steps"]["extract"]["status"] == "failed"
    assert job["metadata"]["workflow_state"]["steps"]["extract"]["error_code"] == (
        "workflow_execution_cancelled"
    )
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "action.started",
            "provider.request_started",
            "provider.request_failed",
            "action.failed",
            "workflow.step_failed",
            "workflow.canceled",
        ],
    )
    _assert_strictly_increasing_event_timestamps(events)
    workflow_step_failed = _event_by_type(events, "workflow.step_failed")[0]
    workflow_canceled = _event_by_type(events, "workflow.canceled")[0]
    assert workflow_step_failed["timestamp"] < workflow_canceled["timestamp"]
    assert workflow_canceled["job_id"] == claimed_job_id
    assert workflow_canceled["result_status"] == JobStatus.canceled.value


def test_workflow_runner_recovers_succeeded_state_for_existing_claimed_job_after_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)
        repository = JobRepository(session)
        claimed = WorkflowJobService(
            repository,
            EventEmitter(EventLogRepository(session)),
        ).claim_created(
            repository.create(
                JobRecord(
                    tenant_id="tenant_demo",
                    region="eu-central",
                    product_id="kernel_demo",
                    frontend_id="kernel_demo_ce",
                    scenario_session_id="scenario_session_demo",
                    workflow_id="kernel_demo.single_action_extract_v1",
                    workflow_version=1,
                )
            ).id
        )
        assert claimed is not None
        claimed_job_id = claimed.id

    with pytest.raises(RuntimeError, match="forced rollback after workflow success"):
        with transaction_boundary(session_factory) as session:
            runner = _build_structured_workflow_runner(session)
            job = JobRepository(session).get(claimed_job_id)
            assert job is not None
            result = asyncio.run(
                runner.run_claimed_job(
                    job,
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )
            assert result.status is JobStatus.succeeded
            # Simulates a downstream failure (e.g. ScenarioSessionService.mark_completed)
            # raising after the workflow already succeeded but before the transaction commits.
            raise RuntimeError("forced rollback after workflow success")

    with transaction_boundary(session_factory) as session:
        job = session.execute(
            sa.select(jobs_table).where(jobs_table.c.id == claimed_job_id)
        ).mappings().one()
        artifacts = list(
            session.execute(
                sa.select(artifacts_table).where(artifacts_table.c.job_id == claimed_job_id)
            ).mappings()
        )
        events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.job_id == claimed_job_id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert job["status"] is JobStatus.succeeded
    assert job["result_artifact_id"] is not None
    assert any(artifact["id"] == job["result_artifact_id"] for artifact in artifacts)
    artifact_created_events = _event_by_type(events, "artifact.created")
    # Two artifact.created events: one for the action's own structured-output
    # artifact (action_run_id set, replayed through the shared sequencer along with
    # the rest of the step's events) and one for the final workflow-result artifact
    # (action_run_id=None).
    assert len(artifact_created_events) == 2
    final_artifact_created = [
        row for row in artifact_created_events if row["action_run_id"] is None
    ]
    assert len(final_artifact_created) == 1
    assert final_artifact_created[0]["artifact_id"] == job["result_artifact_id"]
    # Only the final result artifact (action_run_id=None) is replayed independently by
    # ArtifactService's own recovery callback (phase artifact_events, unsequenced raw
    # created_at) rather than through _emit_recovered_workflow_events' shared
    # sequencer, so its timestamp has no ordering guarantee relative to the other
    # events - excluded from the ordering check below, not part of this fix.
    workflow_events = [row for row in events if row is not final_artifact_created[0]]
    _assert_strictly_increasing_event_timestamps(workflow_events)
    event_types = _event_types(workflow_events)
    assert event_types[0] == "workflow.started"
    assert event_types[-1] == "workflow.succeeded"
    assert "workflow.step_succeeded" in event_types
    workflow_succeeded = _event_by_type(events, "workflow.succeeded")[0]
    assert workflow_succeeded["job_id"] == claimed_job_id
    assert workflow_succeeded["result_status"] == JobStatus.succeeded.value
    assert workflow_succeeded["properties"]["workflow_version"] == 1


def test_workflow_runner_recovers_succeeded_state_for_newly_created_job_after_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)

    with pytest.raises(RuntimeError, match="forced rollback after workflow success"):
        with transaction_boundary(session_factory) as session:
            runner = _build_structured_workflow_runner(session)
            result = asyncio.run(
                runner.run(
                    "kernel_demo.single_action_extract_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )
            assert result.status is JobStatus.succeeded
            # The job row itself was created inside this same transaction (via
            # `run()`, not a pre-claimed job), so it was never committed either -
            # the recovery must reconstruct it from scratch, not just reapply state.
            raise RuntimeError("forced rollback after workflow success")

    with transaction_boundary(session_factory) as session:
        job = session.execute(sa.select(jobs_table)).mappings().one()
        artifacts = list(session.execute(sa.select(artifacts_table)).mappings())
        events = _event_rows(session)

    assert job["status"] is JobStatus.succeeded
    assert job["result_artifact_id"] is not None
    assert any(artifact["id"] == job["result_artifact_id"] for artifact in artifacts)
    artifact_created_events = _event_by_type(events, "artifact.created")
    # See the analogous comment in the existing-claimed-job recovery test: two
    # artifact.created events (the action's own and the final workflow result), only
    # the final one (action_run_id=None) is unsequenced relative to the rest.
    assert len(artifact_created_events) == 2
    final_artifact_created = [
        row for row in artifact_created_events if row["action_run_id"] is None
    ]
    assert len(final_artifact_created) == 1
    assert final_artifact_created[0]["artifact_id"] == job["result_artifact_id"]
    workflow_events = [row for row in events if row is not final_artifact_created[0]]
    _assert_strictly_increasing_event_timestamps(workflow_events)
    event_types = _event_types(workflow_events)
    assert event_types[0] == "workflow.started"
    assert event_types[-1] == "workflow.succeeded"
    workflow_succeeded = _event_by_type(events, "workflow.succeeded")[0]
    assert workflow_succeeded["job_id"] == job["id"]
    assert workflow_succeeded["result_status"] == JobStatus.succeeded.value


def test_workflow_runner_recovers_skipped_action_run_after_success_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    executor = RecordingExecutor(
        {
            "extract": {"values": {"deadline": "Q1", "budget": "5000"}, "missing_fields": []},
            "optional_extract": {"values": {"deadline": "ignored"}, "missing_fields": []},
        }
    )
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)

    with pytest.raises(RuntimeError, match="forced rollback after workflow success"):
        with transaction_boundary(session_factory) as session:
            runner = _build_recording_workflow_runner(session, executor=executor)
            result = asyncio.run(
                runner.run(
                    "kernel_demo.conditional_skip_extract_v1",
                    {
                        "source_text": "deadline budget deliverables",
                        "fields": _EXTRACT_FIELDS,
                        "strict": False,
                        "run_optional_step": False,
                    },
                    context,
                )
            )
            assert result.status is JobStatus.succeeded
            # Simulates a downstream failure (e.g. ScenarioSessionService.mark_completed)
            # raising after the workflow already succeeded but before the transaction commits.
            raise RuntimeError("forced rollback after workflow success")

    with transaction_boundary(session_factory) as session:
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_runs = list(
            session.execute(
                sa.select(action_runs_table).order_by(
                    action_runs_table.c.created_at, action_runs_table.c.id
                )
            ).mappings()
        )
        events = _event_rows(session)

    assert job["status"] is JobStatus.succeeded
    # Without a dedicated recovery callback for the skipped row (registered at creation,
    # symmetric with ActionRunner's own success/failure recovery), this row would be
    # lost on rollback while the recovered job metadata and replayed
    # workflow.step_skipped event still reference its action_run_id.
    assert [row["status"].value for row in action_runs] == ["succeeded", "skipped"]
    skipped = next(row for row in action_runs if row["step_id"] == "optional_extract")
    assert "falsy value" in skipped["metadata"]["skip_reason"]
    assert (
        job["metadata"]["workflow_state"]["steps"]["optional_extract"]["last_action_run_id"]
        == skipped["id"]
    )
    skipped_events = _event_by_type(events, "workflow.step_skipped")
    assert len(skipped_events) == 1
    assert skipped_events[0]["action_run_id"] == skipped["id"]
    assert "falsy value" in skipped_events[0]["properties"]["skip_reason"]


def test_workflow_runner_fails_loudly_instead_of_recovering_succeeded_job_with_lost_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)
        repository = JobRepository(session)
        claimed = WorkflowJobService(
            repository,
            EventEmitter(EventLogRepository(session)),
        ).claim_created(
            repository.create(
                JobRecord(
                    tenant_id="tenant_demo",
                    region="eu-central",
                    product_id="kernel_demo",
                    frontend_id="kernel_demo_ce",
                    scenario_session_id="scenario_session_demo",
                    workflow_id="kernel_demo.single_action_extract_v1",
                    workflow_version=1,
                )
            ).id
        )
        assert claimed is not None
        claimed_job_id = claimed.id

    import anytoolai_platform_core.artifacts.service as artifact_service_module

    def broken_artifact_row_recovery(recovery_session_factory: Any, record: Any) -> None:
        del recovery_session_factory, record
        raise RuntimeError("simulated artifact recovery failure")

    # jobs.result_artifact_id has no DB FK constraint, so nothing else stops the job
    # row from being recovered as `succeeded` even if the artifact it points to never
    # comes back. Breaking the artifact's own recovery callback reproduces that gap:
    # without the fix, the job would still end up succeeded with a dangling reference.
    monkeypatch.setattr(
        artifact_service_module,
        "_recover_artifact_row_after_rollback",
        broken_artifact_row_recovery,
    )

    with pytest.raises(RuntimeError, match="forced rollback after workflow success"):
        with transaction_boundary(session_factory) as session:
            runner = _build_structured_workflow_runner(session)
            job = JobRepository(session).get(claimed_job_id)
            assert job is not None
            result = asyncio.run(
                runner.run_claimed_job(
                    job,
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )
            assert result.status is JobStatus.succeeded
            raise RuntimeError("forced rollback after workflow success")

    with transaction_boundary(session_factory) as session:
        job = session.execute(
            sa.select(jobs_table).where(jobs_table.c.id == claimed_job_id)
        ).mappings().one()
        artifacts = list(
            session.execute(
                sa.select(artifacts_table).where(artifacts_table.c.job_id == claimed_job_id)
            ).mappings()
        )

    assert artifacts == []
    assert job["status"] is JobStatus.running
    assert job["result_artifact_id"] is None


def test_workflow_runner_rejects_claimed_job_context_with_mismatched_ownership_dimensions(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_structured_workflow_runner(session)
        repository = JobRepository(session)
        claimed = WorkflowJobService(
            repository,
            EventEmitter(EventLogRepository(session)),
        ).claim_created(
            repository.create(
                JobRecord(
                    tenant_id="tenant_demo",
                    region="eu-central",
                    product_id="kernel_demo",
                    frontend_id="kernel_demo_ce",
                    scenario_session_id="scenario_session_demo",
                    workflow_id="kernel_demo.single_action_extract_v1",
                    workflow_version=1,
                )
            ).id
        )
        assert claimed is not None

        with pytest.raises(ValueError, match="product_id"):
            asyncio.run(
                runner.run_claimed_job(
                    claimed,
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    replace(context, product_id="kernel_demo_other"),
                )
            )

        action_run_count = session.execute(
            sa.select(sa.func.count()).select_from(action_runs_table)
        ).scalar_one()

    assert action_run_count == 0


def test_workflow_runner_executes_multi_step_workflow_with_input_and_output_mappings(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    executor = RecordingExecutor(
        {
            "extract": {"values": {"deadline": "Q1", "budget": "5000"}, "missing_fields": []},
            "detect_issues": {"issues": [{"category": "timeline", "description": "Timeline risk", "severity": "high"}]},
            "generate_report": {
                "headline": "Report",
                "summary": "Structured workflow complete",
            },
        }
    )
    with transaction_boundary(session_factory) as session:
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_recording_workflow_runner(session, executor=executor)

        result = asyncio.run(
            runner.run(
                "kernel_demo.extract_detect_report_v1",
                {
                    "source_text": "deadline budget deliverables",
                    "fields": _EXTRACT_FIELDS,
                    "strict": False,
                    "taxonomy": ["timeline", "scope"],
                },
                context,
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
        "fields": _EXTRACT_FIELDS,
        "strict": False,
    }
    assert executor.inputs_by_step["detect_issues"][0] == {
        "source_text": "deadline budget deliverables",
        "taxonomy": ["timeline", "scope"],
    }
    assert executor.inputs_by_step["generate_report"][0] == {
        "source_text": "deadline budget deliverables",
        "extracted": {"values": {"deadline": "Q1", "budget": "5000"}, "missing_fields": []},
        "issues": {"issues": [{"category": "timeline", "description": "Timeline risk", "severity": "high"}]},
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
        "values": {"deadline": "Q1", "budget": "5000"},
        "missing_fields": [],
    }
    assert job["metadata"]["workflow_state"]["context"]["detected_issues"] == [
        {"category": "timeline", "description": "Timeline risk", "severity": "high"}
    ]


def test_workflow_runner_skips_step_and_records_reason(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    executor = RecordingExecutor(
        {
            "extract": {"values": {"deadline": "Q1", "budget": "5000"}, "missing_fields": []},
            "optional_extract": {"values": {"deadline": "ignored"}, "missing_fields": []},
        }
    )
    with transaction_boundary(session_factory) as session:
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_recording_workflow_runner(session, executor=executor)

        result = asyncio.run(
            runner.run(
                "kernel_demo.conditional_skip_extract_v1",
                {
                    "source_text": "deadline budget deliverables",
                    "fields": _EXTRACT_FIELDS,
                    "strict": False,
                    "run_optional_step": False,
                },
                context,
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
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_structured_workflow_runner(session, adapter=adapter)

        result = asyncio.run(
            runner.run(
                "kernel_demo.retry_extract_v1",
                {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                context,
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
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_structured_workflow_runner(session, adapter=AlwaysFailAdapter())

        with pytest.raises(
            ProviderGatewayExecutionError,
            match="Provider request failed\\.",
        ):
            asyncio.run(
                runner.run(
                    "kernel_demo.extract_detect_report_v1",
                    {
                        "source_text": "deadline budget deliverables",
                        "fields": _EXTRACT_FIELDS,
                        "strict": False,
                        "taxonomy": ["timeline", "scope"],
                    },
                    context,
                )
            )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_runs = list(session.execute(sa.select(action_runs_table)).mappings())
        events = _event_rows(session)

    assert job["status"].value == "failed"
    assert job["error_code"] == "provider_request_failed"
    assert job["error_message_safe"] == "Provider request failed."
    assert job["completed_at"] is not None
    assert job["result_artifact_id"] is None
    assert [row["step_id"] for row in action_runs] == ["extract"]
    workflow_step_failed = _event_by_type(events, "workflow.step_failed")[0]
    workflow_failed = _event_by_type(events, "workflow.failed")[0]
    assert workflow_step_failed["properties"]["step_id"] == "extract"
    assert workflow_step_failed["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_step_failed["handoff_id"] == "handoff_demo"
    assert workflow_step_failed["acquisition_source"] == "kernel_demo_ce"
    assert not _event_by_type(events, "workflow.step_succeeded")
    assert workflow_failed["guest_id"] == "guest_demo"
    assert workflow_failed["user_id"] == "user_demo"
    assert workflow_failed["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_failed["handoff_id"] == "handoff_demo"
    assert workflow_failed["acquisition_source"] == "kernel_demo_ce"


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
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_workflow_runner_with_action_runner(
            session,
            action_runner=ExplodingActionRunner(),
        )

        with pytest.raises(RuntimeError):
            asyncio.run(
                runner.run(
                    "kernel_demo.single_action_extract_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )
        job = session.execute(sa.select(jobs_table)).mappings().one()

    assert job["status"].value == "failed"
    assert job["error_code"] == "workflow_execution_failed"
    assert job["error_message_safe"] == "Workflow execution failed."
    assert "secret_token" not in job["error_message_safe"]


def test_workflow_runner_preserves_safe_validation_failure_category(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_workflow_runner_with_action_runner(
            session,
            action_runner=ValidationFailingActionRunner(),
        )

        with pytest.raises(StructuredOutputValidationError):
            asyncio.run(
                runner.run(
                    "kernel_demo.single_action_extract_v1",
                    {"source_text": "invalid output"},
                    context,
                )
            )
        job = session.execute(sa.select(jobs_table)).mappings().one()

    assert job["status"].value == "failed"
    assert job["error_code"] == "structured_output_validation_failed"
    assert job["error_message_safe"] == "Structured output validation failed."


def test_workflow_runner_persists_failed_state_when_exception_escapes_transaction_boundary(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)

    with pytest.raises(RuntimeError):
        with transaction_boundary(session_factory) as session:
            runner = _build_workflow_runner_with_action_runner(
                session,
                action_runner=ExplodingActionRunner(),
            )
            asyncio.run(
                runner.run(
                    "kernel_demo.single_action_extract_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )

    with transaction_boundary(session_factory) as session:
        job = session.execute(sa.select(jobs_table)).mappings().one()
        events = _event_rows(session)

    assert job["status"].value == "failed"
    assert job["error_code"] == "workflow_execution_failed"
    assert job["error_message_safe"] == "Workflow execution failed."
    assert job["completed_at"] is not None
    assert _event_counts(events) == Counter(
        {
            "workflow.started": 1,
            "workflow.step_started": 1,
            "workflow.step_failed": 1,
            "workflow.failed": 1,
        }
    )
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "workflow.step_failed",
            "workflow.failed",
        ],
    )
    _assert_strictly_increasing_event_timestamps(events)
    workflow_failed = _event_by_type(events, "workflow.failed")[0]
    assert workflow_failed["job_id"] == job["id"]
    assert workflow_failed["guest_id"] == "guest_demo"
    assert workflow_failed["user_id"] == "user_demo"
    assert workflow_failed["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_failed["handoff_id"] == "handoff_demo"
    assert workflow_failed["acquisition_source"] == "kernel_demo_ce"


def test_workflow_runner_recovers_consistent_failed_state_after_multi_step_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    adapter = FailOnSecondCallAdapter()
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)

    with pytest.raises(ProviderGatewayExecutionError):
        with transaction_boundary(session_factory) as session:
            runner = _build_structured_workflow_runner(session, adapter=adapter)
            asyncio.run(
                runner.run(
                    "kernel_demo.extract_detect_report_v1",
                    {
                        "source_text": "deadline budget deliverables",
                        "fields": _EXTRACT_FIELDS,
                        "strict": False,
                        "taxonomy": ["timeline", "scope"],
                    },
                    context,
                )
            )

    with transaction_boundary(session_factory) as session:
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_runs = list(
            session.execute(
                sa.select(action_runs_table).order_by(action_runs_table.c.created_at, action_runs_table.c.id)
            ).mappings()
        )
        provider_calls = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.created_at,
                    provider_calls_table.c.id,
                )
            ).mappings()
        )
        artifacts = list(session.execute(sa.select(artifacts_table)).mappings())
        events = _event_rows(session)

    assert adapter.call_count == 2
    assert job["status"].value == "failed"
    assert job["error_code"] == "provider_request_failed"
    assert job["error_message_safe"] == "Provider request failed."
    assert [row["step_id"] for row in action_runs] == ["extract", "detect_issues"]
    assert [row["status"].value for row in action_runs] == ["succeeded", "failed"]
    assert len(artifacts) == 1
    assert job["result_artifact_id"] is None
    workflow_state = job["metadata"]["workflow_state"]
    assert workflow_state["last_successful_step_id"] == "extract"
    assert workflow_state["result_artifact_id"] is None
    assert workflow_state["final_output_source"] is None
    assert workflow_state["context"]["extracted"] == {
        "values": {
            "deadline": "next Friday",
            "budget": "$5,000",
            "deliverables": ["logo", "landing page"],
        },
        "missing_fields": [],
        "confidence": {"deadline": 0.9, "budget": 0.8, "deliverables": 0.7},
    }
    assert workflow_state["steps"]["extract"]["status"] == "succeeded"
    assert workflow_state["steps"]["extract"]["last_action_run_id"] == action_runs[0]["id"]
    assert workflow_state["steps"]["extract"]["output_artifact_id"] == artifacts[0]["id"]
    assert workflow_state["steps"]["detect_issues"]["status"] == "failed"
    assert workflow_state["steps"]["detect_issues"]["last_action_run_id"] == action_runs[1]["id"]
    assert workflow_state["steps"]["detect_issues"]["error_code"] == "provider_request_failed"
    assert workflow_state["last_successful_output_artifact_id"] == artifacts[0]["id"]
    assert {row["action_run_id"] for row in provider_calls} == {
        action_runs[0]["id"],
        action_runs[1]["id"],
    }
    assert _event_counts(events) == Counter(
        {
            "workflow.started": 1,
            "workflow.step_started": 2,
            "workflow.step_succeeded": 1,
            "workflow.step_failed": 1,
            "action.started": 2,
            "action.succeeded": 1,
            "action.failed": 1,
            "provider.request_started": 2,
            "provider.request_succeeded": 1,
            "provider.request_failed": 1,
            "artifact.created": 1,
            "workflow.failed": 1,
        }
    )
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "action.started",
            "provider.request_started",
            "provider.request_succeeded",
            "artifact.created",
            "action.succeeded",
            "workflow.step_succeeded",
            "workflow.step_started",
            "action.started",
            "provider.request_started",
            "provider.request_failed",
            "action.failed",
            "workflow.step_failed",
            "workflow.failed",
        ],
    )
    _assert_strictly_increasing_event_timestamps(events)
    workflow_started = _event_by_type(events, "workflow.started")[0]
    workflow_step_succeeded = _event_by_type(events, "workflow.step_succeeded")[0]
    workflow_step_failed = _event_by_type(events, "workflow.step_failed")[0]
    workflow_failed = _event_by_type(events, "workflow.failed")[0]
    assert workflow_started["job_id"] == job["id"]
    assert workflow_started["guest_id"] == "guest_demo"
    assert workflow_started["user_id"] == "user_demo"
    assert workflow_started["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_started["handoff_id"] == "handoff_demo"
    assert workflow_started["acquisition_source"] == "kernel_demo_ce"
    assert workflow_step_succeeded["action_run_id"] == action_runs[0]["id"]
    assert workflow_step_succeeded["artifact_id"] == artifacts[0]["id"]
    assert workflow_step_succeeded["properties"]["step_id"] == "extract"
    assert workflow_step_failed["action_run_id"] == action_runs[1]["id"]
    assert workflow_step_failed["properties"]["step_id"] == "detect_issues"
    assert workflow_step_failed["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_step_failed["handoff_id"] == "handoff_demo"
    assert workflow_step_failed["acquisition_source"] == "kernel_demo_ce"
    assert workflow_failed["job_id"] == job["id"]
    assert workflow_failed["guest_id"] == "guest_demo"
    assert workflow_failed["user_id"] == "user_demo"
    assert workflow_failed["scenario_chain_id"] == "scenario_chain_demo"
    assert workflow_failed["handoff_id"] == "handoff_demo"
    assert workflow_failed["acquisition_source"] == "kernel_demo_ce"


def test_workflow_runner_recovery_does_not_synthesize_step_started_for_pre_start_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)

    with pytest.raises(WorkflowConditionEvaluationError):
        with transaction_boundary(session_factory) as session:
            runner = _build_recording_workflow_runner(
                session,
                executor=RecordingExecutor(
                    {
                        "extract": {"values": {"deadline": "Q1", "budget": "5000"}, "missing_fields": []},
                        "optional_extract": {"values": {"deadline": "ignored"}, "missing_fields": []},
                    }
                ),
            )
            asyncio.run(
                runner.run(
                    "kernel_demo.conditional_skip_extract_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )

    with transaction_boundary(session_factory) as session:
        job = session.execute(sa.select(jobs_table)).mappings().one()
        events = _event_rows(session)

    step_started_events = _event_by_type(events, "workflow.step_started")
    step_failed_events = _event_by_type(events, "workflow.step_failed")
    workflow_failed_events = _event_by_type(events, "workflow.failed")
    assert job["error_code"] == "workflow_condition_evaluation_failed"
    assert len(step_started_events) == 1
    assert step_started_events[0]["properties"]["step_id"] == "extract"
    assert len(step_failed_events) == 1
    assert step_failed_events[0]["properties"]["step_id"] == "optional_extract"
    assert len(workflow_failed_events) == 1
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "action.started",
            "action.succeeded",
            "workflow.step_succeeded",
            "workflow.step_failed",
            "workflow.failed",
        ],
    )
    _assert_strictly_increasing_event_timestamps(events)
    assert step_failed_events[0]["timestamp"] < workflow_failed_events[0]["timestamp"]
    assert workflow_failed_events[0]["timestamp"] == job["completed_at"]
    assert job["metadata"]["workflow_state"]["steps"]["optional_extract"]["started_event_emitted"] is False


def test_workflow_runner_caught_condition_failure_does_not_emit_step_started(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_recording_workflow_runner(
            session,
            executor=RecordingExecutor(
                {
                    "extract": {"values": {"deadline": "Q1", "budget": "5000"}, "missing_fields": []},
                    "optional_extract": {"values": {"deadline": "ignored"}, "missing_fields": []},
                }
            ),
        )

        with pytest.raises(WorkflowConditionEvaluationError):
            asyncio.run(
                runner.run(
                    "kernel_demo.conditional_skip_extract_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        events = _event_rows(session)

    step_started_events = _event_by_type(events, "workflow.step_started")
    step_failed_events = _event_by_type(events, "workflow.step_failed")
    assert job["error_code"] == "workflow_condition_evaluation_failed"
    assert [event["properties"]["step_id"] for event in step_started_events] == ["extract"]
    assert len(step_failed_events) == 1
    assert step_failed_events[0]["properties"]["step_id"] == "optional_extract"
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "action.started",
            "action.succeeded",
            "workflow.step_succeeded",
            "workflow.step_failed",
            "workflow.failed",
        ],
    )
    assert job["metadata"]["workflow_state"]["steps"]["optional_extract"]["started_event_emitted"] is False


def test_workflow_runner_recovery_replays_step_started_for_input_mapping_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)

    with pytest.raises(WorkflowMappingResolutionError):
        with transaction_boundary(session_factory) as session:
            runner = _build_recording_workflow_runner(
                session,
                executor=RecordingExecutor(
                    {
                        "extract": {"values": {"deadline": "Q1", "budget": "5000"}, "missing_fields": []},
                        "detect_issues": {"issues": [{"category": "timeline", "description": "ignored", "severity": "high"}]},
                        "generate_report": {
                            "headline": "Report",
                            "summary": "ignored",
                        },
                    }
                ),
            )
            asyncio.run(
                runner.run(
                    "kernel_demo.extract_detect_report_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )

    with transaction_boundary(session_factory) as session:
        job = session.execute(sa.select(jobs_table)).mappings().one()
        action_runs = list(
            session.execute(
                sa.select(action_runs_table).order_by(
                    action_runs_table.c.created_at,
                    action_runs_table.c.id,
                )
            ).mappings()
        )
        events = _event_rows(session)

    workflow_state = job["metadata"]["workflow_state"]
    step_started_events = _event_by_type(events, "workflow.step_started")
    step_failed_events = _event_by_type(events, "workflow.step_failed")
    assert job["error_code"] == "workflow_mapping_resolution_failed"
    assert [row["step_id"] for row in action_runs] == ["extract"]
    assert {event["properties"]["step_id"] for event in step_started_events} == {
        "extract",
        "detect_issues",
    }
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "action.started",
            "action.succeeded",
            "workflow.step_succeeded",
            "workflow.step_started",
            "workflow.step_failed",
            "workflow.failed",
        ],
    )
    _assert_strictly_increasing_event_timestamps(events)
    assert len(step_failed_events) == 1
    assert step_failed_events[0]["properties"]["step_id"] == "detect_issues"
    assert step_failed_events[0]["action_run_id"] is None
    assert workflow_state["steps"]["detect_issues"]["started_event_emitted"] is True
    assert workflow_state["steps"]["detect_issues"]["last_action_run_id"] is None


def test_workflow_recovery_repairs_regressed_existing_replay_event_timestamp(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    started_at = utc_now()
    action_completed_at = started_at
    completed_at = started_at
    preexisting_failed_at = started_at - timedelta(microseconds=10)

    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)
        job = JobRepository(session).create(
            JobRecord(
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=context.scenario_session_id or "scenario_session_demo",
                workflow_id="kernel_demo.partial_replay_order_v1",
                workflow_version=1,
                status=JobStatus.failed,
                error_code="workflow_condition_evaluation_failed",
                error_message_safe="Workflow condition evaluation failed.",
                started_at=started_at,
                completed_at=completed_at,
                metadata={
                    "guest_id": context.guest_id,
                    "user_id": context.user_id,
                    "scenario_chain_id": context.scenario_chain_id,
                    "handoff_id": context.handoff_id,
                    "acquisition_source": context.acquisition_source,
                    "workflow_state": {
                        "steps": {
                            "extract": {
                                "status": ActionRunStatus.succeeded.value,
                                "retry_count": 0,
                                "attempt_count": 1,
                                "action_type": "text.extract_structured_fields",
                                "action_config_id": (
                                    "kernel_demo.extract_structured_fields_v1"
                                ),
                                "last_action_run_id": "action_run_partial_extract",
                                "output_artifact_id": None,
                                "skip_reason": None,
                                "started_event_emitted": True,
                            },
                            "detect_issues": {
                                "status": ActionRunStatus.failed.value,
                                "retry_count": 0,
                                "attempt_count": 0,
                                "action_type": "text.detect_issues",
                                "action_config_id": "kernel_demo.detect_issues_v1",
                                "last_action_run_id": None,
                                "output_artifact_id": None,
                                "skip_reason": None,
                                "error_code": "workflow_condition_evaluation_failed",
                                "started_event_emitted": False,
                            },
                        },
                        "context": {},
                        "last_successful_step_id": "extract",
                        "last_successful_output_artifact_id": None,
                        "final_output_source": None,
                        "result_artifact_id": None,
                    },
                },
            )
        )
        ActionRunRepository(session).create(
            ActionRunRecord(
                id="action_run_partial_extract",
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=context.scenario_session_id or "scenario_session_demo",
                job_id=job.id,
                workflow_id=job.workflow_id,
                step_id="extract",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                status=ActionRunStatus.succeeded,
                created_at=started_at,
                started_at=started_at,
                completed_at=action_completed_at,
                metadata={"workflow_version": 1},
            )
        )
        preexisting = EventEmitter(EventLogRepository(session)).emit(
            "workflow.step_failed",
            replace(
                context,
                job_id=job.id,
                workflow_id=job.workflow_id,
                workflow_version=job.workflow_version,
                step_id="detect_issues",
                action_type="text.detect_issues",
                action_config_id="kernel_demo.detect_issues_v1",
            ),
            result_status=ActionRunStatus.failed.value,
            properties={
                "step_id": "detect_issues",
                "retry_count": 0,
                "attempt_count": 0,
                "error_code": "workflow_condition_evaluation_failed",
            },
            timestamp=preexisting_failed_at,
            replay=True,
        )

        _emit_recovered_workflow_events(
            session,
            job_id=job.id,
            terminal_event_type="workflow.failed",
            terminal_error_code="workflow_condition_evaluation_failed",
        )

        events = _event_rows(session)
        repaired_failed_event = EventLogRepository(session).get(preexisting.event_id)
        recovered_job = JobRepository(session).get(job.id)

    assert preexisting.event_id.startswith("event_replay_")
    assert repaired_failed_event is not None
    assert recovered_job is not None
    _assert_event_types(
        events,
        [
            "workflow.started",
            "workflow.step_started",
            "action.started",
            "action.succeeded",
            "workflow.step_succeeded",
            "workflow.step_failed",
            "workflow.failed",
        ],
    )
    _assert_strictly_increasing_event_timestamps(events)
    assert repaired_failed_event.timestamp > preexisting_failed_at
    assert repaired_failed_event.timestamp == _event_by_type(events, "workflow.step_failed")[0][
        "timestamp"
    ]
    assert _event_by_type(events, "workflow.step_failed")[0]["properties"]["step_id"] == (
        "detect_issues"
    )
    assert _event_by_type(events, "workflow.step_started")[0]["properties"]["step_id"] == (
        "extract"
    )
    assert recovered_job.completed_at == _event_by_type(events, "workflow.failed")[0]["timestamp"]


def test_workflow_recovery_replays_all_step_action_attempts_in_order(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    context = _base_context()
    first_started_at = utc_now()
    first_completed_at = first_started_at + timedelta(seconds=5)
    second_started_at = first_completed_at + timedelta(seconds=5)
    second_completed_at = second_started_at + timedelta(seconds=5)

    with transaction_boundary(session_factory) as session:
        _seed_context_scenario(session, context)
        job = JobRepository(session).create(
            JobRecord(
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=context.scenario_session_id or "scenario_session_demo",
                workflow_id="kernel_demo.retry_extract_v1",
                workflow_version=1,
                status=JobStatus.succeeded,
                started_at=first_started_at,
                completed_at=second_completed_at,
                metadata={
                    "guest_id": context.guest_id,
                    "user_id": context.user_id,
                    "scenario_chain_id": context.scenario_chain_id,
                    "handoff_id": context.handoff_id,
                    "acquisition_source": context.acquisition_source,
                    "workflow_state": {
                        "steps": {
                            "extract": {
                                "status": ActionRunStatus.succeeded.value,
                                "retry_count": 1,
                                "attempt_count": 2,
                                "action_type": "text.extract_structured_fields",
                                "action_config_id": "kernel_demo.extract_structured_fields_v1",
                                "last_action_run_id": "action_run_retry_2",
                                "output_artifact_id": None,
                                "skip_reason": None,
                                "started_event_emitted": True,
                            }
                        },
                        "context": {},
                        "last_successful_step_id": "extract",
                        "last_successful_output_artifact_id": None,
                        "final_output_source": None,
                        "result_artifact_id": None,
                    },
                },
            )
        )
        repository = ActionRunRepository(session)
        repository.create(
            ActionRunRecord(
                id="action_run_retry_1",
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=context.scenario_session_id or "scenario_session_demo",
                job_id=job.id,
                workflow_id=job.workflow_id,
                step_id="extract",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                status=ActionRunStatus.failed,
                error_code="provider_request_failed",
                created_at=first_started_at,
                started_at=first_started_at,
                completed_at=first_completed_at,
                metadata={"workflow_version": 1},
            )
        )
        repository.create(
            ActionRunRecord(
                id="action_run_retry_2",
                tenant_id=context.tenant_id,
                region=context.region,
                product_id=context.product_id,
                frontend_id=context.frontend_id,
                scenario_session_id=context.scenario_session_id or "scenario_session_demo",
                job_id=job.id,
                workflow_id=job.workflow_id,
                step_id="extract",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                status=ActionRunStatus.succeeded,
                created_at=second_started_at,
                started_at=second_started_at,
                completed_at=second_completed_at,
                metadata={"workflow_version": 1},
            )
        )
        _emit_recovered_workflow_events(
            session,
            job_id=job.id,
            terminal_event_type="workflow.succeeded",
            terminal_error_code=None,
        )

    with transaction_boundary(session_factory) as session:
        _emit_recovered_workflow_events(
            session,
            job_id=job.id,
            terminal_event_type="workflow.succeeded",
            terminal_error_code=None,
        )
        events = _event_rows(session)

    assert [row["event_type"] for row in events] == [
        "workflow.started",
        "workflow.step_started",
        "action.started",
        "action.failed",
        "action.started",
        "action.succeeded",
        "workflow.step_succeeded",
        "workflow.succeeded",
    ]
    assert _event_counts(events) == Counter(
        {
            "workflow.started": 1,
            "workflow.step_started": 1,
            "action.started": 2,
            "action.failed": 1,
            "action.succeeded": 1,
            "workflow.step_succeeded": 1,
            "workflow.succeeded": 1,
        }
    )
    workflow_step_started = _event_by_type(events, "workflow.step_started")[0]
    workflow_step_succeeded = _event_by_type(events, "workflow.step_succeeded")[0]
    workflow_succeeded = _event_by_type(events, "workflow.succeeded")[0]
    assert workflow_step_started["timestamp"] == first_started_at + timedelta(microseconds=1)
    assert workflow_step_succeeded["timestamp"] > second_completed_at
    assert workflow_succeeded["timestamp"] > workflow_step_succeeded["timestamp"]
    _assert_strictly_increasing_event_timestamps(events)


def test_workflow_runner_uses_generic_safe_provider_message_for_unknown_adapter_exceptions(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        context = _base_context()
        _seed_context_scenario(session, context)
        runner = _build_structured_workflow_runner(
            session,
            adapter=UnsafeRawTextProviderAdapter(),
        )

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                runner.run(
                    "kernel_demo.single_action_extract_v1",
                    {"source_text": "deadline budget deliverables", "fields": _EXTRACT_FIELDS, "strict": False},
                    context,
                )
            )
        job = session.execute(sa.select(jobs_table)).mappings().one()
        provider_call = session.execute(sa.select(provider_calls_table)).mappings().one()

    assert exc_info.value.error_code == "provider_request_failed"
    assert exc_info.value.message == "Provider request failed."
    assert job["error_message_safe"] == "Provider request failed."
    assert provider_call["error_message_safe"] == "Provider request failed."
    assert "deadline budget deliverables" not in job["error_message_safe"]
