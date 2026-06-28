from __future__ import annotations

from pathlib import Path
import shutil
import sys

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]
PLATFORM_CORE_SRC = REPO_ROOT / "packages" / "backend" / "platform-core" / "src"

if str(PLATFORM_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(PLATFORM_CORE_SRC))

from anytoolai_platform_core.config.errors import (
    BrokenReferenceError,
    DuplicateConfigIdError,
    InvalidConfigShapeError,
    MissingConfigFileError,
    RegistryLoadError,
)
from anytoolai_platform_core.config.loader import ConfigLoader


CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def _copy_config_tree(tmp_path: Path) -> Path:
    copied_root = tmp_path / "kernel"
    shutil.copytree(CONFIG_ROOT, copied_root)
    return copied_root


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _write_yaml(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def _assert_broken_reference(
    errors: tuple[Exception, ...],
    *,
    config_id: str,
    ref_type: str,
    ref_value: str,
) -> None:
    assert any(
        isinstance(error, BrokenReferenceError)
        and error.config_id == config_id
        and error.ref_type == ref_type
        and error.ref_value == ref_value
        for error in errors
    )


def _assert_invalid_shape(
    errors: tuple[Exception, ...],
    *,
    file_path: Path,
    config_id: str,
    ref_type: str,
    ref_value: str,
    message_part: str,
) -> None:
    assert any(
        isinstance(error, InvalidConfigShapeError)
        and error.file_path == file_path
        and error.config_id == config_id
        and error.ref_type == ref_type
        and str(error.ref_value) == ref_value
        and message_part in error.message
        for error in errors
    )


def _assert_missing_file(
    errors: tuple[Exception, ...],
    *,
    file_path: Path,
    config_id: str,
    ref_type: str,
    ref_value: str,
) -> None:
    assert any(
        isinstance(error, MissingConfigFileError)
        and error.file_path == file_path
        and error.config_id == config_id
        and error.ref_type == ref_type
        and error.ref_value == ref_value
        for error in errors
    )


def test_loader_builds_registry_from_current_tree() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()

    assert registry.get_product("kernel_demo") is not None
    assert registry.get_scenario("kernel_demo.single_action_smoke_v1") is not None
    assert registry.get_workflow("kernel_demo.extract_detect_report_v1") is not None
    assert registry.get_action_configuration("kernel_demo.extract_structured_fields_v1") is not None
    assert registry.get_prompt("kernel_demo.extract_structured_fields.v1") is not None
    assert registry.get_provider_policy("default_fake_provider_v1") is not None
    assert registry.get_schema("kernel.schemas.extract_input_v1") is not None
    assert registry.get_schema("kernel_demo.generic_text_input_v1") is not None

    product = registry.get_product("kernel_demo")
    assert product is not None
    assert product.analytics["product_events"][0] == "kernel_demo.result_viewed"

    prompt = registry.get_prompt("kernel_demo.extract_structured_fields.v1")
    assert prompt is not None
    assert prompt.output_schema_ref == "kernel.schemas.extract_output_v1"

    provider_policy = registry.get_provider_policy("default_fake_provider_v1")
    assert provider_policy is not None
    assert provider_policy.retry_policy.transport.owner == "provider_gateway_litellm_sdk"
    assert provider_policy.retry_policy.transport.litellm_num_retries_per_attempt == 0
    assert (
        provider_policy.retry_policy.hard_limits.max_physical_provider_calls_per_action
        == 2
    )

    with pytest.raises(TypeError):
        registry.products["another"] = product


def test_loader_fails_when_frontends_yaml_is_missing(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "frontends.yaml"
    path.unlink()

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_missing_file(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="frontends_file",
        ref_value="frontends.yaml",
    )


def test_loader_rejects_embedded_frontends_in_product_yaml(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "product.yaml"
    data = _load_yaml(path)
    data["frontends"] = [
        {
            "frontend_id": "kernel_demo_ce",
            "type": "chrome_extension",
            "enabled": True,
        }
    ]
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="frontends",
        ref_value="product.yaml.frontends",
        message_part="frontends.yaml",
    )


def test_loader_uses_empty_analytics_when_analytics_yaml_is_missing(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "analytics.yaml"
    path.unlink()

    registry = ConfigLoader(config_root).load()

    product = registry.get_product("kernel_demo")
    assert product is not None
    assert product.analytics == {}


def test_loader_rejects_embedded_analytics_in_product_yaml(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "product.yaml"
    data = _load_yaml(path)
    data["analytics"] = {"aha_event": "kernel_demo.result_viewed"}
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="analytics",
        ref_value="product.yaml.analytics",
        message_part="analytics.yaml",
    )


def test_loader_fails_on_missing_provider_policies_file(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    path.unlink()

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_missing_file(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel",
        ref_type="provider_policies_file",
        ref_value="provider_policies.yaml",
    )


def test_loader_fails_on_missing_action_configs_file(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "action_configs.yaml"
    path.unlink()

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_missing_file(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="action_configs_file",
        ref_value="action_configs.yaml",
    )


def test_loader_fails_on_duplicate_ids(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "action_configs.yaml"
    data = _load_yaml(path)
    data["action_configs"].append(dict(data["action_configs"][0]))
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    assert any(
        isinstance(error, DuplicateConfigIdError)
        and error.config_id == "kernel_demo.extract_structured_fields_v1"
        for error in exc_info.value.errors
    )


def test_loader_fails_on_missing_workflow_reference(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "scenarios.yaml"
    data = _load_yaml(path)
    data["scenarios"][0]["workflow_id"] = "kernel_demo.missing_workflow_v1"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_broken_reference(
        exc_info.value.errors,
        config_id="kernel_demo.single_action_smoke_v1",
        ref_type="workflow_id",
        ref_value="kernel_demo.missing_workflow_v1",
    )


def test_loader_fails_on_missing_action_config_reference(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    data["workflows"][0]["steps"][0]["action_config_id"] = "kernel_demo.missing_action_config_v1"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_broken_reference(
        exc_info.value.errors,
        config_id="kernel_demo.single_action_extract_v1",
        ref_type="action_config_id",
        ref_value="kernel_demo.missing_action_config_v1",
    )


def test_loader_fails_on_missing_prompt_reference(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "action_configs.yaml"
    data = _load_yaml(path)
    data["action_configs"][0]["prompt_ref"] = "kernel_demo.missing_prompt.v1"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_broken_reference(
        exc_info.value.errors,
        config_id="kernel_demo.extract_structured_fields_v1",
        ref_type="prompt_ref",
        ref_value="kernel_demo.missing_prompt.v1",
    )


def test_loader_fails_on_missing_schema_reference(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    data["workflows"][0]["input_schema_ref"] = "kernel_demo.missing_schema_v1"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_broken_reference(
        exc_info.value.errors,
        config_id="kernel_demo.single_action_extract_v1",
        ref_type="input_schema_ref",
        ref_value="kernel_demo.missing_schema_v1",
    )


def test_loader_fails_on_missing_provider_policy_fallback_reference(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["fallback_policy"] = "missing_provider_policy_v1"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_broken_reference(
        exc_info.value.errors,
        config_id="default_fake_provider_v1",
        ref_type="fallback_policy",
        ref_value="missing_provider_policy_v1",
    )


def test_loader_fails_on_missing_quota_policy_ref_when_quotas_exist(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "product.yaml"
    data = _load_yaml(path)
    data.pop("quota_policy_ref", None)
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="quota_policy_ref",
        ref_value="<missing>",
        message_part="quota_policy_ref",
    )


def test_loader_fails_on_empty_quota_policy_ref_when_quotas_exist(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "product.yaml"
    data = _load_yaml(path)
    data["quota_policy_ref"] = ""
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="quota_policy_ref",
        ref_value="<missing>",
        message_part="quota_policy_ref",
    )


def test_loader_fails_on_missing_provider_policy_tuning_field(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0].pop("timeout_seconds")
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="timeout_seconds",
        ref_value="<missing>",
        message_part="timeout_seconds",
    )


def test_loader_fails_on_null_provider_policy_tuning_field(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["timeout_seconds"] = None
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="timeout_seconds",
        ref_value="<missing>",
        message_part="timeout_seconds",
    )


def test_loader_fails_on_invalid_structured_output_mode(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["structured_output_mode"] = "xml_schema"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="structured_output_mode",
        ref_value="xml_schema",
        message_part="structured_output_mode",
    )


def test_loader_rejects_legacy_provider_policy_max_retries(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["max_retries"] = 1
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="max_retries",
        ref_value="1",
        message_part="legacy retry field",
    )


def test_loader_rejects_legacy_retry_policy_flat_fields(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["retry_policy"]["max_retries"] = 1
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="max_retries",
        ref_value="1",
        message_part="retry_policy.max_retries",
    )


def test_loader_rejects_nonzero_litellm_num_retries_per_attempt(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["retry_policy"]["transport"][
        "litellm_num_retries_per_attempt"
    ] = 1
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="litellm_num_retries_per_attempt",
        ref_value="1",
        message_part="to be 0",
    )


def test_loader_requires_max_physical_provider_calls_per_action(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    del data["provider_policies"][0]["retry_policy"]["hard_limits"][
        "max_physical_provider_calls_per_action"
    ]
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="max_physical_provider_calls_per_action",
        ref_value="None",
        message_part="is required",
    )


def test_loader_rejects_unexpected_retry_policy_top_level_key(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["retry_policy"]["unexpected_section"] = {"enabled": True}
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="unexpected_section",
        ref_value='{"enabled": true}',
        message_part="unsupported field",
    )


def test_loader_rejects_unexpected_transport_retry_key(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["retry_policy"]["transport"]["jitter_seconds"] = 5
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="jitter_seconds",
        ref_value="5",
        message_part="unsupported field",
    )


def test_loader_rejects_unexpected_validation_retry_key(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["retry_policy"]["validation"]["reflect"] = True
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="reflect",
        ref_value="True",
        message_part="unsupported field",
    )


def test_loader_rejects_unexpected_hard_limits_key(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["retry_policy"]["hard_limits"]["burst_limit"] = 3
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="burst_limit",
        ref_value="3",
        message_part="unsupported field",
    )


def test_loader_fails_on_invalid_action_executor(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "action_definitions" / "text.extract_structured_fields.yaml"
    data = _load_yaml(path)
    data["executor"] = "python"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="text.extract_structured_fields",
        ref_type="executor",
        ref_value="python",
        message_part="executor",
    )


def test_loader_rejects_raw_provider_field_in_product_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "product.yaml"
    data = _load_yaml(path)
    data["provider"] = "openai"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="provider",
        ref_value="openai",
        message_part="Product configs must not define",
    )


def test_loader_rejects_nested_raw_model_field_in_product_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "product.yaml"
    data = _load_yaml(path)
    data["metadata"] = {"model": "gpt-4.1-mini"}
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="metadata.model",
        ref_value="gpt-4.1-mini",
        message_part="metadata.model",
    )


def test_loader_rejects_raw_model_field_in_scenario_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "scenarios.yaml"
    data = _load_yaml(path)
    data["scenarios"][0]["model"] = "gpt-5-mini"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.single_action_smoke_v1",
        ref_type="model",
        ref_value="gpt-5-mini",
        message_part="Scenario configs must not define",
    )


def test_loader_rejects_raw_response_format_in_workflow_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    data["workflows"][0]["response_format"] = "json_schema"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.single_action_extract_v1",
        ref_type="response_format",
        ref_value="json_schema",
        message_part="Workflow configs must not define",
    )


def test_loader_rejects_raw_temperature_in_action_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "action_configs.yaml"
    data = _load_yaml(path)
    data["action_configs"][0]["temperature"] = 0.2
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.extract_structured_fields_v1",
        ref_type="temperature",
        ref_value="0.2",
        message_part="Action configs must not define",
    )


def test_loader_rejects_nested_raw_temperature_in_action_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "action_configs.yaml"
    data = _load_yaml(path)
    data["action_configs"][0]["llm"] = {"temperature": 0.2}
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.extract_structured_fields_v1",
        ref_type="llm.temperature",
        ref_value="0.2",
        message_part="llm.temperature",
    )


def test_loader_rejects_raw_litellm_field_in_frontend_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "frontends.yaml"
    data = _load_yaml(path)
    data["frontends"][0]["litellm_cache"] = True
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo_ce",
        ref_type="litellm_cache",
        ref_value="True",
        message_part="Frontend configs must not define",
    )


def test_loader_rejects_nested_litellm_field_in_frontend_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "frontends.yaml"
    data = _load_yaml(path)
    data["frontends"][0]["settings"] = {"litellm_cache": True}
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo_ce",
        ref_type="settings.litellm_cache",
        ref_value="True",
        message_part="settings.litellm_cache",
    )


def test_loader_rejects_nested_raw_response_schema_in_workflow_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    data["workflows"][0]["llm"] = {"response_schema": {"type": "object"}}
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.single_action_extract_v1",
        ref_type="llm.response_schema",
        ref_value='{"type": "object"}',
        message_part="llm.response_schema",
    )


def test_loader_rejects_raw_model_field_in_prompt_front_matter(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = (
        config_root
        / "products"
        / "kernel_demo"
        / "prompts"
        / "extract_structured_fields.v1.md"
    )
    path.write_text(
        "---\nmodel: gpt-5-mini\n---\nPrompt body\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.extract_structured_fields.v1",
        ref_type="model",
        ref_value="gpt-5-mini",
        message_part="Prompt configs must not define",
    )


def test_loader_still_allows_provider_policy_ref_in_action_config(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)

    registry = ConfigLoader(config_root).load()

    action_config = registry.get_action_config("kernel_demo.extract_structured_fields_v1")
    assert action_config is not None
    assert action_config.provider_policy_ref == "default_fake_provider_v1"


def test_loader_rejects_invalid_yaml_in_prompt_front_matter(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = (
        config_root
        / "products"
        / "kernel_demo"
        / "prompts"
        / "extract_structured_fields.v1.md"
    )
    path.write_text(
        "---\nmodel: [unterminated\n---\nPrompt body\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    assert any(
        isinstance(error, InvalidConfigShapeError)
        and error.file_path == path
        and error.message.endswith("Prompt front matter contains invalid YAML")
        for error in exc_info.value.errors
    )


def test_loader_fails_on_invalid_frontend_type(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "frontends.yaml"
    data = _load_yaml(path)
    data["frontends"][0]["type"] = "desktop_app"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo_ce",
        ref_type="type",
        ref_value="desktop_app",
        message_part="frontend type",
    )


def test_loader_fails_on_non_mapping_frontend_entry(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "frontends.yaml"
    data = _load_yaml(path)
    data["frontends"] = ["kernel_demo_ce"]
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="frontends_entry",
        ref_value="str",
        message_part="mapping",
    )


def test_loader_fails_on_invalid_quota_unit(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "quotas.yaml"
    data = _load_yaml(path)
    data["quota_policies"][0]["unit"] = "token"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.guest_quota_v1",
        ref_type="unit",
        ref_value="token",
        message_part="quota unit",
    )


def test_loader_fails_on_invalid_quota_period(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "quotas.yaml"
    data = _load_yaml(path)
    data["quota_policies"][0]["period"] = "daily"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.guest_quota_v1",
        ref_type="period",
        ref_value="daily",
        message_part="quota period",
    )


def test_loader_fails_on_missing_prompt_manifest(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "prompts.yaml"
    path.unlink()

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_missing_file(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="prompt_manifest",
        ref_value="prompts.yaml",
    )


def test_loader_fails_on_missing_prompt_asset(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    manifest_path = config_root / "products" / "kernel_demo" / "prompts.yaml"
    data = _load_yaml(manifest_path)
    data["prompts"][0]["template_path"] = "prompts/missing_prompt.v1.md"
    _write_yaml(manifest_path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_missing_file(
        exc_info.value.errors,
        file_path=config_root / "products" / "kernel_demo" / "prompts" / "missing_prompt.v1.md",
        config_id="kernel_demo.extract_structured_fields.v1",
        ref_type="prompt_asset",
        ref_value="prompts/missing_prompt.v1.md",
    )


def test_loader_fails_on_non_mapping_prompt_manifest_entry(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "prompts.yaml"
    data = _load_yaml(path)
    data["prompts"] = ["kernel_demo.extract_structured_fields.v1"]
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="prompt_manifest_entry",
        ref_value="str",
        message_part="mapping",
    )


def test_loader_fails_on_missing_schema_manifest(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "schemas.yaml"
    path.unlink()

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_missing_file(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel",
        ref_type="schema_manifest",
        ref_value="schemas.yaml",
    )


def test_loader_fails_on_missing_schema_asset(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    manifest_path = config_root / "products" / "kernel_demo" / "schemas.yaml"
    data = _load_yaml(manifest_path)
    data["schemas"][0]["file_path"] = "schemas/missing_extract_input.schema.json"
    _write_yaml(manifest_path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_missing_file(
        exc_info.value.errors,
        file_path=config_root / "products" / "kernel_demo" / "schemas" / "missing_extract_input.schema.json",
        config_id="kernel_demo.extract_input_v1",
        ref_type="schema_asset",
        ref_value="schemas/missing_extract_input.schema.json",
    )


def test_loader_fails_on_non_mapping_schema_manifest_entry(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "schemas.yaml"
    data = _load_yaml(path)
    data["schemas"] = ["kernel_demo.extract_input_v1"]
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo",
        ref_type="schema_manifest_entry",
        ref_value="str",
        message_part="mapping",
    )


def test_loader_wraps_escaped_missing_config_error_into_registry_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = ConfigLoader(CONFIG_ROOT)
    expected_error = MissingConfigFileError(
        CONFIG_ROOT / "provider_policies.yaml",
        "provider_policies.yaml is required because it owns provider policy definitions",
        config_id="kernel",
        ref_type="provider_policies_file",
        ref_value="provider_policies.yaml",
    )

    def _boom() -> None:
        raise expected_error

    monkeypatch.setattr(loader, "_load_tenants", _boom)

    with pytest.raises(RegistryLoadError) as exc_info:
        loader.load()

    assert exc_info.value.errors == (expected_error,)


def test_loader_preserves_config_error_cause_in_unexpected_registry_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = ConfigLoader(CONFIG_ROOT)
    expected_error = MissingConfigFileError(
        CONFIG_ROOT / "provider_policies.yaml",
        "provider_policies.yaml is required because it owns provider policy definitions",
        config_id="kernel",
        ref_type="provider_policies_file",
        ref_value="provider_policies.yaml",
    )

    def _boom() -> None:
        raise RuntimeError("unexpected wrapper") from expected_error

    monkeypatch.setattr(loader, "_load_tenants", _boom)

    with pytest.raises(RegistryLoadError) as exc_info:
        loader.load()

    assert exc_info.value.errors == (expected_error,)
