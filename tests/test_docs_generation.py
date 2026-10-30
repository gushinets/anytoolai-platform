from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from anytoolai_platform_api.schemas import CapabilityManifestResponse


def load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "agent" / "docs_generation.py"
    spec = importlib.util.spec_from_file_location("docs_generation_module", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_documents_are_deterministic_and_source_marked() -> None:
    module = load_module()
    first = module.render_documents()
    second = module.render_documents()

    assert first == second
    assert set(first) == set(module.GENERATED_SOURCES)
    for name, content in first.items():
        if name.endswith(".json"):
            assert isinstance(json.loads(content), dict)
            assert "Generated file. Do not edit by hand." not in content
            continue
        assert "Generated file. Do not edit by hand." in content
        assert module.GENERATED_SOURCES[name] in content


def test_config_registry_surfaces_provider_policy_and_action_config_fields() -> None:
    from dataclasses import fields as dc_fields

    from anytoolai_platform_core.actions.models import ActionConfiguration
    from anytoolai_platform_core.providers.models import ProviderPolicy

    module = load_module()
    first = module.render_config_registry()
    second = module.render_config_registry()

    assert first == second
    assert "metadata" not in first.lower()

    registry = module._registry()
    assert registry.provider_policies, "fixture registry must define at least one provider policy"
    assert registry.action_configurations, "fixture registry must define at least one action config"

    provider_policy_fields = [f.name for f in dc_fields(ProviderPolicy) if f.name != "metadata"]
    action_config_fields = [f.name for f in dc_fields(ActionConfiguration) if f.name != "metadata"]

    # Every non-metadata dataclass field must have its own column — guards against a future
    # field silently missing the doc the way temperature/structured_output_mode/schema_version
    # did before the renderer switched to enumerating dataclass fields.
    assert "| " + " | ".join(provider_policy_fields) + " |" in first
    assert "| " + " | ".join(action_config_fields) + " |" in first

    for ref, policy in registry.provider_policies.items():
        row = "| " + " | ".join(
            module._format_field_value(getattr(policy, name)) for name in provider_policy_fields
        ) + " |"
        assert row in first, f"row for provider policy {ref} must render every field, in order"

    for ref, config in registry.action_configurations.items():
        row = "| " + " | ".join(
            module._format_field_value(getattr(config, name)) for name in action_config_fields
        ) + " |"
        assert row in first, f"row for action config {ref} must render every field, in order"


def test_openapi_includes_handoff_and_runtime_routes() -> None:
    module = load_module()
    openapi = module.render_openapi()

    assert "/health" in openapi
    assert "/v1/products/{product_id}/runtime-config" in openapi
    assert "/v1/handoffs" in openapi
    assert "/v1/handoffs/{handoff_token}" in openapi
    assert "/v1/handoffs/{handoff_token}/accept" in openapi
    assert "/v1/handoffs/{handoff_token}/decline" in openapi


def test_openapi_json_is_valid_and_matches_the_live_schema() -> None:
    module = load_module()
    schema = json.loads(module.render_openapi_json())

    from anytoolai_platform_api.openapi.generate import build_openapi_schema

    assert "/v1/products/{product_id}/runtime-config" in schema["paths"]
    assert schema == build_openapi_schema()


def test_manifest_schema_matches_serialization_model_and_openapi_success() -> None:
    checker_path = (
        Path(__file__).resolve().parents[1] / "scripts/agent/check_capability_manifest_contract.py"
    )
    spec = importlib.util.spec_from_file_location("manifest_checker", checker_path)
    assert spec is not None and spec.loader is not None
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    documents = load_module().render_documents()
    schema = json.loads(documents["capability-manifest-v1.schema.json"])
    assert schema == {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **CapabilityManifestResponse.model_json_schema(mode="serialization"),
    }
    openapi = json.loads(documents["openapi.json"])
    operation = openapi["paths"]["/internal/v1/capability-manifest"]["get"]
    success = operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert success == {"$ref": "#/components/schemas/CapabilityManifestResponse"}
    assert checker.resolve_schema(schema, schema) == checker.resolve_schema(success, openapi)
    assert operation["security"] == [{"PortalServiceBearer": []}]
    assert {item["name"] for item in operation["parameters"]} == {"tenant_id", "region"}


def test_all_generated_documents_are_fresh() -> None:
    root = Path(__file__).resolve().parents[1]
    for name, rendered in load_module().render_documents().items():
        assert (root / "docs/generated" / name).read_bytes() == rendered.encode("utf-8"), name


def test_openapi_exposes_closed_enums_for_the_boundary_fields() -> None:
    # ANY-338: every field the ticket names must resolve to a real enum component in the
    # generated schema, not FastAPI's default `"type": "string"` for a bare `str` field.
    # Enum values are compared against the Core StrEnums themselves, not copied literal lists, so
    # a future member added to a Core enum fails here with a clear diff instead of silently
    # passing a stale hand-written list.
    from anytoolai_platform_core.handoffs.models import HandoffStatus
    from anytoolai_platform_core.products.models import FrontendType
    from anytoolai_platform_core.quotas.models import QuotaDimension, QuotaPeriod, QuotaUnit
    from anytoolai_platform_core.scenarios.models import ScenarioSessionStatus

    module = load_module()
    schema = json.loads(module.render_openapi_json())
    components = schema["components"]["schemas"]

    assert components["FrontendType"]["enum"] == list(FrontendType)
    assert components["QuotaUnit"]["enum"] == list(QuotaUnit)
    assert components["QuotaPeriod"]["enum"] == list(QuotaPeriod)
    assert components["QuotaDimension"]["enum"] == list(QuotaDimension)
    assert components["ScenarioSessionStatus"]["enum"] == list(ScenarioSessionStatus)
    assert components["HandoffStatus"]["enum"] == list(HandoffStatus)

    assert components["RuntimeFrontendResponse"]["properties"]["type"] == {
        "$ref": "#/components/schemas/FrontendType"
    }
    quota_summary_props = components["RuntimeQuotaSummaryResponse"]["properties"]
    assert quota_summary_props["unit"] == {"$ref": "#/components/schemas/QuotaUnit"}
    assert quota_summary_props["period"] == {"$ref": "#/components/schemas/QuotaPeriod"}
    assert quota_summary_props["dimension"] == {"$ref": "#/components/schemas/QuotaDimension"}

    quota_state_props = components["QuotaStateResponse"]["properties"]
    assert quota_state_props["unit"] == {"$ref": "#/components/schemas/QuotaUnit"}
    assert quota_state_props["period"] == {"$ref": "#/components/schemas/QuotaPeriod"}
    assert quota_state_props["quota_dimension"] == {"$ref": "#/components/schemas/QuotaDimension"}

    assert components["ScenarioStartResponse"]["properties"]["status"] == {
        "$ref": "#/components/schemas/ScenarioSessionStatus"
    }
    assert components["ScenarioSessionResponse"]["properties"]["status"] == {
        "$ref": "#/components/schemas/ScenarioSessionStatus"
    }
    assert components["HandoffCreateResponse"]["properties"]["status"] == {
        "$ref": "#/components/schemas/HandoffStatus"
    }
    assert components["HandoffPreviewResponse"]["properties"]["status"] == {
        "$ref": "#/components/schemas/HandoffStatus"
    }
