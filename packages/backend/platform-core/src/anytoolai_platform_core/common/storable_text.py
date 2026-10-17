from __future__ import annotations


def is_unstorable_char(char: str) -> bool:
    """PostgreSQL text and JSONB cannot hold a NUL, and an unpaired surrogate (U+D800-U+DFFF left
    over after JSON decoding) has no UTF-8 encoding."""
    return char == "\x00" or "\ud800" <= char <= "\udfff"


def storable_text(value: str) -> str:
    """Diagnostic text with each unstorable character replaced by U+FFFD, so it can be saved."""
    return "".join("�" if is_unstorable_char(char) else char for char in value)
