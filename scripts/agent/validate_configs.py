#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION_ROOT = ROOT / "configs" / "kernel" / "action_definitions"
KERNEL_DEMO = ROOT / "configs" / "kernel" / "products" / "kernel_demo"

REQUIRED_ACTION_FIELDS = {"action_type", "version", "input_schema_ref", "output_schema_ref", "executor"}


def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise AssertionError(f"{path}: expected mapping")
    return data


def main() -> int:
    errors: list[str] = []
    action_files = sorted(ACTION_ROOT.glob("*.yaml"))
    if len(action_files) != 11:
        errors.append(f"expected 11 action definitions, found {len(action_files)}")

    action_types: set[str] = set()
    for path in action_files:
        data = load_yaml(path)
        missing = REQUIRED_ACTION_FIELDS - set(data)
        for field in sorted(missing):
            errors.append(f"{path}: missing {field}")
        action_type = data.get("action_type")
        if action_type in action_types:
            errors.append(f"duplicate action_type {action_type}")
        action_types.add(action_type)

    action_configs = load_yaml(KERNEL_DEMO / "action_configs.yaml").get("action_configs", [])
    for cfg in action_configs:
        if cfg.get("action_type") not in action_types:
            errors.append(f"unknown action_type in action_config: {cfg}")
        if not cfg.get("prompt_ref"):
            errors.append(f"action_config missing prompt_ref: {cfg}")
        if not cfg.get("provider_policy_ref"):
            errors.append(f"action_config missing provider_policy_ref: {cfg}")

    scenarios = load_yaml(KERNEL_DEMO / "scenarios.yaml").get("scenarios", [])
    scenario_ids = {scenario["scenario_id"] for scenario in scenarios}
    for scenario_id in load_yaml(KERNEL_DEMO / "product.yaml").get("scenarios", []):
        if scenario_id not in scenario_ids:
            errors.append(f"product references unknown scenario: {scenario_id}")

    workflow_ids = {wf["workflow_id"] for wf in load_yaml(KERNEL_DEMO / "workflows.yaml").get("workflows", [])}
    for scenario in scenarios:
        if scenario.get("workflow_id") not in workflow_ids:
            errors.append(f"scenario references unknown workflow: {scenario}")

    action_config_ids = {cfg["action_config_id"] for cfg in action_configs}
    for wf in load_yaml(KERNEL_DEMO / "workflows.yaml").get("workflows", []):
        for step in wf.get("steps", []):
            if step.get("action_config_id") not in action_config_ids:
                errors.append(f"workflow step references unknown action_config: {step}")

    if errors:
        for error in errors:
            print(f"CONFIG ERROR: {error}", file=sys.stderr)
        return 1
    print("Config validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
