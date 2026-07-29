from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError


def is_expected_unique_violation(
    error: IntegrityError,
    *,
    constraint_name: str,
    table_name: str,
    columns: Sequence[str],
) -> bool:
    """Classify whether an IntegrityError is the specific unique-constraint conflict
    an insert-or-select caller is prepared to recover from, across both dialects this
    repo supports.

    On PostgreSQL, ``error.orig.diag.constraint_name`` names the violated constraint
    directly. SQLite's driver exposes no such structured diagnostics, so this falls
    back to parsing "UNIQUE constraint failed: <table>.<col>, ..." out of the raw
    driver message and checking every expected column is named -- a real column-name
    match, not just a generic "some unique constraint failed" signal, so a coincidental
    unrelated conflict on the same table is not misclassified as this one.
    """
    constraint_from_diag = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    if constraint_from_diag == constraint_name:
        return True

    message = str(error.orig)
    if constraint_name in message:
        return True
    if "UNIQUE constraint failed" not in message:
        return False
    return all(f"{table_name}.{column}" in message for column in columns)
