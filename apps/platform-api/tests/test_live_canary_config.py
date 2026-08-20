"""ANY-221: ConfigLoader-only regression guard for the 11 live-provider scenarios added
alongside the deterministic (fake-provider) kernel_demo atoms. No HTTP/DB/network -- verifies the
static config wiring only, same spirit as test_config_loader.py's
test_loader_builds_registry_from_current_tree() but scoped to what's new here: each live scenario
resolves to a 1-step workflow whose action_config points at default_text_generation_v1 and
otherwise matches its fake sibling's action_type/schema refs/prompt_ref exactly (a regression
guard that the fake sibling itself wasn't mutated by this addition).
"""

from __future__ import annotations

from pathlib import Path

from anytoolai_platform_core.config.loader import ConfigLoader

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"

# fake sibling action_config_id -> live sibling action_config_id, one entry per generic atom --
# see scripts/agent/live_canary.py's LIVE_ATOM_SCENARIO_IDS for the matching scenario-id map.
LIVE_ATOM_ACTION_CONFIG_IDS: dict[str, str] = {
    "kernel_demo.extract_structured_fields_v1": "kernel_demo.extract_structured_fields_live_v1",
    "kernel_demo.detect_issues_v1": "kernel_demo.detect_issues_live_v1",
    "kernel_demo.generate_report_v1": "kernel_demo.generate_report_live_v1",
    "kernel_demo.compose_reply_v1": "kernel_demo.compose_reply_live_v1",
    "kernel_demo.generate_clarifying_questions_v1": (
        "kernel_demo.generate_clarifying_questions_live_v1"
    ),
    "kernel_demo.synthesize_angle_v1": "kernel_demo.synthesize_angle_live_v1",
    "kernel_demo.compose_persuasive_text_v1": "kernel_demo.compose_persuasive_text_live_v1",
    "kernel_demo.generate_gap_rewrites_v1": "kernel_demo.generate_gap_rewrites_live_v1",
    "kernel_demo.compare_and_classify_v1": "kernel_demo.compare_and_classify_live_v1",
    "kernel_demo.score_match_by_rubric_v1": "kernel_demo.score_match_by_rubric_live_v1",
    "kernel_demo.score_multidimensional_axes_v1": (
        "kernel_demo.score_multidimensional_axes_live_v1"
    ),
}

# fake action_config_id -> (workflow_id, scenario_id) for its live sibling. Explicit, not derived
# by string substitution: the extract atom's ids are irregularly named (see
# configs/kernel/products/kernel_demo/scenarios.yaml), so no single suffix rule covers all 11.
LIVE_ATOM_WORKFLOW_AND_SCENARIO_IDS: dict[str, tuple[str, str]] = {
    "kernel_demo.extract_structured_fields_v1": (
        "kernel_demo.single_action_extract_live_v1",
        "kernel_demo.single_action_live_smoke_v1",
    ),
    "kernel_demo.detect_issues_v1": (
        "kernel_demo.single_action_detect_issues_live_v1",
        "kernel_demo.single_action_detect_issues_live_smoke_v1",
    ),
    "kernel_demo.generate_report_v1": (
        "kernel_demo.single_action_generate_report_live_v1",
        "kernel_demo.single_action_generate_report_live_smoke_v1",
    ),
    "kernel_demo.compose_reply_v1": (
        "kernel_demo.single_action_compose_reply_live_v1",
        "kernel_demo.single_action_compose_reply_live_smoke_v1",
    ),
    "kernel_demo.generate_clarifying_questions_v1": (
        "kernel_demo.single_action_generate_clarifying_questions_live_v1",
        "kernel_demo.single_action_generate_clarifying_questions_live_smoke_v1",
    ),
    "kernel_demo.synthesize_angle_v1": (
        "kernel_demo.single_action_synthesize_angle_live_v1",
        "kernel_demo.single_action_synthesize_angle_live_smoke_v1",
    ),
    "kernel_demo.compose_persuasive_text_v1": (
        "kernel_demo.single_action_compose_persuasive_text_live_v1",
        "kernel_demo.single_action_compose_persuasive_text_live_smoke_v1",
    ),
    "kernel_demo.generate_gap_rewrites_v1": (
        "kernel_demo.single_action_generate_gap_rewrites_live_v1",
        "kernel_demo.single_action_generate_gap_rewrites_live_smoke_v1",
    ),
    "kernel_demo.compare_and_classify_v1": (
        "kernel_demo.single_action_compare_and_classify_live_v1",
        "kernel_demo.single_action_compare_and_classify_live_smoke_v1",
    ),
    "kernel_demo.score_match_by_rubric_v1": (
        "kernel_demo.single_action_score_match_by_rubric_live_v1",
        "kernel_demo.single_action_score_match_by_rubric_live_smoke_v1",
    ),
    "kernel_demo.score_multidimensional_axes_v1": (
        "kernel_demo.single_action_score_multidimensional_axes_live_v1",
        "kernel_demo.single_action_score_multidimensional_axes_live_smoke_v1",
    ),
}


def test_live_atom_config_maps_cover_all_eleven_generic_atoms() -> None:
    assert len(LIVE_ATOM_ACTION_CONFIG_IDS) == 11
    assert LIVE_ATOM_ACTION_CONFIG_IDS.keys() == LIVE_ATOM_WORKFLOW_AND_SCENARIO_IDS.keys()


def test_live_scenarios_resolve_to_a_one_step_workflow_on_the_live_provider_policy() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()

    for fake_action_config_id, live_action_config_id in LIVE_ATOM_ACTION_CONFIG_IDS.items():
        fake_action_config = registry.get_action_configuration(fake_action_config_id)
        assert fake_action_config is not None, fake_action_config_id
        live_action_config = registry.get_action_configuration(live_action_config_id)
        assert live_action_config is not None, live_action_config_id

        assert live_action_config.action_type == fake_action_config.action_type
        assert live_action_config.prompt_ref == fake_action_config.prompt_ref
        assert live_action_config.provider_policy_ref == "default_text_generation_v1"
        # The fake sibling must still point at the fake provider -- this addition must not have
        # mutated it.
        assert fake_action_config.provider_policy_ref == "default_fake_provider_v1"

        live_workflow_id, live_scenario_id = LIVE_ATOM_WORKFLOW_AND_SCENARIO_IDS[
            fake_action_config_id
        ]
        live_workflow = registry.get_workflow(live_workflow_id)
        assert live_workflow is not None, live_workflow_id
        assert len(live_workflow.steps) == 1
        assert live_workflow.steps[0].action_config_id == live_action_config_id

        live_scenario = registry.get_scenario(live_scenario_id)
        assert live_scenario is not None, live_scenario_id
        assert live_scenario.workflow_id == live_workflow_id

    live_scenario_ids = {
        scenario_id for _workflow_id, scenario_id in LIVE_ATOM_WORKFLOW_AND_SCENARIO_IDS.values()
    }
    product = registry.get_product("kernel_demo")
    assert product is not None
    assert live_scenario_ids.issubset(set(product.scenarios))


def test_live_provider_policy_is_default_text_generation_v1() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()

    policy = registry.get_provider_policy("default_text_generation_v1")
    assert policy is not None
    assert policy.provider == "litellm"
