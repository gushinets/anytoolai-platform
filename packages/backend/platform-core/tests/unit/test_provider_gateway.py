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
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.adapters.fake import FakeProviderAdapter
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderMessage,
    ProviderPolicy,
    ProviderRequest,
    ProviderResponse,
    ProviderRetryHardLimits,
    ProviderRetryPolicy,
    ProviderTransportRetryPolicy,
    ProviderUsage,
    ProviderValidationRetryPolicy,
    ResolvedProviderRequest,
    StructuredOutputMode,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
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
DEFAULT_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
KERNEL_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["title", "fields"],
    "additionalProperties": False,
}


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
def config_registry() -> ConfigRegistry:
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


def make_action_run(
    scenario_session_id: str,
    job_id: str,
    **overrides: Any,
) -> ActionRunRecord:
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
    action_run = ActionRunRepository(session).create(
        make_action_run(scenario_session.id, job.id)
    )
    return scenario_session, job, action_run


def build_request(
    scenario_session: ScenarioSessionRecord,
    job: JobRecord,
    action_run: ActionRunRecord,
    **overrides: Any,
) -> ProviderRequest:
    values = {
        "provider_policy_ref": "default_fake_provider_v1",
        "tenant_id": scenario_session.tenant_id,
        "region": scenario_session.region,
        "product_id": scenario_session.product_id,
        "frontend_id": scenario_session.frontend_id,
        "scenario_session_id": scenario_session.id,
        "job_id": job.id,
        "workflow_id": action_run.workflow_id,
        "workflow_version": job.workflow_version,
        "step_id": action_run.step_id,
        "action_run_id": action_run.id,
        "action_type": action_run.action_type,
        "action_config_id": action_run.action_config_id,
        "prompt": "return structured json",
        "prompt_ref": "kernel_demo.extract_structured_fields.v1",
        "response_schema": None,
        "metadata": {"trace": "trace-123", "api_key": "do-not-persist"},
        "request_id": "req-123",
        "correlation_id": "corr-456",
        "semantic_attempt_index": 1,
        "pydantic_run_id": "pydantic-run-demo",
    }
    values.update(overrides)
    return ProviderRequest(**values)


def build_policy_resolver(*policies: ProviderPolicy) -> ProviderPolicyResolver:
    return ProviderPolicyResolver(
        ConfigRegistry(
            loaded_from=CONFIG_ROOT,
            tenants={},
            regions={},
            provider_policies={
                policy.provider_policy_ref: policy for policy in policies
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


def build_resolved_request(**overrides: Any) -> ResolvedProviderRequest:
    values = {
        "provider_policy_ref": "default_fake_provider_v1",
        "provider": "fake",
        "model": "fake-json-v1",
        "temperature": 0.0,
        "timeout_seconds": 30,
        "retry_policy": ProviderRetryPolicy(
            transport=ProviderTransportRetryPolicy(owner="fake_adapter", max_attempts=1),
            validation=ProviderValidationRetryPolicy(owner="pydanticai", max_attempts=1),
            hard_limits=ProviderRetryHardLimits(
                max_physical_provider_calls_per_action=1
            ),
        ),
        "structured_output_mode": StructuredOutputMode.json_schema,
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "workflow_id": "workflow_demo",
        "workflow_version": 1,
        "step_id": "extract",
        "action_run_id": "action_run_demo",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "prompt": "identical prompt",
        "messages": (
            ProviderMessage(role="user", content="identical prompt"),
        ),
    }
    values.update(overrides)
    return ResolvedProviderRequest(**values)


class TransportRetryAdapter:
    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("transport exploded with secret_token=abc123")
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text='{"ok": true}',
            usage=ProviderUsage(input_tokens=6, output_tokens=2),
        )


class AlwaysFailAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        raise RuntimeError(f"provider exploded for {request.model} with secret_token=abc123")


class UnsafeRawTextAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        raise RuntimeError(
            "provider raw response echoed prompt="
            f"{request.prompt}; user_text=deadline budget deliverables"
        )


class UnsafeGatewayErrorAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        raise ProviderGatewayExecutionError(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            error_code="provider_request_failed",
            error_type="CustomAdapterGatewayError",
            message=(
                "adapter echoed prompt="
                f"{request.prompt}; user_text=deadline budget deliverables"
            ),
            resolved_request=request,
            failure_kind="transport",
        )


class PlatformFailureAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        del request
        raise PlatformError("provider_unavailable", "safe provider failure")


class CancelledAdapter:
    async def complete(self, request: Any) -> ProviderResponse:
        del request
        raise asyncio.CancelledError()


def _provider_rows(session: sa.orm.Session) -> list[dict[str, Any]]:
    return list(
        session.execute(
            sa.select(provider_calls_table).order_by(
                provider_calls_table.c.physical_call_index,
                provider_calls_table.c.id,
            )
        ).mappings()
    )


def test_provider_policy_resolution_uses_nested_retry_policy(
    config_registry: ConfigRegistry,
) -> None:
    policy = ProviderPolicyResolver(config_registry).resolve("default_text_generation_v1")

    assert policy.provider == "litellm"
    assert policy.retry_policy.transport.max_attempts == 2
    assert policy.retry_policy.transport.litellm_num_retries_per_attempt == 0
    assert policy.retry_policy.validation.max_attempts == 2


def test_gateway_success_persists_adr_0007_provider_call_ledger(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: ConfigRegistry,
) -> None:
    gateway = ProviderGateway(
        {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
        ProviderPolicyResolver(config_registry),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        response = asyncio.run(
            gateway.request(
                build_request(
                    scenario_session,
                    job,
                    action_run,
                    response_schema=KERNEL_EXTRACT_SCHEMA,
                ),
                session=session,
            )
        )
        rows = _provider_rows(session)

    assert json.loads(response.output_text)["title"] == "Kernel Demo Source Summary"
    assert response.structured_output is None
    assert len(rows) == 1
    row = rows[0]
    assert row["provider_policy_ref"] == "default_fake_provider_v1"
    assert row["workflow_version"] == 1
    assert row["gateway_backend"] == "fake"
    assert row["gateway_model"] == "fake-json-v1"
    assert row["semantic_attempt_index"] == 1
    assert row["transport_attempt_index"] == 1
    assert row["physical_call_index"] == 1
    assert row["status"] == ProviderCallStatus.succeeded
    assert row["total_tokens"] == row["input_tokens"] + row["output_tokens"]
    assert row["pydantic_run_id"] == "pydantic-run-demo"
    assert row["litellm_response_id"] is None


def test_gateway_uses_caller_supplied_semantic_attempt_index_and_pydantic_run_id(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry: ConfigRegistry,
) -> None:
    gateway = ProviderGateway(
        {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
        ProviderPolicyResolver(config_registry),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        response = asyncio.run(
            gateway.request(
                build_request(
                    scenario_session,
                    job,
                    action_run,
                    semantic_attempt_index=2,
                    pydantic_run_id="pydantic-run-attempt-2",
                ),
                session=session,
            )
        )
        rows = _provider_rows(session)

    assert json.loads(response.output_text)["title"] == "Kernel Demo Source Summary"
    assert len(rows) == 1
    assert rows[0]["semantic_attempt_index"] == 2
    assert rows[0]["transport_attempt_index"] == 1
    assert rows[0]["physical_call_index"] == 1
    assert rows[0]["pydantic_run_id"] == "pydantic-run-attempt-2"


def test_gateway_transport_retry_creates_multiple_rows_with_transport_indexes(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    adapter = TransportRetryAdapter()
    policy = ProviderPolicy(
        provider_policy_ref="transport_retry_policy_v1",
        provider="fake",
        model="fake-json-v1",
        retry_policy=ProviderRetryPolicy(
            transport=ProviderTransportRetryPolicy(
                owner="fake_adapter",
                max_attempts=2,
                litellm_num_retries_per_attempt=0,
            ),
            validation=ProviderValidationRetryPolicy(owner="pydanticai", max_attempts=1),
            hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
        ),
    )
    gateway = ProviderGateway(
        {"fake": adapter},
        build_policy_resolver(policy),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        response = asyncio.run(
            gateway.request(
                build_request(
                    scenario_session,
                    job,
                    action_run,
                    provider_policy_ref="transport_retry_policy_v1",
                    response_schema=DEFAULT_SCHEMA,
                ),
                session=session,
            )
        )
        rows = _provider_rows(session)

    assert adapter.call_count == 2
    assert response.structured_output is None
    assert [row["semantic_attempt_index"] for row in rows] == [1, 1]
    assert [row["transport_attempt_index"] for row in rows] == [1, 2]
    assert [row["physical_call_index"] for row in rows] == [1, 2]
    assert rows[0]["status"] == ProviderCallStatus.failed
    assert rows[1]["status"] == ProviderCallStatus.succeeded
    assert rows[0]["error_code"] == "provider_request_failed"
    assert rows[0]["error_message_safe"] == "Provider request failed."


def test_gateway_enforces_hard_physical_call_limit(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    policy = ProviderPolicy(
        provider_policy_ref="hard_limit_policy_v1",
        provider="fake",
        model="fake-json-v1",
        retry_policy=ProviderRetryPolicy(
            transport=ProviderTransportRetryPolicy(
                owner="fake_adapter",
                max_attempts=3,
                litellm_num_retries_per_attempt=0,
            ),
            validation=ProviderValidationRetryPolicy(owner="pydanticai", max_attempts=1),
            hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
        ),
    )
    gateway = ProviderGateway(
        {"fake": AlwaysFailAdapter()},
        build_policy_resolver(policy),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(
                    build_request(
                        scenario_session,
                        job,
                        action_run,
                        provider_policy_ref="hard_limit_policy_v1",
                    ),
                    session=session,
                )
            )
        rows = _provider_rows(session)

    assert exc_info.value.error_code == "provider_physical_call_limit_exceeded"
    assert len(rows) == 2
    assert [row["physical_call_index"] for row in rows] == [1, 2]


def test_gateway_uses_safe_platform_error_codes_on_failure(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    policy = ProviderPolicy(
        provider_policy_ref="platform_failure_policy_v1",
        provider="fake",
        model="fake-json-v1",
    )
    gateway = ProviderGateway(
        {"fake": PlatformFailureAdapter()},
        build_policy_resolver(policy),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(
                    build_request(
                        scenario_session,
                        job,
                        action_run,
                        provider_policy_ref="platform_failure_policy_v1",
                    ),
                    session=session,
                )
            )
        rows = _provider_rows(session)

    assert exc_info.value.error_code == "provider_unavailable"
    assert len(rows) == 1
    assert rows[0]["error_code"] == "provider_unavailable"
    assert rows[0]["failure_kind"] == "transport"


def test_gateway_persists_provider_call_row_when_exception_escapes_transaction_boundary(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    policy = ProviderPolicy(
        provider_policy_ref="escaped_failure_policy_v1",
        provider="fake",
        model="fake-json-v1",
    )
    gateway = ProviderGateway(
        {"fake": AlwaysFailAdapter()},
        build_policy_resolver(policy),
    )

    with pytest.raises(ProviderGatewayExecutionError) as exc_info:
        with transaction_boundary(session_factory) as session:
            scenario_session, job, action_run = seed_runtime_chain(session)
            asyncio.run(
                gateway.request(
                    build_request(
                        scenario_session,
                        job,
                        action_run,
                        provider_policy_ref="escaped_failure_policy_v1",
                    ),
                    session=session,
                )
            )

    with transaction_boundary(session_factory) as session:
        rows = _provider_rows(session)

    assert exc_info.value.error_code == "provider_request_failed"
    assert len(rows) == 1
    assert rows[0]["status"] == ProviderCallStatus.failed
    assert rows[0]["error_code"] == "provider_request_failed"
    assert rows[0]["failure_kind"] == "transport"


def test_gateway_request_cancellation_persists_failed_provider_call(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    policy = ProviderPolicy(
        provider_policy_ref="cancel_policy_v1",
        provider="fake",
        model="fake-json-v1",
    )
    gateway = ProviderGateway(
        {"fake": CancelledAdapter()},
        build_policy_resolver(policy),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(
                gateway.request(
                    build_request(
                        scenario_session,
                        job,
                        action_run,
                        provider_policy_ref="cancel_policy_v1",
                    ),
                    session=session,
                )
            )
        rows = _provider_rows(session)

    assert len(rows) == 1
    assert rows[0]["error_code"] == "provider_request_cancelled"
    assert rows[0]["status"] == ProviderCallStatus.failed
    assert rows[0]["failure_kind"] == "cancelled"


def test_gateway_unknown_adapter_exception_uses_generic_safe_message(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    policy = ProviderPolicy(
        provider_policy_ref="unsafe_raw_text_policy_v1",
        provider="fake",
        model="fake-json-v1",
    )
    gateway = ProviderGateway(
        {"fake": UnsafeRawTextAdapter()},
        build_policy_resolver(policy),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(
                    build_request(
                        scenario_session,
                        job,
                        action_run,
                        provider_policy_ref="unsafe_raw_text_policy_v1",
                        prompt="rewrite this client note verbatim",
                    ),
                    session=session,
                )
            )
        rows = _provider_rows(session)

    assert exc_info.value.error_code == "provider_request_failed"
    assert exc_info.value.message == "Provider request failed."
    assert "rewrite this client note verbatim" not in exc_info.value.message
    assert len(rows) == 1
    assert rows[0]["error_message_safe"] == "Provider request failed."
    assert rows[0]["metadata"]["error"]["type"] == "RuntimeError"
    assert rows[0]["metadata"]["error"]["message_safe"] == "Provider request failed."
    assert "deadline budget deliverables" not in rows[0]["error_message_safe"]


def test_gateway_sanitizes_adapter_raised_provider_gateway_execution_error(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    policy = ProviderPolicy(
        provider_policy_ref="unsafe_gateway_error_policy_v1",
        provider="fake",
        model="fake-json-v1",
    )
    gateway = ProviderGateway(
        {"fake": UnsafeGatewayErrorAdapter()},
        build_policy_resolver(policy),
    )

    with transaction_boundary(session_factory) as session:
        scenario_session, job, action_run = seed_runtime_chain(session)
        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(
                gateway.request(
                    build_request(
                        scenario_session,
                        job,
                        action_run,
                        provider_policy_ref="unsafe_gateway_error_policy_v1",
                        prompt="rewrite this client note verbatim",
                    ),
                    session=session,
                )
            )
        rows = _provider_rows(session)

    assert exc_info.value.error_code == "provider_request_failed"
    assert exc_info.value.error_type == "CustomAdapterGatewayError"
    assert exc_info.value.message == "Provider request failed."
    assert "rewrite this client note verbatim" not in exc_info.value.message
    assert len(rows) == 1
    assert rows[0]["error_message_safe"] == "Provider request failed."
    assert rows[0]["metadata"]["error"]["type"] == "CustomAdapterGatewayError"
    assert rows[0]["metadata"]["error"]["message_safe"] == "Provider request failed."


def test_gateway_recovery_preserves_started_event_pydantic_run_id(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    policy = ProviderPolicy(
        provider_policy_ref="recovered_started_event_policy_v1",
        provider="fake",
        model="fake-json-v1",
    )

    with pytest.raises(ProviderGatewayExecutionError):
        with transaction_boundary(session_factory) as session:
            gateway = ProviderGateway(
                {"fake": AlwaysFailAdapter()},
                build_policy_resolver(policy),
                provider_call_repository=ProviderCallRepository(session),
                event_emitter=EventEmitter(EventLogRepository(session)),
            )
            scenario_session, job, action_run = seed_runtime_chain(session)
            asyncio.run(
                gateway.request(
                    build_request(
                        scenario_session,
                        job,
                        action_run,
                        provider_policy_ref="recovered_started_event_policy_v1",
                    ),
                    session=session,
                )
            )

    with transaction_boundary(session_factory) as session:
        started_event = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "provider.request_started"
            )
        ).mappings().one()

    assert started_event["pydantic_run_id"] == "pydantic-run-demo"


def test_gateway_skips_persistence_when_required_dimensions_are_invalid(
    config_registry: ConfigRegistry,
) -> None:
    gateway = ProviderGateway(
        {"fake": FakeProviderAdapter(FIXTURE_ROOT)},
        ProviderPolicyResolver(config_registry),
        provider_call_repository=object(),
    )
    scenario_session = make_scenario_session(tenant_id="")
    job = make_job(scenario_session.id)
    action_run = make_action_run(scenario_session.id, job.id)

    response = asyncio.run(
        gateway.request(build_request(scenario_session, job, action_run, tenant_id=""))
    )

    assert json.loads(response.output_text)["title"] == "Kernel Demo Source Summary"


def test_fake_provider_selects_fixture_key_before_action_config_and_ignores_prompt() -> None:
    adapter = FakeProviderAdapter(FIXTURE_ROOT)

    response = asyncio.run(
        adapter.complete(
            build_resolved_request(
                prompt="this prompt should not matter",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                fixture_key="fixture_alpha",
                metadata={"fixture_key": "fixture_beta"},
            )
        )
    )

    assert json.loads(response.output_text) == {"fixture": "alpha"}


def test_fake_provider_uses_request_metadata_fixture_key_before_action_config() -> None:
    adapter = FakeProviderAdapter(FIXTURE_ROOT)

    response = asyncio.run(
        adapter.complete(
            build_resolved_request(
                prompt="completely different prompt text",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                metadata={"fixture_key": "fixture_beta"},
            )
        )
    )

    assert json.loads(response.output_text) == {"fixture": "beta"}


def test_fake_provider_falls_back_to_action_config_id_when_no_fixture_key_present() -> None:
    adapter = FakeProviderAdapter(FIXTURE_ROOT)

    response = asyncio.run(
        adapter.complete(
            build_resolved_request(
                prompt="another prompt that must be ignored",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                metadata={},
            )
        )
    )

    assert json.loads(response.output_text)["title"] == "Kernel Demo Source Summary"
