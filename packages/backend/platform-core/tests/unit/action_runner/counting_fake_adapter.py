from __future__ import annotations

from typing import Any


class CountingFakeAdapter:
    def __init__(self, delegate: Any) -> None:
        self._delegate = delegate
        self.call_count = 0

    async def complete(self, request: Any) -> Any:
        self.call_count += 1
        return await self._delegate.complete(request)
