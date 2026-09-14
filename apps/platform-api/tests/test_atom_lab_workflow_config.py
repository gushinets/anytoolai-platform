from __future__ import annotations

from pathlib import Path

from anytoolai_platform_core.config.loader import ConfigLoader
from anytoolai_platform_core.workflows.mappings import resolve_step_input

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "configs" / "kernel"

EXPECTED_LAB_BINDINGS = {
    "A01": "kernel_demo.extract_structured_fields_live_v1",
    "A02": "kernel_demo.score_match_by_rubric_live_v1",
    "A03": "kernel_demo.score_multidimensional_axes_live_v1",
    "A04": "kernel_demo.detect_issues_live_v1",
    "A05": "kernel_demo.generate_clarifying_questions_live_v1",
    "A06": "kernel_demo.compose_persuasive_text_live_v1",
    "A07": "kernel_demo.compose_reply_live_v1",
    "A08": "kernel_demo.generate_gap_rewrites_live_v1",
    "A09": "kernel_demo.synthesize_angle_live_v1",
    "A10": "kernel_demo.generate_report_live_v1",
    "A11": "kernel_demo.compare_and_classify_live_v1",
}


def test_atom_lab_has_eleven_internal_full_payload_workflow_bindings() -> None:
    """Catches a missing lab binding or accidental reuse of smoke literal mappings."""
    registry = ConfigLoader(CONFIG_ROOT).load()

    for atom_id, action_config_id in EXPECTED_LAB_BINDINGS.items():
        scenario_id = f"kernel_demo.atom_lab_{atom_id.lower()}_v1"
        workflow_id = f"kernel_demo.atom_lab_{atom_id.lower()}_v1"
        scenario = registry.get_scenario(scenario_id)
        workflow = registry.get_workflow(workflow_id)

        assert scenario is not None
        assert scenario.internal_only is True
        assert scenario.workflow_id == workflow_id
        assert workflow is not None
        assert len(workflow.steps) == 1
        assert workflow.steps[0].action_config_id == action_config_id
        assert workflow.steps[0].input_mapping == {}

        action_config = registry.get_action_configuration(action_config_id)
        assert action_config is not None
        action = registry.get_action_definition(action_config.action_type)
        assert action is not None
        assert workflow.input_schema_ref == action.input_schema_ref
        assert workflow.output_schema_ref == action.output_schema_ref


def test_empty_lab_mapping_preserves_non_smoke_values_and_optional_semantics() -> None:
    """Catches replacing full-payload passthrough with fixed smoke literals."""
    payload = {
        "source_text": "Значение, которого нет в smoke fixtures",
        "strict": False,
        "optional_null": None,
        "zero": 0,
        "empty": "",
        "nested": {"items": [False, 0, None]},
    }

    assert (
        resolve_step_input(
            input_mapping={},
            scenario_input=payload,
            step_outputs={},
            context={},
        )
        == payload
    )
