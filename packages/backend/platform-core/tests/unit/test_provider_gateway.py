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
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.models import (
    ProviderCallRecord,
    ProviderCallStatus,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
    ResolvedProviderRequest,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import provider_calls_table
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
        command.upgrade(alembic_config, "0001")

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


class FlakyAdapter:
    def __init__(self) -> None:
        self.seen_attempts: list[tuple[int, int, int]] = []

    async def complete(self, request: ResolvedProviderRequest) -> ProviderResponse:
        self.seen_attempts.append(
            (request.attempt_number, request.timeout_seconds, request.max_retries)
        )
        if request.attempt_number == 1:
            raise RuntimeError("retry me once")
        return ProviderResponse(
            provider_policy_id=request.provider_policy_id,
            provider=request.provider,
            model=request.model,
            output_text=json.dumps({"ok": True}, sort_keys=True),
            usage=ProviderUsage(input_tokens=21, output_tokens=8),
        )


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


def test_provider_policy_resolution_uses_config_registry(config_registry: Any) -> None:
    resolver = ProviderPolicyResolver(config_registry)

    policy = resolver.resolve("default_text_generation_v1")

    assert policy.provider == "openai"
    assert policy.model == "gpt-4.1-mini"


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
    assert row["status"] is ProviderCallStatus.succeeded
    assert row["provider"] == "fake"
    assert row["model"] == "fake-json-v1"
    assert row["input_tokens"] == 120
    assert row["output_tokens"] == 48
    assert row["error_code"] is None
    assert row["error_message_safe"] is None
    assert row["metadata"]["timeout"]["configured_seconds"] == 30
    assert row["metadata"]["retry"] == {"attempt_number": 1, "max_retries": 1}
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
    assert len(rows) == 2
    assert rows[0]["status"] is ProviderCallStatus.failed
    assert rows[1]["status"] is ProviderCallStatus.failed
    assert rows[1]["error_code"] == "provider_request_failed"
    assert rows[1]["error_message_safe"] == "[redacted provider error]"


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


def test_gateway_captures_retry_metadata_and_retries_once(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: Any,
) -> None:
    flaky_adapter = FlakyAdapter()
    gateway = ProviderGateway(
        {"fake": flaky_adapter},
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

    assert json.loads(response.output_text)["ok"] is True
    assert flaky_adapter.seen_attempts == [(1, 30, 1), (2, 30, 1)]
    assert [row["status"] for row in rows] == [
        ProviderCallStatus.failed,
        ProviderCallStatus.succeeded,
    ]
    assert rows[0]["metadata"]["retry"] == {"attempt_number": 1, "max_retries": 1}
    assert rows[1]["metadata"]["retry"] == {"attempt_number": 2, "max_retries": 1}


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
