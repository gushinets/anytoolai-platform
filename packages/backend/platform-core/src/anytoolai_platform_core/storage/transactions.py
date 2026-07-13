from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

RollbackRecoveryCallback = Callable[[sessionmaker[Session]], None]
_ROLLBACK_CALLBACKS_KEY = "rollback_recovery_callbacks"


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False, future=True)


def register_rollback_recovery_callback(
    session: Session,
    callback: RollbackRecoveryCallback,
) -> None:
    callbacks = session.info.setdefault(_ROLLBACK_CALLBACKS_KEY, [])
    callbacks.append(callback)


@contextmanager
def transaction_boundary(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        try:
            with session.begin():
                yield session
        except BaseException as exc:
            for callback in _pop_rollback_recovery_callbacks(session):
                try:
                    callback(_independent_session_factory(session))
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
) -> list[RollbackRecoveryCallback]:
    callbacks = session.info.pop(_ROLLBACK_CALLBACKS_KEY, [])
    return list(callbacks)


def _independent_session_factory(session: Session) -> sessionmaker[Session]:
    bind = session.get_bind()
    engine = bind.engine if isinstance(bind, Connection) else bind
    return build_session_factory(engine)
