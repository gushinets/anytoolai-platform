from anytoolai_platform_core.providers.gateway import ProviderRequest, ProviderResponse


class FakeProviderAdapter:
    def complete(self, request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(content='{"ok": true}', provider="fake", model=request.model)
