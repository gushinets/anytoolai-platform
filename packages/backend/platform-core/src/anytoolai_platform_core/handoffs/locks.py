from __future__ import annotations

from hashlib import sha256

import sqlalchemy as sa
from sqlalchemy.orm import Session

from anytoolai_platform_core.storage.transactions import (
    register_transaction_cleanup_callback,
)

_LOCKED_HANDOFF_KEYS = "handoff_lifecycle_advisory_lock_keys"
_LOCK_NAMESPACE = "anytoolai.handoff.lifecycle.v1"


def acquire_handoff_lifecycle_lock(session: Session, handoff_id: str) -> None:
    """Acquire a PostgreSQL session-level lifecycle lock for one handoff.

    Session-level advisory locks survive transaction rollback, which lets immediate accept hold
    terminal arbitration while rollback recovery commits the quota-failure outcome.
    """
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return

    lock_key = _handoff_lock_key(handoff_id)
    locked_keys = session.info.setdefault(_LOCKED_HANDOFF_KEYS, set())
    if lock_key in locked_keys:
        return

    session.execute(sa.text("SELECT pg_advisory_lock(:lock_key)"), {"lock_key": lock_key})
    locked_keys.add(lock_key)
    register_transaction_cleanup_callback(
        session,
        lambda cleanup_session, key=lock_key: _release_handoff_lifecycle_lock(
            cleanup_session,
            key,
        ),
        critical=True,
    )


def _release_handoff_lifecycle_lock(session: Session, lock_key: int) -> None:
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return
    try:
        unlocked = session.execute(
            sa.text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": lock_key},
        ).scalar_one()
    except BaseException:
        _invalidate_session_connection(session)
        raise
    if unlocked is not True:
        _invalidate_session_connection(session)
        raise RuntimeError(
            "handoff lifecycle advisory unlock failed: connection does not own lock"
        )


def _handoff_lock_key(handoff_id: str) -> int:
    digest = sha256(f"{_LOCK_NAMESPACE}:{handoff_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


def _invalidate_session_connection(session: Session) -> None:
    try:
        session.connection().invalidate()
    except Exception:  # pragma: no cover - best effort after invariant failure
        return
