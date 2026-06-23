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
        and error.ref_value == ref_value
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
