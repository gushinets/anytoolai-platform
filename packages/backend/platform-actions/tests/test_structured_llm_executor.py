from __future__ import annotations

import asyncio
from dataclasses import replace
import tomllib
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import event

from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.models import ProviderCallRecord
from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse
from anytoolai_platform_core.providers.models import ProviderRequest
from anytoolai_platform_core.providers.models import ProviderValidationRetryPolicy
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import artifacts_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.structured_output.errors import (
    STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE,
    STRUCTURED_OUTPUT_VALIDATION_SAFE_MESSAGE,
    StructuredOutputValidationError,
)
from anytoolai_platform_actions.structured_llm.executor import (
    StructuredLlmActionExecutor,
    StructuredLlmActionRequest,
)
from anytoolai_platform_actions.structured_llm.pydanticai_runner import (
    PydanticAIStructuredRunner,
)
from pydantic_ai import UnexpectedModelBehavior

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
PACKAGE_ROOT = REPO_ROOT / "packages" / "backend" / "platform-actions"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    main_db = tmp_path / "platform-actions-main.sqlite3"
    platform_db = tmp_path / "platform-actions-platform.sqlite3"
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


class SpyGateway:
    def __init__(self) -> None:
        self.requests = []
        self.sessions = []

    async def request(self, request, *, session):
        self.requests.append(request)
        self.sessions.append(session)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text='{"title": "Summary", "fields": ["budget", "timeline"]}',
            status=ProviderCallStatus.succeeded,
        )


class ValidationRetrySpyGateway:
    def __init__(self) -> None:
        self.requests = []
        self.sessions = []

    async def request(self, request, *, session):
        self.requests.append(request)
        self.sessions.append(session)
        if len(self.requests) == 1:
            return ProviderResponse(
                provider_policy_ref=request.provider_policy_ref,
                provider="fake",
                model="fake-json-v1",
                output_text="not-json",
                status=ProviderCallStatus.succeeded,
            )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text='{"title": "Summary", "fields": ["budget", "timeline"]}',
            status=ProviderCallStatus.succeeded,
        )


class ExhaustedValidationSpyGateway:
    def __init__(self) -> None:
        self.requests = []
        self.sessions = []

    async def request(self, request, *, session):
        self.requests.append(request)
        self.sessions.append(session)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text="not-json",
            status=ProviderCallStatus.succeeded,
        )


def test_platform_actions_package_declares_runtime_dependencies() -> None:
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    core_pyproject = tomllib.loads(
        (
            REPO_ROOT
            / "packages"
            / "backend"
            / "platform-core"
            / "pyproject.toml"
        ).read_text(encoding="utf-8")
    )

    dependencies = pyproject["project"]["dependencies"]
    core_dependencies = core_pyproject["project"]["dependencies"]
    sources = pyproject["tool"]["uv"]["sources"]

    assert "anytoolai-platform-core" in dependencies
    assert "pydantic-ai-slim>=2.2.0" in dependencies
    assert "sqlalchemy>=2.0" in dependencies
    assert "pydantic-ai-slim>=2.2.0" not in core_dependencies
    assert sources["anytoolai-platform-core"] == {
        "path": "../platform-core",
        "editable": True,
    }


def test_structured_llm_executor_routes_calls_through_provider_gateway() -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = SpyGateway()
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=spy_gateway,
    )
    request = StructuredLlmActionRequest(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        workflow_id="kernel_demo.single_action_extract_v1",
        workflow_version=1,
        step_id="extract",
        action_run_id="action_run_demo",
        action_config_id="kernel_demo.extract_structured_fields_v1",
        input_payload={"source_text": "Budget and timeline details"},
        metadata={"trace": "trace-123"},
        fixture_key="fixture_alpha",
        request_id="req-123",
        correlation_id="corr-456",
    )
    session = object()

    response = asyncio.run(executor.execute(request, session=session))

    assert response.output_text == '{"title": "Summary", "fields": ["budget", "timeline"]}'
    assert spy_gateway.sessions == [session]
    assert len(spy_gateway.requests) == 1
    provider_request = spy_gateway.requests[0]
    assert provider_request.provider_policy_ref == "default_fake_provider_v1"
    assert provider_request.workflow_version == 1
    assert provider_request.action_type == "text.extract_structured_fields"
    assert provider_request.prompt_ref == "kernel_demo.extract_structured_fields.v1"
    assert provider_request.fixture_key == "fixture_alpha"
    assert provider_request.request_id == "req-123"
    assert provider_request.correlation_id == "corr-456"
    assert provider_request.semantic_attempt_index == 1
    assert "Budget and timeline details" in provider_request.prompt
    assert provider_request.response_schema == registry.get_schema(
        "kernel.schemas.extract_output_v1"
    ).schema


def test_structured_llm_executor_owns_validation_retries_through_gateway_dtos() -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = ValidationRetrySpyGateway()
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=spy_gateway,
    )
    base_policy = registry.get_provider_policy("default_fake_provider_v1")
    assert base_policy is not None
    executor._require_provider_policy = lambda _provider_policy_ref: replace(
        base_policy,
        retry_policy=replace(
            base_policy.retry_policy,
            validation=ProviderValidationRetryPolicy(
                owner=base_policy.retry_policy.validation.owner,
                max_attempts=2,
            ),
        ),
    )
    request = StructuredLlmActionRequest(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        workflow_id="kernel_demo.single_action_extract_v1",
        workflow_version=1,
        step_id="extract",
        action_run_id="action_run_demo",
        action_config_id="kernel_demo.extract_structured_fields_v1",
        input_payload={"source_text": "Budget and timeline details"},
    )
    session = object()

    response = asyncio.run(executor.execute(request, session=session))

    assert response.output_text == '{"title": "Summary", "fields": ["budget", "timeline"]}'
    assert response.structured_output == {
        "title": "Summary",
        "fields": ["budget", "timeline"],
    }
    assert response.pydantic_run_id is not None
    assert spy_gateway.sessions == [session, session]
    assert [gateway_request.semantic_attempt_index for gateway_request in spy_gateway.requests] == [
        1,
        2,
    ]


def test_structured_llm_executor_finalizes_and_persists_structured_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = SpyGateway()
    with transaction_boundary(session_factory) as session:
        artifact_service = ArtifactService(
            ArtifactRepository(session),
            EventEmitter(EventLogRepository(session)),
        )
        provider_call_repository = ProviderCallRepository(session)
        provider_call_repository.create(
            ProviderCallRecord(
                tenant_id="tenant_demo",
                region="eu-central",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                scenario_session_id="scenario_session_demo",
                job_id="job_demo",
                action_run_id="action_run_demo",
                workflow_id="kernel_demo.single_action_extract_v1",
                workflow_version=1,
                step_id="extract",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                provider_policy_ref="default_fake_provider_v1",
                provider="fake",
                model="fake-json-v1",
                gateway_backend="fake",
                gateway_model="fake-json-v1",
                semantic_attempt_index=1,
                transport_attempt_index=1,
                physical_call_index=1,
            )
        )
        executor = StructuredLlmActionExecutor(
            config_registry=registry,
            provider_gateway=spy_gateway,
            artifact_service=artifact_service,
        )
        request = StructuredLlmActionRequest(
            tenant_id="tenant_demo",
            region="eu-central",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            scenario_session_id="scenario_session_demo",
            job_id="job_demo",
            workflow_id="kernel_demo.single_action_extract_v1",
            workflow_version=1,
            step_id="extract",
            action_run_id="action_run_demo",
            action_config_id="kernel_demo.extract_structured_fields_v1",
            input_payload={"source_text": "Budget and timeline details"},
        )

        response = asyncio.run(executor.execute(request, session=session))
        artifact_rows = list(
            session.execute(sa.select(artifacts_table)).mappings()
        )

    assert response.structured_output == {
        "title": "Summary",
        "fields": ["budget", "timeline"],
    }
    assert response.metadata["structured_output_artifact_id"].startswith("artifact_")
    assert len(artifact_rows) == 1
    assert artifact_rows[0]["artifact_type"] == "structured_output"
    assert artifact_rows[0]["content_json"] == {
        "title": "Summary",
        "fields": ["budget", "timeline"],
    }


def test_structured_llm_executor_skips_schema_less_finalization_with_artifact_service(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = SpyGateway()
    with transaction_boundary(session_factory) as session:
        artifact_service = ArtifactService(
            ArtifactRepository(session),
            EventEmitter(EventLogRepository(session)),
        )
        executor = StructuredLlmActionExecutor(
            config_registry=registry,
            provider_gateway=spy_gateway,
            artifact_service=artifact_service,
        )
        action_definition = executor._require_action_definition("text.extract_structured_fields")
        executor._require_action_definition = lambda _action_type: replace(
            action_definition,
            output_schema_ref="kernel.schemas.missing_output_v1",
        )
        request = StructuredLlmActionRequest(
            tenant_id="tenant_demo",
            region="eu-central",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            scenario_session_id="scenario_session_demo",
            job_id="job_demo",
            workflow_id="kernel_demo.single_action_extract_v1",
            workflow_version=1,
            step_id="extract",
            action_run_id="action_run_demo",
            action_config_id="kernel_demo.extract_structured_fields_v1",
            input_payload={"source_text": "Budget and timeline details"},
        )

        response = asyncio.run(executor.execute(request, session=session))
        artifact_rows = list(
            session.execute(sa.select(artifacts_table)).mappings()
        )

    assert response.output_text == '{"title": "Summary", "fields": ["budget", "timeline"]}'
    assert response.structured_output is None
    assert "structured_output_artifact_id" not in response.metadata
    assert artifact_rows == []


def test_structured_llm_executor_raises_safe_error_and_persists_debug_artifact_after_retry_exhaustion(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = ExhaustedValidationSpyGateway()
    base_policy = registry.get_provider_policy("default_fake_provider_v1")
    assert base_policy is not None
    with transaction_boundary(session_factory) as session:
        artifact_service = ArtifactService(
            ArtifactRepository(session),
            EventEmitter(EventLogRepository(session)),
        )
        provider_call_repository = ProviderCallRepository(session)
        provider_call_repository.create(
            ProviderCallRecord(
                tenant_id="tenant_demo",
                region="eu-central",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                scenario_session_id="scenario_session_demo",
                job_id="job_demo",
                action_run_id="action_run_demo",
                workflow_id="kernel_demo.single_action_extract_v1",
                workflow_version=1,
                step_id="extract",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_v1",
                provider_policy_ref="default_fake_provider_v1",
                provider="fake",
                model="fake-json-v1",
                gateway_backend="fake",
                gateway_model="fake-json-v1",
                semantic_attempt_index=1,
                transport_attempt_index=1,
                physical_call_index=1,
            )
        )
        executor = StructuredLlmActionExecutor(
            config_registry=registry,
            provider_gateway=spy_gateway,
            artifact_service=artifact_service,
        )
        executor._require_provider_policy = lambda _provider_policy_ref: replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=2,
                ),
            ),
        )
        request = StructuredLlmActionRequest(
            tenant_id="tenant_demo",
            region="eu-central",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            scenario_session_id="scenario_session_demo",
            job_id="job_demo",
            workflow_id="kernel_demo.single_action_extract_v1",
            workflow_version=1,
            step_id="extract",
            action_run_id="action_run_demo",
            action_config_id="kernel_demo.extract_structured_fields_v1",
            input_payload={"source_text": "Budget and timeline details"},
        )

        with pytest.raises(StructuredOutputValidationError) as exc_info:
            asyncio.run(executor.execute(request, session=session))
        artifact_rows = list(
            session.execute(sa.select(artifacts_table)).mappings()
        )

    assert exc_info.value.code == STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE
    assert str(exc_info.value) == STRUCTURED_OUTPUT_VALIDATION_SAFE_MESSAGE
    assert "not-json" not in str(exc_info.value)
    assert [gateway_request.semantic_attempt_index for gateway_request in spy_gateway.requests] == [
        1,
        2,
    ]
    assert len(artifact_rows) == 1
    assert artifact_rows[0]["artifact_type"] == "structured_output_debug_raw"
    assert artifact_rows[0]["content_text"] == "not-json"
    assert artifact_rows[0]["metadata"]["error_code"] == STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE


def test_pydanticai_runner_reraises_non_validation_unexpected_model_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubAgent:
        def __class_getitem__(cls, _item: Any) -> type["StubAgent"]:
            return cls

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs

        def output_validator(self, fn: Any) -> Any:
            return fn

        async def run(self, *args: Any, **kwargs: Any) -> Any:
            deps = kwargs["deps"]
            deps.last_response = ProviderResponse(
                provider_policy_ref=deps.request.provider_policy_ref,
                provider="fake",
                model="fake-json-v1",
                output_text="transient-failure",
                status=ProviderCallStatus.succeeded,
            )
            raise UnexpectedModelBehavior("transport-independent model failure")

    monkeypatch.setattr(
        "anytoolai_platform_actions.structured_llm.pydanticai_runner.Agent",
        StubAgent,
    )

    async def request_executor(_request: Any) -> Any:
        raise AssertionError("request_executor should not be called when Agent is stubbed")

    runner = PydanticAIStructuredRunner()
    request = ProviderRequest(
        provider_policy_ref="default_fake_provider_v1",
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        workflow_id="wf_demo",
        workflow_version=1,
        step_id="step_1",
        action_run_id="action_run_demo",
        action_type="text.extract_structured_fields",
        action_config_id="kernel_demo.extract_structured_fields_v1",
        prompt="Prompt text",
    )

    with pytest.raises(UnexpectedModelBehavior, match="transport-independent model failure"):
        asyncio.run(
            runner.run(
                request,
                request_executor=request_executor,
                validation_max_attempts=2,
            )
        )
