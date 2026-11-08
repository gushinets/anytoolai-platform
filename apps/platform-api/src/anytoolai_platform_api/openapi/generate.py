"""Export the platform API's raw OpenAPI schema.

This is the canonical source for CE-kit's `openapi-typescript` codegen (see
`packages/frontend/ce-kit/scripts/generate-api-types`) -- callers that need the
raw schema should import from here rather than calling `create_app().openapi()`
directly, so there is one place that defines what "the schema" means.
"""

from __future__ import annotations

import json
from typing import Any

from anytoolai_platform_api.schemas import CapabilityManifestResponse


def build_openapi_schema() -> dict[str, Any]:
    from anytoolai_platform_api.main import create_app

    schema = create_app().openapi()
    atom_path = "/v1/atom-lab/atoms/{atom_id}"
    # Share the same error response in clients without changing FastAPI's runtime routes.
    schema["components"].setdefault("responses", {})["AtomLabAtomNotFound"] = (
        schema["paths"][atom_path]["get"]["responses"]["404"]
    )
    for path, method in ((atom_path, "get"), (f"{atom_path}/prompts", "get"),
                         (f"{atom_path}/prompts", "post")):
        schema["paths"][path][method]["responses"]["404"] = {
            "$ref": "#/components/responses/AtomLabAtomNotFound",
        }
    return schema


def render_openapi_json(schema: dict[str, Any] | None = None) -> str:
    if schema is None:
        schema = build_openapi_schema()
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def build_capability_manifest_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        **CapabilityManifestResponse.model_json_schema(mode="serialization"),
    }


def render_capability_manifest_schema_json() -> str:
    return json.dumps(build_capability_manifest_schema(), indent=2, sort_keys=True) + "\n"
