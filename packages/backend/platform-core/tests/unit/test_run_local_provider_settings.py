from __future__ import annotations

import asyncio

from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.providers.gateway import ProviderGateway
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderModelAddressing,
    ProviderPolicy,
    ProviderRequest,
    ProviderResponse,
    ProviderRetryHardLimits,
    ProviderRetryPolicy,
    ProviderTransportRetryPolicy,
    ProviderValidationRetryPolicy,
    ReasoningEffort,
)
from anytoolai_platform_core.providers.policies import ProviderPolicyResolver


class _MemoryRepository:
    def create(self, record):
        return record

    def update(self, record):
        return record


class _RecordingAdapter:
    def __init__(self) -> None:
        self.requests = []

    async def complete(self, request):
        self.requests.append(request)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text='{"ok": true}',
            status=ProviderCallStatus.succeeded,
        )


def _policy(*, model: str) -> ProviderPolicy:
    return ProviderPolicy(
        provider_policy_ref="default_text_generation_v1",
        provider="litellm",
        model=model,
        temperature=1.0,
        timeout_seconds=60,
        retry_policy=ProviderRetryPolicy(
            transport=ProviderTransportRetryPolicy(owner="litellm", max_attempts=2),
            validation=ProviderValidationRetryPolicy(owner="pydanticai", max_attempts=2),
            hard_limits=ProviderRetryHardLimits(max_physical_provider_calls_per_action=4),
        ),
    )


def test_gateway_uses_immutable_run_policy_model_and_reasoning() -> None:
    """Catches re-resolving the default alias after a lab snapshot was accepted."""
    base_policy = _policy(model="anytoolai.default_text")
    local_policy = _policy(model="openai/gpt-5.4-mini")
    registry = ConfigRegistry(
        loaded_from=None,
        tenants={},
        regions={},
        provider_policies={base_policy.provider_policy_ref: base_policy},
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
    adapter = _RecordingAdapter()
    gateway = ProviderGateway(
        {"litellm": adapter},
        policy_resolver=ProviderPolicyResolver(registry),
        provider_call_repository=_MemoryRepository(),
    )
    request = ProviderRequest(
        provider_policy_ref=base_policy.provider_policy_ref,
        tenant_id="tenant",
        region="region",
        product_id="kernel_demo",
        frontend_id="kernel_demo_web",
        scenario_session_id="scenario",
        job_id="job",
        workflow_id="workflow",
        workflow_version=1,
        step_id="run_atom",
        action_run_id="action",
        action_type="text.extract_structured_fields",
        action_config_id="config",
        prompt="edited prompt",
        policy_override=local_policy,
        model_addressing=ProviderModelAddressing.direct,
        reasoning_effort=ReasoningEffort.high,
    )

    asyncio.run(gateway.request(request))

    assert len(adapter.requests) == 1
    resolved = adapter.requests[0]
    assert resolved.model == "openai/gpt-5.4-mini"
    assert resolved.model_addressing is ProviderModelAddressing.direct
    assert resolved.reasoning_effort is ReasoningEffort.high
