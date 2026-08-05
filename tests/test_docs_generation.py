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
