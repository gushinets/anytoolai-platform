from __future__ import annotations

from typing import Any

from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


class ScoreMultidimensionalAxesDominantMismatchThenValidAdapter:
    """First reply's `dominant_axes` disagrees with the recomputed max-score axis ids;
    second is compliant."""

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        dominant_axes = '["structure"]' if self.call_count == 1 else '["clarity"]'
        output_text = (
            '{"scores": ['
            '{"axis_id": "clarity", "score": 8, "commentary": "c"}, '
            '{"axis_id": "structure", "score": 5, "commentary": "c"}], '
            f'"dominant_axes": {dominant_axes}, "weakest_axes": ["structure"]}}'
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )
