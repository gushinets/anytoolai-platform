from __future__ import annotations

from typing import Any


class AlwaysFailFakeAdapter:
    async def complete(self, request: Any) -> Any:
        del request
        raise RuntimeError("provider exploded with secret_token=abc123")
