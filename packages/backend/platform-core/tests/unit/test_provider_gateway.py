from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.context.execution_context import ExecutionContext
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderRequest,
    ProviderResponse,
)
from anytoolai_platform_core.providers.models import ProviderCallStatus
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import event_log_table, provider_calls_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from sqlalchemy import event


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


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
        "script_location", str(_repo_root() / "migrations" / "platform")
    )
    alembic_config.set_main_option("sqlalchemy.url", database_url)
    return alembic_config


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "provider-gateway-main.sqlite3"
    platform_db = tmp_path / "provider-gateway-platform.sqlite3"
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
    }
    values.update(overrides)
    return ExecutionContext(**values)


class SuccessfulAdapter:
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            content="ok",
            provider="openai",
            model=request.model,
            input_tokens=128,
            output_tokens=64,
            total_tokens=192,
            latency_ms=950,
            estimated_cost=0.42,
            http_status=200,
            litellm_response_id="litellm_resp_123",
        )


class TimeoutAdapter:
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        del request
        raise TimeoutError("provider timed out")


class HttpFailure(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"http status {status_code}")
        self.status_code = status_code


class HttpFailureAdapter:
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        del request
        raise HttpFailure(429)


class PlatformFailureAdapter:
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        del request
        raise PlatformError("provider_unavailable", "safe provider failure")


def _build_emitter(session: sa.orm.Session) -> EventEmitter:
    return EventEmitter(EventLogRepository(session))


def test_provider_gateway_success_persists_one_row_per_physical_attempt(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        gateway = ProviderGateway(
            {"openai": SuccessfulAdapter()},
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=_build_emitter(session),
        )

        record, response = gateway.execute(
            "openai",
            ProviderRequest(prompt="hello", model="gpt-5-mini"),
            make_execution_context(),
            provider_policy_id="policy_primary",
            action_run_id="action_run_demo",
            semantic_attempt_index=2,
            transport_attempt_index=1,
            physical_call_index=3,
            pydantic_run_id="pydantic_run_1",
        )

        stored_rows = list(
            session.execute(sa.select(provider_calls_table).order_by(provider_calls_table.c.id))
            .mappings()
        )
        event_rows = list(
            session.execute(
                sa.select(event_log_table).where(
                    event_log_table.c.event_type.like("provider.request_%")
                )
            ).mappings()
        )

    assert response.litellm_response_id == "litellm_resp_123"
    assert len(stored_rows) == 1
    assert record.status is ProviderCallStatus.succeeded
    assert record.workflow_version == 1
    assert record.gateway_backend == "litellm_sdk"
    assert record.gateway_model == "gpt-5-mini"
    assert record.semantic_attempt_index == 2
    assert record.transport_attempt_index == 1
    assert record.physical_call_index == 3
    assert record.input_tokens == 128
    assert record.output_tokens == 64
    assert record.total_tokens == 192
    assert record.http_status == 200
    assert record.pydantic_run_id == "pydantic_run_1"
    assert record.litellm_response_id == "litellm_resp_123"
    assert stored_rows[0]["id"] == record.id
    assert stored_rows[0]["status"] == ProviderCallStatus.succeeded
    assert len(event_rows) == 2


def test_provider_gateway_timeout_updates_existing_row_without_creating_extra_rows(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        gateway = ProviderGateway(
            {"openai": TimeoutAdapter()},
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=_build_emitter(session),
        )

        with pytest.raises(TimeoutError):
            gateway.execute(
                "openai",
                ProviderRequest(prompt="hello", model="gpt-5-mini"),
                make_execution_context(),
                provider_policy_id="policy_primary",
                action_run_id="action_run_demo",
                physical_call_index=4,
                pydantic_run_id="pydantic_run_timeout",
            )

        stored_rows = list(
            session.execute(sa.select(provider_calls_table).order_by(provider_calls_table.c.id))
            .mappings()
        )

    assert len(stored_rows) == 1
    assert stored_rows[0]["status"] == ProviderCallStatus.timed_out
    assert stored_rows[0]["failure_kind"] == "timeout"
    assert stored_rows[0]["error_code"] == "timeout"
    assert stored_rows[0]["http_status"] is None
    assert stored_rows[0]["physical_call_index"] == 4
    assert stored_rows[0]["pydantic_run_id"] == "pydantic_run_timeout"


def test_provider_gateway_http_failure_captures_http_status_and_failure_kind(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        gateway = ProviderGateway(
            {"openai": HttpFailureAdapter()},
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=_build_emitter(session),
        )

        with pytest.raises(HttpFailure):
            gateway.execute(
                "openai",
                ProviderRequest(prompt="hello", model="gpt-5-mini"),
                make_execution_context(),
                provider_policy_id="policy_primary",
                action_run_id="action_run_demo",
            )

        stored = session.execute(sa.select(provider_calls_table)).mappings().one()

    assert stored["status"] == ProviderCallStatus.failed
    assert stored["failure_kind"] == "http_error"
    assert stored["http_status"] == 429


def test_provider_gateway_platform_failure_uses_safe_error_code(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        gateway = ProviderGateway(
            {"openai": PlatformFailureAdapter()},
            provider_call_repository=ProviderCallRepository(session),
            event_emitter=_build_emitter(session),
        )

        with pytest.raises(PlatformError):
            gateway.execute(
                "openai",
                ProviderRequest(prompt="hello", model="gpt-5-mini"),
                make_execution_context(),
                provider_policy_id="policy_primary",
                action_run_id="action_run_demo",
            )

        stored = session.execute(sa.select(provider_calls_table)).mappings().one()

    assert stored["status"] == ProviderCallStatus.failed
    assert stored["failure_kind"] == "platform_error"
    assert stored["error_code"] == "provider_unavailable"
