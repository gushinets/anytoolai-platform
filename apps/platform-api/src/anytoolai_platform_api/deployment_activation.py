from pathlib import Path


def deployment_marker_matches(marker: Path, activation_name: str) -> bool:
    """Return whether the activation marker names this candidate.

    A missing or unreadable marker does not match. Callers treat that as not active,
    including while the operator has not published the marker yet.
    """
    try:
        selected = marker.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return False
    return selected == activation_name
