from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import event

from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.artifacts.service import ArtifactService
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.providers.models import ProviderCallRecord
from anytoolai_platform_core.providers.repository import ProviderCallRepository
from anytoolai_platform_core.storage.db import artifacts_table
from anytoolai_platform_core.storage.transactions import (
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.structured_output.errors import (
    STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE,
    StructuredOutputValidationError,
)
from anytoolai_platform_core.structured_output.service import (
    StructuredOutputFinalizer,
    StructuredOutputPersistenceContext,
)
from anytoolai_platform_core.structured_output.validator import validate_structured_output

REPO_ROOT = Path(__file__).resolve().parents[5]


def _sqlite_url(database_path: Path) -> str:
    return f"sqlite+pysqlite:///{database_path.resolve().as_posix()}"


@pytest.fixture
def runtime_engine(tmp_path: Path) -> sa.Engine:
    main_db = tmp_path / "structured-output-main.sqlite3"
    platform_db = tmp_path / "structured-output-platform.sqlite3"
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

    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(runtime_engine: sa.Engine) -> sa.orm.sessionmaker[sa.orm.Session]:
    return build_session_factory(runtime_engine)


def _artifact_service(session: sa.orm.Session) -> ArtifactService:
    return ArtifactService(ArtifactRepository(session), EventEmitter(EventLogRepository(session)))


def _context() -> StructuredOutputPersistenceContext:
    return StructuredOutputPersistenceContext(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        action_run_id="action_run_demo",
    )


def _provider_call(action_run_id: str = "action_run_demo") -> ProviderCallRecord:
    return ProviderCallRecord(
        tenant_id="tenant_demo",
        region="eu-central",
        product_id="kernel_demo",
        frontend_id="kernel_demo_ce",
        scenario_session_id="scenario_session_demo",
        job_id="job_demo",
        action_run_id=action_run_id,
        workflow_id="wf_demo",
        workflow_version=1,
        step_id="step_1",
        action_type="text.extract_structured_fields",
        action_config_id="kernel_demo.extract_structured_fields_v1",
        provider_policy_ref="default_fake_provider_v1",
        provider="fake",
        model="fake-json-v1",
        gateway_backend="fake",
        gateway_model="fake-json-v1",
        semantic_attempt_index=2,
        transport_attempt_index=1,
        physical_call_index=2,
    )


def _artifacts(session: sa.orm.Session) -> list[dict[str, Any]]:
    return list(
        session.execute(
            sa.select(artifacts_table).order_by(artifacts_table.c.created_at, artifacts_table.c.id)
        ).mappings()
    )


def test_validate_structured_output_normalizes_frozen_schema_to_plain_dict() -> None:
    result = validate_structured_output(
        '{"outer":{"value":"ok"},"items":["a","b"]}',
        schema=MappingProxyType(
            {
                "type": "object",
                "properties": MappingProxyType(
                    {
                        "outer": MappingProxyType(
                            {
                                "type": "object",
                                "properties": MappingProxyType(
                                    {"value": MappingProxyType({"type": "string"})}
                                ),
                                "required": ("value",),
                                "additionalProperties": False,
                            }
                        ),
                        "items": MappingProxyType(
                            {
                                "type": "array",
                                "items": MappingProxyType({"type": "string"}),
                            }
                        ),
                    }
                ),
                "required": ("outer", "items"),
                "additionalProperties": False,
            }
        ),
    )

    assert result.normalized_output == {
        "outer": {"value": "ok"},
        "items": ["a", "b"],
    }
    assert isinstance(result.normalized_output, dict)
    assert isinstance(result.normalized_output["outer"], dict)
    assert isinstance(result.contract.schema, dict)


def test_validate_structured_output_allows_non_object_json_when_not_required() -> None:
    result = validate_structured_output(
        '["a","b"]',
        schema={"type": "array", "items": {"type": "string"}},
        requires_object=False,
    )

    assert result.normalized_output == ["a", "b"]


def test_structured_output_finalizer_persists_success_artifact(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    with transaction_boundary(session_factory) as session:
        finalizer = StructuredOutputFinalizer(
            artifact_service=_artifact_service(session),
            provider_call_repository=ProviderCallRepository(session),
        )

        result = finalizer.finalize(
            '{"summary":"ok","score":1}',
            persistence_context=_context(),
            schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "score": {"type": "integer"},
                },
                "required": ["summary", "score"],
                "additionalProperties": False,
            },
            schema_ref="kernel.schemas.demo_output_v1",
            schema_version=1,
        )
        artifacts = _artifacts(session)

    assert result.validation_result.normalized_output == {"summary": "ok", "score": 1}
    assert result.artifact.artifact_type == "structured_output"
    assert result.artifact.content_json == {"summary": "ok", "score": 1}
    assert artifacts[0]["artifact_type"] == "structured_output"
    assert artifacts[0]["content_json"] == {"summary": "ok", "score": 1}
    assert artifacts[0]["action_run_id"] == "action_run_demo"


@pytest.mark.parametrize(
    ("raw_text", "reason"),
    [
        ("not-json", "malformed_json"),
        ('["not","an","object"]', "non_object_json"),
        ('{"summary":42}', "schema_mismatch"),
    ],
)
def test_structured_output_finalizer_persists_debug_artifact_for_validation_failures(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
    raw_text: str,
    reason: str,
) -> None:
    with transaction_boundary(session_factory) as session:
        provider_repository = ProviderCallRepository(session)
        provider_repository.create(_provider_call())
        finalizer = StructuredOutputFinalizer(
            artifact_service=_artifact_service(session),
            provider_call_repository=provider_repository,
        )

        with pytest.raises(StructuredOutputValidationError) as exc_info:
            finalizer.finalize(
                raw_text,
                persistence_context=_context(),
                schema={
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                    "additionalProperties": False,
                },
                schema_ref="kernel.schemas.demo_output_v1",
                schema_version=1,
            )
        artifacts = _artifacts(session)

    assert exc_info.value.code == STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE
    assert exc_info.value.reason == reason
    assert "not-json" not in str(exc_info.value)
    assert len(artifacts) == 1
    assert artifacts[0]["artifact_type"] == "structured_output_debug_raw"
    assert artifacts[0]["content_text"] == raw_text
    assert artifacts[0]["action_run_id"] == "action_run_demo"
    assert artifacts[0]["metadata"]["reason"] == reason
    assert artifacts[0]["metadata"]["provider_call_id"].startswith("provider_call_")
    assert artifacts[0]["metadata"]["physical_call_index"] == 2
