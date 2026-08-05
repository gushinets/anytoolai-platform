from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

SessionFactory = sessionmaker[Session]
RollbackRecoveryCallback = Callable[[SessionFactory], None]
TransactionCleanupCallback = Callable[[Session], None]
_ROLLBACK_CALLBACKS_KEY = "rollback_recovery_callbacks"
_ROLLBACK_CALLBACK_ORDER_KEY = "rollback_recovery_callback_order"
_CLEANUP_CALLBACKS_KEY = "transaction_cleanup_callbacks"
_CLEANUP_CALLBACK_ORDER_KEY = "transaction_cleanup_callback_order"


class RollbackRecoveryPhase(IntEnum):
    quota_exhaustion = 5
    artifact_rows = 10
    provider_rows = 20
    action_rows = 30
    workflow_rows = 40
    workflow_events = 50
    action_events = 60
    provider_events = 70
    artifact_events = 80


@dataclass(frozen=True)
class RegisteredRollbackRecoveryCallback:
    phase: RollbackRecoveryPhase
    order: int
    callback: RollbackRecoveryCallback
    critical: bool = False


@dataclass(frozen=True)
class RegisteredTransactionCleanupCallback:
    order: int
    callback: TransactionCleanupCallback
    critical: bool = False


def build_session_factory(engine: Engine) -> SessionFactory:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def register_rollback_recovery_callback(
    session: Session,
    callback: RollbackRecoveryCallback,
    *,
    phase: RollbackRecoveryPhase,
    critical: bool = False,
) -> None:
    callbacks = session.info.setdefault(_ROLLBACK_CALLBACKS_KEY, [])
    order = int(session.info.get(_ROLLBACK_CALLBACK_ORDER_KEY, 0))
    session.info[_ROLLBACK_CALLBACK_ORDER_KEY] = order + 1
    callbacks.append(
        RegisteredRollbackRecoveryCallback(
            phase=phase,
            order=order,
            callback=callback,
            critical=critical,
        )
    )


def register_transaction_cleanup_callback(
    session: Session,
    callback: TransactionCleanupCallback,
    *,
    critical: bool = False,
) -> None:
    callbacks = session.info.setdefault(_CLEANUP_CALLBACKS_KEY, [])
    order = int(session.info.get(_CLEANUP_CALLBACK_ORDER_KEY, 0))
    session.info[_CLEANUP_CALLBACK_ORDER_KEY] = order + 1
    callbacks.append(
        RegisteredTransactionCleanupCallback(
            order=order,
            callback=callback,
            critical=critical,
        )
    )


@contextmanager
def transaction_boundary(session_factory: SessionFactory) -> Iterator[Session]:
    bind = _bind_from_session_factory(session_factory)
    connection = bind if isinstance(bind, Connection) else bind.connect()
    owns_connection = not isinstance(bind, Connection)
    session = session_factory(bind=connection)
    try:
        try:
            with session.begin():
                yield session
        except BaseException as exc:
            active_exc = exc
            recovery_failed = False
            try:
                _run_rollback_recovery_callbacks(session, exc)
            except BaseException as recovery_exc:
                active_exc = recovery_exc
                recovery_failed = True
                raise
            finally:
                _run_transaction_cleanup_callbacks(
                    session,
                    active_exc,
                    suppress_critical=recovery_failed,
                )
            raise
        _run_transaction_cleanup_callbacks(session, None)
    finally:
        session.close()
        if owns_connection:
            connection.close()


def _run_rollback_recovery_callbacks(session: Session, exc: BaseException) -> None:
    for registered_callback in _pop_rollback_recovery_callbacks(session):
        try:
            registered_callback.callback(_independent_session_factory(session))
        except Exception as recovery_exc:  # pragma: no cover - defensive
            if registered_callback.critical:
                raise RuntimeError(
                    "critical rollback recovery callback failed"
                ) from recovery_exc
            exc.add_note(
                "rollback recovery callback failed: "
                f"{type(recovery_exc).__name__}: {recovery_exc}"
            )


def _run_transaction_cleanup_callbacks(
    session: Session,
    exc: BaseException | None,
    *,
    suppress_critical: bool = False,
) -> None:
    for registered_callback in _pop_transaction_cleanup_callbacks(session):
        try:
            registered_callback.callback(session)
        except Exception as cleanup_exc:  # pragma: no cover - defensive
            if registered_callback.critical and not suppress_critical:
                raise RuntimeError(
                    "critical transaction cleanup callback failed"
                ) from cleanup_exc
            if exc is not None:
                exc.add_note(
                    "transaction cleanup callback failed: "
                    f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                )
                continue
            raise


def _pop_rollback_recovery_callbacks(
    session: Session,
) -> list[RegisteredRollbackRecoveryCallback]:
    callbacks = session.info.pop(_ROLLBACK_CALLBACKS_KEY, [])
    session.info.pop(_ROLLBACK_CALLBACK_ORDER_KEY, None)
    return sorted(
        callbacks,
        key=lambda callback: (callback.phase, callback.order),
    )


def _pop_transaction_cleanup_callbacks(
    session: Session,
) -> list[RegisteredTransactionCleanupCallback]:
    callbacks = session.info.pop(_CLEANUP_CALLBACKS_KEY, [])
    session.info.pop(_CLEANUP_CALLBACK_ORDER_KEY, None)
    return sorted(callbacks, key=lambda callback: callback.order)


def _engine_from_bind(bind: Connection | Engine) -> Engine:
    return bind.engine if isinstance(bind, Connection) else bind


def engine_from_session_factory(session_factory: SessionFactory) -> Engine:
    """Recover the bound `Engine` from a `sessionmaker`.

    Composition code (and nearly every test) is only ever handed a
    `session_factory`, never the underlying `Engine` directly -- but per-job
    features like a dedicated advisory-lock connection need a raw `Engine` to
    open their own connections outside the ORM's pool.
    """
    session = session_factory()
    try:
        return _engine_from_bind(session.get_bind())
    finally:
        session.close()


def _independent_session_factory(session: Session) -> SessionFactory:
    return sessionmaker(
        bind=session.get_bind(),
        expire_on_commit=False,
        autoflush=False,
        future=True,
    )


def _bind_from_session_factory(session_factory: SessionFactory) -> Connection | Engine:
    bind = session_factory.kw.get("bind")
    if bind is not None:
        return bind
    session = session_factory()
    try:
        return session.get_bind()
    finally:
        session.close()
