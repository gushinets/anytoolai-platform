from __future__ import annotations

from typing import Any

from anytoolai_platform_core.providers.models import ProviderCallStatus, ProviderResponse


class GapRewritesCountMismatchThenValidAdapter:
    """First reply returns fewer rewrites than the requested n (rewrite-count
    cross-validation violation); second reply matches n."""

    def __init__(self) -> None:
        self.call_count = 0

    async def complete(self, request: Any) -> ProviderResponse:
        self.call_count += 1
        output_text = (
            '{"rewrites": [{"text": "Only one rewrite.", "explanation": "e", '
            '"change_made": "c"}], "best_pick": 0}'
            if self.call_count == 1
            else (
                '{"rewrites": ['
                '{"text": "First rewrite.", "explanation": "e", "change_made": "c"}, '
                '{"text": "Second rewrite.", "explanation": "e", "change_made": "c"}'
                '], "best_pick": 1}'
            )
        )
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider=request.provider,
            model=request.model,
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )
