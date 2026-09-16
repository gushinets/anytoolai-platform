from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from typing import Any

import pytest
import sqlalchemy as sa
from anytoolai_platform_core.actions.models import ActionRunRecord
from anytoolai_platform_core.actions.repository import ActionRunRepository
from anytoolai_platform_core.actions.runner import _recover_atom_lab_action_link_after_rollback
from anytoolai_platform_core.artifacts.models import ArtifactRecord
from anytoolai_platform_core.artifacts.repository import ArtifactRepository
from anytoolai_platform_core.atom_lab.models import (
    AtomLabPresetIdentityRecord,
    AtomLabPresetVersionRecord,
    AtomLabRunRecord,
    ReasoningEffort,
)
from anytoolai_platform_core.atom_lab.repository import (
    AtomLabPresetRepository,
    AtomLabRunRepository,
    PresetVersionConflictError,
)
from anytoolai_platform_core.common.time import utc_now
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.transactions import build_session_factory, transaction_boundary
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository

from tests.db_support import provision_database

pytestmark = [pytest.mark.postgresql, pytest.mark.slow]
SECOND_VERSION = 2


@pytest.fixture
def session_factory() -> Iterator[sa.orm.sessionmaker[sa.orm.Session]]:
    with provision_database(
        database_name_prefix="anytoolai_atom_lab_storage_test",
        skip_reason="PostgreSQL Atom Lab snapshot coverage",
    ) as (engine, _alembic_config, _database_url):
        yield build_session_factory(engine)


def _snapshot(**overrides: Any) -> AtomLabRunRecord:
    values: dict[str, Any] = {
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_web",
        "scenario_session_id": "scenario_session_lab",
        "job_id": "job_lab",
        "atom_id": "A01",
        "scenario_id": "kernel_demo.atom_lab_a01_v1",
        "scenario_version": 1,
        "workflow_id": "kernel_demo.atom_lab_a01_v1",
        "workflow_version": 1,
        "step_id": "run_atom",
        "action_type": "text.extract_structured_fields",
        "action_definition_version": 1,
        "action_config_id": "kernel_demo.extract_structured_fields_live_v1",
        "action_config_schema_version": 1,
        "prompt_ref": "kernel_demo.extract_structured_fields.v1",
        "prompt_version": 1,
        "base_prompt": "Base prompt",
        "prompt": "Edited prompt",
        "input_schema_ref": "kernel.schemas.extract_input_v1",
        "input_schema_version": 1,
        "input_schema": {"type": "object"},
        "output_schema_ref": "kernel.schemas.extract_output_v1",
        "output_schema_version": 1,
        "output_schema": {"type": "object"},
        "input_payload": {"source_text": "exact lab input", "strict": False},
        "provider_policy_ref": "default_text_generation_v1",
        "provider_policy": {
            "provider": "litellm",
            "temperature": 1.0,
            "timeout_seconds": 60,
            "transport_max_attempts": 2,
            "validation_max_attempts": 2,
            "max_physical_provider_calls_per_action": 4,
        },
        "model_id": "openai/gpt-5.4-mini",
        "reasoning_effort": ReasoningEffort.high,
        "capability_snapshot_id": "capability_snapshot_1",
        "capability_provenance": {"source": "fixture", "version": "1"},
        "workflow_definition": {"input_mapping": {}},
        "action_definition": {"executor": "structured_llm"},
        "action_config_definition": {"prompt_ref": "kernel_demo.extract_structured_fields.v1"},
        "execution_definition_hash": "a" * 64,
    }
    values.update(overrides)
    return AtomLabRunRecord(**values)


def test_snapshot_round_trips_and_runtime_ids_are_fill_once(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """Catches snapshot mutation or replacement of already-bound execution IDs."""
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_lab",
                tenant_id="tenant_demo",
                region="eu-central",
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                scenario_id="kernel_demo.atom_lab_a01_v1",
                scenario_version=1,
                metadata={
                    "runtime_scope": "atom_lab",
                    "input": {"source_text": "exact lab input", "strict": False},
                },
            )
        )
        job = JobRepository(session).create(
            JobRecord(
                id="job_lab",
                tenant_id=scenario.tenant_id,
                region=scenario.region,
                product_id=scenario.product_id,
                frontend_id=scenario.frontend_id,
                scenario_session_id=scenario.id,
                workflow_id="kernel_demo.atom_lab_a01_v1",
                workflow_version=1,
            )
        )
        action_run = ActionRunRepository(session).create(
            ActionRunRecord(
                id="action_run_1",
                tenant_id=scenario.tenant_id,
                region=scenario.region,
                product_id=scenario.product_id,
                frontend_id=scenario.frontend_id,
                scenario_session_id=scenario.id,
                job_id=job.id,
                workflow_id=job.workflow_id,
                step_id="run_atom",
                action_type="text.extract_structured_fields",
                action_config_id="kernel_demo.extract_structured_fields_live_v1",
            )
        )
        ArtifactRepository(session).create(
            ArtifactRecord(
                id="artifact_1",
                tenant_id=scenario.tenant_id,
                region=scenario.region,
                product_id=scenario.product_id,
                frontend_id=scenario.frontend_id,
                scenario_session_id=scenario.id,
                job_id=job.id,
                action_run_id=action_run.id,
                artifact_type="structured_output",
            )
        )
        repository = AtomLabRunRepository(session)
        stored = repository.create(_snapshot())
        original_snapshot = stored.snapshot_payload()

    _recover_atom_lab_action_link_after_rollback(
        session_factory,
        run_id=stored.id,
        action_run_id="action_run_1",
    )

    with transaction_boundary(session_factory) as session:
        repository = AtomLabRunRepository(session)
        bound = repository.bind_runtime_ids(
            stored.id,
            artifact_id="artifact_1",
        )

        assert bound.action_run_id == "action_run_1"
        assert bound.artifact_id == "artifact_1"
        assert bound.snapshot_payload() == original_snapshot
        with pytest.raises(ValueError, match="already bound"):
            repository.bind_runtime_ids(stored.id, action_run_id="action_run_2")


def test_snapshot_create_rejects_non_lab_or_mismatched_runtime_link(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """Catches orphan snapshots and snapshots attached to ordinary jobs."""
    with (
        pytest.raises(ValueError, match="Atom Lab scenario session"),
        transaction_boundary(session_factory) as session,
    ):
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_public",
                tenant_id="tenant_demo",
                region="eu-central",
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                scenario_id="kernel_demo.single_action_smoke_v1",
                scenario_version=1,
                metadata={"input": {}},
            )
        )
        JobRepository(session).create(
            JobRecord(
                id="job_public",
                tenant_id=scenario.tenant_id,
                region=scenario.region,
                product_id=scenario.product_id,
                frontend_id=scenario.frontend_id,
                scenario_session_id=scenario.id,
                workflow_id="kernel_demo.single_action_extract_v1",
                workflow_version=1,
            )
        )
        AtomLabRunRepository(session).create(
            replace(
                _snapshot(),
                scenario_session_id=scenario.id,
                job_id="job_public",
            )
        )


def test_runtime_id_binding_is_fill_once_under_postgresql_concurrency(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    """Catches two reconcilers overwriting a previously null action link."""
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_lab",
                tenant_id="tenant_demo",
                region="eu-central",
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                scenario_id="kernel_demo.atom_lab_a01_v1",
                scenario_version=1,
                metadata={
                    "runtime_scope": "atom_lab",
                    "input": {"source_text": "exact lab input", "strict": False},
                },
            )
        )
        job = JobRepository(session).create(
            JobRecord(
                id="job_lab",
                tenant_id=scenario.tenant_id,
                region=scenario.region,
                product_id=scenario.product_id,
                frontend_id=scenario.frontend_id,
                scenario_session_id=scenario.id,
                workflow_id="kernel_demo.atom_lab_a01_v1",
                workflow_version=1,
            )
        )
        for action_run_id in ("action_run_one", "action_run_two"):
            ActionRunRepository(session).create(
                ActionRunRecord(
                    id=action_run_id,
                    tenant_id=scenario.tenant_id,
                    region=scenario.region,
                    product_id=scenario.product_id,
                    frontend_id=scenario.frontend_id,
                    scenario_session_id=scenario.id,
                    job_id=job.id,
                    workflow_id=job.workflow_id,
                    step_id="run_atom",
                    action_type="text.extract_structured_fields",
                    action_config_id="kernel_demo.extract_structured_fields_live_v1",
                )
            )
        record = AtomLabRunRepository(session).create(_snapshot())

    def bind(action_run_id: str) -> str:
        try:
            with transaction_boundary(session_factory) as session:
                AtomLabRunRepository(session).bind_runtime_ids(
                    record.id,
                    action_run_id=action_run_id,
                )
            return action_run_id
        except ValueError as exc:
            assert "already bound" in str(exc)
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(bind, ("action_run_one", "action_run_two")))

    assert outcomes.count("conflict") == 1
    with transaction_boundary(session_factory) as session:
        stored = AtomLabRunRepository(session).get(record.id)
        assert stored is not None
        assert stored.action_run_id in {"action_run_one", "action_run_two"}


def test_preset_version_number_is_atomic_under_postgresql_concurrency(
    session_factory: sa.orm.sessionmaker[sa.orm.Session],
) -> None:
    identity = AtomLabPresetIdentityRecord(
        tenant_id="tenant_demo",
        region="eu-central",
    )
    base_values: dict[str, Any] = {
        "preset_id": identity.id,
        "version": 1,
        "name": "Version one",
        "description": "Initial preset",
        "atom_id": "A01",
        "base_action_config_id": "kernel_demo.extract_structured_fields_live_v1",
        "input_schema_ref": "kernel.schemas.extract_input_v1",
        "input_schema_version": 1,
        "output_schema_ref": "kernel.schemas.extract_output_v1",
        "output_schema_version": 1,
        "prompt": "Initial prompt",
        "prompt_ref": "kernel_demo.extract_structured_fields.v1",
        "model_id": "openai/gpt-5.4-mini",
        "reasoning_effort": ReasoningEffort.high,
        "fixed_fields": ("fields",),
        "example_input": {"source_text": "fixture", "fields": [], "strict": False},
        "tenant_id": identity.tenant_id,
        "region": identity.region,
    }
    with transaction_boundary(session_factory) as session:
        AtomLabPresetRepository(session).create(
            identity,
            AtomLabPresetVersionRecord(**base_values),
        )

    def save_version(name: str) -> str:
        try:
            with transaction_boundary(session_factory) as session:
                AtomLabPresetRepository(session).add_version(
                    AtomLabPresetVersionRecord(
                        **{
                            **base_values,
                            "version": SECOND_VERSION,
                            "name": name,
                            "created_at": utc_now(),
                        }
                    ),
                    base_version=1,
                )
            return name
        except PresetVersionConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(save_version, ("Version two A", "Version two B")))

    assert outcomes.count("conflict") == 1
    with transaction_boundary(session_factory) as session:
        repository = AtomLabPresetRepository(session)
        stored_identity = repository.get_identity(
            identity.id,
            tenant_id=identity.tenant_id,
            region=identity.region,
        )
        versions = repository.list_versions(
            identity.id,
            tenant_id=identity.tenant_id,
            region=identity.region,
            limit=10,
        )
    assert stored_identity is not None
    assert stored_identity.latest_version == SECOND_VERSION
    assert [version.version for version in versions] == [SECOND_VERSION, 1]
