from __future__ import annotations

import pytest
import sqlalchemy as sa

from anytoolai_platform_core.storage.transactions import (
    RollbackRecoveryPhase,
    build_session_factory,
    register_rollback_recovery_callback,
    register_transaction_cleanup_callback,
    transaction_boundary,
)


def test_noncritical_rollback_recovery_failure_preserves_original_exception() -> None:
    session_factory = build_session_factory(sa.create_engine("sqlite:///:memory:", future=True))

    with pytest.raises(RuntimeError, match="original failure") as error:
        with transaction_boundary(session_factory) as session:
            register_rollback_recovery_callback(
                session,
                lambda _session_factory: (_ for _ in ()).throw(
                    RuntimeError("recovery failure")
                ),
                phase=RollbackRecoveryPhase.workflow_events,
            )
            raise RuntimeError("original failure")

    assert any(
        "rollback recovery callback failed: RuntimeError: recovery failure" in note
        for note in getattr(error.value, "__notes__", [])
    )


def test_critical_rollback_recovery_failure_runs_cleanup_and_blocks_original_error() -> None:
    session_factory = build_session_factory(sa.create_engine("sqlite:///:memory:", future=True))
    cleanup_calls: list[str] = []

    with pytest.raises(RuntimeError, match="critical rollback recovery callback failed") as error:
        with transaction_boundary(session_factory) as session:
            register_transaction_cleanup_callback(
                session,
                lambda _session: cleanup_calls.append("cleanup"),
            )
            register_rollback_recovery_callback(
                session,
                lambda _session_factory: (_ for _ in ()).throw(
                    RuntimeError("recovery failure")
                ),
                phase=RollbackRecoveryPhase.quota_exhaustion,
                critical=True,
            )
            raise RuntimeError("original failure")

    assert str(error.value.__cause__) == "recovery failure"
    assert cleanup_calls == ["cleanup"]


def test_critical_cleanup_failure_blocks_original_exception_after_successful_recovery() -> None:
    session_factory = build_session_factory(sa.create_engine("sqlite:///:memory:", future=True))

    with pytest.raises(RuntimeError, match="critical transaction cleanup callback failed") as error:
        with transaction_boundary(session_factory) as session:
            register_transaction_cleanup_callback(
                session,
                lambda _session: (_ for _ in ()).throw(
                    RuntimeError("cleanup failure")
                ),
                critical=True,
            )
            register_rollback_recovery_callback(
                session,
                lambda _session_factory: None,
                phase=RollbackRecoveryPhase.quota_exhaustion,
                critical=True,
            )
            raise RuntimeError("original failure")

    assert str(error.value.__cause__) == "cleanup failure"


def test_critical_recovery_failure_preserved_when_critical_cleanup_also_fails() -> None:
    session_factory = build_session_factory(sa.create_engine("sqlite:///:memory:", future=True))

    with pytest.raises(RuntimeError, match="critical rollback recovery callback failed") as error:
        with transaction_boundary(session_factory) as session:
            register_transaction_cleanup_callback(
                session,
                lambda _session: (_ for _ in ()).throw(
                    RuntimeError("cleanup failure")
                ),
                critical=True,
            )
            register_rollback_recovery_callback(
                session,
                lambda _session_factory: (_ for _ in ()).throw(
                    RuntimeError("recovery failure")
                ),
                phase=RollbackRecoveryPhase.quota_exhaustion,
                critical=True,
            )
            raise RuntimeError("original failure")

    assert str(error.value.__cause__) == "recovery failure"
    assert any(
        "transaction cleanup callback failed: RuntimeError: cleanup failure" in note
        for note in getattr(error.value, "__notes__", [])
    )
