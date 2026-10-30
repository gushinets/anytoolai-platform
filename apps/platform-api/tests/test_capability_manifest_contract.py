from __future__ import annotations

import copy
import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from anytoolai_platform_api.bootstrap import build_runtime
from anytoolai_platform_api.manifest_auth import PortalPrincipal
from anytoolai_platform_api.routers.capability_manifest import get_capability_manifest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
EXPECTED_PRODUCT_COUNT = 6
EXPECTED_METRIC_COUNT = 2


@pytest.fixture(scope="module")
def oracle() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "manifest_contract_oracle", ROOT / "scripts/agent/check_capability_manifest_contract.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def schema(oracle: ModuleType) -> dict[str, Any]:
    return json.loads(oracle.SCHEMA.read_text(encoding="utf-8"))


@pytest.fixture
def positive(oracle: ModuleType) -> dict[str, Any]:
    return json.loads(
        (oracle.CONTRACT / "fixtures/valid-manifest.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def peer_contract(oracle: ModuleType, schema: dict[str, Any], tmp_path: Path) -> Path:
    peer = tmp_path / "docs/contracts/kernel-capability-manifest/v1"
    (peer / "fixtures").mkdir(parents=True)
    for name in ("valid-manifest.json", "valid-manifest.digest"):
        (peer / "fixtures" / name).write_bytes((oracle.CONTRACT / "fixtures" / name).read_bytes())
    (peer / "manifest.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    return peer


def test_canonical_fixtures_checksums_and_negative_cases(oracle: ModuleType) -> None:
    oracle.check_fixtures()


def test_real_producer_serialization_matches_complete_disabled_fixture(
    oracle: ModuleType, schema: dict[str, Any], positive: dict[str, Any]
) -> None:
    runtime = build_runtime(config_root=ROOT / "configs/kernel", database_url="")
    response = get_capability_manifest(
        PortalPrincipal(tenant_id="anytoolai", region="ru"), runtime.config_registry
    ).model_dump(mode="json")
    oracle.validate_manifest(response, schema)
    expected = json.loads(
        (oracle.CONTRACT / "fixtures/default-disabled-manifest.json").read_text(encoding="utf-8")
    )
    assert {k: v for k, v in response.items() if k != "generated_at"} == {
        k: v for k, v in expected.items() if k != "generated_at"
    }
    assert {row["product_id"] for row in response["products"]} == {
        row["product_id"] for row in positive["products"]
    }
    assert len(response["products"]) == EXPECTED_PRODUCT_COUNT
    assert len(response["usage_metrics"]) == EXPECTED_METRIC_COUNT
    assert all(not row["enabled"] for row in response["products"] + response["usage_metrics"])


def test_timestamp_and_array_object_order_do_not_change_version(
    oracle: ModuleType, schema: dict[str, Any], positive: dict[str, Any]
) -> None:
    positive["generated_at"] = "2026-10-29T12:00:00+08:00"
    positive["products"].reverse()
    positive["usage_metrics"].reverse()
    reordered = json.loads(json.dumps(positive, sort_keys=True))
    oracle.validate_manifest(reordered, schema)
    assert oracle.semantic_digest(reordered) == oracle.POSITIVE_VERSION


def test_enabled_test_declarations_serialize_to_retained_positive_semantics(
    oracle: ModuleType, schema: dict[str, Any], positive: dict[str, Any]
) -> None:
    registry = build_runtime(config_root=ROOT / "configs/kernel", database_url="").config_registry
    enabled = {"proposal_ai", "brief_decoder"}
    isolated = replace(
        registry,
        products={
            key: replace(
                product,
                commercial_admission_enabled=key in enabled,
                usage_metrics=tuple(
                    replace(metric, enabled=True) for metric in product.usage_metrics
                ),
            )
            for key, product in registry.products.items()
        },
    )
    response = get_capability_manifest(
        PortalPrincipal(tenant_id="anytoolai", region="ru"), isolated
    ).model_dump(mode="json")
    oracle.validate_manifest(response, schema)
    assert response["manifest_version"] == oracle.POSITIVE_VERSION
    positive["usage_metrics"].sort(key=lambda row: row["metric_key"])
    assert {k: v for k, v in response.items() if k != "generated_at"} == {
        k: v for k, v in positive.items() if k != "generated_at"
    }
    assert all(not product.commercial_admission_enabled for product in registry.products.values())


@pytest.mark.parametrize(
    ("collection", "field", "value"),
    [
        (None, "tenant_id", "other"),
        (None, "region", "other"),
        (None, "schema_version", 2),
        ("products", "product_id", "changed"),
        ("products", "enabled", True),
        ("usage_metrics", "metric_key", "changed"),
        ("usage_metrics", "product_id", "brief_decoder"),
        ("usage_metrics", "unit", "changed"),
        ("usage_metrics", "enabled", False),
    ],
)
def test_independent_digest_detects_material_field_changes(
    oracle: ModuleType,
    positive: dict[str, Any],
    collection: str | None,
    field: str,
    value: Any,
) -> None:
    target = positive if collection is None else positive[collection][0]
    assert target[field] != value
    target[field] = value
    assert oracle.semantic_digest(positive) != oracle.POSITIVE_VERSION


@pytest.mark.parametrize("collection", ["products", "usage_metrics"])
def test_independent_digest_detects_removed_declarations(
    oracle: ModuleType, positive: dict[str, Any], collection: str
) -> None:
    positive[collection].pop()
    assert oracle.semantic_digest(positive) != oracle.POSITIVE_VERSION


def test_protocol_integer_is_strict(
    oracle: ModuleType, schema: dict[str, Any], positive: dict[str, Any]
) -> None:
    positive["schema_version"] = 1.0
    with pytest.raises(oracle.ContractFailure, match="^wire$"):
        oracle.validate_manifest(positive, schema)


def test_vendor_copy_check_detects_fixture_and_schema_drift(
    oracle: ModuleType, schema: dict[str, Any], tmp_path: Path, peer_contract: Path
) -> None:
    peer = peer_contract
    oracle.check_portal_copy(tmp_path)
    fixture = peer / "fixtures/valid-manifest.json"
    fixture.write_bytes(fixture.read_bytes() + b"\n")
    with pytest.raises(oracle.ContractFailure, match="^portal_fixture_drift$"):
        oracle.check_portal_copy(tmp_path)
    fixture.write_bytes((oracle.CONTRACT / "fixtures/valid-manifest.json").read_bytes())
    changed = copy.deepcopy(schema)
    changed["properties"]["tenant_id"]["minLength"] = 2
    (peer / "manifest.schema.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(oracle.ContractFailure, match="^portal_schema_drift$"):
        oracle.check_portal_copy(tmp_path)
    # A wire field named like a schema annotation must still participate in comparison.
    changed = copy.deepcopy(schema)
    changed["properties"]["description"] = {"type": "string"}
    (peer / "manifest.schema.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(oracle.ContractFailure, match="^portal_schema_drift$"):
        oracle.check_portal_copy(tmp_path)


def test_vendor_copy_check_refuses_reference_constraints_that_hide_wire_drift(
    oracle: ModuleType,
    schema: dict[str, Any],
    positive: dict[str, Any],
    tmp_path: Path,
    peer_contract: Path,
) -> None:
    changed = copy.deepcopy(schema)
    changed["$defs"]["Unit"] = {"type": "string", "minLength": 2}
    changed["$defs"]["CapabilityMetricResponse"]["properties"]["unit"] = {
        "$ref": "#/$defs/Unit",
        "minLength": 1,
    }
    Draft202012Validator.check_schema(changed)
    positive["usage_metrics"][0]["unit"] = "x"
    assert Draft202012Validator(schema).is_valid(positive)
    assert not Draft202012Validator(changed).is_valid(positive)
    (peer_contract / "manifest.schema.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(oracle.ContractFailure, match="^unsupported_reference_siblings$"):
        oracle.check_portal_copy(tmp_path)


@pytest.mark.parametrize("constraint", [{"minLength": 1}, {"type": "string"}, {"pattern": ".*"}])
def test_reference_validation_siblings_are_rejected(
    oracle: ModuleType, constraint: dict[str, Any]
) -> None:
    schema = {
        "$defs": {"Unit": {"type": "string", "minLength": 2}},
        "$ref": "#/$defs/Unit",
        **constraint,
    }
    with pytest.raises(oracle.ContractFailure, match="^unsupported_reference_siblings$"):
        oracle.resolve_schema(schema, schema)


def test_reference_annotations_preserve_referenced_constraints(oracle: ModuleType) -> None:
    unit = {"type": "string", "minLength": 2}
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": {"Unit": unit},
        "$ref": "#/$defs/Unit",
        "title": "Annotated unit",
        "description": "Documentation only",
    }
    assert oracle.resolve_schema(schema, schema) == unit


@pytest.mark.parametrize("offset", ["+00:60", "-00:60", "+01:99", "-01:99", "+24:00", "-24:00"])
def test_invalid_timezone_offsets_are_rejected_without_optional_format_checker(
    oracle: ModuleType,
    schema: dict[str, Any],
    positive: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    offset: str,
) -> None:
    monkeypatch.setattr(oracle, "FormatChecker", lambda: None)
    positive["generated_at"] = f"2026-10-15T00:00:00{offset}"
    with pytest.raises(oracle.ContractFailure, match="^wire$"):
        oracle.validate_manifest(positive, schema)


@pytest.mark.parametrize("offset", ["Z", "z", "+00:00", "-00:00", "+23:59", "-23:59", "+05:30"])
def test_valid_timezone_offsets_preserve_version_without_optional_format_checker(
    oracle: ModuleType,
    schema: dict[str, Any],
    positive: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    offset: str,
) -> None:
    monkeypatch.setattr(oracle, "FormatChecker", lambda: None)
    positive["generated_at"] = f"2026-10-15T00:00:00{offset}"
    oracle.validate_manifest(positive, schema)
    assert oracle.semantic_digest(positive) == oracle.POSITIVE_VERSION
