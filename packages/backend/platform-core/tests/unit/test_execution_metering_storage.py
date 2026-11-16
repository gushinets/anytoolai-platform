from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, replace

import pytest
import sqlalchemy as sa
from alembic import command
from anytoolai_platform_core.actions.models import ActionRunRecord
from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.handoffs.models import HandoffRecord, HandoffStartPolicy
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.providers.models import ProviderCallRecord
from anytoolai_platform_core.quotas.execution_repository import (
    ExecutionReservationRepository,
    PaidAllowanceConflictError,
    PaidAllowanceUsageRepository,
)
from anytoolai_platform_core.quotas.models import (
    MAX_ALLOWANCE_QUANTITY,
    ExecutionOwner,
    ExecutionOwnerKind,
    ExecutionReplayNamespace,
    ExecutionReservation,
    QuotaDimension,
)
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import (
    execution_reservations_table,
    guest_quota_usage_table,
    jobs_table,
    paid_allowance_usage_table,
    runtime_metadata,
)
from anytoolai_platform_core.workflows.models import JobConsumptionMode, JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from sqlalchemy.orm import Session
from test_execution_metering_models import paid_allowance

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def engine() -> Iterator[sa.Engine]:
    with provision_database(
        database_name_prefix="any507_storage",
        skip_reason="execution metering storage",
    ) as (engine, _, _):
        yield engine


def _execution(session: Session, *, guest_id: str | None = None) -> JobRecord:
    scenario = ScenarioSessionRepository(session).create(
        ScenarioSessionRecord(
            tenant_id="test",
            region="ru",
            product_id="kernel_demo",
            frontend_id="test_web",
            scenario_id="smoke",
            scenario_version=1,
            guest_id=guest_id,
        )
    )
    return JobRepository(session).create(
        JobRecord(
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            workflow_id="smoke",
            workflow_version=1,
            consumption_mode=JobConsumptionMode.reserved,
        )
    )


def _reservation(session: Session, *, guest: bool = False) -> ExecutionReservation:
    if guest:
        identity = GuestIdentityRepository(session).create(
            GuestIdentityRecord(
                tenant_id="test",
                region="ru",
            )
        )
        owner = ExecutionOwner("test", "ru", ExecutionOwnerKind.guest, identity.id)
        bucket = QuotaUsageRepository(session).ensure_usage(
            tenant_id="test",
            region="ru",
            guest_id=identity.id,
            product_id="kernel_demo",
            quota_policy_id="test",
            quota_dimension=QuotaDimension.product,
            dimension_key="kernel_demo",
            scenario_id=None,
            period_key="lifetime",
            limit_count=2,
        )
        job = _execution(session, guest_id=identity.id)
        buckets = {"guest_quota_usage_id": bucket.id}
    else:
        allowance = paid_allowance()
        owner = allowance.owner
        bucket = PaidAllowanceUsageRepository(session).ensure_usage(allowance)
        job = _execution(session)
        buckets = {"paid_allowance_usage_id": bucket.id}
    return ExecutionReservation(
        owner=owner,
        scenario_session_id=job.scenario_session_id,
        job_id=job.id,
        product_id=job.product_id,
        scenario_id="smoke",
        frontend_id=job.frontend_id,
        replay_namespace=ExecutionReplayNamespace.start,
        replay_key=job.id,
        request_hash="a" * 64,
        **buckets,
    )


def _raw_reservation(record: ExecutionReservation) -> dict:
    values = asdict(record)
    values.update(values.pop("owner"))
    return values


def _snapshot(connection: sa.Connection, metadata: sa.MetaData) -> dict:
    return {
        table.name: [
            dict(row)
            for row in connection.execute(
                sa.select(table).order_by(*table.primary_key.columns),
            ).mappings()
        ]
        for table in sorted(metadata.tables.values(), key=lambda table: table.fullname)
    }


def _seed_0015(connection: sa.Connection, metadata: sa.MetaData) -> None:
    scope = {"tenant_id": "historic-tenant", "region": "historic-region"}
    dimensions = {**scope, "product_id": "kernel_demo", "frontend_id": "old_frontend"}
    guest = GuestIdentityRecord(**scope)
    scenario = ScenarioSessionRecord(
        **dimensions,
        scenario_id="old_scenario",
        scenario_version=1,
        guest_id=guest.id,
        user_id="historical-body-user",
        metadata={"input": {"text": "history"}},
    )
    job = JobRecord(
        **dimensions,
        scenario_session_id=scenario.id,
        workflow_id="old_workflow",
        workflow_version=1,
    )
    action = ActionRunRecord(
        **dimensions,
        scenario_session_id=scenario.id,
        job_id=job.id,
        workflow_id=job.workflow_id,
        step_id="one",
        action_type="text.extract_structured_fields",
        action_config_id="old_config",
    )
    provider = ProviderCallRecord(
        **dimensions,
        scenario_session_id=scenario.id,
        job_id=job.id,
        action_run_id=action.id,
        workflow_id=job.workflow_id,
        workflow_version=1,
        step_id="one",
        action_type=action.action_type,
        action_config_id=action.action_config_id,
        provider_policy_ref="old_policy",
        provider="fake",
        model="old_model",
        gateway_backend="fake",
        gateway_model="old_model",
        semantic_attempt_index=1,
        transport_attempt_index=1,
        physical_call_index=1,
    )
    artifact = ArtifactRecord(
        **dimensions,
        scenario_session_id=scenario.id,
        job_id=job.id,
        artifact_type="structured_output",
        content_json={"historical": True},
    )
    handoff = HandoffRecord(
        **scope,
        handoff_definition_id="old_handoff",
        token_hash="b" * 64,
        source_product_id=job.product_id,
        source_frontend_id=job.frontend_id,
        source_scenario_id=scenario.scenario_id,
        source_scenario_session_id=scenario.id,
        source_job_id=job.id,
        source_artifact_id=artifact.id,
        target_product_id="kernel_demo",
        target_frontend_id="old_frontend",
        target_scenario_id="old_target",
        scenario_chain_id=scenario.id,
        consent_required=True,
        target_start_policy=HandoffStartPolicy.immediate,
        context_payload={"text": "historical"},
        preview_payload={"text": "historical"},
        expires_at=utc_now(),
    )
    for name, record in (
        ("guest_identities", guest),
        ("scenario_sessions", scenario),
        ("jobs", job),
        ("action_runs", action),
        ("provider_calls", provider),
        ("artifacts", artifact),
        ("product_handoffs", handoff),
    ):
        table = metadata.tables[f"platform.{name}"]
        values = {key: value for key, value in asdict(record).items() if key in table.c}
        connection.execute(sa.insert(table).values(values))
    old_jobs = metadata.tables["platform.jobs"]
    for status in (JobStatus.running, JobStatus.succeeded, JobStatus.failed, JobStatus.canceled):
        values = asdict(replace(job, id=f"historic_{status.value}", status=status))
        values.pop("consumption_mode")
        connection.execute(sa.insert(old_jobs).values(values))
    usage = metadata.tables["platform.guest_quota_usage"]
    # Includes an over-limit historical row and every window; upgrade must never refund/rebucket.
    for index, period in enumerate(
        ("lifetime", "day:2026-11-03", "week:2026-W45", "month:2026-11")
    ):
        connection.execute(
            sa.insert(usage).values(
                **scope,
                id=f"old_usage_{index}",
                guest_id=guest.id,
                product_id="kernel_demo",
                quota_policy_id="old_policy",
                quota_dimension="product",
                dimension_key="kernel_demo",
                period_key=period,
                limit_count=1,
                used_count=index,
                created_at=utc_now(),
                updated_at=utc_now(),
                metadata={"historic": index},
            )
        )
    connection.execute(
        sa.insert(metadata.tables["platform.event_log"]).values(
            **dimensions,
            event_id="old_event",
            event_type="workflow.started",
            timestamp=utc_now(),
            scenario_session_id=scenario.id,
            job_id=job.id,
            properties={"keep": "verbatim"},
        )
    )


def test_populated_0015_upgrade_preserves_every_historical_column_and_repeats() -> None:
    with provision_database(
        database_name_prefix="any507_upgrade",
        upgrade_target="0015",
        skip_reason="populated execution metering migration",
    ) as (engine, config, _):
        old = sa.MetaData(schema="platform")
        with engine.begin() as connection:
            old.reflect(connection, schema="platform")
            _seed_0015(connection, old)
            before = _snapshot(connection, old)
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert _snapshot(connection, old) == before
            usages = connection.execute(sa.select(guest_quota_usage_table)).mappings().all()
            assert all(row["legacy_used_count"] == row["used_count"] for row in usages)
            assert all(row["reserved_count"] == 0 for row in usages)
            assert connection.execute(sa.select(jobs_table.c.consumption_mode)).scalars().all() == [
                JobConsumptionMode.legacy,
            ] * len(before["jobs"])
            after = sa.MetaData(schema="platform")
            after.reflect(connection, schema="platform")
            first = _snapshot(connection, after)
            command.upgrade(config, "head")
            assert _snapshot(connection, after) == first


def test_clean_upgrade_matches_storage_metadata(engine: sa.Engine) -> None:
    inspector = sa.inspect(engine)
    for table in (paid_allowance_usage_table, execution_reservations_table):
        actual = {
            column["name"]: column
            for column in inspector.get_columns(
                table.name,
                schema="platform",
            )
        }
        assert set(actual) == set(table.c.keys())
        assert {
            c["name"] for c in inspector.get_check_constraints(table.name, schema="platform")
        } == {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint)
        }
        assert {c["name"] for c in inspector.get_foreign_keys(table.name, schema="platform")} == {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.ForeignKeyConstraint)
        }
    for name in ("quantity", "used_count", "reserved_count"):
        assert isinstance(
            sa.inspect(engine).get_columns("paid_allowance_usage", schema="platform")[
                list(paid_allowance_usage_table.c.keys()).index(name)
            ]["type"],
            sa.BigInteger,
        )
    assert "platform.execution_reservations" in runtime_metadata.tables


@pytest.mark.parametrize("guest", [False, True])
def test_reservation_roundtrip_and_caller_rollback(engine: sa.Engine, guest: bool) -> None:
    with Session(engine) as session:
        candidate = _reservation(session, guest=guest)
        repo = ExecutionReservationRepository(session)
        stored = repo.create(candidate)
        assert stored == candidate
        assert (
            repo.find_replay(
                owner=candidate.owner,
                product_id=candidate.product_id,
                scenario_id=candidate.scenario_id,
                namespace=candidate.replay_namespace,
                replay_key=candidate.replay_key,
            )
            == candidate
        )
        assert (
            repo.find_replay(
                owner=replace(candidate.owner, region="other"),
                product_id=candidate.product_id,
                scenario_id=candidate.scenario_id,
                namespace=candidate.replay_namespace,
                replay_key=candidate.replay_key,
            )
            is None
        )
        session.rollback()
    with engine.connect() as connection:
        for table in (jobs_table, paid_allowance_usage_table, execution_reservations_table):
            assert (
                connection.execute(sa.select(sa.func.count()).select_from(table)).scalar_one() == 0
            )


def test_paid_binding_reuses_history_and_new_cycle_gets_independent_bucket(
    engine: sa.Engine,
) -> None:
    with Session(engine) as session, session.begin():
        repo = PaidAllowanceUsageRepository(session)
        assert repo.get(tenant_id="test", region="ru", allowance_id="cycle-one") is None
        first = repo.ensure_usage(paid_allowance())
        session.execute(sa.update(paid_allowance_usage_table).values(used_count=1))
        same = repo.ensure_usage(paid_allowance())
        other = repo.ensure_usage(replace(paid_allowance(), allowance_id="cycle-two"))
        assert same.id == first.id
        assert same.used_count == 1
        assert other.id != first.id
        assert other.used_count == other.reserved_count == 0


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "owner",
            ExecutionOwner(
                "test", "ru", ExecutionOwnerKind.portal_user, "2415eefa-647a-4777-a27e-ef3e78835492"
            ),
        ),
        ("product_id", "other_product"),
        ("metric_key", "other_metric"),
        ("unit", "other_unit"),
        ("quantity", 2),
    ],
)
def test_paid_rebinding_is_rejected_without_changing_usage(
    engine: sa.Engine,
    field: str,
    value: object,
) -> None:
    with Session(engine) as session, session.begin():
        repo = PaidAllowanceUsageRepository(session)
        original = repo.ensure_usage(paid_allowance())
        with pytest.raises(PaidAllowanceConflictError):
            repo.ensure_usage(replace(paid_allowance(), **{field: value}))
        assert repo.get(tenant_id="test", region="ru", allowance_id="cycle-one") == original
        column = "owner_id" if field == "owner" else field
        raw_value = value.owner_id if field == "owner" else value
        with (
            pytest.raises(sa.exc.IntegrityError, match="binding cannot change"),
            session.begin_nested(),
        ):
            session.execute(sa.update(paid_allowance_usage_table).values(**{column: raw_value}))


@pytest.mark.parametrize(
    "values",
    [
        {"quantity": -1},
        {"quantity": MAX_ALLOWANCE_QUANTITY + 1},
        {"used_count": -1},
        {"reserved_count": -1},
        {"used_count": 1, "reserved_count": 1},
    ],
)
def test_paid_counter_constraints(engine: sa.Engine, values: dict) -> None:
    with Session(engine) as session:
        # The immutable binding trigger also rejects quantity edits; INSERT tests the range itself.
        allowance = paid_allowance()
        raw = asdict(allowance)
        owner = raw.pop("owner")
        owner.pop("owner_kind")
        raw.update(owner)
        raw.update(
            id="bad", used_count=0, reserved_count=0, created_at=utc_now(), updated_at=utc_now()
        )
        raw.update(values)
        with pytest.raises(sa.exc.IntegrityError):
            session.execute(sa.insert(paid_allowance_usage_table).values(raw))


@pytest.mark.parametrize(
    "values",
    [
        {"guest_quota_usage_id": "missing"},
        {"paid_allowance_usage_id": None},
        {"job_id": "missing"},
        {"scenario_session_id": "missing"},
        {"paid_allowance_usage_id": "missing"},
        {"result_artifact_id": "missing"},
        {"handoff_id": "missing"},
        {"owner_kind": "unknown"},
        {"state": "unknown"},
        {"replay_namespace": "unknown"},
        {"replay_namespace": None},
        {"replay_key": None},
        {"request_hash": None},
        {"request_hash": "short"},
        {"replay_namespace": "handoff"},
        {"state": "consumed"},
        {"state": "released"},
    ],
)
def test_reservation_constraints(engine: sa.Engine, values: dict) -> None:
    with Session(engine) as session:
        raw = _raw_reservation(_reservation(session))
        raw.update(values)
        with pytest.raises((sa.exc.IntegrityError, sa.exc.StatementError)):
            session.execute(sa.insert(execution_reservations_table).values(raw))


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario_session_id", "missing"),
        ("product_id", "other"),
        ("frontend_id", "other"),
        ("scenario_id", "other"),
        (
            "owner",
            ExecutionOwner(
                "test",
                "other",
                ExecutionOwnerKind.portal_user,
                "c795407a-b60f-45be-840d-1a80d07ebf6e",
            ),
        ),
    ],
)
def test_reservation_repository_rejects_mismatched_execution(
    engine: sa.Engine,
    field: str,
    value: object,
) -> None:
    with Session(engine) as session:
        candidate = _reservation(session)
        with pytest.raises(ValueError, match="matching scenario"):
            ExecutionReservationRepository(session).create(replace(candidate, **{field: value}))


def test_reserved_job_requires_reservation_at_commit_and_cannot_lose_it(engine: sa.Engine) -> None:
    with Session(engine) as session:
        _execution(session)
        with pytest.raises(sa.exc.IntegrityError, match="consumption mode and reservation"):
            session.commit()
        session.rollback()
        record = ExecutionReservationRepository(session).create(_reservation(session))
        session.commit()
        session.execute(
            sa.delete(execution_reservations_table).where(
                execution_reservations_table.c.id == record.id,
            )
        )
        with pytest.raises(sa.exc.IntegrityError, match="consumption mode and reservation"):
            session.commit()


@pytest.mark.parametrize("duplicate", ["job", "session", "replay"])
def test_reservation_uniqueness(engine: sa.Engine, duplicate: str) -> None:
    with Session(engine) as session:
        first = _reservation(session)
        ExecutionReservationRepository(session).create(first)
        second = _reservation(session)
        raw = _raw_reservation(second)
        if duplicate == "job":
            raw["job_id"] = first.job_id
        elif duplicate == "session":
            raw["scenario_session_id"] = first.scenario_session_id
        else:
            raw["replay_key"] = first.replay_key
        with pytest.raises(sa.exc.IntegrityError):
            session.execute(sa.insert(execution_reservations_table).values(raw))


def test_reservation_preserves_legacy_debit(engine: sa.Engine) -> None:
    with Session(engine) as session:
        candidate = _reservation(session, guest=True)
        repo = QuotaUsageRepository(session)
        session.execute(sa.update(guest_quota_usage_table).where(
            guest_quota_usage_table.c.id == candidate.guest_quota_usage_id
        ).values(used_count=1, legacy_used_count=1))
        bucket = repo.get(candidate.guest_quota_usage_id)
        reserved = repo.reserve_if_available(bucket)
        assert reserved.used_count == reserved.legacy_used_count == 1
        assert reserved.reserved_count == 1


@pytest.mark.parametrize(
    "values",
    [
        {"reserved_count": -1},
        {"legacy_used_count": -1},
        {"legacy_used_count": 1},
    ],
)
def test_guest_new_counter_constraints(engine: sa.Engine, values: dict) -> None:
    with Session(engine) as session:
        _reservation(session, guest=True)
        with pytest.raises(sa.exc.IntegrityError):
            session.execute(sa.update(guest_quota_usage_table).values(values))


@pytest.mark.parametrize("quantity", [0, MAX_ALLOWANCE_QUANTITY])
def test_paid_bigint_boundaries_roundtrip(engine: sa.Engine, quantity: int) -> None:
    with Session(engine) as session, session.begin():
        repo = PaidAllowanceUsageRepository(session)
        allowance = replace(paid_allowance(), quantity=quantity)
        stored = repo.ensure_usage(allowance)
        session.execute(sa.update(paid_allowance_usage_table).values(used_count=quantity))
        assert (
            repo.get(
                tenant_id="test",
                region="ru",
                allowance_id=stored.allowance.allowance_id,
            ).used_count
            == quantity
        )


@pytest.mark.parametrize("guest", [False, True])
def test_reservation_rejects_another_owners_bucket(engine: sa.Engine, guest: bool) -> None:
    with Session(engine) as session:
        candidate = _reservation(session, guest=guest)
        other = _reservation(session, guest=guest)
        if guest:
            invalid = replace(candidate, guest_quota_usage_id=other.guest_quota_usage_id)
        else:
            owner = replace(candidate.owner, owner_id="2415eefa-647a-4777-a27e-ef3e78835492")
            bucket = PaidAllowanceUsageRepository(session).ensure_usage(
                replace(
                    paid_allowance(),
                    owner=owner,
                    allowance_id="another-owner",
                )
            )
            invalid = replace(candidate, paid_allowance_usage_id=bucket.id)
        with pytest.raises(ValueError, match="bucket must match"):
            ExecutionReservationRepository(session).create(invalid)


def test_same_replay_key_for_different_paid_owners_is_independent(engine: sa.Engine) -> None:
    with Session(engine) as session, session.begin():
        first = _reservation(session)
        repo = ExecutionReservationRepository(session)
        repo.create(first)
        owner = replace(first.owner, owner_id="2415eefa-647a-4777-a27e-ef3e78835492")
        bucket = PaidAllowanceUsageRepository(session).ensure_usage(
            replace(
                paid_allowance(),
                owner=owner,
                allowance_id="another-owner",
            )
        )
        second = replace(
            _reservation(session),
            owner=owner,
            paid_allowance_usage_id=bucket.id,
            replay_key=first.replay_key,
        )
        repo.create(second)
        assert (
            repo.find_replay(
                owner=owner,
                product_id=first.product_id,
                scenario_id=first.scenario_id,
                namespace=first.replay_namespace,
                replay_key=first.replay_key,
            )
            == second
        )


@pytest.mark.parametrize("mode", [JobConsumptionMode.legacy, JobConsumptionMode.unmetered])
def test_other_job_modes_cannot_have_reservations(
    engine: sa.Engine, mode: JobConsumptionMode
) -> None:
    with Session(engine) as session:
        candidate = _reservation(session)
        session.execute(sa.update(jobs_table).values(consumption_mode=mode))
        with pytest.raises(ValueError, match="reserved job"):
            ExecutionReservationRepository(session).create(candidate)
        session.execute(sa.insert(execution_reservations_table).values(_raw_reservation(candidate)))
        with pytest.raises(sa.exc.IntegrityError, match="consumption mode and reservation"):
            session.commit()


def test_job_mode_is_immutable_through_repository(engine: sa.Engine) -> None:
    with Session(engine) as session:
        job = _execution(session)
        with pytest.raises(ValueError, match="immutable field consumption_mode"):
            JobRepository(session).update(
                replace(job, consumption_mode=JobConsumptionMode.unmetered)
            )


def test_downgrade_without_new_history_preserves_guest_used() -> None:
    with (
        provision_database(
            database_name_prefix="any507_downgrade",
            upgrade_target="0015",
            skip_reason="storage migration downgrade",
        ) as (engine, config, _),
        engine.begin() as connection,
    ):
        old = sa.MetaData(schema="platform")
        old.reflect(connection, schema="platform")
        _seed_0015(connection, old)
        before = _snapshot(connection, old)
        config.attributes["connection"] = connection
        # This characterizes the ANY-507 downgrade boundary. The later V3
        # consumer-coherence cutover intentionally refuses schema downgrade.
        command.upgrade(config, "0019")
        command.downgrade(config, "0015")
        assert _snapshot(connection, old) == before
        command.upgrade(config, "head")
        assert _snapshot(connection, old) == before


def test_downgrade_refuses_to_discard_new_history() -> None:
    with provision_database(
        database_name_prefix="any507_refuse_downgrade",
        upgrade_target="0019",
        skip_reason="metering history safety",
    ) as (engine, config, _):
        with Session(engine) as session, session.begin():
            stored = ExecutionReservationRepository(session).create(_reservation(session))
        with (
            pytest.raises(sa.exc.ProgrammingError, match="backup restore"),
            engine.begin() as connection,
        ):
            config.attributes["connection"] = connection
            command.downgrade(config, "0015")
        with Session(engine) as session:
            assert ExecutionReservationRepository(session).get_by_job(stored.job_id) == stored
