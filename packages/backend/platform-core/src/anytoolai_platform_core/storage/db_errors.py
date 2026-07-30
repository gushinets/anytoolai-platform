from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


def unique_constraint_columns(table: sa.Table, constraint_name: str) -> tuple[str, ...]:
    """Look up a named UniqueConstraint's column list from a table's own metadata.

    Shared by every dialect-fallback race-classifier (quotas, scenarios) that needs a
    SQLite-side column list to match against `IntegrityError` text: deriving it from
    the live constraint means it can never silently drift out of sync with the actual
    constraint definition in storage/db.py.
    """
    for constraint in table.constraints:
        if isinstance(constraint, sa.UniqueConstraint) and constraint.name == constraint_name:
            return tuple(constraint.columns.keys())
    raise LookupError(f"unique constraint not found on {table.name}: {constraint_name}")


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
