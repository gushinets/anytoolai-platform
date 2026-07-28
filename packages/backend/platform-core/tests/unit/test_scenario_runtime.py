from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityNotFoundError
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService
from anytoolai_platform_core.scenarios.checkpoints import (
    FAILED_CHECKPOINT_ID,
    PROCESSING_CHECKPOINT_ID,
    RESULT_READY_CHECKPOINT_ID,
    resolve_checkpoint_state,
    resolve_effective_status,
)
from anytoolai_platform_core.scenarios.models import (
    ScenarioSessionRecord,
    ScenarioSessionStatus,
)
from anytoolai_platform_core.scenarios.next_actions import (
    ScenarioCheckpointConflictError,
    ScenarioCheckpointNotActionableError,
    ScenarioNextActionNotAllowedError,
)
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import (
    IdempotencyKeyConflictError,
    IdempotencyKeyInvalidError,
    ScenarioFrontendInvalidError,
    ScenarioInputInvalidError,
    ScenarioNotFoundError,
    ScenarioRuntimeService,
    ScenarioSessionService,
    compute_idempotency_request_hash,
)
from anytoolai_platform_core.storage.db import event_log_table, scenario_sessions_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "scenario-runtime-main.sqlite3"
    platform_db = tmp_path / "scenario-runtime-platform.sqlite3"
    engine = sa.create_engine(_sqlite_url(main_db), future=True)

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        dbapi_connection.execute(
            f"ATTACH DATABASE '{platform_db.resolve().as_posix()}' AS platform"
        )

    alembic_config = Config()
    alembic_config.set_main_option(
        "script_location", str(REPO_ROOT / "migrations" / "platform")
    )
    alembic_config.set_main_option("sqlalchemy.url", _sqlite_url(main_db))

    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(runtime_engine: sa.Engine) -> sa.orm.sessionmaker[sa.orm.Session]:
    return build_session_factory(runtime_engine)


@pytest.fixture
def config_registry():
    return build_config_registry(CONFIG_ROOT)


def _runtime_service(
    session: sa.orm.Session,
    *,
    config_registry,
) -> ScenarioRuntimeService:
    event_emitter = EventEmitter(EventLogRepository(session))
    session_repository = ScenarioSessionRepository(session)
    return ScenarioRuntimeService(
        config_registry=config_registry,
        session_repository=session_repository,
        session_service=ScenarioSessionService(session_repository, event_emitter),
        job_repository=JobRepository(session),
        event_emitter=event_emitter,
    )


def test_start_session_creates_linked_session_and_job(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)

        snapshot = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
        )

        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            snapshot.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        job = JobRepository(session).get(snapshot.job_id)

    assert snapshot.status is ScenarioSessionStatus.started
    assert snapshot.current_checkpoint_id == PROCESSING_CHECKPOINT_ID
    assert snapshot.allowed_next_actions == ()
    assert scenario_session is not None
    assert scenario_session.metadata["input"] == {
        "source_text": "deadline budget deliverables"
    }
    assert scenario_session.current_checkpoint_id == PROCESSING_CHECKPOINT_ID
    assert scenario_session.scenario_chain_id == scenario_session.id
    assert job is not None
    assert job.scenario_session_id == scenario_session.id
    assert job.product_id == scenario_session.product_id
    assert job.frontend_id == scenario_session.frontend_id
    assert job.metadata["guest_id"] == "guest_demo"
    assert job.metadata["scenario_chain_id"] == scenario_session.scenario_chain_id


def test_start_session_rejects_unknown_guest_before_writing_any_row(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    # consume_for_accepted_start() now requires a QuotaValidation obtained from
    # validate_accepted_start(), and start_session() calls validate_accepted_start()
    # before the insert-or-select. A request for an unknown guest_id must therefore
    # fail before any scenario_sessions row (or its scenario.started event) is ever
    # written, instead of writing-then-rolling-back on every rejected attempt.
    with transaction_boundary(session_factory) as session:
        event_emitter = EventEmitter(EventLogRepository(session))
        session_repository = ScenarioSessionRepository(session)
        service = ScenarioRuntimeService(
            config_registry=config_registry,
            session_repository=session_repository,
            session_service=ScenarioSessionService(session_repository, event_emitter),
            job_repository=JobRepository(session),
            event_emitter=event_emitter,
            quota_service=GuestQuotaService(
                config_registry=config_registry,
                quota_repository=QuotaUsageRepository(session),
                guest_repository=GuestIdentityRepository(session),
                event_emitter=event_emitter,
            ),
        )

        with pytest.raises(GuestIdentityNotFoundError):
            service.start_session(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                scenario_id="kernel_demo.single_action_smoke_v1",
                frontend_id="kernel_demo_ce",
                input_payload={"source_text": "deadline budget deliverables"},
                guest_id="guest_does_not_exist",
                idempotency_key="idem-unknown-guest",
            )

        scenario_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()
        started_count = session.execute(
            sa.select(sa.func.count())
            .select_from(event_log_table)
            .where(event_log_table.c.event_type == "scenario.started")
        ).scalar_one()

    assert scenario_count == 0
    assert started_count == 0


def test_start_session_replays_existing_session_despite_later_config_drift(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    # A replay of an already-accepted start must not depend on product/frontend/quota
    # config still being valid at replay time -- only a genuinely NEW request needs
    # that validation. Disabling the frontend between the original request and the
    # retry must not break the retry: it is exactly the browser back-button/timeout-
    # retry case Idempotency-Key exists for, and the original request already proved
    # the frontend was valid when it was accepted.
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        first = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="idem-config-drift",
        )

        product = config_registry.get_product("kernel_demo")
        assert product is not None
        disabled_frontends = tuple(
            replace(frontend, enabled=False)
            if frontend.frontend_id == "kernel_demo_ce"
            else frontend
            for frontend in product.frontends
        )
        drifted_registry = replace(
            config_registry,
            products={
                **dict(config_registry.products),
                "kernel_demo": replace(product, frontends=disabled_frontends),
            },
        )
        drifted_service = _runtime_service(session, config_registry=drifted_registry)

        # A genuinely new request against the drifted config really is rejected.
        with pytest.raises(ScenarioFrontendInvalidError):
            drifted_service.start_session(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                scenario_id="kernel_demo.single_action_smoke_v1",
                frontend_id="kernel_demo_ce",
                input_payload={"source_text": "deadline budget deliverables"},
                guest_id="guest_demo",
                idempotency_key="idem-config-drift-new",
            )

        # But the replay of the ALREADY-ACCEPTED key must still succeed.
        second = drifted_service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="idem-config-drift",
        )

    assert second.scenario_session_id == first.scenario_session_id
    assert second.job_id == first.job_id


def test_start_session_sequential_replay_survives_scenario_version_bump(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    # Pinning the replay's scenario resolution to existing.scenario_version would
    # 404 (ScenarioNotFoundError) every replay whose scenario was bumped to a new
    # version by an ordinary config deploy since the original accepted start -- the
    # registry only ever holds the current definition per scenario_id, not history.
    # The retry must still return the original 200 snapshot.
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        first = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="idem-version-bump",
        )

        scenario = config_registry.get_scenario("kernel_demo.single_action_smoke_v1")
        assert scenario is not None
        bumped_registry = replace(
            config_registry,
            scenarios={
                **dict(config_registry.scenarios),
                "kernel_demo.single_action_smoke_v1": replace(
                    scenario, version=scenario.version + 1
                ),
            },
        )
        bumped_service = _runtime_service(session, config_registry=bumped_registry)

        second = bumped_service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="idem-version-bump",
        )

    assert second.scenario_session_id == first.scenario_session_id
    assert second.job_id == first.job_id


def test_start_session_race_loss_replay_survives_scenario_version_bump(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Same config-drift guarantee as the sequential-replay case above, but for the
    # race-loss branch specifically: a losing concurrent request must not 404 either,
    # even if it resolved config (e.g. on a different API instance mid rolling
    # deploy) after the winner's version had already moved on.
    with transaction_boundary(session_factory) as session:
        event_emitter = EventEmitter(EventLogRepository(session))
        session_repository = ScenarioSessionRepository(session)
        winner_service = ScenarioRuntimeService(
            config_registry=config_registry,
            session_repository=session_repository,
            session_service=ScenarioSessionService(session_repository, event_emitter),
            job_repository=JobRepository(session),
            event_emitter=event_emitter,
        )
        winner = winner_service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="idem-race-version-bump",
        )

        scenario = config_registry.get_scenario("kernel_demo.single_action_smoke_v1")
        assert scenario is not None
        bumped_registry = replace(
            config_registry,
            scenarios={
                **dict(config_registry.scenarios),
                "kernel_demo.single_action_smoke_v1": replace(
                    scenario, version=scenario.version + 1
                ),
            },
        )
        loser_service = ScenarioRuntimeService(
            config_registry=bumped_registry,
            session_repository=session_repository,
            session_service=ScenarioSessionService(session_repository, event_emitter),
            job_repository=JobRepository(session),
            event_emitter=event_emitter,
        )

        # Simulate the race window: the loser's early idempotency lookup misses the
        # winner's already-committed row once, forcing an insert attempt that then
        # hits the real unique-constraint IntegrityError and recovers via re-select.
        real_get_by_idempotency_key = session_repository.get_by_idempotency_key
        calls: list[int] = []

        def _miss_once(*args: Any, **kwargs: Any) -> ScenarioSessionRecord | None:
            calls.append(1)
            if len(calls) == 1:
                return None
            return real_get_by_idempotency_key(*args, **kwargs)

        monkeypatch.setattr(session_repository, "get_by_idempotency_key", _miss_once)

        loser = loser_service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="idem-race-version-bump",
        )

    assert loser.scenario_session_id == winner.scenario_session_id
    assert loser.job_id == winner.job_id


def test_start_session_looks_up_idempotency_key_at_most_once_for_a_new_key(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # start_session()'s own early lookup and start_or_get_existing()'s (now removed)
    # optimistic pre-read used to run the identical SELECT twice for the dominant
    # case (a genuinely new key). Assert the repository method fires exactly once per
    # start_session() call for a brand-new key -- catches a future regression that
    # reintroduces the redundant second lookup.
    with transaction_boundary(session_factory) as session:
        session_repository = ScenarioSessionRepository(session)
        event_emitter = EventEmitter(EventLogRepository(session))
        service = ScenarioRuntimeService(
            config_registry=config_registry,
            session_repository=session_repository,
            session_service=ScenarioSessionService(session_repository, event_emitter),
            job_repository=JobRepository(session),
            event_emitter=event_emitter,
        )

        real_get_by_idempotency_key = session_repository.get_by_idempotency_key
        calls: list[int] = []

        def _counting(*args: Any, **kwargs: Any) -> ScenarioSessionRecord | None:
            calls.append(1)
            return real_get_by_idempotency_key(*args, **kwargs)

        monkeypatch.setattr(session_repository, "get_by_idempotency_key", _counting)

        service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="idem-single-lookup",
        )

    assert len(calls) == 1


def test_start_session_rejects_oversized_idempotency_key_before_any_write(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    # An Idempotency-Key longer than the storage column (VARCHAR(256)) must be
    # rejected with a clean PlatformError (422) instead of reaching sa.insert() and
    # crashing with an unhandled DataError on PostgreSQL.
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)

        with pytest.raises(IdempotencyKeyInvalidError):
            service.start_session(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                scenario_id="kernel_demo.single_action_smoke_v1",
                frontend_id="kernel_demo_ce",
                input_payload={"source_text": "deadline budget deliverables"},
                guest_id="guest_demo",
                idempotency_key="k" * 257,
            )

        scenario_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()

    assert scenario_count == 0


def test_start_session_treats_blank_idempotency_key_as_absent(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    # An empty/whitespace-only Idempotency-Key header must behave like no header at
    # all, not like a real shared key -- two callers that both send a blank header
    # must not be scoped together as duplicates of each other.
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)

        first = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="   ",
        )
        second = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
            guest_id="guest_demo",
            idempotency_key="",
        )

        stored_first = ScenarioSessionRepository(session).get_in_scope(
            first.scenario_session_id, tenant_id="anytoolai", region="default"
        )
        stored_second = ScenarioSessionRepository(session).get_in_scope(
            second.scenario_session_id, tenant_id="anytoolai", region="default"
        )

    assert first.scenario_session_id != second.scenario_session_id
    assert stored_first is not None
    assert stored_second is not None
    assert stored_first.idempotency_key is None
    assert stored_second.idempotency_key is None


def test_idempotency_key_conflict_error_has_stable_code_and_message() -> None:
    error = IdempotencyKeyConflictError()

    assert error.code == "idempotency_key_conflict"
    assert str(error) == "Idempotency-Key was already used with a different request."


def _idempotency_hash_kwargs(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "tenant_id": "anytoolai",
        "region": "default",
        "product_id": "kernel_demo",
        "scenario_id": "kernel_demo.single_action_smoke_v1",
        "frontend_id": "kernel_demo_ce",
        "guest_id": "guest_demo",
        "user_id": None,
        "input_payload": {"source_text": "deadline budget deliverables"},
    }
    values.update(overrides)
    return values


SHA256_HEX_DIGEST_LENGTH = 64


def test_compute_idempotency_request_hash_is_deterministic() -> None:
    first = compute_idempotency_request_hash(**_idempotency_hash_kwargs())
    second = compute_idempotency_request_hash(**_idempotency_hash_kwargs())

    assert first == second
    assert len(first) == SHA256_HEX_DIGEST_LENGTH


def test_compute_idempotency_request_hash_ignores_input_payload_key_order() -> None:
    ordered = compute_idempotency_request_hash(
        **_idempotency_hash_kwargs(input_payload={"a": 1, "b": 2})
    )
    reordered = compute_idempotency_request_hash(
        **_idempotency_hash_kwargs(input_payload={"b": 2, "a": 1})
    )

    assert ordered == reordered


def test_compute_idempotency_request_hash_rejects_non_json_serializable_input() -> None:
    # isinstance(input_payload, Mapping) only guarantees the container shape, not that
    # every value inside is JSON-serializable. A datetime (or any other non-JSON
    # value) must surface as the same safe ScenarioInputInvalidError the caller
    # already raises for a non-Mapping payload, not a raw unhandled TypeError.
    with pytest.raises(ScenarioInputInvalidError):
        compute_idempotency_request_hash(
            **_idempotency_hash_kwargs(input_payload={"when": datetime.now(UTC)})
        )


def test_start_session_rejects_non_json_serializable_input_with_idempotency_key(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)

        with pytest.raises(ScenarioInputInvalidError):
            service.start_session(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                scenario_id="kernel_demo.single_action_smoke_v1",
                frontend_id="kernel_demo_ce",
                input_payload={"when": datetime.now(UTC)},
                guest_id="guest_demo",
                idempotency_key="idem-non-serializable",
            )

        scenario_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()

    assert scenario_count == 0


def test_compute_idempotency_request_hash_changes_with_input_payload() -> None:
    baseline = compute_idempotency_request_hash(**_idempotency_hash_kwargs())
    changed = compute_idempotency_request_hash(
        **_idempotency_hash_kwargs(input_payload={"source_text": "different"})
    )

    assert baseline != changed


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "region", "product_id", "scenario_id", "frontend_id"],
)
def test_compute_idempotency_request_hash_changes_with_scope_fields(field: str) -> None:
    baseline = compute_idempotency_request_hash(**_idempotency_hash_kwargs())
    changed = compute_idempotency_request_hash(
        **_idempotency_hash_kwargs(**{field: "something_else"})
    )

    assert baseline != changed


def test_compute_idempotency_request_hash_distinguishes_guest_and_user() -> None:
    guest_only = compute_idempotency_request_hash(
        **_idempotency_hash_kwargs(guest_id="guest_demo", user_id=None)
    )
    user_only = compute_idempotency_request_hash(
        **_idempotency_hash_kwargs(guest_id=None, user_id="guest_demo")
    )

    assert guest_only != user_only


def _idempotent_start_record(**overrides: Any) -> ScenarioSessionRecord:
    values: dict[str, Any] = {
        "tenant_id": "anytoolai",
        "region": "default",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_id": "kernel_demo.single_action_smoke_v1",
        "scenario_version": 1,
        "guest_id": "guest_demo",
    }
    values.update(overrides)
    return ScenarioSessionRecord(**values)


def test_start_or_get_existing_without_key_behaves_like_start(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        service = ScenarioSessionService(repository, EventEmitter(EventLogRepository(session)))

        stored, inserted = service.start_or_get_existing(_idempotent_start_record())

        event_count = session.execute(
            sa.select(sa.func.count())
            .select_from(event_log_table)
            .where(event_log_table.c.event_type == "scenario.started")
        ).scalar_one()

    assert inserted is True
    assert stored.idempotency_key is None
    assert event_count == 1


def test_start_or_get_existing_replays_same_key_without_new_insert_or_event(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        service = ScenarioSessionService(repository, EventEmitter(EventLogRepository(session)))

        first, first_inserted = service.start_or_get_existing(
            _idempotent_start_record(idempotency_key="idem-1")
        )
        second, second_inserted = service.start_or_get_existing(
            _idempotent_start_record(idempotency_key="idem-1")
        )

        session_count = session.execute(
            sa.select(sa.func.count()).select_from(scenario_sessions_table)
        ).scalar_one()
        event_count = session.execute(
            sa.select(sa.func.count())
            .select_from(event_log_table)
            .where(event_log_table.c.event_type == "scenario.started")
        ).scalar_one()

    assert first_inserted is True
    assert second_inserted is False
    assert second.id == first.id
    assert session_count == 1
    assert event_count == 1


def test_start_or_get_existing_recovers_from_concurrent_insert_race(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    # start_or_get_existing() has no optimistic pre-read of its own (removed once its
    # only caller, start_session(), started doing an equivalent lookup before ever
    # calling this): every call with an idempotency_key attempts the insert directly,
    # so a second call for an already-taken key deterministically hits a real
    # IntegrityError from the unique constraint -- no monkeypatch/simulated miss
    # needed to exercise the begin_nested()/IntegrityError recovery path here.
    with transaction_boundary(session_factory) as session:
        repository = ScenarioSessionRepository(session)
        service = ScenarioSessionService(repository, EventEmitter(EventLogRepository(session)))

        winner, winner_inserted = service.start_or_get_existing(
            _idempotent_start_record(idempotency_key="idem-race")
        )
        assert winner_inserted is True

        loser, loser_inserted = service.start_or_get_existing(
            _idempotent_start_record(
                id="scenario_session_loser", idempotency_key="idem-race"
            )
        )

        event_count = session.execute(
            sa.select(sa.func.count())
            .select_from(event_log_table)
            .where(event_log_table.c.event_type == "scenario.started")
        ).scalar_one()

    assert loser_inserted is False
    assert loser.id == winner.id
    assert event_count == 1


def test_get_session_snapshot_returns_result_ready_checkpoint_and_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        session_service = ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        )
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )

        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        claimed_job = JobRepository(session).claim_created(started.job_id)
        assert claimed_job is not None
        scenario_session = session_service.mark_running(scenario_session)
        job = JobRepository(session).get(started.job_id)
        assert job is not None

        result_artifact = ArtifactRepository(session).create(
            ArtifactRecord(
                tenant_id=job.tenant_id,
                region=job.region,
                product_id=job.product_id,
                frontend_id=job.frontend_id,
                scenario_session_id=job.scenario_session_id,
                job_id=job.id,
                artifact_type="structured_output",
                status=ArtifactStatus.stored,
                content_json={"ok": True},
            )
        )
        succeeded_job = JobRepository(session).mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=result_artifact.id,
                completed_at=result_artifact.created_at,
            )
        )
        session_service.mark_completed(
            replace(
                scenario_session,
                completed_at=succeeded_job.completed_at,
            )
        )

        snapshot = service.get_session_snapshot(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )

    assert snapshot.status is ScenarioSessionStatus.completed
    assert snapshot.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert snapshot.result_artifact_id == result_artifact.id
    assert snapshot.allowed_next_actions == ("copy_result", "create_handoff")


def test_record_next_action_emits_event_and_validates_checkpoint(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        session_service = ScenarioSessionService(
            ScenarioSessionRepository(session),
            EventEmitter(EventLogRepository(session)),
        )
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )
        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        claimed_job = JobRepository(session).claim_created(started.job_id)
        assert claimed_job is not None
        scenario_session = session_service.mark_running(scenario_session)
        job = JobRepository(session).get(started.job_id)
        assert job is not None
        result_artifact = ArtifactRepository(session).create(
            ArtifactRecord(
                tenant_id=job.tenant_id,
                region=job.region,
                product_id=job.product_id,
                frontend_id=job.frontend_id,
                scenario_session_id=job.scenario_session_id,
                job_id=job.id,
                artifact_type="structured_output",
                status=ArtifactStatus.stored,
                content_json={"ok": True},
            )
        )
        succeeded_job = JobRepository(session).mark_succeeded(
            replace(
                job,
                status=JobStatus.succeeded,
                result_artifact_id=result_artifact.id,
                completed_at=result_artifact.created_at,
            )
        )
        session_service.mark_completed(
            replace(scenario_session, completed_at=succeeded_job.completed_at)
        )

        snapshot = service.record_next_action(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
            next_action_id="copy_result",
            checkpoint_id=RESULT_READY_CHECKPOINT_ID,
        )

        event_row = session.execute(
            sa.select(event_log_table).where(
                event_log_table.c.event_type == "client.next_action_clicked"
            )
        ).mappings().one()

        with pytest.raises(ScenarioCheckpointConflictError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="copy_result",
                checkpoint_id=FAILED_CHECKPOINT_ID,
            )

        with pytest.raises(ScenarioNextActionNotAllowedError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="view_paywall",
                checkpoint_id=RESULT_READY_CHECKPOINT_ID,
            )

    assert snapshot.current_checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert event_row["scenario_session_id"] == started.scenario_session_id
    assert event_row["job_id"] == started.job_id
    assert event_row["properties"]["checkpoint_id"] == RESULT_READY_CHECKPOINT_ID
    assert event_row["properties"]["next_action_id"] == "copy_result"


def test_record_next_action_rejects_non_actionable_processing_checkpoint(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )

        with pytest.raises(ScenarioCheckpointNotActionableError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="copy_result",
                checkpoint_id=PROCESSING_CHECKPOINT_ID,
            )


def test_record_next_action_returns_safe_error_when_result_ready_job_is_missing(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        session_repository = ScenarioSessionRepository(session)
        scenario = config_registry.get_scenario("kernel_demo.single_action_smoke_v1")
        assert scenario is not None
        started = session_repository.create(
            ScenarioSessionRecord(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                scenario_id=scenario.scenario_id,
                scenario_version=scenario.version,
                status=ScenarioSessionStatus.completed,
                current_checkpoint_id=RESULT_READY_CHECKPOINT_ID,
            )
        )

        with pytest.raises(ScenarioCheckpointNotActionableError):
            service.record_next_action(
                started.id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="copy_result",
                checkpoint_id=RESULT_READY_CHECKPOINT_ID,
            )


def test_get_session_snapshot_rejects_persisted_scenario_version_mismatch(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )
        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        ScenarioSessionRepository(session).update(
            replace(scenario_session, scenario_version=scenario_session.scenario_version + 1),
            tenant_id=scenario_session.tenant_id,
            region=scenario_session.region,
            product_id=scenario_session.product_id,
            frontend_id=scenario_session.frontend_id,
        )

        with pytest.raises(ScenarioNotFoundError):
            service.get_session_snapshot(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
            )


def test_record_next_action_rejects_persisted_scenario_version_mismatch(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    config_registry,
) -> None:
    with transaction_boundary(session_factory) as session:
        service = _runtime_service(session, config_registry=config_registry)
        started = service.start_session(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            scenario_id="kernel_demo.single_action_smoke_v1",
            frontend_id="kernel_demo_ce",
            input_payload={"source_text": "deadline budget deliverables"},
        )
        scenario_session = ScenarioSessionRepository(session).get_in_scope(
            started.scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert scenario_session is not None
        ScenarioSessionRepository(session).update(
            replace(scenario_session, scenario_version=scenario_session.scenario_version + 1),
            tenant_id=scenario_session.tenant_id,
            region=scenario_session.region,
            product_id=scenario_session.product_id,
            frontend_id=scenario_session.frontend_id,
        )

        with pytest.raises(ScenarioNotFoundError):
            service.record_next_action(
                started.scenario_session_id,
                tenant_id="anytoolai",
                region="default",
                next_action_id="copy_result",
                checkpoint_id=PROCESSING_CHECKPOINT_ID,
            )


def test_checkpoint_resolution_falls_back_to_job_state(config_registry) -> None:
    scenario = config_registry.get_scenario("kernel_demo.single_action_smoke_v1")
    assert scenario is not None

    session = ScenarioSessionRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.version,
        status=ScenarioSessionStatus.running,
        current_checkpoint_id=None,
    )
    succeeded_job = JobRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id=session.id,
        workflow_id=scenario.workflow_id,
        workflow_version=1,
        status=JobStatus.succeeded,
        result_artifact_id="artifact_result",
    )
    failed_job = replace(
        succeeded_job,
        status=JobStatus.failed,
        result_artifact_id=None,
    )

    succeeded_state = resolve_checkpoint_state(
        scenario=scenario,
        session=session,
        job=succeeded_job,
    )
    failed_state = resolve_checkpoint_state(
        scenario=scenario,
        session=session,
        job=failed_job,
    )

    assert resolve_effective_status(session=session, job=succeeded_job) is ScenarioSessionStatus.completed
    assert succeeded_state.checkpoint_id == RESULT_READY_CHECKPOINT_ID
    assert succeeded_state.allowed_next_actions == ("copy_result", "create_handoff")

    assert resolve_effective_status(session=session, job=failed_job) is ScenarioSessionStatus.failed
    assert failed_state.checkpoint_id == FAILED_CHECKPOINT_ID
    assert failed_state.allowed_next_actions == ()


def test_processing_checkpoint_does_not_override_terminal_canceled_job(config_registry) -> None:
    scenario = config_registry.get_scenario("kernel_demo.single_action_smoke_v1")
    assert scenario is not None

    session = ScenarioSessionRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.version,
        status=ScenarioSessionStatus.started,
        current_checkpoint_id=PROCESSING_CHECKPOINT_ID,
    )
    canceled_job = JobRecord(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id=session.id,
        workflow_id=scenario.workflow_id,
        workflow_version=1,
        status=JobStatus.canceled,
    )

    checkpoint_state = resolve_checkpoint_state(
        scenario=scenario,
        session=session,
        job=canceled_job,
    )

    assert resolve_effective_status(session=session, job=canceled_job) is ScenarioSessionStatus.failed
    assert checkpoint_state.checkpoint_id == FAILED_CHECKPOINT_ID
    assert checkpoint_state.allowed_next_actions == ()
