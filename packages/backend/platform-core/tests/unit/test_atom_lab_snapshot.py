from __future__ import annotations

from pathlib import Path

import pytest
from anytoolai_platform_core.atom_lab.snapshots import (
    AtomLabSnapshotCompatibilityError,
    AtomLabSnapshotRequest,
    build_atom_lab_run_record,
    load_run_local_action_settings,
)
from anytoolai_platform_core.bootstrap.registry import build_config_registry
from anytoolai_platform_core.providers.models import ReasoningEffort
from anytoolai_platform_core.scenarios.models import ScenarioSessionRecord
from anytoolai_platform_core.workflows.models import JobRecord

CONFIG_ROOT = Path(__file__).resolve().parents[5] / "configs" / "kernel"


def _runtime_records() -> tuple[ScenarioSessionRecord, JobRecord]:
    scenario = ScenarioSessionRecord(
        id="scenario_session_lab",
        tenant_id="anytoolai",
        region="default",
        product_id="kernel_demo",
        frontend_id="kernel_demo_web",
        scenario_id="kernel_demo.atom_lab_a01_v1",
        scenario_version=1,
        metadata={
            "runtime_scope": "atom_lab",
            "input": {"source_text": "snapshot input", "fields": []},
        },
    )
    return scenario, JobRecord(
        id="job_lab",
        tenant_id=scenario.tenant_id,
        region=scenario.region,
        product_id=scenario.product_id,
        frontend_id=scenario.frontend_id,
        scenario_session_id=scenario.id,
        workflow_id="kernel_demo.atom_lab_a01_v1",
        workflow_version=1,
    )


def test_snapshot_builder_captures_registry_definitions_and_typed_local_settings() -> None:
    """Catches snapshots that only retain refs and silently read changed settings later."""
    registry = build_config_registry(CONFIG_ROOT)
    scenario, job = _runtime_records()
    record = build_atom_lab_run_record(
        registry,
        scenario=scenario,
        job=job,
        request=AtomLabSnapshotRequest(
            atom_id="A01",
            input_payload={"source_text": "snapshot input", "fields": []},
            prompt="Edited lab prompt",
            model_id="openai/gpt-5.4-mini",
            reasoning_effort=ReasoningEffort.high,
            capability_snapshot_id="capability_fixture_v1",
            capability_provenance={"source": "fixture", "version": "1"},
        ),
    )

    assert record.action_config_id == "kernel_demo.extract_structured_fields_live_v1"
    assert record.input_schema_ref == "kernel.schemas.extract_input_v1"
    assert record.input_schema["type"] == "object"
    assert record.base_prompt != record.prompt
    assert record.workflow_definition["steps"] == [
        {
            "step_id": "run_atom",
            "action_config_id": "kernel_demo.extract_structured_fields_live_v1",
            "input_mapping": {},
            "output_mapping": {},
            "when": None,
            "retry_count": 0,
            "schema_version": 1,
            "metadata": {},
        }
    ]
    assert record.action_config_definition["metadata"]["atom_lab"]["atom_id"] == "A01"
    assert "emits_events" in record.action_definition
    settings = load_run_local_action_settings(registry, record)
    assert settings.run_id == record.id
    assert settings.prompt == "Edited lab prompt"
    assert settings.provider_policy.model == "openai/gpt-5.4-mini"
    assert settings.reasoning_effort is ReasoningEffort.high


def test_snapshot_compatibility_rejects_registry_drift_before_action_execution() -> None:
    """Catches silently executing a snapshot against a changed registry definition."""
    registry = build_config_registry(CONFIG_ROOT)
    scenario, job = _runtime_records()
    record = build_atom_lab_run_record(
        registry,
        scenario=scenario,
        job=job,
        request=AtomLabSnapshotRequest(
            atom_id="A01",
            input_payload={"source_text": "snapshot input", "fields": []},
            prompt="Edited lab prompt",
            model_id="openai/gpt-5.4-mini",
            reasoning_effort=None,
            capability_snapshot_id="capability_fixture_v1",
            capability_provenance={"source": "fixture", "version": "1"},
        ),
    )

    with pytest.raises(AtomLabSnapshotCompatibilityError):
        load_run_local_action_settings(
            registry,
            record.__class__(
                **{
                    **record.__dict__,
                    "execution_definition_hash": "0" * 64,
                }
            ),
        )
