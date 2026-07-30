from __future__ import annotations

from anytoolai_platform_core.providers.models import ResolvedProviderRequest


class ProviderGatewayExecutionError(RuntimeError):
    def __init__(
        self,
        *,
        provider_policy_ref: str,
        provider: str,
        model: str,
        error_code: str,
        error_type: str,
        message: str,
        resolved_request: ResolvedProviderRequest | None = None,
        failure_kind: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_policy_ref = provider_policy_ref
        self.provider = provider
        self.model = model
        self.error_code = error_code
        self.error_type = error_type
        self.message = message
        self.resolved_request = resolved_request
        self.failure_kind = failure_kind