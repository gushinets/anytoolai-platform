from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from anytoolai_platform_core.atom_lab.models import (
    AtomLabPresetIdentityRecord,
    AtomLabPresetVersionRecord,
    AtomLabRunRecord,
    ReasoningEffort,
)
from anytoolai_platform_core.atom_lab.repository import (
    AtomLabPresetRepository,
    AtomLabRunRepository,
)
from anytoolai_platform_core.atom_lab.snapshots import (
    AtomLabSnapshotRequest,
    build_atom_lab_run_record,
)
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.scenarios.repository import ScenarioSessionRepository
from anytoolai_platform_core.storage.db import runtime_metadata
from anytoolai_platform_core.storage.transactions import (
    SessionFactory,
    build_session_factory,
    transaction_boundary,
)
from anytoolai_platform_core.workflows.models import JobRecord
from anytoolai_platform_core.workflows.repository import JobRepository

from tests.support.sqlite_harness import build_sqlite_runtime_engine

CONFIG_ROOT = Path(__file__).resolve().parents[5] / "configs" / "kernel"
TENANT_ID = "tenant_demo"
REGION = "eu-central"


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


def _preset_version(preset_id: str, **overrides: Any) -> AtomLabPresetVersionRecord:
    values: dict[str, Any] = {
        "preset_id": preset_id,
        "version": 1,
        "name": "Extract fields",
        "description": "Preset fixture",
        "atom_id": "A01",
        "base_action_config_id": "kernel_demo.extract_structured_fields_live_v1",
        "input_schema_ref": "kernel.schemas.extract_input_v1",
        "input_schema_version": 1,
        "output_schema_ref": "kernel.schemas.extract_output_v1",
        "output_schema_version": 1,
        "prompt": "Edited prompt",
        "prompt_ref": "kernel_demo.extract_structured_fields.v1",
        "model_id": "openai/gpt-5.4-mini",
        "reasoning_effort": ReasoningEffort.high,
        "fixed_fields": ("fields",),
        "example_input": {"source_text": "fixture", "fields": [], "strict": False},
    }
    values.update(overrides)
    return AtomLabPresetVersionRecord(**values)


def _seed_runtime(session_factory: SessionFactory) -> AtomLabRunRecord:
    input_payload = {"source_text": "fixture", "fields": [], "strict": False}
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_lab",
                tenant_id=TENANT_ID,
                region=REGION,
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                scenario_id="kernel_demo.atom_lab_a01_v1",
                scenario_version=1,
                metadata={"runtime_scope": "atom_lab", "input": input_payload},
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
    return build_atom_lab_run_record(
        build_config_registry(CONFIG_ROOT),
        scenario=scenario,
        job=job,
        request=AtomLabSnapshotRequest(
            atom_id="A01",
            input_payload=input_payload,
            prompt="Edited prompt",
            model_id="openai/gpt-5.4-mini",
            reasoning_effort=ReasoningEffort.high,
            capability_snapshot_id="capability_snapshot_1",
            capability_provenance={},
        ),
    )


def test_run_snapshot_accepts_only_complete_matching_preset_reference(
    session_factory: SessionFactory,
) -> None:
    snapshot = _seed_runtime(session_factory)
    with transaction_boundary(session_factory) as session:
        identity = AtomLabPresetIdentityRecord(
            tenant_id=snapshot.tenant_id,
            region=snapshot.region,
            atom_id="A01",
        )
        AtomLabPresetRepository(session).create(
            identity,
            _preset_version(
                identity.id,
                tenant_id=snapshot.tenant_id,
                region=snapshot.region,
            ),
        )
        stored = AtomLabRunRepository(session).create(
            replace(snapshot, preset_id=identity.id, preset_version=1)
        )
        assert stored.preset_id == identity.id
        assert stored.preset_version == 1

    with (
        pytest.raises(ValueError, match="preset reference is incomplete"),
        transaction_boundary(session_factory) as session,
    ):
        AtomLabRunRepository(session).create(
            replace(snapshot, id="atom_lab_run_incomplete", preset_id=identity.id)
        )


def test_run_snapshot_rejects_preset_for_different_atom_contract(
    session_factory: SessionFactory,
) -> None:
    snapshot = _seed_runtime(session_factory)
    with transaction_boundary(session_factory) as session:
        identity = AtomLabPresetIdentityRecord(
            tenant_id=snapshot.tenant_id,
            region=snapshot.region,
            atom_id="A02",
        )
        AtomLabPresetRepository(session).create(
            identity,
            _preset_version(
                identity.id,
                atom_id="A02",
                tenant_id=snapshot.tenant_id,
                region=snapshot.region,
            ),
        )

    with (
        pytest.raises(ValueError, match="preset provenance"),
        transaction_boundary(session_factory) as session,
    ):
        AtomLabRunRepository(session).create(
            replace(snapshot, preset_id=identity.id, preset_version=1)
        )


def test_saved_version_round_trips_without_requiring_current_model_catalog(
    session_factory: SessionFactory,
) -> None:
    with transaction_boundary(session_factory) as session:
        identity = AtomLabPresetIdentityRecord(
            tenant_id=TENANT_ID,
            region=REGION,
            atom_id="A01",
        )
        stored = AtomLabPresetRepository(session).create(
            identity,
            _preset_version(
                identity.id,
                tenant_id=TENANT_ID,
                region=REGION,
                model_id="openai/removed-historical-model",
            ),
        )

    with transaction_boundary(session_factory) as session:
        reopened = AtomLabPresetRepository(session).get_version(
            identity.id,
            1,
            tenant_id=TENANT_ID,
            region=REGION,
        )

    assert reopened == stored
    assert reopened is not None
    assert reopened.model_id == "openai/removed-historical-model"


def test_source_run_requires_matching_lab_scope_and_provenance(
    session_factory: SessionFactory,
) -> None:
    snapshot = _seed_runtime(session_factory)
    with transaction_boundary(session_factory) as session:
        source = AtomLabRunRepository(session).create(snapshot)
        identity = AtomLabPresetIdentityRecord(
            tenant_id=snapshot.tenant_id,
            region=snapshot.region,
            atom_id="A01",
        )
        stored = AtomLabPresetRepository(session).create(
            identity,
            _preset_version(
                identity.id,
                tenant_id=snapshot.tenant_id,
                region=snapshot.region,
                source_run_id=source.id,
            ),
        )
        assert stored.source_run_id == source.id

    with (
        pytest.raises(ValueError, match="provenance"),
        transaction_boundary(session_factory) as session,
    ):
        mismatched = AtomLabPresetIdentityRecord(
            tenant_id=snapshot.tenant_id,
            region=snapshot.region,
            atom_id="A02",
        )
        AtomLabPresetRepository(session).create(
            mismatched,
            _preset_version(
                mismatched.id,
                atom_id="A02",
                tenant_id=snapshot.tenant_id,
                region=snapshot.region,
                source_run_id=source.id,
            ),
        )


def test_create_rejects_identity_that_does_not_point_to_version_one(
    session_factory: SessionFactory,
) -> None:
    identity = AtomLabPresetIdentityRecord(
        tenant_id=TENANT_ID,
        region=REGION,
        atom_id="A01",
        latest_version=2,
    )

    with (
        pytest.raises(ValueError, match="start at version 1"),
        transaction_boundary(session_factory) as session,
    ):
        AtomLabPresetRepository(session).create(
            identity,
            _preset_version(identity.id, tenant_id=TENANT_ID, region=REGION),
        )


def test_new_version_cannot_switch_preset_atom(
    session_factory: SessionFactory,
) -> None:
    with transaction_boundary(session_factory) as session:
        identity = AtomLabPresetIdentityRecord(
            tenant_id=TENANT_ID,
            region=REGION,
            atom_id="A01",
        )
        repository = AtomLabPresetRepository(session)
        repository.create(
            identity,
            _preset_version(identity.id, tenant_id=TENANT_ID, region=REGION),
        )

    with (
        pytest.raises(ValueError, match="preset atom"),
        transaction_boundary(session_factory) as session,
    ):
        AtomLabPresetRepository(session).add_version(
            _preset_version(
                identity.id,
                version=2,
                atom_id="A02",
                tenant_id=TENANT_ID,
                region=REGION,
            ),
            base_version=1,
        )

    with transaction_boundary(session_factory) as session:
        versions = AtomLabPresetRepository(session).list_versions(
            identity.id,
            tenant_id=TENANT_ID,
            region=REGION,
            limit=10,
        )
    assert [version.version for version in versions] == [1]
