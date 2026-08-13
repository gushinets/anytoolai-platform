from __future__ import annotations

from typing import Any

from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


class SynthesizeAngleSecondaryOutOfOptionsThenValidAdapter:
    """`angle` is always in-options; the first reply's `secondary_angle` violates the
    caller's options-membership cross-validation rule, second is compliant."""

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        output_text = (
            '{"angle": "Lead with urgency", "rationale": "r", '
            '"secondary_angle": "Not one of the offered options"}'
            if self.call_count == 1
            else '{"angle": "Lead with urgency", "rationale": "r", '
            '"secondary_angle": "Anchor on budget"}'
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )
