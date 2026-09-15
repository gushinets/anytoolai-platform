from __future__ import annotations

import asyncio
from pathlib import Path

from anytoolai_platform_actions.structured_llm.executor import StructuredLlmActionExecutor
from anytoolai_platform_core.actions.executor import ActionExecutorRequest, RunLocalActionSettings
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderModelAddressing,
    ProviderResponse,
    ReasoningEffort,
)

CONFIG_ROOT = Path(__file__).resolve().parents[4] / "configs" / "kernel"


class _RetrySpyGateway:
    def __init__(self) -> None:
        self.requests = []

    async def request(self, request, *, session):
        del session
        self.requests.append(request)
        output = (
            "not json"
            if len(self.requests) == 1
            else '{"values": {}, "missing_fields": ["deadline"]}'
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="litellm",
            model=request.policy_override.model,
            output_text=output,
            status=ProviderCallStatus.succeeded,
        )


def test_run_local_prompt_model_and_reasoning_survive_validation_retry() -> None:
    """Catches an executor retry that falls back to registry prompt/model settings."""
    registry = build_config_registry(CONFIG_ROOT)
    base_policy = registry.get_provider_policy("default_text_generation_v1")
    assert base_policy is not None
    gateway = _RetrySpyGateway()
    executor = StructuredLlmActionExecutor(config_registry=registry, provider_gateway=gateway)
    settings = RunLocalActionSettings(
        run_id="atom_lab_run_1",
        action_type="text.extract_structured_fields",
        action_config_id="kernel_demo.extract_structured_fields_live_v1",
        prompt="Edited prompt unique to this run",
        prompt_ref="kernel_demo.extract_structured_fields.v1",
        prompt_version=1,
        provider_policy=base_policy.__class__(
            **{**base_policy.__dict__, "model": "openai/gpt-5.4-mini", "fallback_policy": None}
        ),
        model_id="openai/gpt-5.4-mini",
        reasoning_effort=ReasoningEffort.high,
    )
    request = ActionExecutorRequest(
        tenant_id="tenant",
        region="region",
        product_id="kernel_demo",
        frontend_id="kernel_demo_web",
        scenario_session_id="scenario",
        job_id="job",
        workflow_id="kernel_demo.atom_lab_a01_v1",
        workflow_version=1,
        step_id="run_atom",
        action_run_id="action",
        action_type=settings.action_type,
        action_config_id=settings.action_config_id,
        input_payload={"source_text": "unique input", "fields": []},
        run_local_settings=settings,
    )

    asyncio.run(executor.execute(request, session=object()))

    assert len(gateway.requests) == 2
    for provider_request in gateway.requests:
        assert provider_request.prompt.startswith("Edited prompt unique to this run")
        assert "unique input" in provider_request.prompt
        assert provider_request.policy_override.model == "openai/gpt-5.4-mini"
        assert provider_request.model_addressing is ProviderModelAddressing.direct
        assert provider_request.reasoning_effort is ReasoningEffort.high
