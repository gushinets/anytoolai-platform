"""Shared fixtures for apps/platform-api/tests -- a module-level fixture of the same name (e.g.
test_scenario_runtime_api.py's PostgreSQL-backed `session_factory`) always overrides this one for
that module, per normal pytest fixture resolution; this only fills in for suites that don't define
their own.

Code review finding (ANY-227): this exact SQLite `session_factory` fixture body was duplicated
verbatim across test_demo_api.py and test_proposal_ai_bundle.py -- moved here once a second real
consumer proved it, per the repo's own "extract shared abstractions only once a second use proves
them" rule.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import httpx
import pytest
from anytoolai_platform_api.bootstrap import RuntimeStorageDependencies
from anytoolai_platform_api.main import create_app
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.storage.db import runtime_metadata
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)

from tests.support.sqlite_harness import build_sqlite_runtime_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


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


@pytest.fixture
def platform_api_app_factory(session_factory: SessionFactory):
    """Shared by test_proposal_ai_bundle.py and test_client_update_writer_bundle.py (ANY-414 code
    review finding: this exact `app` fixture body -- seed one guest identity, build the app, swap
    in the SQLite-backed session_factory -- was duplicated verbatim across the two). A plain
    module-level function importable across `apps/platform-api/tests/` subdirectories would need
    a package-qualified import path that's ambiguous in this monorepo's multi-root pytest layout
    (this same directory's own `tests.support.sqlite_harness` import resolves to the *top-level*
    `tests/` package, not this one) -- a fixture, discovered by pytest without any import, sidesteps
    that entirely. Returns a factory (not the app directly) since each caller needs its own
    guest_id."""

    def _make(*, guest_id: str) -> Any:
        with transaction_boundary(session_factory) as session:
            GuestIdentityRepository(session).create(
                GuestIdentityRecord(id=guest_id, tenant_id="anytoolai", region="default")
            )
        application = create_app(config_root=CONFIG_ROOT)
        application.state.runtime = replace(
            application.state.runtime,
            storage=RuntimeStorageDependencies(session_factory=session_factory),
        )
        return application

    return _make


@pytest.fixture
def request_platform_api():
    """Shared by test_proposal_ai_bundle.py and test_client_update_writer_bundle.py -- same
    duplication, same fixture-not-import reasoning as `platform_api_app_factory` above."""

    async def _request(
        app: Any,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        request_id: str,
    ) -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(
                method,
                path,
                json=json,
                headers={"X-Request-ID": request_id},
            )

    return _request
