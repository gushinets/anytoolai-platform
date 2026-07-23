from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from anytoolai_platform_core.artifacts.models import ArtifactRecord, ArtifactStatus
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.events.emitter import EventEmitter
from anytoolai_platform_core.events.repository import EventLogRepository
from anytoolai_platform_core.handoffs.models import (
    AcceptHandoffCommand,
    CreateHandoffCommand,
    HandoffStartPolicy,
    HandoffStatus,
)
from anytoolai_platform_core.handoffs.payloads import HandoffPayloadBuilder
from anytoolai_platform_core.handoffs.repository import HandoffRepository
from anytoolai_platform_core.handoffs.service import (
    HandoffExpiredError,
    HandoffNotActionableError,
    HandoffService,
    HandoffSourceInvalidError,
)
from anytoolai_platform_core.handoffs.tokens import HandoffTokenService
from anytoolai_platform_core.identity.models import GuestIdentityRecord
from anytoolai_platform_core.identity.repository import GuestIdentityRepository
from anytoolai_platform_core.quotas.repository import QuotaUsageRepository
from anytoolai_platform_core.quotas.service import GuestQuotaService
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord, ScenarioSessionStatus
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.scenarios.service import ScenarioRuntimeService, ScenarioSessionService
from anytoolai_platform_core.storage.db import event_log_table, product_handoffs_table
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
from anytoolai_platform_core.workflows.models import JobRecord, JobStatus
from anytoolai_platform_core.workflows.repository import JobRepository
from sqlalchemy import event

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"
SHA256_HEX_LENGTH = 64


def test_handoff_token_service_enforces_256_bit_minimum() -> None:
    token = HandoffTokenService().generate()
    assert token.startswith("hnd_")
    assert len(HandoffTokenService.hash(token)) == SHA256_HEX_LENGTH
    with pytest.raises(ValueError, match="at least 256 bits"):
        HandoffTokenService(entropy_bytes=31).generate()


def _session_factory(tmp_path: Path):
    main_db = tmp_path / "handoff-main.sqlite3"
    platform_db = tmp_path / "handoff-platform.sqlite3"
    engine = sa.create_engine(f"sqlite+pysqlite:///{main_db.as_posix()}", future=True)

    @event.listens_for(engine, "connect")
    def attach(dbapi_connection: Any, connection_record: Any) -> None:
        del connection_record
        dbapi_connection.execute(f"ATTACH DATABASE '{platform_db.as_posix()}' AS platform")

    config = Config()
    config.set_main_option("script_location", str(REPO_ROOT / "migrations" / "platform"))
    config.set_main_option("sqlalchemy.url", f"sqlite+pysqlite:///{main_db.as_posix()}")
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    return build_session_factory(engine)


def _seed_source(session, *, guest_id: str = "guest_handoff") -> tuple[str, str]:
    GuestIdentityRepository(session).create(
        GuestIdentityRecord(id=guest_id, tenant_id="anytoolai", region="default")
    )
    scenario = ScenarioSessionRepository(session).create(
        ScenarioSessionRecord(
            tenant_id="anytoolai",
            region="default",
            product_id="kernel_demo",
            frontend_id="kernel_demo_ce",
            scenario_id="kernel_demo.handoff_smoke_source_v1",
            scenario_version=1,
            guest_id=guest_id,
            status=ScenarioSessionStatus.completed,
            current_checkpoint_id="result_ready",
            scenario_chain_id="chain_handoff",
            completed_at=datetime.now(UTC),
        )
    )
    jobs = JobRepository(session)
    job = jobs.create(
        JobRecord(
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            workflow_id="kernel_demo.single_action_extract_v1",
            workflow_version=1,
        )
    )
    job = jobs.claim_created(job.id)
    assert job is not None
    artifact = ArtifactRepository(session).create(
        ArtifactRecord(
            tenant_id=scenario.tenant_id,
            region=scenario.region,
            product_id=scenario.product_id,
            frontend_id=scenario.frontend_id,
            scenario_session_id=scenario.id,
            job_id=job.id,
            artifact_type="structured_output",
            status=ArtifactStatus.stored,
            content_json={"title": "Safe summary", "fields": ["deadline", "budget"]},
            metadata={
                "artifact_role": "workflow_result",
                "schema_ref": "kernel_demo.extract_output_v1",
                "schema_version": 1,
                "workflow_id": job.workflow_id,
                "workflow_version": job.workflow_version,
            },
        )
    )
    jobs.mark_succeeded(
        replace(
            job,
            status=JobStatus.succeeded,
            result_artifact_id=artifact.id,
            completed_at=datetime.now(UTC),
        )
    )
    return scenario.id, artifact.id


def _service(session, registry, *, clock=lambda: datetime.now(UTC)) -> HandoffService:
    emitter = EventEmitter(EventLogRepository(session))
    sessions = ScenarioSessionRepository(session)
    jobs = JobRepository(session)
    guests = GuestIdentityRepository(session)
    runtime = ScenarioRuntimeService(
        config_registry=registry,
        session_repository=sessions,
        session_service=ScenarioSessionService(sessions, emitter),
        job_repository=jobs,
        event_emitter=emitter,
        quota_service=GuestQuotaService(
            config_registry=registry,
            quota_repository=QuotaUsageRepository(session),
            guest_repository=guests,
            event_emitter=emitter,
        ),
    )
    return HandoffService(
        config_registry=registry,
        repository=HandoffRepository(session),
        payload_builder=HandoffPayloadBuilder(
            config_registry=registry,
            session_repository=sessions,
            job_repository=jobs,
            artifact_repository=ArtifactRepository(session),
        ),
        scenario_runtime=runtime,
        scenario_repository=sessions,
        guest_repository=guests,
        event_emitter=emitter,
        clock=clock,
    )


def _create(service: HandoffService, scenario_id: str, artifact_id: str):
    return service.create_handoff(
        CreateHandoffCommand(
            tenant_id="anytoolai",
            region="default",
            handoff_definition_id="kernel_demo_source_to_target_v1",
            source_scenario_session_id=scenario_id,
            source_artifact_id=artifact_id,
        )
    )


def test_handoff_create_view_accept_and_double_accept(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(factory) as session:
        source_session_id, artifact_id = _seed_source(session)
        created = _create(_service(session, registry), source_session_id, artifact_id)
        row = session.execute(sa.select(product_handoffs_table)).mappings().one()
        assert created.handoff_token.startswith("hnd_")
        assert created.handoff_token not in str(dict(row))
        assert len(row["token_hash"]) == SHA256_HEX_LENGTH

    with transaction_boundary(factory) as session:
        service = _service(session, registry)
        viewed = service.get_preview(created.handoff_token, tenant_id="anytoolai", region="default")
        assert viewed.status is HandoffStatus.viewed
        assert viewed.preview == {"title": "Safe summary", "fields": ["deadline", "budget"]}
        service.get_preview(created.handoff_token, tenant_id="anytoolai", region="default")

    with transaction_boundary(factory) as session:
        accepted = _service(session, registry).accept(
            created.handoff_token,
            AcceptHandoffCommand(tenant_id="anytoolai", region="default"),
        )
        assert accepted.preview.status is HandoffStatus.consumed
        assert accepted.preview.target_scenario_session_id is not None
        assert accepted.preview.target_job_id is not None
        target = ScenarioSessionRepository(session).get_in_scope(
            accepted.preview.target_scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert target is not None
        assert target.parent_scenario_session_id == source_session_id
        assert target.metadata["handoff_id"] == accepted.preview.handoff_id
        assert target.metadata["input"] == {"source_text": "Safe summary"}

    with transaction_boundary(factory) as session:
        with pytest.raises(HandoffNotActionableError) as error:
            _service(session, registry).accept(
                created.handoff_token,
                AcceptHandoffCommand(tenant_id="anytoolai", region="default"),
            )
        assert error.value.code == "handoff_already_accepted"
        events = list(session.execute(sa.select(event_log_table.c.event_type)).scalars())
        assert events.count("handoff.viewed") == 1
        assert events.count("handoff.accepted") == 1
        assert events.count("handoff.consumed") == 1


@pytest.mark.parametrize(
    "artifact_changes",
    [
        {"artifact_type": "structured_output_debug_raw"},
        {"status": ArtifactStatus.failed},
        {"action_run_id": "action_run_untrusted"},
        {"content_json": None},
        {"metadata": {"artifact_role": "debug"}},
    ],
)
def test_handoff_rejects_noncanonical_or_schema_invalid_artifacts(
    tmp_path: Path,
    artifact_changes: dict[str, Any],
) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        artifacts = ArtifactRepository(session)
        artifact = artifacts.get(artifact_id)
        assert artifact is not None
        artifacts.update(replace(artifact, **artifact_changes))

        with pytest.raises(HandoffSourceInvalidError):
            _create(_service(session, registry), source_id, artifact_id)


def test_handoff_context_must_pass_target_workflow_input_schema(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    target_workflow = registry.get_workflow("kernel_demo.single_action_extract_v1")
    assert target_workflow is not None
    strict_registry = replace(
        registry,
        workflows={
            **registry.workflows,
            target_workflow.workflow_id: replace(
                target_workflow,
                input_schema_ref="kernel_demo.extract_input_v1",
            ),
        },
    )
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        artifacts = ArtifactRepository(session)
        artifact = artifacts.get(artifact_id)
        assert artifact is not None
        artifacts.update(replace(artifact, content_json={"title": 123, "fields": []}))

        with pytest.raises(HandoffSourceInvalidError):
            _create(_service(session, strict_registry), source_id, artifact_id)


def test_handoff_revalidates_full_source_artifact_before_mapping(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    source_schema = registry.get_schema("kernel_demo.extract_output_v1")
    assert source_schema is not None
    strict_registry = replace(
        registry,
        schemas={
            **registry.schemas,
            source_schema.schema_ref: replace(
                source_schema,
                schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "minLength": 1},
                        "fields": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["title", "fields"],
                    "additionalProperties": False,
                },
            ),
        },
    )
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        artifacts = ArtifactRepository(session)
        artifact = artifacts.get(artifact_id)
        assert artifact is not None
        # The mapped target source_text remains valid; only an unmapped source field is invalid.
        artifacts.update(
            replace(
                artifact,
                content_json={"title": "target-valid title", "fields": "not-an-array"},
            )
        )

        with pytest.raises(HandoffSourceInvalidError):
            _create(_service(session, strict_registry), source_id, artifact_id)


def test_handoff_preview_is_allowlisted_and_bounded(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        artifacts = ArtifactRepository(session)
        artifact = artifacts.get(artifact_id)
        assert artifact is not None
        artifacts.update(
            replace(
                artifact,
                content_json={
                    "title": "safe target input",
                    "fields": ["x" * 600 for _ in range(20)],
                    "raw_provider_output": "must never appear",
                    "debug_metadata": {"model": "must never appear"},
                },
            )
        )
        created = _create(_service(session, registry), source_id, artifact_id)

        assert created.preview.preview == {"summary": "[TRUNCATED]"}
        serialized = str(created.preview)
        assert "raw_provider_output" not in serialized
        assert "debug_metadata" not in serialized


def test_handoff_decline_expiry_and_deferred_target(tmp_path: Path) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    current = [datetime(2026, 7, 22, 12, 0, tzinfo=UTC)]
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        created = _create(
            _service(session, registry, clock=lambda: current[0]), source_id, artifact_id
        )
    current[0] += timedelta(minutes=31)
    with transaction_boundary(factory) as session:
        preview = _service(session, registry, clock=lambda: current[0]).get_preview(
            created.handoff_token, tenant_id="anytoolai", region="default"
        )
        assert preview.status is HandoffStatus.expired
        with pytest.raises(HandoffExpiredError):
            _service(session, registry, clock=lambda: current[0]).accept(
                created.handoff_token,
                AcceptHandoffCommand(tenant_id="anytoolai", region="default"),
            )

    deferred_definition = replace(
        registry.get_handoff("kernel_demo_source_to_target_v1"),
        target_start_policy=HandoffStartPolicy.deferred,
    )
    deferred_registry = replace(
        registry,
        handoffs={deferred_definition.handoff_id: deferred_definition},
    )
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session, guest_id="guest_deferred")
        service = _service(session, deferred_registry)
        deferred = _create(service, source_id, artifact_id)
        accepted = service.accept(
            deferred.handoff_token,
            AcceptHandoffCommand(tenant_id="anytoolai", region="default"),
        )
        assert accepted.preview.status is HandoffStatus.accepted
        assert accepted.preview.target_job_id is None
        snapshot = service._scenario_runtime.get_session_snapshot(  # verifies A12 jobless retrieval
            accepted.preview.target_scenario_session_id,
            tenant_id="anytoolai",
            region="default",
        )
        assert snapshot.job_id is None
        assert snapshot.current_checkpoint_id == "handoff_ready"


@pytest.mark.parametrize("operation", ["preview", "decline", "accept"])
def test_handoff_transition_cannot_cross_expiry_boundary(
    tmp_path: Path,
    operation: str,
) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    created_at = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        created = _create(
            _service(session, registry, clock=lambda: created_at),
            source_id,
            artifact_id,
        )

    expires_at = created.preview.expires_at
    clock_values = iter((expires_at - timedelta(microseconds=1), expires_at))
    with transaction_boundary(factory) as session:
        service = _service(session, registry, clock=lambda: next(clock_values))
        if operation == "preview":
            preview = service.get_preview(
                created.handoff_token,
                tenant_id="anytoolai",
                region="default",
            )
            assert preview.status is HandoffStatus.expired
        elif operation == "decline":
            with pytest.raises(HandoffExpiredError):
                service.decline(
                    created.handoff_token,
                    tenant_id="anytoolai",
                    region="default",
                )
        else:
            with pytest.raises(HandoffExpiredError):
                service.accept(
                    created.handoff_token,
                    AcceptHandoffCommand(tenant_id="anytoolai", region="default"),
                )

        row = (
            session.execute(
                sa.select(product_handoffs_table).where(
                    product_handoffs_table.c.id == created.preview.handoff_id
                )
            )
            .mappings()
            .one()
        )
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).where(
                    event_log_table.c.handoff_id == created.preview.handoff_id
                )
            ).scalars()
        )

        assert row["status"] == HandoffStatus.expired.value
        assert row["viewed_at"] is None
        assert row["declined_at"] is None
        assert row["accepted_at"] is None
        assert event_types.count("handoff.expired") == 1
        assert "handoff.viewed" not in event_types
        assert "handoff.declined" not in event_types
        assert "handoff.accepted" not in event_types


@pytest.mark.parametrize("competing_transition", ["decline", "expire"])
def test_reserved_quota_failure_blocks_competing_terminal_transition(
    tmp_path: Path,
    competing_transition: str,
) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    created_at = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        created = _create(
            _service(session, registry, clock=lambda: created_at),
            source_id,
            artifact_id,
        )
        reserved = HandoffRepository(session).reserve_quota_failure_recovery(
            created.preview.handoff_id,
            error_code="quota_exhausted",
            now=created_at,
        )
        assert reserved is True

    with transaction_boundary(factory) as session:
        service = _service(session, registry, clock=lambda: created_at)
        if competing_transition == "decline":
            with pytest.raises(HandoffNotActionableError) as error:
                service.decline(
                    created.handoff_token,
                    tenant_id="anytoolai",
                    region="default",
                )
            assert error.value.code == "handoff_failed"
        else:
            record = service.get_by_id(
                created.preview.handoff_id,
                tenant_id="anytoolai",
                region="default",
            )
            unchanged = service.expire(record, now=created.preview.expires_at)
            assert unchanged.status is HandoffStatus.created
            assert unchanged.error_code == "quota_exhausted"

    with transaction_boundary(factory) as session:
        service = _service(session, registry)
        failed = service.mark_failed(
            created.preview.handoff_id,
            tenant_id="anytoolai",
            region="default",
            error_code="quota_exhausted",
        )
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).where(
                    event_log_table.c.handoff_id == created.preview.handoff_id
                )
            ).scalars()
        )

        assert failed.status is HandoffStatus.failed
        assert failed.error_code == "quota_exhausted"
        assert failed.declined_at is None
        assert failed.expired_at is None
        assert event_types.count("handoff.failed") == 1
        assert "handoff.declined" not in event_types
        assert "handoff.expired" not in event_types


@pytest.mark.parametrize(
    "terminal_status",
    [
        HandoffStatus.accepted,
        HandoffStatus.consumed,
        HandoffStatus.declined,
        HandoffStatus.failed,
    ],
)
def test_expired_terminal_handoff_token_is_redacted_without_mutating_state(
    tmp_path: Path,
    terminal_status: HandoffStatus,
) -> None:
    factory = _session_factory(tmp_path)
    registry = build_config_registry(CONFIG_ROOT)
    if terminal_status is HandoffStatus.accepted:
        definition = registry.get_handoff("kernel_demo_source_to_target_v1")
        assert definition is not None
        deferred_definition = replace(
            definition,
            target_start_policy=HandoffStartPolicy.deferred,
        )
        registry = replace(
            registry,
            handoffs={deferred_definition.handoff_id: deferred_definition},
        )

    current = [datetime(2026, 7, 23, 12, 0, tzinfo=UTC)]
    with transaction_boundary(factory) as session:
        source_id, artifact_id = _seed_source(session)
        service = _service(session, registry, clock=lambda: current[0])
        created = _create(service, source_id, artifact_id)

        if terminal_status in {HandoffStatus.accepted, HandoffStatus.consumed}:
            service.accept(
                created.handoff_token,
                AcceptHandoffCommand(tenant_id="anytoolai", region="default"),
            )
        elif terminal_status is HandoffStatus.declined:
            service.decline(
                created.handoff_token,
                tenant_id="anytoolai",
                region="default",
            )
        else:
            service.mark_failed(
                created.preview.handoff_id,
                tenant_id="anytoolai",
                region="default",
                error_code="handoff_acceptance_failed",
            )

        stored = service.get_by_id(
            created.preview.handoff_id,
            tenant_id="anytoolai",
            region="default",
        )
        unexpired = service.get_preview(
            created.handoff_token,
            tenant_id="anytoolai",
            region="default",
        )
        assert stored.status is terminal_status
        assert unexpired.status is terminal_status
        assert unexpired.preview == created.preview.preview
        assert unexpired.target_scenario_session_id == stored.target_scenario_session_id
        assert unexpired.target_job_id == stored.target_job_id

    current[0] += timedelta(minutes=31)
    with transaction_boundary(factory) as session:
        service = _service(session, registry, clock=lambda: current[0])
        expired = service.get_preview(
            created.handoff_token,
            tenant_id="anytoolai",
            region="default",
        )
        assert expired.status is HandoffStatus.expired
        assert expired.preview == {}
        assert expired.target_scenario_session_id is None
        assert expired.target_job_id is None

        with pytest.raises(HandoffExpiredError):
            service.accept(
                created.handoff_token,
                AcceptHandoffCommand(tenant_id="anytoolai", region="default"),
            )
        with pytest.raises(HandoffExpiredError):
            service.decline(
                created.handoff_token,
                tenant_id="anytoolai",
                region="default",
            )

        stored = service.get_by_id(
            created.preview.handoff_id,
            tenant_id="anytoolai",
            region="default",
        )
        event_types = list(
            session.execute(
                sa.select(event_log_table.c.event_type).where(
                    event_log_table.c.handoff_id == created.preview.handoff_id
                )
            ).scalars()
        )
        assert stored.status is terminal_status
        assert stored.expired_at is None
        assert stored.target_scenario_session_id == unexpired.target_scenario_session_id
        assert stored.target_job_id == unexpired.target_job_id
        assert "handoff.expired" not in event_types
