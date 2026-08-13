from __future__ import annotations

from typing import Any

from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


class CompareAndClassifyOutOfCategoriesThenValidAdapter:
    """First verdict violates the caller's categories-membership cross-validation rule;
    second is compliant."""

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        output_text = (
            '{"verdict": "not_a_category", "confidence": 0.7, '
            '"deltas": [{"criterion_id": "tone", "status": "match", "evidence": "e"}], '
            '"rationale": "r"}'
            if self.call_count == 1
            else '{"verdict": "meets_bar", "confidence": 0.7, '
            '"deltas": [{"criterion_id": "tone", "status": "match", "evidence": "e"}], '
            '"rationale": "r"}'
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )
