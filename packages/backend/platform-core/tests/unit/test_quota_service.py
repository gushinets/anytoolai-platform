from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.handoffs.models import (
    HandoffRecord,
    HandoffStartPolicy,
    HandoffStatus,
)
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.identity.service import GuestIdentityService
from anytoolai_platform_core.quotas.models import QuotaDimension
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService, QuotaExhaustedError
from anytoolai_platform_core.storage.db import (
    event_log_table,
    guest_quota_usage_table,
)
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_quota_service_test",
        skip_reason="PostgreSQL quota service coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


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


def _create_recoverable_handoff(
    session: sa.orm.Session,
    *,
    guest_id: str,
) -> HandoffRecord:
    now = utc_now()
    return HandoffRepository(session).create(
        HandoffRecord(
            handoff_definition_id="kernel_demo.summary_to_action_v1",
            tenant_id="anytoolai",
            region="default",
            token_hash="test_handoff_quota_recovery_token_hash",
            source_product_id="kernel_demo",
            source_frontend_id="kernel_demo_ce",
            source_scenario_id="kernel_demo.single_action_smoke_v1",
            source_scenario_session_id="scenario_session_source_handoff",
            source_job_id="job_source_handoff",
            source_artifact_id="artifact_source_handoff",
            target_product_id="kernel_demo",
            target_frontend_id="kernel_demo_ce",
            target_scenario_id="kernel_demo.handoff_smoke_target_v1",
            scenario_chain_id="scenario_chain_handoff",
            created_by_guest_id=guest_id,
            consent_required=False,
            target_start_policy=HandoffStartPolicy.immediate,
            context_payload={},
            preview_payload={},
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(minutes=30),
        )
    )


def _consume_accepted_start(
    service: GuestQuotaService,
    *,
    guest_id: str,
    scenario_id: str,
    scenario_session_id: str,
    scenario_chain_id: str | None = None,
    handoff_id: str | None = None,
):
    validation = service.validate_accepted_start(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        guest_id=guest_id,
        scenario_id=scenario_id,
    )
    assert validation is not None
    return service.consume_for_accepted_start(
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        guest_id=guest_id,
        scenario_id=scenario_id,
        scenario_session_id=scenario_session_id,
        scenario_chain_id=scenario_chain_id,
        handoff_id=handoff_id,
        validation=validation,
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

        first = _consume_accepted_start(
            service,
            guest_id=guest_id,
            scenario_id="kernel_demo.single_action_smoke_v1",
            scenario_session_id="scenario_session_product_first",
        )
        second = _consume_accepted_start(
            service,
            guest_id=guest_id,
            scenario_id="kernel_demo.multi_step_workflow_smoke_v1",
            scenario_session_id="scenario_session_product_second",
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
            _consume_accepted_start(
                service,
                guest_id=guest_id,
                scenario_id=first_scenario_id,
                scenario_session_id=f"scenario_session_first_{index}",
            )
            for index in range(3)
        ]
        with pytest.raises(QuotaExhaustedError):
            _consume_accepted_start(
                service,
                guest_id=guest_id,
                scenario_id=first_scenario_id,
                scenario_session_id="scenario_session_first_exhausted",
            )
        second_scenario_state = _consume_accepted_start(
            service,
            guest_id=guest_id,
            scenario_id=second_scenario_id,
            scenario_session_id="scenario_session_second_first",
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
            _consume_accepted_start(
                service,
                guest_id=guest_id,
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_session_id=f"scenario_session_demo_{index}",
                scenario_chain_id=f"scenario_session_demo_{index}",
            )
            for index in range(3)
        ]
        with pytest.raises(QuotaExhaustedError):
            _consume_accepted_start(
                service,
                guest_id=guest_id,
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_session_id="scenario_session_demo_exhausted",
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
        _consume_accepted_start(
            _quota_service(session, registry=registry),
            guest_id=guest_id,
            scenario_id="kernel_demo.single_action_smoke_v1",
            scenario_session_id="scenario_session_rejected_non_handoff",
            scenario_chain_id="scenario_chain_non_handoff",
        )

    with transaction_boundary(session_factory) as session:
        usage = session.execute(sa.select(guest_quota_usage_table)).mappings().one()
        quota_events = list(
            session.execute(
                sa.select(event_log_table)
                .where(
                    event_log_table.c.scenario_session_id
                    == "scenario_session_rejected_non_handoff"
                )
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
        event["scenario_session_id"] == "scenario_session_rejected_non_handoff"
        for event in quota_events
    )
    assert all(event["handoff_id"] is None for event in quota_events)
    assert quota_events[-1]["error_code"] == "quota_exhausted"
    assert quota_events[-1]["properties"]["exhausted"] is True


def test_handoff_quota_exhaustion_recovery_survives_caller_transaction_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    registry = _registry_with_quota_limit(0)
    with transaction_boundary(session_factory) as session:
        guest_id = _create_guest(session)
        handoff = _create_recoverable_handoff(session, guest_id=guest_id)

    with pytest.raises(QuotaExhaustedError), transaction_boundary(
        session_factory
    ) as session:
        _consume_accepted_start(
            _quota_service(session, registry=registry),
            guest_id=guest_id,
            scenario_id="kernel_demo.handoff_smoke_target_v1",
            scenario_session_id="scenario_session_rejected_handoff",
            scenario_chain_id="scenario_chain_handoff",
            handoff_id=handoff.id,
        )

    with transaction_boundary(session_factory) as session:
        recovered = HandoffRepository(session).get_by_id(
            handoff.id,
            tenant_id="anytoolai",
            region="default",
        )
        assert recovered is not None
        quota_events = list(
            session.execute(
                sa.select(event_log_table)
                .where(event_log_table.c.handoff_id == handoff.id)
                .order_by(event_log_table.c.timestamp, event_log_table.c.event_id)
            ).mappings()
        )

    assert recovered.status is HandoffStatus.failed
    assert recovered.error_code == "quota_exhausted"
    assert [event["event_type"] for event in quota_events] == [
        "quota.checked",
        "quota.exhausted",
        "handoff.failed",
    ]
    assert quota_events[0]["scenario_session_id"] == "scenario_session_rejected_handoff"
    assert quota_events[1]["scenario_session_id"] == "scenario_session_rejected_handoff"
    assert quota_events[1]["error_code"] == "quota_exhausted"
    assert quota_events[2]["error_code"] == "quota_exhausted"
    assert quota_events[2]["properties"]["error_code"] == "quota_exhausted"
