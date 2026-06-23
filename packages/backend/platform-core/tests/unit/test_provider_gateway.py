from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.actions.models import ActionRunRecord
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.events.emitter import EventEmitter, EventValidationError
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.models import (
    ProviderCallRecord,
    ProviderCallStatus,
    ProviderPolicy,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
    ResolvedProviderRequest,
    StructuredOutputMode,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import event_log_table, provider_calls_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "provider" / "fake_provider_outputs"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "runtime-main.sqlite3"
    platform_db = tmp_path / "runtime-platform.sqlite3"

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
def config_registry() -> Any:
    return build_config_registry(CONFIG_ROOT)


def make_scenario_session(**overrides: Any) -> ScenarioSessionRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_id": "kernel_demo.single_action_smoke_v1",
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
        "workflow_id": "kernel_demo.single_action_extract_v1",
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
        "workflow_id": "kernel_demo.single_action_extract_v1",
        "step_id": "extract",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
    }
    values.update(overrides)
    return ActionRunRecord(**values)


def seed_runtime_chain(
    session: sa.orm.Session,
) -> tuple[ScenarioSessionRecord, JobRecord, ActionRunRecord]:
    scenario_session = ScenarioSessionRepository(session).create(make_scenario_session())
    job = JobRepository(session).create(make_job(scenario_session.id))
    action_run = ActionRunRepository(session).create(make_action_run(scenario_session.id, job.id))
    return scenario_session, job, action_run


def build_request(
    scenario_session: ScenarioSessionRecord,
    job: JobRecord,
    action_run: ActionRunRecord,
    **overrides: Any,
) -> ProviderRequest:
    values = {
        "provider_policy_id": "default_fake_provider_v1",
        "tenant_id": scenario_session.tenant_id,
        "region": scenario_session.region,
        "product_id": scenario_session.product_id,
        "frontend_id": scenario_session.frontend_id,
        "scenario_session_id": scenario_session.id,
        "job_id": job.id,
        "workflow_id": action_run.workflow_id,
        "step_id": action_run.step_id,
        "action_run_id": action_run.id,
        "action_type": action_run.action_type,
        "action_config_id": action_run.action_config_id,
        "prompt": "this prompt text should not influence fake fixture selection",
        "prompt_ref": "kernel_demo.extract_structured_fields.v1",
        "metadata": {"api_key": "should-not-persist", "trace": "trace-123"},
        "request_id": "req-123",
        "correlation_id": "corr-456",
    }
    values.update(overrides)
    return ProviderRequest(**values)


class AlwaysFailAdapter:
    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        raise RuntimeError(f"provider exploded for {request.model} with secret_token=abc123")


class SingleAttemptFailureAdapter:
    def __init__(self) -> None:
        self.seen_attempts: list[tuple[int, int, int]] = []

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        self.seen_attempts.append(
            (request.attempt_number, request.timeout_seconds, request.max_retries)
        )
        raise RuntimeError("do not retry in gateway")


class RecordingProviderCallRepository:
    def __init__(self) -> None:
        self.created: list[ProviderCallRecord] = []
        self.updated: list[ProviderCallRecord] = []

    def create(self, record: ProviderCallRecord) -> ProviderCallRecord:
        self.created.append(record)
        return record

    def update(self, record: ProviderCallRecord) -> ProviderCallRecord:
        self.updated.append(record)
        return record


class RecordingEventEmitter:
    def __init__(self) -> None:
        self.emitted: list[tuple[str, Any, dict[str, Any]]] = []

    def emit(self, event_type: str, context: Any, **kwargs: Any) -> None:
        self.emitted.append((event_type, context, kwargs))


class PlatformFailureAdapter:
    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        del request
        raise PlatformError("provider_unavailable", "safe provider failure")


class ResponseErrorCodeAdapter:
    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_id=request.provider_policy_id,
            provider=request.provider,
            model=request.model,
            output_text=json.dumps({"ok": True}, sort_keys=True),
            usage=ProviderUsage(input_tokens=7, output_tokens=3),
            error_code="provider_response_warning",
            error_type="IgnoredErrorType",
            error_message_safe="safe warning",
        )


class ResponseStatusAdapter:
    def __init__(
        self,
        *,
        status: ProviderCallStatus,
        error_code: str | None = None,
        error_message_safe: str | None = None,
    ) -> None:
        self._status = status
        self._error_code = error_code
        self._error_message_safe = error_message_safe

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_id=request.provider_policy_id,
            provider=request.provider,
            model=request.model,
            output_text=json.dumps({"ok": False}, sort_keys=True),
            status=self._status,
            usage=ProviderUsage(input_tokens=3, output_tokens=1),
            error_code=self._error_code,
            error_message_safe=self._error_message_safe,
        )


class CancelledAdapter:
    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        del request
        raise asyncio.CancelledError()


class FallbackSuccessAdapter:
    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_id=request.provider_policy_id,
            provider=request.provider,
            model=request.model,
            output_text=json.dumps({"ok": True}, sort_keys=True),
            usage=ProviderUsage(input_tokens=5, output_tokens=2),
        )


def build_policy_resolver_with_fallback() -> ProviderPolicyResolver:
    return ProviderPolicyResolver(
        build_config_registry(CONFIG_ROOT).__class__(
            loaded_from=CONFIG_ROOT,
            tenants={},
            regions={},
            provider_policies={
                "primary_policy_v1": ProviderPolicy(
                    provider_policy_id="primary_policy_v1",
                    provider="primary",
                    model="primary-model",
                    timeout_seconds=30,
                    max_retries=1,
                    fallback_policy="fallback_policy_v1",
                    structured_output_mode=StructuredOutputMode.json_schema,
                ),
                "fallback_policy_v1": ProviderPolicy(
                    provider_policy_id="fallback_policy_v1",
                    provider="fallback",
                    model="fallback-model",
                    timeout_seconds=30,
                    max_retries=1,
                    structured_output_mode=StructuredOutputMode.json_schema,
                ),
            },
            action_definitions={},
            action_configurations={},
            workflows={},
            scenarios={},
            products={},
            prompts={},
            schemas={},
            quotas={},
            handoffs={},
        )
    )


def test_provider_policy_resolution_uses_config_registry(config_registry: Any) -> None:
    resolver = ProviderPolicyResolver(config_registry)

    policy = resolver.resolve("default_text_generation_v1")

    assert policy.provider == "litellm"
    assert policy.model == "anytoolai.default_text"
    assert policy.metadata["model_group"] == "anytoolai.default_text"


def test_gateway_success_persists_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    gateway = ProviderGateway(
        {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
        ProviderPolicyResolver(config_registry),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        response = asyncio.run(
            gateway.request(build_request(scenario_session, job, action_run), session=session)
        )

        rows = (
            session.execute(
                sa.select(provider_calls_table).order_by(provider_calls_table.c.created_at)
            )
            .mappings()
            .all()
        )

    assert json.loads(response.output_text)["title"] == "Kernel Demo Source Summary"
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == ProviderCallStatus.succeeded
    assert row["provider"] == "fake"
    assert row["model"] == "fake-json-v1"
    assert row["input_tokens"] == 120
    assert row["output_tokens"] == 48
    assert row["error_code"] is None
    assert row["error_message_safe"] is None
    assert row["metadata"]["timeout"]["configured_seconds"] == 30
    assert row["metadata"]["retry"] == {"owned_by": "adapter", "max_retries": 1}
    assert row["metadata"]["request_id"] == "req-123"
    assert row["metadata"]["correlation_id"] == "corr-456"
    assert row["metadata"]["request_metadata"]["api_key"] == "[redacted]"
    assert row["metadata"]["response_metadata"]["fixture_metadata"]["fixture_id"] == (
        "kernel_demo.extract_structured_fields_v1"
    )


def test_gateway_failure_persists_failed_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    gateway = ProviderGateway(
        {"fake": AlwaysFailAdapter()},
        ProviderPolicyResolver(config_registry),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(
                    build_request(scenario_session, job, action_run),
                    session=session,
                )
            )

        rows = (
            session.execute(
                sa.select(provider_calls_table).order_by(provider_calls_table.c.created_at)
            )
            .mappings()
            .all()
        )

    assert exc_info.value.error_type == "RuntimeError"
    assert exc_info.value.error_code == "provider_request_failed"
    assert len(rows) == 1
    assert rows[0]["status"] == ProviderCallStatus.failed
    assert rows[0]["error_code"] == "provider_request_failed"
    assert rows[0]["error_message_safe"] == "[redacted provider error]"


def test_fake_provider_selects_fixtures_by_metadata_not_prompt_text() -> None:
    adapter = FakeProviderAdapter(FIXTURE_ROOT)
    common_kwargs = {
        "provider_policy_id": "default_fake_provider_v1",
        "provider": "fake",
        "model": "fake-json-v1",
        "temperature": 0.0,
        "timeout_seconds": 30,
        "max_retries": 1,
        "structured_output_mode": build_config_registry(CONFIG_ROOT)
        .get_provider_policy("default_fake_provider_v1")
        .structured_output_mode,
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "workflow_id": "workflow_demo",
        "step_id": "extract",
        "action_run_id": "action_run_demo",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "prompt": "identical prompt",
    }

    alpha = asyncio.run(
        adapter.complete(
            ResolvedProviderRequest(
                **common_kwargs,
                fixture_key="fixture_alpha",
            )
        )
    )
    beta = asyncio.run(
        adapter.complete(
            ResolvedProviderRequest(
                **common_kwargs,
                fixture_key="fixture_beta",
            )
        )
    )

    assert alpha.output_text != beta.output_text
    assert json.loads(alpha.output_text)["fixture"] == "alpha"
    assert json.loads(beta.output_text)["fixture"] == "beta"


def test_fake_provider_rejects_fixture_path_traversal() -> None:
    adapter = FakeProviderAdapter(FIXTURE_ROOT)
    common_kwargs = {
        "provider_policy_id": "default_fake_provider_v1",
        "provider": "fake",
        "model": "fake-json-v1",
        "temperature": 0.0,
        "timeout_seconds": 30,
        "max_retries": 1,
        "structured_output_mode": build_config_registry(CONFIG_ROOT)
        .get_provider_policy("default_fake_provider_v1")
        .structured_output_mode,
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "workflow_id": "workflow_demo",
        "step_id": "extract",
        "action_run_id": "action_run_demo",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "prompt": "identical prompt",
    }

    for fixture_key in ("..\\..\\secret", "../secret", "C:\\secret", "/secret"):
        with pytest.raises(PlatformError, match="fake provider fixture key is invalid") as exc_info:
            asyncio.run(
                adapter.complete(
                    ResolvedProviderRequest(
                        **common_kwargs,
                        fixture_key=fixture_key,
                    )
                )
            )
        assert exc_info.value.code == "provider_fixture_key_invalid"


def test_fake_provider_missing_fixture_uses_normal_not_found_behavior() -> None:
    adapter = FakeProviderAdapter(FIXTURE_ROOT)
    common_kwargs = {
        "provider_policy_id": "default_fake_provider_v1",
        "provider": "fake",
        "model": "fake-json-v1",
        "temperature": 0.0,
        "timeout_seconds": 30,
        "max_retries": 1,
        "structured_output_mode": build_config_registry(CONFIG_ROOT)
        .get_provider_policy("default_fake_provider_v1")
        .structured_output_mode,
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "workflow_id": "workflow_demo",
        "step_id": "extract",
        "action_run_id": "action_run_demo",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "prompt": "identical prompt",
    }

    with pytest.raises(FileNotFoundError, match="fake provider fixture not found: missing_fixture"):
        asyncio.run(
            adapter.complete(
                ResolvedProviderRequest(
                    **common_kwargs,
                    fixture_key="missing_fixture",
                )
            )
        )


def test_gateway_records_router_owned_retry_metadata_without_gateway_retries(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    flaky_adapter = SingleAttemptFailureAdapter()
    gateway = ProviderGateway(
        {"fake": flaky_adapter},
        ProviderPolicyResolver(config_registry),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(build_request(scenario_session, job, action_run), session=session)
            )
        rows = (
            session.execute(
                sa.select(provider_calls_table).order_by(provider_calls_table.c.created_at)
            )
            .mappings()
            .all()
        )

    assert exc_info.value.error_code == "provider_request_failed"
    assert flaky_adapter.seen_attempts == [(1, 30, 1)]
    assert len(rows) == 1
    assert rows[0]["status"] == ProviderCallStatus.failed
    assert rows[0]["metadata"]["retry"] == {"owned_by": "adapter", "max_retries": 1}


def test_gateway_supports_explicit_provider_call_repository_dependency(
    config_registry: Any,
) -> None:
    repository = RecordingProviderCallRepository()
    gateway = ProviderGateway(
        {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
        ProviderPolicyResolver(config_registry),
        provider_call_repository=repository,
    )
    scenario_session = make_scenario_session()
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    response = asyncio.run(
        gateway.request(build_request(scenario_session, job, action_run))
    )

    assert json.loads(response.output_text)["title"] == "Kernel Demo Source Summary"
    assert len(repository.created) == 1
    assert len(repository.updated) == 1
    assert repository.updated[0].status is ProviderCallStatus.succeeded


def test_gateway_persists_response_error_code_not_error_type(
    config_registry: Any,
) -> None:
    repository = RecordingProviderCallRepository()
    gateway = ProviderGateway(
        {"fake": ResponseErrorCodeAdapter()},
        ProviderPolicyResolver(config_registry),
        provider_call_repository=repository,
    )
    scenario_session = make_scenario_session()
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    response = asyncio.run(
        gateway.request(build_request(scenario_session, job, action_run))
    )

    assert json.loads(response.output_text)["ok"] is True
    assert len(repository.updated) == 1
    assert repository.updated[0].error_code == "provider_response_warning"
    assert repository.updated[0].error_code != "IgnoredErrorType"
    assert repository.updated[0].error_message_safe == "safe warning"


def test_gateway_skips_provider_call_persistence_when_required_dimensions_invalid(
    config_registry: Any,
) -> None:
    repository = RecordingProviderCallRepository()
    gateway = ProviderGateway(
        {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
        ProviderPolicyResolver(config_registry),
        provider_call_repository=repository,
    )
    scenario_session = make_scenario_session(tenant_id="")
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    response = asyncio.run(
        gateway.request(build_request(scenario_session, job, action_run, tenant_id=""))
    )

    assert json.loads(response.output_text)["title"] == "Kernel Demo Source Summary"
    assert repository.created == []
    assert repository.updated == []


def test_gateway_request_emits_provider_events_when_event_emitter_configured(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = EventEmitter(EventLogRepository(session))
        gateway = ProviderGateway(
            {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
            ProviderPolicyResolver(config_registry),
            event_emitter=emitter,
        )
        scenario_session, job, action_run = seed_runtime_chain(session)

        asyncio.run(
            gateway.request(build_request(scenario_session, job, action_run), session=session)
        )

        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).order_by(event_log_table.c.timestamp)
            ).scalars()
        )

    assert {"provider.request_started", "provider.request_succeeded"} <= set(event_types)


def test_gateway_failed_provider_response_emits_failed_event_without_raising(
    config_registry: Any,
) -> None:
    repository = RecordingProviderCallRepository()
    emitter = RecordingEventEmitter()
    gateway = ProviderGateway(
        {
            "fake": ResponseStatusAdapter(
                status=ProviderCallStatus.failed,
                error_code="provider_response_failed",
                error_message_safe="safe failure",
            )
        },
        ProviderPolicyResolver(config_registry),
        provider_call_repository=repository,
        event_emitter=emitter,
    )
    scenario_session = make_scenario_session()
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    response = asyncio.run(gateway.request(build_request(scenario_session, job, action_run)))

    assert response.status is ProviderCallStatus.failed
    assert repository.updated[0].status is ProviderCallStatus.failed
    succeeded_events = [event for event in emitter.emitted if event[0] == "provider.request_succeeded"]
    failed_events = [event for event in emitter.emitted if event[0] == "provider.request_failed"]
    assert succeeded_events == []
    assert len(failed_events) == 1
    assert failed_events[0][2]["result_status"] == ProviderCallStatus.failed.value
    assert failed_events[0][2]["properties"]["error_code"] == "provider_response_failed"


def test_gateway_timed_out_provider_response_emits_failed_event_without_raising(
    config_registry: Any,
) -> None:
    repository = RecordingProviderCallRepository()
    emitter = RecordingEventEmitter()
    gateway = ProviderGateway(
        {"fake": ResponseStatusAdapter(status=ProviderCallStatus.timed_out)},
        ProviderPolicyResolver(config_registry),
        provider_call_repository=repository,
        event_emitter=emitter,
    )
    scenario_session = make_scenario_session()
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    response = asyncio.run(gateway.request(build_request(scenario_session, job, action_run)))

    assert response.status is ProviderCallStatus.timed_out
    assert repository.updated[0].status is ProviderCallStatus.timed_out
    succeeded_events = [event for event in emitter.emitted if event[0] == "provider.request_succeeded"]
    failed_events = [event for event in emitter.emitted if event[0] == "provider.request_failed"]
    assert succeeded_events == []
    assert len(failed_events) == 1
    assert failed_events[0][2]["result_status"] == ProviderCallStatus.timed_out.value
    assert failed_events[0][2]["properties"]["error_code"] == "provider_request_timed_out"


def test_gateway_request_failure_emits_failed_event_with_safe_platform_error_code(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = EventEmitter(EventLogRepository(session))
        gateway = ProviderGateway(
            {"fake": PlatformFailureAdapter()},
            ProviderPolicyResolver(config_registry),
            event_emitter=emitter,
        )
        scenario_session, job, action_run = seed_runtime_chain(session)

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(build_request(scenario_session, job, action_run), session=session)
            )

        failed_event = (
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.event_type == "provider.request_failed")
                .order_by(event_log_table.c.timestamp.desc(), event_log_table.c.event_id.desc())
            )
            .mappings()
            .first()
        )

    assert failed_event is not None
    assert exc_info.value.error_code == "provider_unavailable"
    assert failed_event["error_code"] == "provider_unavailable"


def test_gateway_fallback_success_event_context_uses_resolved_provider_policy_id() -> None:
    repository = RecordingProviderCallRepository()
    emitter = RecordingEventEmitter()
    gateway = ProviderGateway(
        {"primary": AlwaysFailAdapter(), "fallback": FallbackSuccessAdapter()},
        build_policy_resolver_with_fallback(),
        provider_call_repository=repository,
        event_emitter=emitter,
    )
    scenario_session = make_scenario_session()
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    response = asyncio.run(
        gateway.request(
            build_request(
                scenario_session,
                job,
                action_run,
                provider_policy_id="primary_policy_v1",
            )
        )
    )

    assert json.loads(response.output_text)["ok"] is True
    assert repository.updated[0].provider_policy_id == "fallback_policy_v1"
    succeeded_events = [
        event for event in emitter.emitted if event[0] == "provider.request_succeeded"
    ]
    assert len(succeeded_events) == 1
    assert succeeded_events[0][1].provider_policy_id == "fallback_policy_v1"


def test_gateway_fallback_failure_event_context_uses_resolved_provider_policy_id() -> None:
    repository = RecordingProviderCallRepository()
    emitter = RecordingEventEmitter()
    gateway = ProviderGateway(
        {"primary": AlwaysFailAdapter(), "fallback": PlatformFailureAdapter()},
        build_policy_resolver_with_fallback(),
        provider_call_repository=repository,
        event_emitter=emitter,
    )
    scenario_session = make_scenario_session()
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    with pytest.raises(ProviderGatewayExecutionError) as exc_info:
        asyncio.run(
            gateway.request(
                build_request(
                    scenario_session,
                    job,
                    action_run,
                    provider_policy_id="primary_policy_v1",
                )
            )
        )

    assert exc_info.value.provider_policy_id == "fallback_policy_v1"
    assert repository.updated[0].provider_policy_id == "fallback_policy_v1"
    failed_events = [event for event in emitter.emitted if event[0] == "provider.request_failed"]
    assert len(failed_events) == 1
    assert failed_events[0][1].provider_policy_id == "fallback_policy_v1"


def test_gateway_request_cancellation_cleans_up_running_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    with transaction_boundary(session_factory) as session:
        gateway = ProviderGateway(
            {"fake": CancelledAdapter()},
            ProviderPolicyResolver(config_registry),
        )
        scenario_session, job, action_run = seed_runtime_chain(session)

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(
                gateway.request(build_request(scenario_session, job, action_run), session=session)
            )

        rows = (
            session.execute(
                sa.select(provider_calls_table).order_by(provider_calls_table.c.created_at)
            )
            .mappings()
            .all()
        )

    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == ProviderCallStatus.failed
    assert row["completed_at"] is not None
    assert row["latency_ms"] >= 0
    assert row["error_code"] == "provider_request_cancelled"
    assert row["error_message_safe"] == "provider request cancelled"


@pytest.mark.parametrize(("field_name", "value"), [("tenant_id", ""), ("region", "")])
def test_gateway_request_invalid_event_dimensions_raise_and_skip_persistence(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
    field_name: str,
    value: str,
) -> None:
    with transaction_boundary(session_factory) as session:
        emitter = EventEmitter(EventLogRepository(session))
        gateway = ProviderGateway(
            {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
            ProviderPolicyResolver(config_registry),
            event_emitter=emitter,
        )
        scenario_session, job, action_run = seed_runtime_chain(session)
        request = build_request(scenario_session, job, action_run, **{field_name: value})

        with pytest.raises(EventValidationError, match=field_name):
            asyncio.run(gateway.request(request, session=session))

        provider_call_count = session.execute(
            sa.select(sa.func.count()).select_from(provider_calls_table)
        ).scalar_one()
        event_count = session.execute(
            sa.select(sa.func.count()).select_from(event_log_table)
        ).scalar_one()

    assert provider_call_count == 0
    assert event_count == 0
