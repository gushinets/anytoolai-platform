from __future__ import annotations

from hashlib import sha256

_PART_SEPARATOR = "\x1f"


def digest_parts(*parts: str) -> str:
    """Join parts with a field separator byte and return their sha256 hex digest.

    \x1f (unit separator) cannot appear in any of the plain identifiers/timestamps
    this is used to hash, so it is a safe delimiter that cannot be spoofed by
    concatenation collisions (e.g. "ab" + "c" vs "a" + "bc").
    """
    return sha256(_PART_SEPARATOR.join(parts).encode("utf-8")).hexdigest()
