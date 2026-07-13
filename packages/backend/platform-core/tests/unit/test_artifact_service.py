from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import event

from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.storage.db import artifacts_table, event_log_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)

REPO_ROOT = Path(__file__).resolve().parents[5]


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def session_factory(tmp_path: Path) -> sa.orm.sessionmaker[sa.orm.Session]:
    main_db = tmp_path / "artifact-service-main.sqlite3"
    platform_db = tmp_path / "artifact-service-platform.sqlite3"
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

    try:
        yield build_session_factory(engine)
    finally:
        engine.dispose()


def _make_artifact(**overrides: Any) -> ArtifactRecord:
    values = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "action_run_id": "action_run_demo",
        "artifact_type": "structured_output",
        "content_json": {"title": "Kernel Demo Source Summary"},
        "metadata": {"schema_ref": "kernel.schemas.extract_output_v1"},
    }
    values.update(overrides)
    return ArtifactRecord(**values)


def test_artifact_service_persists_created_artifact_once_after_transaction_rollback(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with pytest.raises(RuntimeError, match="force rollback"):
        with transaction_boundary(session_factory) as session:
            service = ArtifactService(
                ArtifactRepository(session),
                EventEmitter(EventLogRepository(session)),
            )
            service.create(_make_artifact())
            raise RuntimeError("force rollback")

    with transaction_boundary(session_factory) as session:
        artifacts = session.execute(sa.select(artifacts_table)).mappings().all()
        events = session.execute(sa.select(event_log_table)).mappings().all()

    assert len(artifacts) == 1
    assert Counter(str(row["event_type"]) for row in events) == Counter(
        {"artifact.created": 1}
    )
