from __future__ import annotations

import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path

import pytest
import yaml
from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_core.config.errors import DuplicateConfigIdError, RegistryLoadError
from anytoolai_platform_core.config.loader import ConfigLoader
from anytoolai_platform_core.config.registry import ConfigRegistry
from anytoolai_platform_core.products.capabilities import project_capability_manifest

CONFIG_ROOT = Path(__file__).resolve().parents[3] / "configs/kernel"
APPROVED_EXAMPLE_DIGEST = "sha256:a39bac9f210a6ac67e97e117f8481a5954dc3f36bdaab2fd54c7522b27d6ec29"
EXPECTED_PRODUCTS = {
    "kernel_demo",
    "proposal_ai",
    "client_update_writer",
    "brief_decoder",
    "acceptance_builder",
    "task_finder",
}
EXPECTED_METRICS = {
    ("proposal_ai.test_generations", "proposal_ai", "generation"),
    ("brief_decoder.test_analyses", "brief_decoder", "analysis"),
}


@pytest.fixture(scope="module")
def registry() -> ConfigRegistry:
    return build_runtime(config_root=CONFIG_ROOT, database_url="").config_registry


def test_complete_ordinary_vocabulary_is_disabled(registry: ConfigRegistry) -> None:
    manifest = project_capability_manifest(registry, tenant_id="anytoolai", region="ru")

    assert {product.product_id for product in manifest.products} == EXPECTED_PRODUCTS
    assert {
        (metric.metric_key, metric.product_id, metric.unit) for metric in manifest.usage_metrics
    } == EXPECTED_METRICS
    assert all(not product.enabled for product in manifest.products)
    assert all(not metric.enabled for metric in manifest.usage_metrics)
    assert [product.product_id for product in manifest.products] == sorted(EXPECTED_PRODUCTS)
    assert [metric.metric_key for metric in manifest.usage_metrics] == sorted(
        item[0] for item in EXPECTED_METRICS
    )
    assert manifest.manifest_version != APPROVED_EXAMPLE_DIGEST
    for product in registry.products.values():
        assert isinstance(product.usage_metrics, tuple)
        if product.product_id not in {"proposal_ai", "brief_decoder"}:
            assert product.usage_metrics == ()


def test_enabled_example_preserves_independent_accepted_digest(registry: ConfigRegistry) -> None:
    enabled = {"proposal_ai", "brief_decoder"}
    test_registry = replace(
        registry,
        products={
            product_id: replace(
                product,
                commercial_admission_enabled=product_id in enabled,
                usage_metrics=tuple(
                    replace(metric, enabled=True) for metric in product.usage_metrics
                ),
            )
            for product_id, product in registry.products.items()
        },
    )

    manifest = project_capability_manifest(test_registry, tenant_id="anytoolai", region="ru")

    assert manifest.manifest_version == APPROVED_EXAMPLE_DIGEST
    assert all(not product.commercial_admission_enabled for product in registry.products.values())


def test_nested_declarations_and_projection_are_immutable(registry: ConfigRegistry) -> None:
    product = registry.products["proposal_ai"]
    metric = product.usage_metrics[0]
    original_metrics = [replace(metric, metadata={"nested": ["original"]})]
    copied = replace(
        registry, products={product.product_id: replace(product, usage_metrics=original_metrics)}
    )
    original_metrics.clear()
    frozen = copied.products[product.product_id]
    assert frozen.usage_metrics[0].metadata["nested"] == ("original",)
    with pytest.raises(FrozenInstanceError):
        frozen.usage_metrics[0].enabled = True
    with pytest.raises(TypeError):
        frozen.usage_metrics[0].metadata["nested"] = ()
    with pytest.raises(FrozenInstanceError):
        frozen.commercial_admission_enabled = True
    manifest = project_capability_manifest(copied, tenant_id="anytoolai", region="ru")
    with pytest.raises(FrozenInstanceError):
        manifest.usage_metrics[0].unit = "other"
    with pytest.raises(FrozenInstanceError):
        manifest.products[0].enabled = True


@pytest.mark.parametrize("product_enabled", [False, True])
def test_product_and_metric_admission_flags_remain_independent(
    registry: ConfigRegistry, product_enabled: bool
) -> None:
    product = registry.products["proposal_ai"]
    changed = replace(
        registry,
        products={
            **registry.products,
            product.product_id: replace(
                product,
                commercial_admission_enabled=product_enabled,
                usage_metrics=tuple(
                    replace(metric, enabled=not product_enabled) for metric in product.usage_metrics
                ),
            ),
        },
    )
    manifest = project_capability_manifest(changed, tenant_id="anytoolai", region="ru")
    projected_product = next(
        item for item in manifest.products if item.product_id == product.product_id
    )
    projected_metric = next(
        item for item in manifest.usage_metrics if item.product_id == product.product_id
    )
    assert projected_product.enabled is product_enabled
    assert projected_metric.enabled is not product_enabled


def test_hash_ignores_registry_order_metadata_and_unrelated_runtime_config(
    registry: ConfigRegistry,
) -> None:
    before = project_capability_manifest(registry, tenant_id="anytoolai", region="ru")
    changed = replace(
        registry,
        loaded_from=Path("/other-root"),
        products={
            product_id: replace(
                product,
                display_name="Other name",
                frontends=(),
                scenarios=(),
                quota_policy_ref=None,
                analytics={},
                metadata={"other": True},
                usage_metrics=tuple(
                    replace(metric, metadata={"other": True})
                    for metric in reversed(product.usage_metrics)
                ),
            )
            for product_id, product in reversed(list(registry.products.items()))
        },
    )
    after = project_capability_manifest(changed, tenant_id="anytoolai", region="ru")

    assert before == after
    assert before.manifest_version == after.manifest_version
    reordered = replace(
        before,
        products=tuple(reversed(before.products)),
        usage_metrics=tuple(reversed(before.usage_metrics)),
    )
    assert reordered.manifest_version == before.manifest_version


@pytest.mark.parametrize(
    "change",
    [
        "tenant",
        "region",
        "schema",
        "product_id",
        "product_enabled",
        "metric_key",
        "metric_owner",
        "metric_unit",
        "metric_enabled",
        "remove_product",
        "remove_metric",
    ],
)
def test_hash_changes_with_every_semantic_dimension(registry: ConfigRegistry, change: str) -> None:
    before = project_capability_manifest(registry, tenant_id="anytoolai", region="ru")
    product, *other_products = before.products
    metric, *other_metrics = before.usage_metrics
    variants = {
        "tenant": replace(before, tenant_id="other"),
        "region": replace(before, region="other"),
        "schema": replace(before, schema_version=2),
        "product_id": replace(
            before, products=(replace(product, product_id="other"), *other_products)
        ),
        "product_enabled": replace(
            before, products=(replace(product, enabled=True), *other_products)
        ),
        "metric_key": replace(
            before, usage_metrics=(replace(metric, metric_key="other"), *other_metrics)
        ),
        "metric_owner": replace(
            before, usage_metrics=(replace(metric, product_id=product.product_id), *other_metrics)
        ),
        "metric_unit": replace(
            before, usage_metrics=(replace(metric, unit="other"), *other_metrics)
        ),
        "metric_enabled": replace(
            before, usage_metrics=(replace(metric, enabled=True), *other_metrics)
        ),
        "remove_product": replace(before, products=tuple(other_products)),
        "remove_metric": replace(before, usage_metrics=tuple(other_metrics)),
    }
    assert before.manifest_version != variants[change].manifest_version


def test_utf8_compact_canonical_json_and_timestamp_exclusion(registry: ConfigRegistry) -> None:
    manifest = project_capability_manifest(registry, tenant_id="тест", region="ру")
    semantic = asdict(manifest)
    expected = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        ).hexdigest()
    )
    assert manifest.manifest_version == expected
    assert "generated_at" not in semantic
    assert "manifest_version" not in semantic


def test_repeated_concurrent_projection_and_reload_have_same_version(
    registry: ConfigRegistry,
) -> None:
    def read_version(_: int) -> str:
        return project_capability_manifest(
            registry, tenant_id="anytoolai", region="ru"
        ).manifest_version

    expected = read_version(0)
    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(read_version, range(16))) == [expected] * 16
    reloaded = build_runtime(config_root=CONFIG_ROOT, database_url="").config_registry
    assert (
        project_capability_manifest(reloaded, tenant_id="anytoolai", region="ru").manifest_version
        == expected
    )


@pytest.mark.parametrize("reverse_order", [False, True])
def test_duplicate_disabled_metrics_across_bundle_roots_fail(
    registry: ConfigRegistry, tmp_path: Path, reverse_order: bool
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for destination, product_id in ((first, "proposal_ai"), (second, "brief_decoder")):
        source = Path(registry.products[product_id].metadata["_file_path"]).parent
        shutil.copytree(source, destination)
        path = destination / "product.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["usage_metrics"] = [
            {"metric_key": "shared.test_units", "unit": "unit", "enabled": False}
        ]
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
    roots = [second, first] if reverse_order else [first, second]

    with pytest.raises(RegistryLoadError) as exc_info:
        ConfigLoader(CONFIG_ROOT, extra_product_roots=roots).load()

    assert any(
        isinstance(error, DuplicateConfigIdError)
        and error.ref_type == "metric_key"
        and error.ref_value == "shared.test_units"
        and error.first_file == roots[0] / "product.yaml"
        and error.second_file == roots[1] / "product.yaml"
        for error in exc_info.value.errors
    )
