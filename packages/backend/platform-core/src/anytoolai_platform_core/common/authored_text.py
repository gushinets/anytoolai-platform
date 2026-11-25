"""Test whether a string contains authored content without changing its spelling."""

import re

# Unicode 17.0: White_Space, Cc, Cf and Default_Ignorable_Code_Point.
_AUTHORED_TEXT = re.compile(
    r"[^"
    r"\u0000-\u0020\u007f-\u00a0\u00ad\u034f\u0600-\u0605"
    r"\u061c\u06dd\u070f\u0890-\u0891\u08e2"
    r"\u115f-\u1160\u1680\u17b4-\u17b5\u180b-\u180f\u2000-\u200f"
    r"\u2028-\u202f\u205f-\u206f\u3000\u3164\ufe00-\ufe0f"
    r"\ufeff\uffa0\ufff0-\ufffb\U000110bd\U000110cd"
    r"\U00013430-\U0001343f\U0001bca0-\U0001bca3\U0001d173-\U0001d17a\U000e0000-\U000e0fff"
    r"]"
)


def has_authored_text(value: str) -> bool:
    return _AUTHORED_TEXT.search(value) is not None
