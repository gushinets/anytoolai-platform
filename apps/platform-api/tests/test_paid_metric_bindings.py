from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_core.config.errors import BrokenReferenceError, RegistryLoadError
from anytoolai_platform_core.config.loader import ConfigLoader
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_sdk.contracts import ScenarioDefinition

ROOT = Path(__file__).resolve().parents[3]
CONFIG_ROOT = ROOT / "configs/kernel"
APPROVED_BINDINGS = [
    ("proposal_ai", "proposal_ai.generate_v1", "proposal_ai.generations", "generation"),
    (
        "client_update_writer",
        "client_update_writer.update_v1",
        "client_update_writer.messages",
        "message",
    ),
    (
        "client_update_writer",
        "client_update_writer.prepaid_request_v1",
        "client_update_writer.messages",
        "message",
    ),
    (
        "client_update_writer",
        "client_update_writer.reply_draft_v1",
        "client_update_writer.messages",
        "message",
    ),
    ("brief_decoder", "brief_decoder.decode_v1", "brief_decoder.analyses", "analysis"),
    ("acceptance_builder", "acceptance_builder.draft_v1", "acceptance_builder.results", "result"),
    ("acceptance_builder", "acceptance_builder.check_v1", "acceptance_builder.results", "result"),
]


@pytest.fixture(scope="module")
def registry() -> ConfigRegistry:
    return build_runtime(config_root=CONFIG_ROOT, database_url="").config_registry


@pytest.mark.parametrize(("product_id", "scenario_id", "metric_key", "unit"), APPROVED_BINDINGS)
def test_approved_scenario_resolves_owned_disabled_metric_and_sdk_contract(
    registry: ConfigRegistry, product_id: str, scenario_id: str, metric_key: str, unit: str
) -> None:
    product = registry.products[product_id]
    scenario = registry.scenarios[scenario_id]
    assert scenario_id in product.scenarios
    assert scenario.paid_metric_key == metric_key
    metric = next(item for item in product.usage_metrics if item.metric_key == metric_key)
    assert metric.unit == unit
    assert not metric.enabled
    assert not product.commercial_admission_enabled
    assert (
        ScenarioDefinition.model_validate(scenario, from_attributes=True).paid_metric_key
        == metric_key
    )


@pytest.mark.parametrize("metric_key", ["brief_decoder.analyses", "brief_decoder.test_analyses"])
def test_foreign_metric_binding_fails_with_scenario_diagnostics(
    registry: ConfigRegistry, tmp_path: Path, metric_key: str
) -> None:
    roots = []
    for product_id in ("proposal_ai", "brief_decoder"):
        root = tmp_path / product_id
        shutil.copytree(Path(registry.products[product_id].metadata["_file_path"]).parent, root)
        roots.append(root)
    path = roots[0] / "scenarios.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["scenarios"][0]["paid_metric_key"] = metric_key
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(CONFIG_ROOT, extra_product_roots=roots).load()

    assert any(
        isinstance(error, BrokenReferenceError)
        and error.file_path == path
        and error.config_id == "proposal_ai.generate_v1"
        and error.ref_type == "paid_metric_key"
        and error.ref_value == metric_key
        for error in exc_info.value.errors
    )


def test_guest_policies_and_unbound_products_remain_unchanged(registry: ConfigRegistry) -> None:
    assert registry.products["client_update_writer"].quota_policy_ref is None
    for product_id in ("proposal_ai", "brief_decoder", "acceptance_builder"):
        assert registry.products[product_id].quota_policy_ref == f"{product_id}.guest_quota_v1"
    for product_id in ("kernel_demo", "task_finder"):
        product = registry.products[product_id]
        assert product.usage_metrics == ()
        assert all(registry.scenarios[key].paid_metric_key is None for key in product.scenarios)


def test_test_only_metric_identities_remain_disabled(registry: ConfigRegistry) -> None:
    for product_id, key, unit in (
        ("proposal_ai", "proposal_ai.test_generations", "generation"),
        ("brief_decoder", "brief_decoder.test_analyses", "analysis"),
    ):
        metric = next(
            item for item in registry.products[product_id].usage_metrics if item.metric_key == key
        )
        assert metric.unit == unit
        assert not metric.enabled
        assert all(scenario.paid_metric_key != key for scenario in registry.scenarios.values())
