from __future__ import annotations

import asyncio
from typing import Any


class CancelledFakeAdapter:
    async def complete(self, request: Any) -> Any:
        del request
        raise asyncio.CancelledError()
