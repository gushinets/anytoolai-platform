from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityService
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService, QuotaExhaustedError
from anytoolai_platform_core.storage.db import event_log_table
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


def _quota_service(session: sa.orm.Session) -> GuestQuotaService:
    return GuestQuotaService(
        config_registry=build_config_registry(CONFIG_ROOT),
        quota_repository=QuotaUsageRepository(session),
        guest_repository=GuestIdentityRepository(session),
        event_emitter=EventEmitter(EventLogRepository(session)),
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
