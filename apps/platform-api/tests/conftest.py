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
from pathlib import Path

import pytest
from anytoolai_platform_core.storage.db import runtime_metadata
from anytoolai_platform_core.storage.transactions import SessionFactory, build_session_factory

from tests.support.sqlite_harness import build_sqlite_runtime_engine


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
