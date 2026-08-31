from __future__ import annotations

import importlib.util
import json
from pathlib import Path


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
        if name == "openapi.json":
            # Raw OpenAPI schema consumed by openapi-typescript codegen: must stay valid JSON,
            # so it carries no human-readable header.
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
