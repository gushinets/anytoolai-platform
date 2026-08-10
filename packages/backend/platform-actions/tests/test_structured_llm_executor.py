from __future__ import annotations

import asyncio
from dataclasses import replace
import tomllib
from pathlib import Path
from typing import Any, Iterator

import pytest
import sqlalchemy as sa

from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.gateway import (
    ProviderGateway,
    ProviderGatewayExecutionError,
)
from anytoolai_platform_core.providers.models import ProviderCallRecord
from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse
from anytoolai_platform_core.providers.models import ProviderRequest
from anytoolai_platform_core.providers.models import (
    ProviderPolicy,
    ProviderRetryHardLimits,
    ProviderRetryPolicy,
    ProviderTransportRetryPolicy,
    ProviderValidationRetryPolicy,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import artifacts_table, provider_calls_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.structured_output.errors import (
    STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE,
    STRUCTURED_OUTPUT_VALIDATION_SAFE_MESSAGE,
    StructuredOutputValidationError,
)
from anytoolai_platform_actions.structured_llm.cross_validation import (
    ComposeReplyCrossValidator,
    DetectIssuesByTaxonomyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
)
from anytoolai_platform_actions.structured_llm.executor import (
    StructuredLlmActionExecutor,
    StructuredLlmActionRequest,
)
from anytoolai_platform_actions.structured_llm import pydanticai_runner
from anytoolai_platform_actions.structured_llm.pydanticai_runner import (
    PydanticAIStructuredRunner,
)
from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
PACKAGE_ROOT = REPO_ROOT / "packages" / "backend" / "platform-actions"
pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_platform_actions_test",
        skip_reason="PostgreSQL platform actions coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


class _FixedResponseSpyGateway:
    """Every request receives the same output_text."""

    def __init__(self, output_text: str) -> None:
        self._output_text = output_text
        self.requests = []
        self.sessions = []

    async def request(self, request, *, session):
        self.requests.append(request)
        self.sessions.append(session)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text=self._output_text,
            status=ProviderCallStatus.succeeded,
        )


class _TwoAttemptSpyGateway:
    """The first request receives first_output_text; every later request receives
    second_output_text."""

    def __init__(self, first_output_text: str, second_output_text: str) -> None:
        self._first_output_text = first_output_text
        self._second_output_text = second_output_text
        self.requests = []
        self.sessions = []

    async def request(self, request, *, session):
        self.requests.append(request)
        self.sessions.append(session)
        output_text = (
            self._first_output_text if len(self.requests) == 1 else self._second_output_text
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text=output_text,
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
    spy_gateway = _FixedResponseSpyGateway(
        '{"values": {"budget": "5000", "timeline": "Q1"}, "missing_fields": []}'
    )
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

    assert response.structured_output == {
        "values": {"budget": "5000", "timeline": "Q1"},
        "missing_fields": [],
    }
    assert response.provider_call is not None
    assert response.provider_call.provider == "fake"
    assert response.provider_call.model == "fake-json-v1"
    assert response.provider_call.provider_policy_ref == "default_fake_provider_v1"
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
    spy_gateway = _TwoAttemptSpyGateway(
        "not-json",
        '{"values": {"budget": "5000", "timeline": "Q1"}, "missing_fields": []}',
    )
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

    assert response.structured_output == {
        "values": {"budget": "5000", "timeline": "Q1"},
        "missing_fields": [],
    }
    assert response.provider_call is not None
    assert spy_gateway.sessions == [session, session]
    assert [gateway_request.semantic_attempt_index for gateway_request in spy_gateway.requests] == [
        1,
        2,
    ]
    assert {gateway_request.action_run_id for gateway_request in spy_gateway.requests} == {
        "action_run_demo"
    }


def test_structured_llm_executor_retries_compose_reply_on_cross_validation_failure() -> None:
    """A07: caller-supplied constraints.max_length is enforced via cross-validation (the
    static output schema only bounds text to a fixed maxLength, not the per-call limit), and
    a violation must get the same semantic retry as a static schema mismatch."""
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _TwoAttemptSpyGateway(
        '{"text": "This reply is far longer than the ten character limit."}',
        '{"text": "Short."}',
    )
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=spy_gateway,
        output_cross_validators={
            "text.compose_reply": ComposeReplyCrossValidator(),
        },
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
        workflow_id="kernel_demo.compose_reply_v1",
        workflow_version=1,
        step_id="compose_reply",
        action_run_id="action_run_demo",
        action_type="text.compose_reply",
        action_config_id="kernel_demo.compose_reply_v1",
        input_payload={
            "situation": "The client asked for a status update on the project.",
            "intent": "Reassure the client and confirm the new delivery date.",
            "tone": "warm",
            "constraints": {"max_length": 10},
        },
    )
    session = object()

    response = asyncio.run(executor.execute(request, session=session))

    assert response.structured_output == {"text": "Short."}
    assert [gateway_request.semantic_attempt_index for gateway_request in spy_gateway.requests] == [
        1,
        2,
    ]


def test_structured_llm_executor_retries_on_cross_validation_failure() -> None:
    """ANY-251 regression: cross-validation failures must get the same semantic
    retries as static schema mismatches, not just a single unretried check."""
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _TwoAttemptSpyGateway(
        '{"issues": [{"category": "not_in_taxonomy", '
        '"description": "d", "severity": "high"}]}',
        '{"issues": [{"category": "timeline", '
        '"description": "d", "severity": "high"}]}',
    )
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=spy_gateway,
        output_cross_validators={
            "text.detect_issues_by_taxonomy": DetectIssuesByTaxonomyCrossValidator(),
        },
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
        workflow_id="kernel_demo.extract_detect_report_v1",
        workflow_version=1,
        step_id="detect_issues",
        action_run_id="action_run_demo",
        action_type="text.detect_issues_by_taxonomy",
        action_config_id="kernel_demo.detect_issues_v1",
        input_payload={"source_text": "text", "taxonomy": ["timeline"]},
    )
    session = object()

    response = asyncio.run(executor.execute(request, session=session))

    assert response.structured_output == {
        "issues": [{"category": "timeline", "description": "d", "severity": "high"}]
    }
    assert [gateway_request.semantic_attempt_index for gateway_request in spy_gateway.requests] == [
        1,
        2,
    ]


def test_structured_llm_executor_retries_on_invalid_date_with_actionable_feedback() -> None:
    """ANY-251 regression: a non-ISO `date` field value must be rejected and retried, and
    the retry prompt must carry the specific field-level reason (not just the generic safe
    message), so the model can self-correct."""
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _TwoAttemptSpyGateway(
        '{"values": {"deadline": "next Friday"}, "missing_fields": []}',
        '{"values": {"deadline": "2026-08-14"}, "missing_fields": []}',
    )
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=spy_gateway,
        output_cross_validators={
            "text.extract_structured_fields": ExtractStructuredFieldsCrossValidator(),
        },
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
        input_payload={
            "source_text": "text",
            "fields": [
                {
                    "name": "deadline",
                    "type": "date",
                    "description": "deadline",
                    "required": False,
                }
            ],
        },
    )
    session = object()

    response = asyncio.run(executor.execute(request, session=session))

    assert response.structured_output == {
        "values": {"deadline": "2026-08-14"},
        "missing_fields": [],
    }
    assert [gateway_request.semantic_attempt_index for gateway_request in spy_gateway.requests] == [
        1,
        2,
    ]
    retry_message_texts = [
        message.content
        for message in spy_gateway.requests[1].messages
        if message.role == "user"
    ]
    assert any("field_type_mismatch:deadline" in text for text in retry_message_texts)
    assert not any(
        STRUCTURED_OUTPUT_VALIDATION_SAFE_MESSAGE in text and "field_type_mismatch" not in text
        for text in retry_message_texts
    )


def test_structured_llm_executor_finalize_cross_validation_uses_resolved_action_type() -> None:
    """ANY-251 regression: the retry loop resolves the cross-validator via
    `action_config.action_type`, but `_finalize_response` used to look it up via
    `request.action_type` instead -- a different field that direct executor callers are not
    required to keep in sync with `action_config_id`. When they diverge (here `request.action_type`
    is left at its default `""`), the exhaustion path must still re-run cross-validation with the
    validator resolved from the action config, not silently skip it and let an already-exhausted,
    taxonomy-violating response be accepted as a successful final output."""
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _FixedResponseSpyGateway(
        '{"issues": [{"category": "not_in_taxonomy", '
        '"description": "d", "severity": "high"}]}'
    )
    executor = StructuredLlmActionExecutor(
        config_registry=registry,
        provider_gateway=spy_gateway,
        output_cross_validators={
            "text.detect_issues_by_taxonomy": DetectIssuesByTaxonomyCrossValidator(),
        },
    )
    request = StructuredLlmActionRequest(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        workflow_id="kernel_demo.extract_detect_report_v1",
        workflow_version=1,
        step_id="detect_issues",
        action_run_id="action_run_demo",
        # Deliberately NOT setting action_type, unlike ActionRunner always does -- this is the
        # divergence the finding relies on.
        action_config_id="kernel_demo.detect_issues_v1",
        input_payload={"source_text": "text", "taxonomy": ["timeline"]},
    )
    session = object()

    with pytest.raises(StructuredOutputValidationError):
        asyncio.run(executor.execute(request, session=session))


def test_structured_llm_executor_raises_safe_error_when_cross_validation_never_passes(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _FixedResponseSpyGateway(
        '{"issues": [{"category": "not_in_taxonomy", '
        '"description": "d", "severity": "high"}]}'
    )
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
                workflow_id="kernel_demo.extract_detect_report_v1",
                workflow_version=1,
                step_id="detect_issues",
                action_type="text.detect_issues_by_taxonomy",
                action_config_id="kernel_demo.detect_issues_v1",
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
            output_cross_validators={
                "text.detect_issues_by_taxonomy": DetectIssuesByTaxonomyCrossValidator(),
            },
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
            workflow_id="kernel_demo.extract_detect_report_v1",
            workflow_version=1,
            step_id="detect_issues",
            action_run_id="action_run_demo",
            action_type="text.detect_issues_by_taxonomy",
            action_config_id="kernel_demo.detect_issues_v1",
            input_payload={"source_text": "text", "taxonomy": ["timeline"]},
        )

        with pytest.raises(StructuredOutputValidationError) as exc_info:
            asyncio.run(executor.execute(request, session=session))
        artifact_rows = list(session.execute(sa.select(artifacts_table)).mappings())

    assert exc_info.value.code == STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE
    assert len(spy_gateway.requests) == 2
    assert len(artifact_rows) == 1
    assert artifact_rows[0]["artifact_type"] == "structured_output_debug_raw"


def test_structured_llm_executor_finalizes_and_persists_structured_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _FixedResponseSpyGateway(
        '{"values": {"budget": "5000", "timeline": "Q1"}, "missing_fields": []}'
    )
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
        "values": {"budget": "5000", "timeline": "Q1"},
        "missing_fields": [],
    }
    assert response.provider_call is not None
    assert response.metadata["structured_output_artifact_id"].startswith("artifact_")
    assert len(artifact_rows) == 1
    assert artifact_rows[0]["artifact_type"] == "structured_output"
    assert artifact_rows[0]["content_json"] == {
        "values": {"budget": "5000", "timeline": "Q1"},
        "missing_fields": [],
    }
    # ANY-251 regression: persisted metadata must reflect the resolved action_config's
    # action_type ("text.extract_structured_fields"), not request.action_type, which this
    # request deliberately leaves at its default "" -- the same divergence finding #2
    # (cross-validator lookup) already fixed for the retry/finalize path.
    assert artifact_rows[0]["metadata"]["action_type"] == "text.extract_structured_fields"


def test_structured_llm_executor_skips_schema_less_finalization_with_artifact_service(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _FixedResponseSpyGateway(
        '{"values": {"budget": "5000", "timeline": "Q1"}, "missing_fields": []}'
    )
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

    assert response.structured_output is None
    assert response.provider_call is not None
    assert "structured_output_artifact_id" not in response.metadata
    assert artifact_rows == []


def test_structured_llm_executor_raises_safe_error_and_persists_debug_artifact_after_retry_exhaustion(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = build_config_registry(CONFIG_ROOT)
    spy_gateway = _FixedResponseSpyGateway("not-json")
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


class _TransportFailureThenInvalidJsonAdapter:
    """Fails the first physical call transport-level (retryable); the transport
    retry that follows succeeds but returns invalid JSON, forcing PydanticAI to
    issue a semantic retry - which must then be blocked by the shared
    action-wide physical-call budget instead of getting a fresh one.
    """

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        if self.call_count == 1:
            raise RuntimeError("transient provider error")
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text="not-json",
            status=ProviderCallStatus.succeeded,
        )


def _build_provider_policy_resolver(policy: ProviderPolicy) -> ProviderPolicyResolver:
    return ProviderPolicyResolver(
        ConfigRegistry(
            loaded_from=CONFIG_ROOT,
            tenants={},
            regions={},
            provider_policies={policy.provider_policy_ref: policy},
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


def test_structured_llm_executor_shares_physical_call_budget_across_validation_retries(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """E2E regression for ANY-149.

    Wires a real ``ProviderGateway`` + real ``PydanticAIStructuredRunner`` exactly
    the way ``StructuredLlmActionExecutor.execute()`` does in production, and
    combines both retry axes in one action: the first physical call fails
    transport-level and gets a transport retry (``_execute_transport_attempts``),
    that retry succeeds but returns invalid JSON, so PydanticAI issues a semantic
    retry (via ``ModelRetry``). Before the fix, that semantic retry would have
    gotten its own fresh ``max_physical_provider_calls_per_action`` budget; after
    the fix, the hard limit must fire on it immediately because the transport
    retry already spent the whole action-wide budget.
    """

    registry = build_config_registry(CONFIG_ROOT)
    adapter = _TransportFailureThenInvalidJsonAdapter()
    gateway_policy = ProviderPolicy(
        provider_policy_ref="default_fake_provider_v1",
        provider="fake",
        model="fake-json-v1",
        retry_policy=ProviderRetryPolicy(
            transport=ProviderTransportRetryPolicy(
                owner="fake_adapter",
                max_attempts=2,
                litellm_num_retries_per_attempt=0,
            ),
            validation=ProviderValidationRetryPolicy(owner="pydanticai", max_attempts=5),
            hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=2),
        ),
    )
    gateway = ProviderGateway(
        {"fake": adapter},
        _build_provider_policy_resolver(gateway_policy),
    )

    base_policy = registry.get_provider_policy("default_fake_provider_v1")
    assert base_policy is not None

    with transaction_boundary(session_factory) as session:
        executor = StructuredLlmActionExecutor(
            config_registry=registry,
            provider_gateway=gateway,
        )
        executor._require_provider_policy = lambda _provider_policy_ref: replace(
            base_policy,
            retry_policy=replace(
                base_policy.retry_policy,
                validation=ProviderValidationRetryPolicy(
                    owner=base_policy.retry_policy.validation.owner,
                    max_attempts=5,
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

        with pytest.raises(ProviderGatewayExecutionError) as exc_info:
            asyncio.run(executor.execute(request, session=session))
        rows = list(
            session.execute(
                sa.select(provider_calls_table).order_by(
                    provider_calls_table.c.physical_call_index
                )
            ).mappings()
        )

    assert exc_info.value.error_code == "provider_physical_call_limit_exceeded"
    # Adapter is invoked exactly twice: the failing transport attempt and the
    # transport retry that succeeds with invalid JSON. The blocked semantic
    # retry must never reach the adapter at all.
    assert adapter.call_count == 2
    assert len(rows) == 2
    assert [row["physical_call_index"] for row in rows] == [1, 2]
    # Both persisted physical calls belong to the SAME semantic attempt (the
    # transport retry happens inside it); the hard limit fires on the next
    # semantic attempt before any physical call - and therefore any row - for
    # it is created.
    assert [row["semantic_attempt_index"] for row in rows] == [1, 1]
    assert [row["transport_attempt_index"] for row in rows] == [1, 2]
    assert rows[0]["status"] == ProviderCallStatus.failed
    assert rows[1]["status"] == ProviderCallStatus.succeeded
    assert rows[0]["error_code"] == "provider_request_failed"


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
            raise pydanticai_runner.UnexpectedModelBehavior(
                "transport-independent model failure"
            )

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

    with pytest.raises(
        pydanticai_runner.UnexpectedModelBehavior,
        match="transport-independent model failure",
    ):
        asyncio.run(
            runner.run(
                request,
                request_executor=request_executor,
                validation_max_attempts=2,
            )
        )
