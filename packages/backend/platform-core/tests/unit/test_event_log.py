from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from anytoolai_platform_core.actions.models import ActionRunRecord, ActionRunStatus
from anytoolai_platform_core.actions.runner import ActionRunService
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter, EventValidationError
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.events.taxonomy import PLATFORM_EVENT_GROUPS, PLATFORM_EVENTS
from anytoolai_platform_core.providers.gateway import ProviderGateway, ProviderGatewayExecutionError
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioSessionService
from anytoolai_platform_core.storage.db import event_log_table, provider_calls_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from anytoolai_platform_core.workflows.runner import WorkflowJobService
from sqlalchemy import event


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


CONFIG_ROOT = _repo_root() / "configs" / "kernel"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


def _build_runtime_engine(main_db: Path, platform_db: Path) -> sa.Engine:
    engine = sa.create_engine(_sqlite_url(main_db), future=True)

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        dbapi_connection.execute(
            f"ATTACH DATABASE '{platform_db.resolve().as_posix()}' AS platform"
        )

    return engine


def _build_alembic_config(database_url: str) -> Config:
    alembic_config = Config()
    alembic_config.set_main_option(
        "script_location",
        str(_repo_root() / "migrations" / "platform"),
    )
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "event-log-main.sqlite3"
    platform_db = tmp_path / "event-log-platform.sqlite3"
    engine = _build_runtime_engine(main_db, platform_db)
    alembic_config = _build_alembic_config(_sqlite_url(main_db))

    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(runtime_engine: sa.Engine) -> sa.orm.sessionmaker[sa.orm.Session]:
    return build_session_factory(runtime_engine)


@pytest.fixture
def config_registry() -> Any:
    return build_config_registry(CONFIG_ROOT)


def make_execution_context(**overrides: Any) -> ExecutionContext:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "workflow_id": "wf_smoke",
        "workflow_version": 1,
        "step_id": "step_1",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "cfg_extract",
        "artifact_id": "artifact_demo",
    }
    values.update(overrides)
    return ExecutionContext(**values)


def make_scenario_session(**overrides: Any) -> ScenarioSessionRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_id": "smoke_start",
        "scenario_version": 1,
    }
    values.update(overrides)
    return ScenarioSessionRecord(**values)


def make_job(scenario_session_id: str, **overrides: Any) -> JobRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "workflow_id": "wf_smoke",
        "workflow_version": 1,
    }
    values.update(overrides)
    return JobRecord(**values)


def make_action_run(scenario_session_id: str, job_id: str, **overrides: Any) -> ActionRunRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "job_id": job_id,
        "workflow_id": "wf_smoke",
        "step_id": "step_1",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "cfg_extract",
    }
    values.update(overrides)
    return ActionRunRecord(**values)


def make_artifact(scenario_session_id: str, **overrides: Any) -> ArtifactRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": scenario_session_id,
        "artifact_type": "structured_output",
    }
    values.update(overrides)
    return ArtifactRecord(**values)


class SuccessfulAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            output_text="ok",
            provider=request.provider,
            model=request.model,
            usage=ProviderUsage(input_tokens=128, output_tokens=64),
            latency_ms=950,
            estimated_cost=0.42,
        )


class TimeoutAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        del request
        raise TimeoutError("provider timed out")


class PlatformFailureAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        del request
        raise PlatformError("provider_unavailable", "safe provider failure")


class FailedResponseAdapter:
    def __init__(
        self,
        *,
        status: ProviderCallStatus,
        error_code: str | None = None,
    ) -> None:
        self._status = status
        self._error_code = error_code

    async def complete(self, request: Any) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            output_text="not-ok",
            provider=request.provider,
            model=request.model,
            status=self._status,
            error_code=self._error_code,
            error_message_safe="safe provider response failure",
        )


def build_provider_request(action: ActionRunRecord, job: JobRecord, **overrides: Any) -> ProviderRequest:
    values = {
        "provider_policy_ref": "default_fake_provider_v1",
        "tenant_id": action.tenant_id,
        "region": action.region,
        "product_id": action.product_id,
        "frontend_id": action.frontend_id,
        "scenario_session_id": action.scenario_session_id,
        "job_id": job.id,
        "workflow_id": action.workflow_id,
        "workflow_version": job.workflow_version,
        "step_id": action.step_id,
        "action_run_id": action.id,
        "action_type": action.action_type,
        "action_config_id": action.action_config_id,
        "prompt": "hello",
        "prompt_ref": "kernel_demo.extract_structured_fields.v1",
        "semantic_attempt_index": 1,
        "pydantic_run_id": "pydantic-run-demo",
    }
    values.update(overrides)
    return ProviderRequest(**values)


def _build_emitter(session: sa.orm.Session) -> EventEmitter:
    return EventEmitter(EventLogRepository(session))


def _event_types(session: sa.orm.Session) -> list[str]:
    return list(
        session.execute(
            sa.select(event_log_table.c.event_type).order_by(
                event_log_table.c.timestamp,
                event_log_table.c.event_id,
            )
        ).scalars()
    )


def test_event_log_migration_creates_table_at_0002(tmp_path: Path) -> None:
    main_db = tmp_path / "migration-main.sqlite3"
    platform_db = tmp_path / "migration-platform.sqlite3"
    engine = _build_runtime_engine(main_db, platform_db)
    alembic_config = _build_alembic_config(_sqlite_url(main_db))
    try:
        with engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "0002")
            table_names = set(
                connection.execute(
                    sa.text("SELECT name FROM platform.sqlite_master WHERE type = 'table'")
                ).scalars()
            )
            index_names = set(
                connection.execute(
                    sa.text("SELECT name FROM platform.sqlite_master WHERE type = 'index'")
                ).scalars()
            )
            event_log_columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "event_log",
                    schema="platform",
                )
            }

        assert "event_log" in table_names
        assert "provider_policy_ref" in event_log_columns
        assert "provider_policy_id" not in event_log_columns
        assert {
            "ix_event_log_timestamp",
            "ix_event_log_event_type",
            "ix_event_log_product_id",
            "ix_event_log_scenario_session_id",
            "ix_event_log_job_id",
            "ix_event_log_action_run_id",
            "ix_event_log_provider_call_id",
            "ix_event_log_handoff_id",
        }.issubset(index_names)
    finally:
        engine.dispose()


def test_platform_migration_chain_is_single_head() -> None:
    script = ScriptDirectory.from_config(_build_alembic_config("sqlite+pysqlite://"))
    assert script.get_heads() == ["0006"]


def test_event_log_upgrade_from_0005_renames_provider_policy_column(tmp_path: Path) -> None:
    main_db = tmp_path / "migration-upgrade-main.sqlite3"
    platform_db = tmp_path / "migration-upgrade-platform.sqlite3"
    engine = _build_runtime_engine(main_db, platform_db)
    alembic_config = _build_alembic_config(_sqlite_url(main_db))
    try:
        with engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "0005")
            connection.execute(
                sa.text(
                    "ALTER TABLE platform.event_log "
                    "RENAME COLUMN provider_policy_ref TO provider_policy_id"
                )
            )

        with engine.begin() as connection:
            alembic_config.attributes["connection"] = connection
            command.upgrade(alembic_config, "head")
            event_log_columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns(
                    "event_log",
                    schema="platform",
                )
            }

        assert "provider_policy_ref" in event_log_columns
        assert "provider_policy_id" not in event_log_columns
    finally:
        engine.dispose()


def test_event_emitter_persists_round_trip_and_maps_dimensions(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        created = emitter.emit(
            "scenario.started",
            make_execution_context(
                guest_id="guest_demo",
                user_id="user_demo",
                scenario_chain_id="chain_demo",
                action_run_id="action_run_demo",
                provider_policy_ref="policy_demo",
                provider_call_id="provider_call_demo",
                provider="openai",
                model="gpt-5-mini",
                physical_call_index=2,
                pydantic_run_id="pydantic-run-demo",
                litellm_response_id="litellm-response-demo",
                acquisition_source="kernel_demo_ce",
            ),
            properties={"scenario_id": "smoke_start"},
        )

        stored = EventLogRepository(session).get(created.event_id)

    assert stored == created
    assert stored is not None
    assert stored.tenant_id == "tenant_demo"
    assert stored.region == "eu-central"
    assert stored.product_id == "kernel_demo"
    assert stored.frontend_id == "kernel_demo_ce"
    assert stored.guest_id == "guest_demo"
    assert stored.user_id == "user_demo"
    assert stored.scenario_chain_id == "chain_demo"
    assert stored.action_run_id == "action_run_demo"
    assert stored.provider_policy_ref == "policy_demo"
    assert stored.provider_call_id == "provider_call_demo"
    assert stored.provider == "openai"
    assert stored.model == "gpt-5-mini"
    assert stored.physical_call_index == 2
    assert stored.pydantic_run_id == "pydantic-run-demo"
    assert stored.litellm_response_id == "litellm-response-demo"
    assert stored.properties["scenario_id"] == "smoke_start"


def test_event_emitter_rejects_missing_tenant_id(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        with pytest.raises(EventValidationError, match="tenant_id"):
            emitter.emit(
                "scenario.started",
                make_execution_context(tenant_id=""),
            )


def test_event_emitter_rejects_missing_region(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        with pytest.raises(EventValidationError, match="region"):
            emitter.emit(
                "scenario.started",
                make_execution_context(region=""),
            )


def test_event_emitter_sanitizes_properties_and_keeps_persistence_safe(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    class Unsupported:
        pass

    oversized = "x" * 1100
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        created = emitter.emit(
            "provider.request_failed",
            make_execution_context(provider="openai", model="gpt-5-mini"),
            result_status="failed",
            properties={
                "password": "super-secret",
                "token_value": "should-hide",
                "error_code": "provider_unavailable",
                "when": datetime(2026, 6, 19, tzinfo=UTC),
                "tags": {"beta", "alpha"},
                "payload": Unsupported(),
                "large_text": oversized,
                "non_finite": float("inf"),
            },
        )

        stored = EventLogRepository(session).get(created.event_id)

    assert stored is not None
    assert stored.error_code == "provider_unavailable"
    assert stored.properties["password"] == "[REDACTED]"
    assert stored.properties["token_value"] == "[REDACTED]"
    assert stored.properties["when"] == "2026-06-19 00:00:00+00:00"
    assert sorted(stored.properties["tags"]) == ["alpha", "beta"]
    assert stored.properties["payload"] == "[UNSUPPORTED]"
    assert stored.properties["non_finite"] == "[UNSUPPORTED]"
    assert stored.properties["large_text"].endswith("[TRUNCATED]")
    assert len(stored.properties["large_text"]) <= 1024


def test_platform_taxonomy_covers_required_groups_and_events() -> None:
    required_groups = {
        "guest",
        "quota",
        "scenario",
        "workflow",
        "action",
        "provider",
        "artifact",
        "handoff",
        "client",
    }
    assert required_groups <= set(PLATFORM_EVENT_GROUPS)
    assert "guest.created" in PLATFORM_EVENTS
    assert "quota.checked" in PLATFORM_EVENTS
    assert "scenario.started" in PLATFORM_EVENTS
    assert "workflow.started" in PLATFORM_EVENTS
    assert "action.started" in PLATFORM_EVENTS
    assert "provider.request_started" in PLATFORM_EVENTS
    assert "artifact.created" in PLATFORM_EVENTS
    assert "handoff.created" in PLATFORM_EVENTS
    assert "client.result_copied" in PLATFORM_EVENTS


def test_runtime_services_emit_required_success_events(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        scenario_service = ScenarioSessionService(
            ScenarioSessionRepository(session),
            emitter,
        )
        workflow_service = WorkflowJobService(JobRepository(session), emitter)
        action_service = ActionRunService(ActionRunRepository(session), emitter)
        artifact_service = ArtifactService(ArtifactRepository(session), emitter)
        gateway = ProviderGateway(
            {"fake": SuccessfulAdapter()},
            policy_resolver=ProviderPolicyResolver(config_registry),
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=emitter,
        )

        scenario = scenario_service.start(make_scenario_session())
        job = workflow_service.start(make_job(scenario.id))
        action = action_service.start(make_action_run(scenario.id, job.id))
        artifact_service.create(
            make_artifact(
                scenario.id,
                job_id=job.id,
                action_run_id=action.id,
            )
        )
        asyncio.run(gateway.request(build_provider_request(action, job), session=session))
        action_service.mark_succeeded(
            replace(
                action,
                status=ActionRunStatus.succeeded,
                completed_at=utc_now(),
            )
        )
        workflow_service.mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                completed_at=utc_now(),
            )
        )
        scenario_service.mark_completed(
            replace(
                scenario,
                status=ScenarioSessionStatus.completed,
                completed_at=utc_now(),
            )
        )

        event_types = _event_types(session)

    assert {
        "scenario.started",
        "workflow.started",
        "action.started",
        "artifact.created",
        "provider.request_started",
        "provider.request_succeeded",
        "action.succeeded",
        "workflow.succeeded",
        "scenario.completed",
    } <= set(event_types)


def test_provider_events_include_adr_0007_correlation_properties(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        gateway = ProviderGateway(
            {"fake": SuccessfulAdapter()},
            policy_resolver=ProviderPolicyResolver(config_registry),
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=emitter,
        )

        action = make_action_run("scenario_session_demo", "job_demo")
        job = make_job(action.scenario_session_id, id=action.job_id)

        asyncio.run(gateway.request(build_provider_request(action, job), session=session))

        provider_call = session.execute(
            sa.select(provider_calls_table)
            .order_by(provider_calls_table.c.created_at.desc(), provider_calls_table.c.id.desc())
        ).mappings().one()
        provider_events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.event_type.like("provider.request_%"))
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    started_event, succeeded_event = provider_events
    assert started_event["event_type"] == "provider.request_started"
    assert succeeded_event["event_type"] == "provider.request_succeeded"
    assert started_event["action_run_id"] == provider_call["action_run_id"]
    assert succeeded_event["action_run_id"] == provider_call["action_run_id"]
    assert started_event["provider_policy_ref"] == "default_fake_provider_v1"
    assert succeeded_event["provider_policy_ref"] == "default_fake_provider_v1"
    assert started_event["provider_call_id"] == provider_call["id"]
    assert succeeded_event["provider_call_id"] == provider_call["id"]
    assert started_event["physical_call_index"] == 1
    assert succeeded_event["physical_call_index"] == 1
    assert started_event["properties"]["provider_call_id"] == provider_call["id"]
    assert succeeded_event["properties"]["provider_call_id"] == provider_call["id"]
    assert started_event["properties"]["provider_policy_ref"] == "default_fake_provider_v1"
    assert succeeded_event["properties"]["provider_policy_ref"] == "default_fake_provider_v1"
    assert started_event["properties"]["physical_call_index"] == 1
    assert succeeded_event["properties"]["physical_call_index"] == 1
    assert succeeded_event["pydantic_run_id"]
    assert succeeded_event["litellm_response_id"] is None
    assert succeeded_event["properties"]["semantic_attempt_index"] == 1
    assert succeeded_event["properties"]["transport_attempt_index"] == 1
    assert succeeded_event["properties"]["pydantic_run_id"]
    assert succeeded_event["properties"]["total_tokens"] == "[REDACTED]"
    assert provider_call["total_tokens"] == 192


def test_runtime_services_emit_required_failure_events(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        scenario_service = ScenarioSessionService(
            ScenarioSessionRepository(session),
            emitter,
        )
        workflow_service = WorkflowJobService(JobRepository(session), emitter)
        action_service = ActionRunService(ActionRunRepository(session), emitter)
        gateway = ProviderGateway(
            {"fake": TimeoutAdapter()},
            policy_resolver=ProviderPolicyResolver(config_registry),
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=emitter,
        )

        scenario = scenario_service.start(make_scenario_session())
        job = workflow_service.start(make_job(scenario.id))
        action = action_service.start(make_action_run(scenario.id, job.id))

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(gateway.request(build_provider_request(action, job), session=session))

        action_service.mark_failed(action, error_code="timeout")
        workflow_service.mark_failed(job, error_code="timeout")
        scenario_service.mark_failed(scenario, error_code="timeout")

        event_types = _event_types(session)
        provider_call_statuses = list(
            session.execute(sa.select(provider_calls_table.c.status)).scalars()
        )

    assert exc_info.value.error_code == "provider_request_timed_out"
    assert {
        "provider.request_failed",
        "action.failed",
        "workflow.failed",
        "scenario.failed",
    } <= set(event_types)
    assert ProviderCallStatus.timed_out in provider_call_statuses


def test_provider_gateway_failure_uses_safe_platform_error_code(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        gateway = ProviderGateway(
            {"fake": PlatformFailureAdapter()},
            policy_resolver=ProviderPolicyResolver(config_registry),
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=emitter,
        )

        action = make_action_run("scenario_session_demo", "job_demo")
        job = make_job(action.scenario_session_id, id=action.job_id)

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(gateway.request(build_provider_request(action, job), session=session))

        failed_event = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "provider.request_failed"
            )
        ).mappings().one()

    assert exc_info.value.error_code == "provider_unavailable"
    assert failed_event["error_code"] == "provider_unavailable"


@pytest.mark.parametrize(
    ("status", "expected_error_code"),
    [
        (ProviderCallStatus.failed, "provider_request_failed"),
        (ProviderCallStatus.timed_out, "provider_request_timed_out"),
    ],
)
def test_provider_gateway_failed_provider_response_emits_failed_event_and_persists_status(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
    status: ProviderCallStatus,
    expected_error_code: str,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        gateway = ProviderGateway(
            {"fake": FailedResponseAdapter(status=status)},
            policy_resolver=ProviderPolicyResolver(config_registry),
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=emitter,
        )

        action = make_action_run("scenario_session_demo", "job_demo")
        job = make_job(action.scenario_session_id, id=action.job_id)

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(gateway.request(build_provider_request(action, job), session=session))

        event_types = _event_types(session)
        failed_event = session.execute(
            sa.select(event_log_table)
            .where(event_log_table.c.event_type == "provider.request_failed")
            .order_by(event_log_table.c.timestamp.desc(), event_log_table.c.event_id.desc())
        ).mappings().first()
        provider_call = session.execute(
            sa.select(provider_calls_table).order_by(
                provider_calls_table.c.created_at.desc(),
                provider_calls_table.c.id.desc(),
            )
        ).mappings().first()

    assert exc_info.value.error_code == expected_error_code
    assert "provider.request_succeeded" not in event_types
    assert "provider.request_failed" in event_types
    assert failed_event is not None
    assert failed_event["result_status"] == status.value
    assert failed_event["error_code"] == expected_error_code
    assert provider_call is not None
    assert provider_call["status"] == status


@pytest.mark.parametrize(("field_name", "value"), [("tenant_id", ""), ("region", "")])
def test_provider_gateway_does_not_persist_provider_call_when_event_dimensions_are_invalid(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
    field_name: str,
    value: str,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = _build_emitter(session)
        gateway = ProviderGateway(
            {"fake": SuccessfulAdapter()},
            policy_resolver=ProviderPolicyResolver(config_registry),
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=emitter,
        )
        action = make_action_run("scenario_session_demo", "job_demo", **{field_name: value})
        job = make_job(action.scenario_session_id, id=action.job_id, **{field_name: value})

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(
                    build_provider_request(action, job, **{field_name: value}),
                    session=session,
                )
            )

        provider_call_count = session.execute(
            sa.select(sa.func.count()).select_from(provider_calls_table)
        ).scalar_one()

    assert exc_info.value.error_code == "provider_request_failed"
    assert field_name in exc_info.value.message
    assert provider_call_count == 0
