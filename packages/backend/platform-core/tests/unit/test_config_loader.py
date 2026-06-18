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

    assert any(
        isinstance(error, InvalidConfigShapeError)
        and error.file_path == path
        and error.config_id == "default_fake_provider_v1"
        and "structured_output_mode" in error.message
        for error in exc_info.value.errors
    )
