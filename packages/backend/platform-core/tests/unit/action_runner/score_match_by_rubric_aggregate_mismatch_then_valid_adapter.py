from __future__ import annotations

from typing import Any

from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


class ScoreMatchByRubricAggregateMismatchThenValidAdapter:
    """First reply's aggregate `score` disagrees with the rubric-weighted average of
    `criterion_scores` beyond tolerance; second is compliant."""

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        aggregate_score = 40 if self.call_count == 1 else 80
        output_text = (
            '{"criterion_scores": ['
            '{"criterion_id": "tone", "score": 90, "rationale": "r"}, '
            '{"criterion_id": "completeness", "score": 70, "rationale": "r"}], '
            f'"score": {aggregate_score}, "strengths": [], "gaps": [], '
            '"overall_rationale": "Overall summary."}'
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )
