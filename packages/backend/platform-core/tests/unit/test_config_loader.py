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


def test_loader_builds_registry_from_current_tree() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()

    assert registry.get_product("kernel_demo") is not None
    assert registry.get_scenario("kernel_demo.single_action_smoke_v1") is not None
    assert registry.get_workflow("kernel_demo.extract_detect_report_v1") is not None
    assert registry.get_action_config("kernel_demo.extract_structured_fields_v1") is not None
    assert registry.get_prompt("kernel_demo.extract_structured_fields.v1") is not None
    assert registry.get_provider_policy("default_fake_provider_v1") is not None
    assert registry.get_schema("kernel.schemas.extract_input_v1") is not None
    assert registry.get_schema("kernel_demo.generic_text_input_v1") is not None

    product = registry.get_product("kernel_demo")
    assert product is not None
    assert isinstance(product.scenarios, tuple)

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
