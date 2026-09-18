from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import timedelta
from http import HTTPStatus
from pathlib import Path

import httpx
import pytest
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.providers.catalog import ModelCatalogItem
from anytoolai_platform_core.providers.catalog_repository import ModelCatalogRepository
from anytoolai_platform_core.providers.models import (
    ModelCatalogCompatibility,
    ModelCatalogReason,
)
from anytoolai_platform_core.storage.transactions import transaction_boundary

from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
ACCESS_CODE = "atom-lab-models-test-code"
pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


async def _request(app, method: str, path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.request(
            method,
            path,
            headers={"X-Atom-Lab-Access-Code": ACCESS_CODE},
        )


@pytest.fixture
def database_url() -> Iterator[str]:
    with provision_database(
        database_name_prefix="anytoolai_atom_lab_models_api_test",
        skip_reason="PostgreSQL Atom Lab model catalog API coverage",
    ) as (_engine, _alembic_config, database_url):
        yield database_url


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, database_url: str):
    monkeypatch.setenv("ANYTOOLAI_ATOM_LAB_ACCESS_CODE", ACCESS_CODE)
    monkeypatch.setenv("ANYTOOLAI_MODEL_CATALOG_ACCOUNT_SCOPE", "test-account")
    return create_app(config_root=CONFIG_ROOT, database_url=database_url)


def test_empty_catalog_is_explicitly_pending_stale_and_not_executable(app) -> None:
    response = asyncio.run(_request(app, "GET", "/v1/atom-lab/models"))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "items": [],
        "snapshot_id": None,
        "last_success_at": None,
        "stale": True,
        "refresh_status": "pending",
        "error": "Каталог моделей ещё не загружен.",
    }


def test_manual_refresh_returns_accepted_pending_state(app) -> None:
    response = asyncio.run(_request(app, "POST", "/v1/atom-lab/models/refresh"))

    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json()["refresh_status"] == "pending"
    assert response.json()["stale"] is True


def test_get_models_returns_last_good_catalog_without_credentials(app) -> None:
    now = utc_now()
    with transaction_boundary(app.state.runtime.storage.session_factory) as session:
        repository = ModelCatalogRepository(session)
        repository.request_refresh("test-account", now=now)
        lease = repository.claim_refresh(
            "test-account", now=now, lease_duration=timedelta(seconds=30)
        )
        assert lease is not None
        repository.complete_refresh(
            lease,
            snapshot_id="snapshot-1",
            items=(
                ModelCatalogItem(
                    model_id="gpt-one",
                    compatibility=ModelCatalogCompatibility.compatible,
                    reason=ModelCatalogReason.confirmed_openai_text_gpt,
                    reasoning_supported=True,
                    allowed_reasoning_efforts=None,
                    provenance={
                        "availability": {
                            "source": "openai_models_api",
                            "fetched_at": now.isoformat(),
                        }
                    },
                ),
            ),
            now=now,
            ttl=timedelta(hours=24),
        )

    response = asyncio.run(_request(app, "GET", "/v1/atom-lab/models"))

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["snapshot_id"] == "snapshot-1"
    assert payload["refresh_status"] == "current"
    assert payload["items"][0]["allowed_reasoning_efforts"] is None
    assert "OPENAI_API_KEY" not in response.text


def test_manual_refresh_during_cooldown_returns_pending(app) -> None:
    now = utc_now()
    with transaction_boundary(app.state.runtime.storage.session_factory) as session:
        repository = ModelCatalogRepository(session)
        lease = repository.claim_refresh(
            "test-account", now=now, lease_duration=timedelta(seconds=30)
        )
        assert lease is not None
        repository.complete_refresh(
            lease,
            snapshot_id="snapshot-current",
            items=(),
            now=now,
            ttl=timedelta(hours=24),
        )

    response = asyncio.run(_request(app, "POST", "/v1/atom-lab/models/refresh"))

    assert response.status_code == HTTPStatus.ACCEPTED
    assert response.json()["snapshot_id"] == "snapshot-current"
    assert response.json()["refresh_status"] == "pending"


def test_get_models_returns_stale_last_good_catalog_after_refresh_failure(app) -> None:
    now = utc_now()
    with transaction_boundary(app.state.runtime.storage.session_factory) as session:
        repository = ModelCatalogRepository(session)
        lease = repository.claim_refresh(
            "test-account", now=now, lease_duration=timedelta(seconds=30)
        )
        assert lease is not None
        repository.complete_refresh(
            lease,
            snapshot_id="snapshot-last-good",
            items=(
                ModelCatalogItem(
                    model_id="gpt-last-good",
                    compatibility=ModelCatalogCompatibility.compatible,
                    reason=ModelCatalogReason.confirmed_openai_text_gpt,
                    reasoning_supported=True,
                    allowed_reasoning_efforts=None,
                    provenance={"availability": {"source": "openai_models_api"}},
                ),
            ),
            now=now - timedelta(hours=25),
            ttl=timedelta(hours=24),
        )

    with transaction_boundary(app.state.runtime.storage.session_factory) as session:
        repository = ModelCatalogRepository(session)
        repository.request_refresh("test-account", now=now)
        lease = repository.claim_refresh(
            "test-account", now=now, lease_duration=timedelta(seconds=30)
        )
        assert lease is not None
        repository.fail_refresh(
            lease,
            error="Upstream model catalog refresh failed.",
            now=now,
            retry_after=timedelta(seconds=60),
        )

    response = asyncio.run(_request(app, "GET", "/v1/atom-lab/models"))

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["snapshot_id"] == "snapshot-last-good"
    assert [item["model_id"] for item in payload["items"]] == ["gpt-last-good"]
    assert payload["stale"] is True
    assert payload["refresh_status"] == "pending"
    assert payload["error"] == "Upstream model catalog refresh failed."
