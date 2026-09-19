from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.atom_lab.repository import AtomLabRunRepository
from anytoolai_platform_core.atom_lab.service import (
    AtomLabActiveRunLimitError,
    AtomLabDailyLimitError,
    AtomLabIdempotencyConflictError,
    AtomLabRunAdmissionRequest,
    AtomLabRunService,
    compute_atom_lab_request_hash,
)
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.providers.models import ReasoningEffort
from anytoolai_platform_core.scenarios.models import ScenarioSessionStatus
from anytoolai_platform_core.storage.db import (
    atom_lab_admission_scopes_table,
    atom_lab_runs_table,
    guest_identities_table,
    jobs_table,
    runtime_metadata,
    scenario_sessions_table,
)
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobStatus

from tests.db_support import provision_database
from tests.support.sqlite_harness import build_sqlite_runtime_engine

CONFIG_ROOT = Path(__file__).resolve().parents[5] / "configs" / "kernel"
TENANT_ID = "anytoolai"
REGION = "default"
FIRST_DAY = datetime(2026, 9, 18, 10, 0, tzinfo=UTC)


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[SessionFactory]:
    engine = build_sqlite_runtime_engine(
        tmp_path / "main.sqlite3",
        tmp_path / "platform.sqlite3",
    )
    runtime_metadata.create_all(engine)
    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


def _request(**overrides: Any) -> AtomLabRunAdmissionRequest:
    values: dict[str, Any] = {
        "tenant_id": TENANT_ID,
        "region": REGION,
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_web",
        "atom_id": "A01",
        "input_payload": {
            "source_text": "exact lab input",
            "fields": [
                {
                    "name": "deadline",
                    "type": "string",
                    "description": "Project deadline.",
                    "required": True,
                }
            ],
            "strict": False,
        },
        "prompt": "Edited prompt",
        "model_id": "openai/gpt-5.4-mini",
        "reasoning_effort": ReasoningEffort.high,
        "capability_snapshot_id": "capability_snapshot_1",
        "capability_provenance": {"source": "fixture", "version": "1"},
        "idempotency_key": "admission-key-1",
    }
    values.update(overrides)
    return AtomLabRunAdmissionRequest(**values)


def _service(
    session: sa.orm.Session,
    *,
    now: datetime | Callable[[], datetime] = FIRST_DAY,
    daily_limit: int = 100,
    active_limit: int = 1,
) -> AtomLabRunService:
    clock = now if callable(now) else lambda: now
    return AtomLabRunService(
        session=session,
        config_registry=build_config_registry(CONFIG_ROOT),
        now=clock,
        daily_limit=daily_limit,
        active_limit=active_limit,
    )


def _table_counts(session_factory: SessionFactory) -> tuple[int, ...]:
    with transaction_boundary(session_factory) as session:
        return tuple(
            int(session.execute(sa.select(sa.func.count()).select_from(table)).scalar_one())
            for table in (
                guest_identities_table,
                scenario_sessions_table,
                jobs_table,
                atom_lab_runs_table,
                atom_lab_admission_scopes_table,
            )
        )


def test_request_hash_is_canonical_for_nested_json_key_order() -> None:
    """Catches idempotency hashes that depend on JSON object insertion order."""
    first = _request(
        input_payload={"z": [{"b": 2, "a": 1}], "a": {"d": 4, "c": 3}},
        capability_provenance={"right": 2, "left": {"y": 2, "x": 1}},
    )
    reordered = _request(
        input_payload={"a": {"c": 3, "d": 4}, "z": [{"a": 1, "b": 2}]},
        capability_provenance={"left": {"x": 1, "y": 2}, "right": 2},
    )

    assert compute_atom_lab_request_hash(first) == compute_atom_lab_request_hash(reordered)
    assert compute_atom_lab_request_hash(first) != compute_atom_lab_request_hash(
        replace(reordered, reasoning_effort=ReasoningEffort.low)
    )


def test_replay_returns_original_run_before_validation_and_limits(
    session_factory: SessionFactory,
) -> None:
    """Catches retries being revalidated, recounted, or assigned a new guest/job."""
    request = _request()
    with transaction_boundary(session_factory) as session:
        first = _service(session).start(request, validate=lambda: None)

    validation_calls = 0

    def fail_if_revalidated() -> None:
        nonlocal validation_calls
        validation_calls += 1
        raise AssertionError("accepted replay must skip current validation")

    with transaction_boundary(session_factory) as session:
        replay = _service(
            session,
            daily_limit=1,
            active_limit=1,
        ).start(request, validate=fail_if_revalidated)
        stored = session.execute(
            sa.select(atom_lab_runs_table).where(atom_lab_runs_table.c.id == replay.run_id)
        ).mappings().one()
        admission = session.execute(sa.select(atom_lab_admission_scopes_table)).mappings().one()

    assert replay == replace(first, replayed=True)
    assert validation_calls == 0
    assert stored["guest_id"] == first.guest_id
    assert admission["accepted_count"] == 1
    assert _table_counts(session_factory) == (1, 1, 1, 1, 1)


def test_same_key_with_different_canonical_request_conflicts_without_writes(
    session_factory: SessionFactory,
) -> None:
    """Catches a reused key silently returning a run for a different request."""
    request = _request()
    with transaction_boundary(session_factory) as session:
        _service(session).start(request, validate=lambda: None)

    with (
        pytest.raises(AtomLabIdempotencyConflictError),
        transaction_boundary(session_factory) as session,
    ):
        _service(session).start(
            replace(request, prompt="Different prompt"),
            validate=lambda: None,
        )

    assert _table_counts(session_factory) == (1, 1, 1, 1, 1)


def test_active_limit_rejects_new_key_before_creating_runtime_rows(
    session_factory: SessionFactory,
) -> None:
    """Catches an active created/running job admitting another paid run."""
    with transaction_boundary(session_factory) as session:
        _service(session).start(
            _request(),
            validate=lambda: None,
        )

    with (
        pytest.raises(AtomLabActiveRunLimitError),
        transaction_boundary(session_factory) as session,
    ):
        _service(session).start(
            _request(idempotency_key="admission-key-2"),
            validate=lambda: None,
        )

    assert _table_counts(session_factory) == (1, 1, 1, 1, 1)


def test_terminal_session_releases_active_slot_while_job_remains_created(
    session_factory: SessionFactory,
) -> None:
    """Catches a terminal session being counted active because its job is still created."""
    with transaction_boundary(session_factory) as session:
        first = _service(session, active_limit=1).start(
            _request(),
            validate=lambda: None,
        )
        session.execute(
            sa.update(scenario_sessions_table)
            .where(scenario_sessions_table.c.id == first.scenario_session_id)
            .values(status=ScenarioSessionStatus.expired, completed_at=FIRST_DAY)
        )

    with transaction_boundary(session_factory) as session:
        first_job_status = session.execute(
            sa.select(jobs_table.c.status).where(jobs_table.c.id == first.job_id)
        ).scalar_one()
        second = _service(session, active_limit=1).start(
            _request(idempotency_key="admission-key-after-expired-session"),
            validate=lambda: None,
        )

    assert first_job_status is JobStatus.created
    assert second.run_id != first.run_id
    assert _table_counts(session_factory) == (2, 2, 2, 2, 1)


def test_daily_counter_rolls_over_on_the_next_utc_date(
    session_factory: SessionFactory,
) -> None:
    """Catches yesterday's accepted count blocking a new UTC day."""
    first_request = _request()
    with transaction_boundary(session_factory) as session:
        first = _service(session, daily_limit=1).start(
            first_request,
            validate=lambda: None,
        )
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == first.job_id)
            .values(status=JobStatus.succeeded, completed_at=FIRST_DAY)
        )

    with (
        pytest.raises(AtomLabDailyLimitError),
        transaction_boundary(session_factory) as session,
    ):
        _service(session, daily_limit=1).start(
            _request(idempotency_key="same-day-key"),
            validate=lambda: None,
        )

    next_day = datetime(2026, 9, 19, 0, 0, tzinfo=UTC)
    with transaction_boundary(session_factory) as session:
        second = _service(
            session,
            now=next_day,
            daily_limit=1,
        ).start(
            _request(idempotency_key="next-day-key"),
            validate=lambda: None,
        )
        admission = session.execute(sa.select(atom_lab_admission_scopes_table)).mappings().one()

    assert second.run_id != first.run_id
    assert admission["accepted_on"] == date(2026, 9, 19)
    assert admission["accepted_count"] == 1
    assert _table_counts(session_factory) == (2, 2, 2, 2, 1)


def test_delayed_older_replay_cannot_rewind_newer_utc_day_count(
    session_factory: SessionFactory,
) -> None:
    """Catches a pre-midnight clock sample rewinding a scope locked after midnight."""
    first_request = _request(idempotency_key="older-day-key")
    with transaction_boundary(session_factory) as session:
        first = _service(session, daily_limit=1).start(
            first_request,
            validate=lambda: None,
        )
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == first.job_id)
            .values(status=JobStatus.succeeded, completed_at=FIRST_DAY)
        )

    next_day = datetime(2026, 9, 19, 0, 0, tzinfo=UTC)
    with transaction_boundary(session_factory) as session:
        second = _service(session, now=next_day, daily_limit=1).start(
            _request(idempotency_key="newer-day-key"),
            validate=lambda: None,
        )
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == second.job_id)
            .values(status=JobStatus.succeeded, completed_at=next_day)
        )

    samples: list[datetime] = []
    delayed_samples = iter((FIRST_DAY, next_day))

    def delayed_clock() -> datetime:
        sampled = next(delayed_samples)
        samples.append(sampled)
        return sampled

    with transaction_boundary(session_factory) as session:
        replay = _service(
            session,
            now=delayed_clock,
            daily_limit=1,
        ).start(first_request, validate=lambda: None)

    assert replay.replayed is True
    assert samples == [FIRST_DAY, next_day]

    with (
        pytest.raises(AtomLabDailyLimitError),
        transaction_boundary(session_factory) as session,
    ):
        _service(session, now=next_day, daily_limit=1).start(
            _request(idempotency_key="must-still-be-limited"),
            validate=lambda: None,
        )


def test_failure_after_runtime_creation_rolls_back_all_admission_state(
    session_factory: SessionFactory,
) -> None:
    """Catches partial guest/session/job/count persistence on pre-provider failure."""
    with (
        pytest.raises(ValueError, match="prompt"),
        transaction_boundary(session_factory) as session,
    ):
        _service(session).start(
            _request(prompt="   "),
            validate=lambda: None,
        )

    assert _table_counts(session_factory) == (0, 0, 0, 0, 0)


def test_run_listing_uses_stable_created_at_and_run_id_order(
    session_factory: SessionFactory,
) -> None:
    """Catches pagination order becoming unstable for equal timestamps."""
    with transaction_boundary(session_factory) as session:
        first = _service(session).start(
            _request(idempotency_key="listing-a"),
            validate=lambda: None,
        )
        session.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == first.job_id)
            .values(status=JobStatus.succeeded, completed_at=FIRST_DAY)
        )
        second = _service(session).start(
            _request(idempotency_key="listing-b"),
            validate=lambda: None,
        )
        session.execute(
            sa.update(atom_lab_runs_table).values(created_at=FIRST_DAY)
        )
        rows = AtomLabRunRepository(session).list_in_scope(
            tenant_id=TENANT_ID,
            region=REGION,
            limit=10,
        )

    assert [row.id for row in rows] == sorted(
        [first.run_id, second.run_id],
        reverse=True,
    )


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_scope_lock_serializes_concurrent_duplicate_admission() -> None:
    """Catches two API processes admitting duplicate jobs for one new key."""
    request = _request(idempotency_key="postgres-race-key")
    with provision_database(
        database_name_prefix="anytoolai_atom_lab_admission_test",
        skip_reason="PostgreSQL Atom Lab admission race coverage",
    ) as (engine, _alembic_config, _database_url):
        factory = build_session_factory(engine)

        def admit() -> Any:
            with transaction_boundary(factory) as session:
                return _service(session).start(request, validate=lambda: None)

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _index: admit(), range(2)))

        assert {result.run_id for result in results} == {results[0].run_id}
        assert sorted(result.replayed for result in results) == [False, True]
        assert _table_counts(factory) == (1, 1, 1, 1, 1)


@pytest.mark.postgresql
@pytest.mark.slow
def test_postgresql_scope_lock_serializes_active_limit_for_distinct_requests() -> None:
    """Catches two API processes exceeding active_limit with different new keys."""
    requests = (
        _request(idempotency_key="postgres-active-race-a"),
        _request(idempotency_key="postgres-active-race-b"),
    )
    with provision_database(
        database_name_prefix="anytoolai_atom_lab_active_limit_test",
        skip_reason="PostgreSQL Atom Lab active-limit race coverage",
    ) as (engine, _alembic_config, _database_url):
        factory = build_session_factory(engine)

        def admit(request: AtomLabRunAdmissionRequest) -> Any:
            with transaction_boundary(factory) as session:
                return _service(session, active_limit=1).start(request, validate=lambda: None)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(admit, request) for request in requests]
            results: list[Any] = []
            errors: list[Exception] = []
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as exc:  # noqa: BLE001 -- assert the concurrent domain outcome.
                    errors.append(exc)

        assert len(results) == 1
        assert len(errors) == 1
        assert isinstance(errors[0], AtomLabActiveRunLimitError)
        assert errors[0].code == "lab_busy"
        assert _table_counts(factory) == (1, 1, 1, 1, 1)
        with transaction_boundary(factory) as session:
            accepted_count = session.execute(
                sa.select(atom_lab_admission_scopes_table.c.accepted_count)
            ).scalar_one()
        assert accepted_count == 1
