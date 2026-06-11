from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
KERNEL_DEMO = ROOT / "configs" / "kernel" / "products" / "kernel_demo"


def load(name: str) -> dict:
    return yaml.safe_load((KERNEL_DEMO / name).read_text(encoding="utf-8")) or {}


def test_workflow_steps_reference_existing_action_configs() -> None:
    action_ids = {cfg["action_config_id"] for cfg in load("action_configs.yaml")["action_configs"]}
    for workflow in load("workflows.yaml")["workflows"]:
        for step in workflow["steps"]:
            assert step["action_config_id"] in action_ids


def test_product_references_existing_scenarios() -> None:
    scenario_ids = {scenario["scenario_id"] for scenario in load("scenarios.yaml")["scenarios"]}
    for scenario_id in load("product.yaml")["scenarios"]:
        assert scenario_id in scenario_ids


def test_action_configs_have_prompt_and_provider_policy_refs() -> None:
    for config in load("action_configs.yaml")["action_configs"]:
        assert config.get("prompt_ref")
        assert config.get("provider_policy_ref")
