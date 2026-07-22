from __future__ import annotations

import secrets
from dataclasses import dataclass
from hashlib import sha256

MIN_HANDOFF_TOKEN_ENTROPY_BYTES = 32


@dataclass(frozen=True)
class HandoffTokenService:
    """Generate opaque handoff capabilities and storage-safe lookup keys."""

    entropy_bytes: int = MIN_HANDOFF_TOKEN_ENTROPY_BYTES
    prefix: str = "hnd_"

    def generate(self) -> str:
        if self.entropy_bytes < MIN_HANDOFF_TOKEN_ENTROPY_BYTES:
            raise ValueError("handoff tokens require at least 256 bits of entropy")
        return self.prefix + secrets.token_urlsafe(self.entropy_bytes)

    @staticmethod
    def hash(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()
