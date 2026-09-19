"""Bounded display of final answer text, never provider reasoning or arbitrary metadata."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

ATOM_LAB_DEBUG_MAX_BYTES = 8 * 1024
ATOM_LAB_DEBUG_VERSION = 1
_ANSI_ESCAPE = re.compile(
    r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
)
_JSON_ESCAPE = re.compile(r'\\(?:u([0-9a-fA-F]{4})|(["\\/bfnrt]))')
_JSON_SIMPLE_ESCAPES = {
    '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
}

# Invalid JSON cannot be safely traversed by key. Withhold the whole answer when it
# contains credential or reasoning-envelope markers, including malformed envelopes.
# Collapsing separators may join ordinary prose to a credential prefix, so prefix
# detection must not require a leading word boundary.
_SENSITIVE_OUTPUT = re.compile(
    r"api[\s_-]*key|private[\s_-]*key|authorization|bearer|password|credential|secret|"
    r"access[\s_-]*code|token|"
    r"sk-[a-z0-9_-]+|eyJ[a-z0-9_-]+\.[a-z0-9_-]+|"
    r"reasoning|chain[\s_-]*of[\s_-]*thought|<\s*/?\s*(?:think(?:ing)?|analysis)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class AtomLabDebugText:
    text: str
    truncated: bool
    redacted: bool


def bound_atom_lab_debug_text(raw_text: str) -> AtomLabDebugText:
    text = _strip_controls(raw_text)
    marker_text = _detection_text(raw_text)
    compact_marker_text = marker_text.replace("_", "").replace("-", "")
    if any(_SENSITIVE_OUTPUT.search(value) for value in (text, marker_text, compact_marker_text)):
        return AtomLabDebugText(text="[redacted]", truncated=False, redacted=True)
    encoded = text.encode("utf-8")
    return AtomLabDebugText(
        text=encoded[:ATOM_LAB_DEBUG_MAX_BYTES].decode("utf-8", errors="ignore"),
        truncated=len(encoded) > ATOM_LAB_DEBUG_MAX_BYTES,
        redacted=text != raw_text,
    )


def _detection_text(text: str) -> str:
    # This representation is detection-only: decode escapes even in malformed JSON,
    # then collapse separators so split credential/reasoning labels cannot evade it.
    decoded = _JSON_ESCAPE.sub(
        lambda match: (
            chr(int(match.group(1), 16))
            if match.group(1) is not None
            else _JSON_SIMPLE_ESCAPES[match.group(2)]
        ),
        text,
    )
    normalized = unicodedata.normalize("NFKC", _ANSI_ESCAPE.sub("", decoded)).casefold()
    return "".join(
        char for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("C")
    )


def _strip_controls(text: str) -> str:
    # Strip controls before marker matching so ANSI/bidi/NUL cannot split a marker.
    return "".join(
        char for char in _ANSI_ESCAPE.sub("", text)
        if char in "\n\t" or not unicodedata.category(char).startswith("C")
    )
