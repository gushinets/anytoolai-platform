from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterator

import pytest
import sqlalchemy as sa

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
from tests.db_support import provision_database

REPO_ROOT = Path(__file__).resolve().parents[5]
pytestmark = [pytest.mark.postgresql, pytest.mark.slow]


@pytest.fixture
def session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_artifact_service_test",
        skip_reason="PostgreSQL artifact service coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


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
        "metadata": {
            "schema_ref": "kernel.schemas.extract_output_v1",
            "workflow_id": "kernel_demo.single_action_extract_v1",
            "workflow_version": 1,
            "guest_id": "guest_demo",
            "user_id": "user_demo",
            "scenario_chain_id": "scenario_chain_demo",
            "handoff_id": "handoff_demo",
            "acquisition_source": "kernel_demo_ce",
            "action_type": "text.extract_structured_fields",
            "action_config_id": "kernel_demo.extract_structured_fields_v1",
            "provider_call_id": "provider_call_demo",
            "provider_policy_ref": "default_fake_provider_v1",
            "physical_call_index": 2,
            "pydantic_run_id": "pydantic_run_demo",
            "prompt_text": "must not leak",
        },
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
    event = events[0]
    assert event["workflow_id"] == "kernel_demo.single_action_extract_v1"
    assert event["workflow_version"] == 1
    assert event["guest_id"] == "guest_demo"
    assert event["user_id"] == "user_demo"
    assert event["scenario_chain_id"] == "scenario_chain_demo"
    assert event["handoff_id"] == "handoff_demo"
    assert event["acquisition_source"] == "kernel_demo_ce"
    assert event["action_type"] == "text.extract_structured_fields"
    assert event["action_config_id"] == "kernel_demo.extract_structured_fields_v1"
    assert event["provider_call_id"] == "provider_call_demo"
    assert event["provider_policy_ref"] == "default_fake_provider_v1"
    assert event["physical_call_index"] == 2
    assert event["pydantic_run_id"] == "pydantic_run_demo"
    assert event["properties"] == {"artifact_type": "structured_output"}
    assert "prompt_text" not in event["properties"]
