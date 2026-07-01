from __future__ import annotations

import asyncio
from dataclasses import replace
import tomllib
from pathlib import Path

from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse
from anytoolai_platform_core.providers.models import ProviderValidationRetryPolicy
from anytoolai_platform_actions.structured_llm.executor import (
    StructuredLlmActionExecutor,
    StructuredLlmActionRequest,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
PACKAGE_ROOT = REPO_ROOT / "packages" / "backend" / "platform-actions"


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
