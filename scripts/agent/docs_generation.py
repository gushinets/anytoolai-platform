from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
PLATFORM_CORE_SRC = ROOT / "packages" / "backend" / "platform-core" / "src"
PLATFORM_API_SRC = ROOT / "apps" / "platform-api" / "src"
for source_root in (PLATFORM_CORE_SRC, PLATFORM_API_SRC):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

GENERATED_SOURCES = {
    "action-registry.md": "configs/kernel/action_definitions/*.yaml",
    "config-registry.md": "configs/kernel via ConfigLoader",
    "db-schema.md": "anytoolai_platform_core.storage.db.runtime_metadata",
    "event-catalog.md": "configs/kernel/platform_events.yaml",
    "openapi.md": "anytoolai_platform_api.main.create_app().openapi()",
}


def _header(title: str, source: str) -> list[str]:
    return [
        f"# {title}",
        "",
        "<!-- Generated file. Do not edit by hand. -->",
        f"Canonical source: {source}.",
        "",
    ]


def _registry() -> Any:
    from anytoolai_platform_core.config.loader import ConfigLoader

    return ConfigLoader(ROOT / "configs" / "kernel").load()


def render_action_registry() -> str:
    registry = _registry()
    lines = _header("Action Registry", GENERATED_SOURCES["action-registry.md"])
    lines.extend(["| Action type | Input schema | Output schema |", "|---|---|---|"])
    for action_type, definition in sorted(registry.action_definitions.items()):
        lines.append(
            f"| {action_type} | {definition.input_schema_ref} | "
            f"{definition.output_schema_ref} |"
        )
    return "\n".join(lines) + "\n"


def render_config_registry() -> str:
    registry = _registry()
    sections = (
        ("Tenants", registry.tenants),
        ("Regions", registry.regions),
        ("Provider policies", registry.provider_policies),
        ("Action definitions", registry.action_definitions),
        ("Action configurations", registry.action_configurations),
        ("Workflows", registry.workflows),
        ("Scenarios", registry.scenarios),
        ("Products", registry.products),
        ("Prompts", registry.prompts),
        ("Schemas", registry.schemas),
        ("Quotas", registry.quotas),
        ("Handoffs", registry.handoffs),
    )
    lines = _header("Config Registry", GENERATED_SOURCES["config-registry.md"])
    for title, values in sections:
        lines.extend([f"## {title}", "", *[f"- {key}" for key in sorted(values)], ""])
    return "\n".join(lines)


def render_db_schema() -> str:
    from anytoolai_platform_core.storage.db import runtime_metadata

    lines = _header("DB Schema", GENERATED_SOURCES["db-schema.md"])
    lines.extend(
        [
            "Definitions remain in repository configuration; these tables store runtime state.",
            "",
        ]
    )
    for table in sorted(runtime_metadata.tables.values(), key=lambda item: item.fullname):
        lines.extend(
            [
                f"## {table.fullname}",
                "",
                "| Column | Type | Nullable |",
                "|---|---|---|",
            ]
        )
        for column in table.columns:
            lines.append(
                f"| {column.name} | {column.type} | "
                f"{'yes' if column.nullable else 'no'} |"
            )
        lines.append("")
    return "\n".join(lines)


def render_event_catalog() -> str:
    taxonomy_path = (
        PLATFORM_CORE_SRC / "anytoolai_platform_core" / "events" / "taxonomy.py"
    )
    spec = importlib.util.spec_from_file_location("generated_event_taxonomy", taxonomy_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load event taxonomy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.render_event_catalog_markdown()


def render_openapi() -> str:
    from anytoolai_platform_api.main import create_app

    schema = create_app().openapi()
    lines = _header("OpenAPI", GENERATED_SOURCES["openapi.md"])
    lines.extend(
        [
            f"API title: {schema['info']['title']}",
            "",
            f"Version: {schema['info']['version']}",
            "",
            "## Implemented operations",
            "",
            "| Method | Path | Operation ID |",
            "|---|---|---|",
        ]
    )
    for path, operations in sorted(schema.get("paths", {}).items()):
        for method, operation in sorted(operations.items()):
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            lines.append(
                f"| {method.upper()} | {path} | {operation.get('operationId', '')} |"
            )
    lines.extend(["", "## Component schemas", ""])
    schemas = schema.get("components", {}).get("schemas", {})
    lines.extend(f"- {name}" for name in sorted(schemas))
    lines.append("")
    return "\n".join(lines)


def render_documents() -> dict[str, str]:
    return {
        "action-registry.md": render_action_registry(),
        "config-registry.md": render_config_registry(),
        "db-schema.md": render_db_schema(),
        "event-catalog.md": render_event_catalog(),
        "openapi.md": render_openapi(),
    }


def write_documents(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, content in render_documents().items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="\n")
