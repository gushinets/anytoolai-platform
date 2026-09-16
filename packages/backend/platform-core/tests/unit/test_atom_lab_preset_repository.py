from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from anytoolai_platform_core.atom_lab.models import (
    ATOM_LAB_REGION,
    ATOM_LAB_TENANT_ID,
    AtomLabPresetIdentityRecord,
    AtomLabPresetVersionRecord,
    AtomLabRunRecord,
    ReasoningEffort,
)
from anytoolai_platform_core.atom_lab.repository import (
    AtomLabPresetRepository,
    AtomLabRunRepository,
)
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


def _snapshot(preset_id: str | None, preset_version: int | None) -> AtomLabRunRecord:
    return AtomLabRunRecord(
        tenant_id=ATOM_LAB_TENANT_ID,
        region=ATOM_LAB_REGION,
        product_id="kernel_demo",
        frontend_id="kernel_demo_web",
        scenario_session_id="scenario_session_lab",
        job_id="job_lab",
        atom_id="A01",
        scenario_id="kernel_demo.atom_lab_a01_v1",
        scenario_version=1,
        workflow_id="kernel_demo.atom_lab_a01_v1",
        workflow_version=1,
        step_id="run_atom",
        action_type="text.extract_structured_fields",
        action_definition_version=1,
        action_config_id="kernel_demo.extract_structured_fields_live_v1",
        action_config_schema_version=1,
        prompt_ref="kernel_demo.extract_structured_fields.v1",
        prompt_version=1,
        base_prompt="Base prompt",
        prompt="Edited prompt",
        input_schema_ref="kernel.schemas.extract_input_v1",
        input_schema_version=1,
        input_schema={"type": "object"},
        output_schema_ref="kernel.schemas.extract_output_v1",
        output_schema_version=1,
        output_schema={"type": "object"},
        input_payload={"source_text": "fixture", "fields": [], "strict": False},
        provider_policy_ref="default_text_generation_v1",
        provider_policy={},
        model_id="openai/gpt-5.4-mini",
        reasoning_effort=ReasoningEffort.high,
        capability_snapshot_id="capability_snapshot_1",
        capability_provenance={},
        workflow_definition={},
        action_definition={},
        action_config_definition={},
        execution_definition_hash="a" * 64,
        preset_id=preset_id,
        preset_version=preset_version,
    )


def _seed_runtime(session_factory: SessionFactory) -> None:
    with transaction_boundary(session_factory) as session:
        scenario = ScenarioSessionRepository(session).create(
            ScenarioSessionRecord(
                id="scenario_session_lab",
                tenant_id=ATOM_LAB_TENANT_ID,
                region=ATOM_LAB_REGION,
                product_id="kernel_demo",
                frontend_id="kernel_demo_web",
                scenario_id="kernel_demo.atom_lab_a01_v1",
                scenario_version=1,
                metadata={"runtime_scope": "atom_lab", "input": {}},
            )
        )
        JobRepository(session).create(
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


def test_run_snapshot_accepts_only_complete_matching_preset_reference(
    session_factory: SessionFactory,
) -> None:
    _seed_runtime(session_factory)
    with transaction_boundary(session_factory) as session:
        identity = AtomLabPresetIdentityRecord()
        AtomLabPresetRepository(session).create(identity, _preset_version(identity.id))
        stored = AtomLabRunRepository(session).create(_snapshot(identity.id, 1))
        assert stored.preset_id == identity.id
        assert stored.preset_version == 1

    with (
        pytest.raises(ValueError, match="preset reference is incomplete"),
        transaction_boundary(session_factory) as session,
    ):
        AtomLabRunRepository(session).create(_snapshot(identity.id, None))


def test_run_snapshot_rejects_preset_for_different_atom_contract(
    session_factory: SessionFactory,
) -> None:
    _seed_runtime(session_factory)
    with transaction_boundary(session_factory) as session:
        identity = AtomLabPresetIdentityRecord()
        AtomLabPresetRepository(session).create(
            identity,
            _preset_version(identity.id, atom_id="A02"),
        )

    with (
        pytest.raises(ValueError, match="preset provenance"),
        transaction_boundary(session_factory) as session,
    ):
        AtomLabRunRepository(session).create(_snapshot(identity.id, 1))


def test_saved_version_round_trips_without_requiring_current_model_catalog(
    session_factory: SessionFactory,
) -> None:
    with transaction_boundary(session_factory) as session:
        identity = AtomLabPresetIdentityRecord()
        stored = AtomLabPresetRepository(session).create(
            identity,
            _preset_version(identity.id, model_id="openai/removed-historical-model"),
        )

    with transaction_boundary(session_factory) as session:
        reopened = AtomLabPresetRepository(session).get_version(
            identity.id,
            1,
            tenant_id=ATOM_LAB_TENANT_ID,
            region=ATOM_LAB_REGION,
        )

    assert reopened == stored
    assert reopened is not None
    assert reopened.model_id == "openai/removed-historical-model"


def test_source_run_requires_matching_lab_scope_and_provenance(
    session_factory: SessionFactory,
) -> None:
    _seed_runtime(session_factory)
    with transaction_boundary(session_factory) as session:
        source = AtomLabRunRepository(session).create(_snapshot(None, None))
        identity = AtomLabPresetIdentityRecord()
        stored = AtomLabPresetRepository(session).create(
            identity,
            _preset_version(identity.id, source_run_id=source.id),
        )
        assert stored.source_run_id == source.id

    with (
        pytest.raises(ValueError, match="provenance"),
        transaction_boundary(session_factory) as session,
    ):
        mismatched = AtomLabPresetIdentityRecord()
        AtomLabPresetRepository(session).create(
            mismatched,
            _preset_version(
                mismatched.id,
                atom_id="A02",
                source_run_id=source.id,
            ),
        )
