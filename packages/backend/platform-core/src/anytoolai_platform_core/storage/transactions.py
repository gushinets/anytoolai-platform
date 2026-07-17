from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import IntEnum

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

RollbackRecoveryCallback = Callable[[sessionmaker[Session]], None]
_ROLLBACK_CALLBACKS_KEY = "rollback_recovery_callbacks"
_ROLLBACK_CALLBACK_ORDER_KEY = "rollback_recovery_callback_order"


class RollbackRecoveryPhase(IntEnum):
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


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def register_rollback_recovery_callback(
    session: Session,
    callback: RollbackRecoveryCallback,
    *,
    phase: RollbackRecoveryPhase,
) -> None:
    callbacks = session.info.setdefault(_ROLLBACK_CALLBACKS_KEY, [])
    order = int(session.info.get(_ROLLBACK_CALLBACK_ORDER_KEY, 0))
    session.info[_ROLLBACK_CALLBACK_ORDER_KEY] = order + 1
    callbacks.append(
        RegisteredRollbackRecoveryCallback(
            phase=phase,
            order=order,
            callback=callback,
        )
    )


@contextmanager
def transaction_boundary(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        try:
            with session.begin():
                yield session
        except BaseException as exc:
            for registered_callback in _pop_rollback_recovery_callbacks(session):
                try:
                    registered_callback.callback(_independent_session_factory(session))
                except Exception as recovery_exc:  # pragma: no cover - defensive
                    exc.add_note(
                        "rollback recovery callback failed: "
                        f"{type(recovery_exc).__name__}: {recovery_exc}"
                    )
            raise
    finally:
        session.close()


def _pop_rollback_recovery_callbacks(
    session: Session,
) -> list[RegisteredRollbackRecoveryCallback]:
    callbacks = session.info.pop(_ROLLBACK_CALLBACKS_KEY, [])
    session.info.pop(_ROLLBACK_CALLBACK_ORDER_KEY, None)
    return sorted(
        callbacks,
        key=lambda callback: (callback.phase, callback.order),
    )


def _independent_session_factory(session: Session) -> sessionmaker[Session]:
    bind = session.get_bind()
    engine = bind.engine if isinstance(bind, Connection) else bind
    return build_session_factory(engine)
