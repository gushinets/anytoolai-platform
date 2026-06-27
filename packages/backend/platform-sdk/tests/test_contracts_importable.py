from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from anytoolai_platform_sdk.contracts import (
    ActionConfiguration,
    ActionDefinition,
    FrontendDefinition,
    HandoffDefinition,
    ProductDefinition,
    PromptRef,
    ProviderPolicy,
    ProviderTransportRetryPolicy,
    QuotaPolicy,
    ScenarioDefinition,
    WorkflowDefinition,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[4]
KERNEL_DEMO = ROOT / "configs" / "kernel" / "products" / "kernel_demo"
ACTION_ROOT = ROOT / "configs" / "kernel" / "action_definitions"


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    assert isinstance(data, dict)
    return data


def test_kernel_demo_configs_parse_into_sdk_contracts() -> None:
    ProductDefinition.model_validate(load_yaml(KERNEL_DEMO / "product.yaml"))

    for frontend in load_yaml(KERNEL_DEMO / "frontends.yaml")["frontends"]:
        FrontendDefinition.model_validate(frontend)

    for scenario in load_yaml(KERNEL_DEMO / "scenarios.yaml")["scenarios"]:
        ScenarioDefinition.model_validate(scenario)

    for workflow in load_yaml(KERNEL_DEMO / "workflows.yaml")["workflows"]:
        WorkflowDefinition.model_validate(workflow)

    for action_config in load_yaml(KERNEL_DEMO / "action_configs.yaml")["action_configs"]:
        ActionConfiguration.model_validate(action_config)

    for quota_policy in load_yaml(KERNEL_DEMO / "quotas.yaml")["quota_policies"]:
        QuotaPolicy.model_validate(quota_policy)

    for handoff in load_yaml(KERNEL_DEMO / "handoffs.yaml")["handoffs"]:
        HandoffDefinition.model_validate(handoff)

    for provider_policy in load_yaml(ROOT / "configs" / "kernel" / "provider_policies.yaml")[
        "provider_policies"
    ]:
        ProviderPolicy.model_validate(provider_policy)

    for path in sorted(ACTION_ROOT.glob("*.yaml")):
        ActionDefinition.model_validate(load_yaml(path))


def test_prompt_ref_contract_is_validatable() -> None:
    prompt = PromptRef.model_validate(
        {
            "prompt_ref": "kernel_demo.extract_structured_fields.v1",
            "version": 1,
            "template_path": "prompts/extract_structured_fields.v1.md",
            "input_variables": ["source_text"],
            "output_schema_ref": "kernel_demo.extract_output_v1",
        }
    )

    assert prompt.prompt_ref == "kernel_demo.extract_structured_fields.v1"


def test_missing_required_fields_fail_validation() -> None:
    with pytest.raises(ValidationError):
        ActionDefinition.model_validate({"action_type": "text.extract_structured_fields"})

    with pytest.raises(ValidationError):
        ProviderPolicy.model_validate(
            {
                "provider_policy_id": "default_fake_provider_v1",
                "provider": "fake",
                "model": "fake-json-v1",
            }
        )

    with pytest.raises(ValidationError):
        PromptRef.model_validate(
            {
                "prompt_ref": "kernel_demo.extract_structured_fields.v1",
                "version": 1,
                "template_path": "prompts/extract_structured_fields.v1.md",
                "input_variables": [],
            }
        )


def test_invalid_enum_values_fail_validation() -> None:
    with pytest.raises(ValidationError):
        FrontendDefinition.model_validate({"frontend_id": "mobile_app", "type": "mobile"})


def test_unknown_top_level_fields_fail_validation() -> None:
    with pytest.raises(ValidationError):
        ProviderPolicy.model_validate(
            {
                "provider_policy_id": "default_fake_provider_v1",
                "provider": "fake",
                "model": "fake-json-v1",
                "retry_policy": {
                    "transport": {
                        "owner": "provider_gateway_litellm_sdk",
                        "max_attempts": 1,
                        "litellm_num_retries_per_attempt": 0,
                    },
                    "validation": {
                        "owner": "pydantic_ai",
                        "max_attempts": 1,
                    },
                    "hard_limits": {
                        "max_physical_provider_calls_per_action": 2,
                    },
                },
                "unexpected_field": True,
            }
        )


def test_provider_policy_split_retry_shape_is_validatable() -> None:
    policy = ProviderPolicy.model_validate(
        {
            "provider_policy_id": "default_fake_provider_v1",
            "provider": "fake",
            "model": "fake-json-v1",
            "retry_policy": {
                "transport": {
                    "owner": "provider_gateway_litellm_sdk",
                    "max_attempts": 1,
                    "litellm_num_retries_per_attempt": 0,
                },
                "validation": {
                    "owner": "pydantic_ai",
                    "max_attempts": 1,
                },
                "hard_limits": {
                    "max_physical_provider_calls_per_action": 2,
                },
            },
        }
    )

    assert policy.retry_policy.transport.owner == "provider_gateway_litellm_sdk"
    assert policy.retry_policy.hard_limits.max_physical_provider_calls_per_action == 2

    with pytest.raises(ValidationError):
        ProviderTransportRetryPolicy.model_validate(
            {
                "owner": "provider_gateway_litellm_sdk",
                "max_attempts": 1,
                "litellm_num_retries_per_attempt": 1,
            }
        )


def test_optional_metadata_allows_unknown_nested_values() -> None:
    config = ActionConfiguration.model_validate(
        {
            "action_config_id": "kernel_demo.extract_structured_fields_v1",
            "action_type": "text.extract_structured_fields",
            "prompt_ref": "kernel_demo.extract_structured_fields.v1",
            "provider_policy_ref": "default_fake_provider_v1",
            "metadata": {"future": {"nested": True}},
        }
    )

    assert config.metadata["future"]["nested"] is True
