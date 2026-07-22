from __future__ import annotations

from pathlib import Path
import shutil

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[5]

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
    config_id: str | None,
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


def test_loader_builds_registry_from_current_tree() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()

    assert registry.get_product("kernel_demo") is not None
    assert registry.get_scenario("kernel_demo.single_action_smoke_v1") is not None
    assert registry.get_workflow("kernel_demo.extract_detect_report_v1") is not None
    assert (
        registry.get_action_configuration("kernel_demo.extract_structured_fields_v1")
        is not None
    )
    assert registry.get_prompt("kernel_demo.extract_structured_fields.v1") is not None
    assert registry.get_provider_policy("default_fake_provider_v1") is not None
    quota_policy = registry.get_quota_policy("kernel_demo.guest_quota_v1")
    assert quota_policy is not None
    assert quota_policy.dimension.value == "product"
    assert registry.get_schema("kernel.schemas.extract_input_v1") is not None
    assert registry.get_schema("kernel_demo.generic_text_input_v1") is not None

    product = registry.get_product("kernel_demo")
    assert product is not None
    assert isinstance(product.scenarios, tuple)

    multi_step = registry.get_workflow("kernel_demo.extract_detect_report_v1")
    assert multi_step is not None
    assert multi_step.steps[0].input_mapping == {
        "source_text": "scenario.input.source_text",
    }
    assert multi_step.steps[2].output_mapping == {
        "context.workflow_output": "steps.generate_report.output",
    }

    retry_workflow = registry.get_workflow("kernel_demo.retry_extract_v1")
    assert retry_workflow is not None
    assert retry_workflow.steps[0].retry_count == 1

    with pytest.raises(TypeError):
        registry.products["another"] = product


def test_loader_preserves_provider_policy_yaml_metadata() -> None:
    registry = ConfigLoader(CONFIG_ROOT).load()

    policy = registry.get_provider_policy("default_text_generation_v1")

    assert policy is not None
    assert policy.provider == "litellm"
    assert policy.model == "anytoolai.default_text"
    assert policy.retry_policy.transport.max_attempts == 2
    assert policy.retry_policy.transport.litellm_num_retries_per_attempt == 0
    assert policy.retry_policy.validation.max_attempts == 2
    assert policy.metadata["model_group"] == "anytoolai.default_text"
    assert policy.metadata["routing_profile"] == "default_text"
    assert policy.metadata["_file_path"].endswith("provider_policies.yaml")


def test_default_text_generation_policy_has_no_duplicate_retry_key_in_yaml() -> None:
    provider_policies_yaml = (CONFIG_ROOT / "provider_policies.yaml").read_text(
        encoding="utf-8"
    )
    default_policy_start = provider_policies_yaml.index(
        "  - provider_policy_ref: default_text_generation_v1"
    )
    default_policy_block = provider_policies_yaml[default_policy_start:]

    assert default_policy_block.count("litellm_num_retries_per_attempt:") == 1


@pytest.mark.parametrize("metadata_value", [None, ["not", "a", "dict"], "scalar-metadata"])
def test_loader_fails_on_non_mapping_provider_policy_metadata(
    tmp_path: Path,
    metadata_value: object,
) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["metadata"] = metadata_value
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="metadata",
        ref_value=str(metadata_value),
        message_part="metadata must be a dictionary object",
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


def test_loader_rejects_legacy_max_retries_provider_policy_field(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][0]["max_retries"] = 9
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_fake_provider_v1",
        ref_type="max_retries",
        ref_value="9",
        message_part="legacy max_retries",
    )


def test_loader_rejects_non_zero_litellm_num_retries_per_attempt(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    data = _load_yaml(path)
    data["provider_policies"][1]["retry_policy"]["transport"][
        "litellm_num_retries_per_attempt"
    ] = 1
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="default_text_generation_v1",
        ref_type="litellm_num_retries_per_attempt",
        ref_value="1",
        message_part="to be 0",
    )


def test_loader_rejects_duplicate_yaml_keys_in_provider_policy_file(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "provider_policies.yaml"
    path.write_text(
        "\n".join(
            [
                "provider_policies:",
                "  - provider_policy_ref: duplicate_retry_key_v1",
                "    provider: litellm",
                "    model: anytoolai.default_text",
                "    temperature: 0.3",
                "    timeout_seconds: 60",
                "    retry_policy:",
                "      transport:",
                "        owner: litellm",
                "        max_attempts: 2",
                "        litellm_num_retries_per_attempt: 0",
                "        litellm_num_retries_per_attempt: 1",
                "      validation:",
                "        owner: pydanticai",
                "        max_attempts: 2",
                "      hard_limits:",
                "        max_physical_provider_calls_per_action: 4",
                "    structured_output_mode: json_schema",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id=None,
        ref_type="duplicate_key",
        ref_value="litellm_num_retries_per_attempt",
        message_part="Duplicate YAML key",
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


def test_loader_fails_on_invalid_quota_dimension(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "quotas.yaml"
    data = _load_yaml(path)
    data["quota_policies"][0]["dimension"] = "frontend"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.guest_quota_v1",
        ref_type="dimension",
        ref_value="frontend",
        message_part="quota dimension",
    )


def test_loader_rejects_negative_workflow_step_retry_count(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    data["workflows"][-1]["steps"][0]["retry_count"] = -1
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.retry_extract_v1",
        ref_type="step_id",
        ref_value="extract",
        message_part="retry_count",
    )


def test_loader_rejects_forward_step_reference_in_workflow_input_mapping(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    data["workflows"][1]["steps"][0]["input_mapping"] = {
        "source_text": "steps.detect_issues.output.issues"
    }
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.extract_detect_report_v1",
        ref_type="step_id",
        ref_value="extract",
        message_part="previous step output",
    )


def test_loader_allows_missing_workflow_step_input_mapping_for_backward_compatibility(
    tmp_path: Path,
) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    del data["workflows"][0]["steps"][0]["input_mapping"]
    _write_yaml(path, data)

    registry = ConfigLoader(config_root).load()
    workflow = registry.get_workflow("kernel_demo.single_action_extract_v1")

    assert workflow is not None
    assert workflow.steps[0].input_mapping == {}


def test_loader_rejects_duplicate_workflow_step_ids(tmp_path: Path) -> None:
    config_root = _copy_config_tree(tmp_path)
    path = config_root / "products" / "kernel_demo" / "workflows.yaml"
    data = _load_yaml(path)
    data["workflows"][1]["steps"][1]["step_id"] = "extract"
    _write_yaml(path, data)

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(config_root).load()

    _assert_invalid_shape(
        exc_info.value.errors,
        file_path=path,
        config_id="kernel_demo.extract_detect_report_v1",
        ref_type="step_id",
        ref_value="extract",
        message_part="must be unique within a workflow",
    )
