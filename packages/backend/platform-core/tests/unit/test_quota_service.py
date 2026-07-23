from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityService
from anytoolai_platform_core.quotas.models import QuotaDimension
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService, QuotaExhaustedError
from anytoolai_platform_core.storage.db import event_log_table, guest_quota_usage_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


def _build_runtime_engine(main_db: Path, platform_db: Path) -> sa.Engine:
    engine = sa.create_engine(_sqlite_url(main_db), future=True)

    @event.listens_for(engine, "connect")
    def attach_platform_schema(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        dbapi_connection.execute(
            f"ATTACH DATABASE '{platform_db.resolve().as_posix()}' AS platform"
        )

    return engine


def _build_session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    main_db = tmp_path / "quota-main.sqlite3"
    platform_db = tmp_path / "quota-platform.sqlite3"
    engine = _build_runtime_engine(main_db, platform_db)
    alembic_config = Config()
    alembic_config.set_main_option(
        "script_location",
        str(REPO_ROOT / "migrations" / "platform"),
    )
    alembic_config.set_main_option("sqlalchemy.url", _sqlite_url(main_db))

    with engine.begin() as connection:
        alembic_config.attributes["connection"] = connection
        command.upgrade(alembic_config, "head")

    return build_session_factory(engine)


@pytest.fixture
def session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    return _build_session_factory(tmp_path)


def _create_guest(
    session: sa.orm.Session,
    *,
    tenant_id: str = "anytoolai",
    region: str = "default",
) -> str:
    guest = GuestIdentityService(
        GuestIdentityRepository(session),
        EventEmitter(EventLogRepository(session)),
    ).create_guest(tenant_id=tenant_id, region=region)
    return guest.id


def _quota_service(
    session: sa.orm.Session,
    *,
    registry: ConfigRegistry | None = None,
) -> GuestQuotaService:
    return GuestQuotaService(
        config_registry=registry or build_config_registry(CONFIG_ROOT),
        quota_repository=QuotaUsageRepository(session),
        guest_repository=GuestIdentityRepository(session),
        event_emitter=EventEmitter(EventLogRepository(session)),
    )


def _registry_with_quota_dimension(dimension: QuotaDimension) -> ConfigRegistry:
    registry = build_config_registry(CONFIG_ROOT)
    policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
    assert policy is not None
    return replace(
        registry,
        quotas={
            **dict(registry.quotas),
            policy.quota_policy_id: replace(policy, dimension=dimension),
        },
    )


def _registry_with_quota_limit(limit_count: int) -> ConfigRegistry:
    registry = build_config_registry(CONFIG_ROOT)
    policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
    assert policy is not None
    return replace(
        registry,
        quotas={
            **dict(registry.quotas),
            policy.quota_policy_id: replace(policy, limit_count=limit_count),
        },
    )


def _event_types(session: sa.orm.Session) -> list[str]:
    return list(
        session.execute(
            sa.select(event_log_table.c.event_type).order_by(
                event_log_table.c.timestamp,
                event_log_table.c.event_id,
            )
        ).scalars()
    )


def test_guest_create_and_quota_check_do_not_consume(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)
        service = _quota_service(session)

        first = service.check_quota(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            guest_id=guest_id,
        )
        second = service.check_quota(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            guest_id=guest_id,
        )
        event_types = _event_types(session)

    assert guest_id.startswith("guest_")
    assert first.used_count == 0
    assert first.remaining_count == 3
    assert second.used_count == 0
    assert second.remaining_count == 3
    assert event_types.count("guest.created") == 1
    assert event_types.count("quota.checked") == 2


def test_product_dimension_shares_quota_across_scenarios(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)
        service = _quota_service(session)

        first = service.consume_for_accepted_start(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            guest_id=guest_id,
            scenario_id="kernel_demo.single_action_smoke_v1",
        )
        second = service.consume_for_accepted_start(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            guest_id=guest_id,
            scenario_id="kernel_demo.multi_step_workflow_smoke_v1",
        )
        usages = list(session.execute(sa.select(guest_quota_usage_table)).mappings())
        consumed_events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.event_type == "quota.consumed")
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert first is not None
    assert second is not None
    assert first.quota_dimension is QuotaDimension.product
    assert second.quota_dimension is QuotaDimension.product
    assert first.dimension_key == "kernel_demo"
    assert second.dimension_key == "kernel_demo"
    assert len(usages) == 1
    assert usages[0]["quota_dimension"] == "product"
    assert usages[0]["dimension_key"] == "kernel_demo"
    assert usages[0]["scenario_id"] is None
    assert usages[0]["used_count"] == 2
    assert consumed_events[-1]["properties"]["scenario_id"] == (
        "kernel_demo.multi_step_workflow_smoke_v1"
    )
    assert consumed_events[-1]["properties"]["quota_dimension"] == "product"
    assert consumed_events[-1]["properties"]["quota_dimension_key"] == "kernel_demo"


def test_scenario_dimension_uses_independent_counters_and_events(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = _registry_with_quota_dimension(QuotaDimension.scenario)
    first_scenario_id = "kernel_demo.single_action_smoke_v1"
    second_scenario_id = "kernel_demo.multi_step_workflow_smoke_v1"

    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)
        service = _quota_service(session, registry=registry)

        first_scenario_states = [
            service.consume_for_accepted_start(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                guest_id=guest_id,
                scenario_id=first_scenario_id,
            )
            for _ in range(3)
        ]
        with pytest.raises(QuotaExhaustedError):
            service.consume_for_accepted_start(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                guest_id=guest_id,
                scenario_id=first_scenario_id,
            )
        second_scenario_state = service.consume_for_accepted_start(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            guest_id=guest_id,
            scenario_id=second_scenario_id,
        )
        usages = {
            row["scenario_id"]: row
            for row in session.execute(sa.select(guest_quota_usage_table)).mappings()
        }
        consumed_event = (
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.event_type == "quota.consumed")
                .order_by(event_log_table.c.timestamp.desc(), event_log_table.c.event_id.desc())
            )
            .mappings()
            .first()
        )

    assert [state.used_count for state in first_scenario_states if state is not None] == [
        1,
        2,
        3,
    ]
    assert second_scenario_state is not None
    assert second_scenario_state.used_count == 1
    assert second_scenario_state.quota_dimension is QuotaDimension.scenario
    assert second_scenario_state.dimension_key == second_scenario_id
    assert usages[first_scenario_id]["used_count"] == 3
    assert usages[second_scenario_id]["used_count"] == 1
    assert usages[first_scenario_id]["dimension_key"] == first_scenario_id
    assert usages[second_scenario_id]["dimension_key"] == second_scenario_id
    assert consumed_event is not None
    assert consumed_event["properties"]["quota_dimension"] == "scenario"
    assert consumed_event["properties"]["quota_dimension_key"] == second_scenario_id
    assert consumed_event["properties"]["quota_scenario_id"] == second_scenario_id


def test_quota_check_can_be_read_only_without_usage_or_events(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)
        state = _quota_service(session).check_quota(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            guest_id=guest_id,
            emit_event=False,
            persist_usage=False,
        )
        usage_count = session.execute(
            sa.select(sa.func.count()).select_from(guest_quota_usage_table)
        ).scalar_one()
        event_types = _event_types(session)

    assert state.used_count == 0
    assert state.remaining_count == 3
    assert usage_count == 0
    assert event_types == ["guest.created"]


def test_quota_consume_exhausted_and_repeat_calls(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)
        service = _quota_service(session)

        states = [
            service.consume_for_accepted_start(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                guest_id=guest_id,
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_session_id=f"scenario_session_demo_{index}",
                scenario_chain_id=f"scenario_session_demo_{index}",
            )
            for index in range(3)
        ]
        with pytest.raises(QuotaExhaustedError):
            service.consume_for_accepted_start(
                tenant_id="anytoolai",
                region="default",
                product_id="kernel_demo",
                frontend_id="kernel_demo_ce",
                guest_id=guest_id,
                scenario_id="kernel_demo.single_action_smoke_v1",
            )
        exhausted = service.check_quota(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            guest_id=guest_id,
            emit_event=False,
        )
        event_types = _event_types(session)

    assert [state.used_count for state in states if state is not None] == [1, 2, 3]
    assert exhausted.used_count == 3
    assert exhausted.remaining_count == 0
    assert exhausted.exhausted is True
    assert event_types.count("quota.consumed") == 3
    assert event_types.count("quota.exhausted") == 1


def test_quota_exhaustion_recovery_survives_caller_transaction_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = _registry_with_quota_limit(0)
    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)

    with pytest.raises(QuotaExhaustedError), transaction_boundary(
        session_factory
    ) as session:
        _quota_service(session, registry=registry).consume_for_accepted_start(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            guest_id=guest_id,
            scenario_id="kernel_demo.handoff_smoke_target_v1",
            scenario_session_id="scenario_session_rejected_handoff",
            scenario_chain_id="scenario_chain_handoff",
            handoff_id="handoff_quota_recovery",
        )

    with transaction_boundary(session_factory) as session:
        usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()
        quota_events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.handoff_id == "handoff_quota_recovery")
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert usage["limit_count"] == 0
    assert usage["used_count"] == 0
    assert [event["event_type"] for event in quota_events] == [
        "quota.checked",
        "quota.exhausted",
    ]
    assert all(
        event["scenario_session_id"] == "scenario_session_rejected_handoff"
        for event in quota_events
    )
    assert quota_events[-1]["error_code"] == "quota_exhausted"
    assert quota_events[-1]["properties"]["exhausted"] is True


def test_quota_conditional_consume_blocks_stale_concurrent_read(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)
        usage = QuotaUsageRepository(session).ensure_usage(
            tenant_id="anytoolai",
            region="default",
            guest_id=guest_id,
            product_id="kernel_demo",
            quota_policy_id="kernel_demo.guest_quota_v1",
            quota_dimension=QuotaDimension.product,
            dimension_key="kernel_demo",
            scenario_id=None,
            period_key="lifetime",
            limit_count=1,
        )

    first_session = session_factory()
    second_session = session_factory()
    try:
        first_repo = QuotaUsageRepository(first_session)
        second_repo = QuotaUsageRepository(second_session)
        first_read = first_repo.get(usage.id)
        second_read = second_repo.get(usage.id)
        assert first_read is not None
        assert second_read is not None

        first_consumed = first_repo.consume_if_available(first_read)
        first_session.commit()

        second_consumed = second_repo.consume_if_available(second_read)
        second_session.commit()
    finally:
        first_session.close()
        second_session.close()

    with transaction_boundary(session_factory) as session:
        final_usage = QuotaUsageRepository(session).get(usage.id)

    assert first_consumed is not None
    assert second_consumed is None
    assert final_usage is not None
    assert final_usage.used_count == 1
