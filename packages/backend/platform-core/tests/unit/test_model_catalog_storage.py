from __future__ import annotations

import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.providers.catalog import ModelCatalogItem
from anytoolai_platform_core.providers.catalog_refresh import ModelCatalogRefreshService
from anytoolai_platform_core.providers.catalog_repository import ModelCatalogRepository
from anytoolai_platform_core.providers.models import (
    ModelCatalogCompatibility,
    ModelCatalogRefreshStatus,
)
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_model_catalog_test",
        skip_reason="PostgreSQL model catalog lease coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


EXPECTED_REFRESH_CALLS = 2


@pytest.fixture
def now(session_factory: sa.orm.sessionmaker[sa.orm.Session]) -> datetime:
    return datetime.now(UTC)


def _item(model_id: str) -> ModelCatalogItem:
    return ModelCatalogItem(
        model_id=model_id,
        compatibility=ModelCatalogCompatibility.compatible,
        reason="confirmed_openai_text_gpt",
        reasoning_supported=None,
        allowed_reasoning_efforts=None,
        provenance={"availability": {"source": "openai_models_api"}},
    )


def test_manual_refresh_coalesces_and_obeys_cooldown(
    session_factory: sa.orm.sessionmaker[sa.orm.Session], now: datetime
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ModelCatalogRepository(session)
        first = repository.request_refresh("account-a", now=now, cooldown=timedelta(seconds=60))
        second = repository.request_refresh(
            "account-a", now=now + timedelta(seconds=1), cooldown=timedelta(seconds=60)
        )
        assert first.refresh_status(now) is ModelCatalogRefreshStatus.pending
        assert second.refresh_requested_at == first.refresh_requested_at

    with transaction_boundary(session_factory) as session:
        repository = ModelCatalogRepository(session)
        lease = repository.claim_refresh("account-a", now=now, lease_duration=timedelta(seconds=30))
        assert lease is not None
        repository.complete_refresh(
            lease,
            snapshot_id="snapshot-1",
            items=(_item("gpt-one"),),
            now=now + timedelta(seconds=2),
            ttl=timedelta(hours=24),
        )

    with transaction_boundary(session_factory) as session:
        state = ModelCatalogRepository(session).request_refresh(
            "account-a", now=now + timedelta(seconds=20), cooldown=timedelta(seconds=60)
        )
        assert (
            state.refresh_status(now + timedelta(seconds=20)) is ModelCatalogRefreshStatus.current
        )
        assert state.snapshot_id == "snapshot-1"


def test_only_one_postgresql_lease_is_claimed_and_expired_lease_is_recoverable(
    session_factory: sa.orm.sessionmaker[sa.orm.Session], now: datetime
) -> None:
    with transaction_boundary(session_factory) as session:
        ModelCatalogRepository(session).request_refresh(
            "account-a", now=now, cooldown=timedelta(seconds=60)
        )

    def claim(at: datetime) -> str | None:
        with transaction_boundary(session_factory) as session:
            lease = ModelCatalogRepository(session).claim_refresh(
                "account-a", now=at, lease_duration=timedelta(seconds=30)
            )
            return None if lease is None else lease.lease_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed = list(executor.map(claim, (now, now)))
    assert sum(value is not None for value in claimed) == 1
    assert claim(now + timedelta(seconds=31)) is not None


def test_due_snapshot_and_expired_lease_report_pending(
    session_factory: sa.orm.sessionmaker[sa.orm.Session], now: datetime
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ModelCatalogRepository(session)
        lease = repository.claim_refresh("account-a", now=now, lease_duration=timedelta(seconds=30))
        assert lease is not None
        assert (
            repository.get("account-a").refresh_status(now + timedelta(seconds=31))
            is ModelCatalogRefreshStatus.pending
        )


def test_failed_refresh_keeps_last_good_snapshot_and_marks_it_stale(
    session_factory: sa.orm.sessionmaker[sa.orm.Session], now: datetime
) -> None:
    with transaction_boundary(session_factory) as session:
        repository = ModelCatalogRepository(session)
        repository.request_refresh("account-a", now=now, cooldown=timedelta(seconds=60))
        lease = repository.claim_refresh("account-a", now=now, lease_duration=timedelta(seconds=30))
        assert lease is not None
        repository.complete_refresh(
            lease,
            snapshot_id="snapshot-1",
            items=(_item("gpt-one"),),
            now=now,
            ttl=timedelta(hours=24),
        )

    with transaction_boundary(session_factory) as session:
        repository = ModelCatalogRepository(session)
        repository.request_refresh(
            "account-a", now=now + timedelta(seconds=61), cooldown=timedelta(seconds=60)
        )
        lease = repository.claim_refresh(
            "account-a", now=now + timedelta(seconds=61), lease_duration=timedelta(seconds=30)
        )
        assert lease is not None
        repository.fail_refresh(
            lease,
            error="Upstream model catalog refresh failed.",
            now=now + timedelta(seconds=62),
            retry_after=timedelta(seconds=60),
        )

    with transaction_boundary(session_factory) as session:
        state = ModelCatalogRepository(session).get("account-a")
        assert state is not None
        assert state.snapshot_id == "snapshot-1"
        assert [item.model_id for item in state.items] == ["gpt-one"]
        assert state.is_stale(now + timedelta(seconds=62)) is True
        assert state.last_error == "Upstream model catalog refresh failed."


@pytest.mark.parametrize("finalizer", ["complete", "fail"])
def test_expired_lease_cannot_finalize_catalog_state(
    session_factory: sa.orm.sessionmaker[sa.orm.Session], finalizer: str
) -> None:
    expired_start = datetime.now(UTC) - timedelta(minutes=1)
    with transaction_boundary(session_factory) as session:
        repository = ModelCatalogRepository(session)
        lease = repository.claim_refresh(
            f"account-{finalizer}",
            now=expired_start,
            lease_duration=timedelta(seconds=30),
        )
        assert lease is not None

    with (
        pytest.raises(ValueError, match="lease is no longer owned"),
        transaction_boundary(session_factory) as session,
    ):
        repository = ModelCatalogRepository(session)
        if finalizer == "complete":
            repository.complete_refresh(
                lease,
                snapshot_id="expired-snapshot",
                items=(_item("gpt-expired"),),
                now=expired_start,
                ttl=timedelta(hours=24),
            )
        else:
            repository.fail_refresh(
                lease,
                error="must not publish",
                now=expired_start,
                retry_after=timedelta(seconds=60),
            )


def test_refresh_service_loads_initial_snapshot_and_refreshes_after_ttl(
    session_factory: sa.orm.sessionmaker[sa.orm.Session], now: datetime
) -> None:
    class Source:
        def __init__(self) -> None:
            self.calls = 0

        async def fetch_openai_model_ids(self) -> tuple[str, ...]:
            self.calls += 1
            return (f"gpt-{self.calls}",)

        async def fetch_litellm_metadata(self) -> dict[str, dict[str, object]]:
            return {
                f"gpt-{self.calls}": {
                    "litellm_provider": "openai",
                    "mode": "chat",
                    "supported_output_modalities": ["text"],
                }
            }

    source = Source()
    current_time = [now]
    service = ModelCatalogRefreshService(
        session_factory=session_factory,
        account_scope="account-a",
        source=source,
        overrides={},
        ttl=timedelta(hours=24),
        retry_after=timedelta(seconds=60),
        lease_duration=timedelta(seconds=30),
        now=lambda: current_time[0],
    )

    asyncio.run(service.refresh_if_due())
    current_time[0] = now + timedelta(hours=24, seconds=1)
    asyncio.run(service.refresh_if_due())

    with transaction_boundary(session_factory) as session:
        state = ModelCatalogRepository(session).get("account-a")
        assert state is not None
        assert [item.model_id for item in state.items] == ["gpt-2"]
        assert state.last_error is None
    assert source.calls == EXPECTED_REFRESH_CALLS
