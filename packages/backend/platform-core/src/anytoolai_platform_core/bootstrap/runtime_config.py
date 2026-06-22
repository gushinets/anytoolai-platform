"""Frontend-safe runtime config projection helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from anytoolai_platform_core.config.registry import ConfigRegistry

BASE_UI_CAPABILITIES = ("render_input", "render_output")
JSON_SCHEMA_RENDERER = "json_schema"


@dataclass(frozen=True)
class RuntimeRendererHint:
    renderer: str
    schema_ref: str
    schema_version: int | None = None


@dataclass(frozen=True)
class RuntimeFrontendMetadata:
    frontend_id: str
    type: str
    enabled: bool


@dataclass(frozen=True)
class RuntimeScenarioMetadata:
    scenario_id: str
    version: int
    allowed_next_actions: tuple[str, ...]
    input_renderer_hint: RuntimeRendererHint
    output_renderer_hint: RuntimeRendererHint


@dataclass(frozen=True)
class RuntimeQuotaSummary:
    quota_policy_id: str
    unit: str
    limit_count: int
    period: str


@dataclass(frozen=True)
class RuntimeProductConfig:
    product_id: str
    frontend_ids: tuple[str, ...]
    frontends: tuple[RuntimeFrontendMetadata, ...]
    scenario_ids: tuple[str, ...]
    scenarios: tuple[RuntimeScenarioMetadata, ...]
    quota_summary: RuntimeQuotaSummary | None
    allowed_ui_capabilities: tuple[str, ...]


def build_product_runtime_config(
    registry: ConfigRegistry,
    product_id: str,
) -> RuntimeProductConfig | None:
    """Return frontend-safe product runtime metadata, or ``None`` when unknown.

    This projection intentionally avoids prompt text, prompt refs, system prompts,
    provider policies/models, internal file paths, storage locations, and secrets.
    """

    product = registry.get_product(product_id)
    if product is None:
        return None

    frontends = tuple(
        RuntimeFrontendMetadata(
            frontend_id=frontend.frontend_id,
            type=_safe_value(frontend.type),
            enabled=frontend.enabled,
        )
        for frontend in product.frontends
        if frontend.enabled
    )
    scenario_metadata_items: list[RuntimeScenarioMetadata] = []
    for scenario_id in product.scenarios:
        scenario_metadata = _build_scenario_metadata(registry, scenario_id)
        if scenario_metadata is not None:
            scenario_metadata_items.append(scenario_metadata)
    scenarios = tuple(scenario_metadata_items)

    return RuntimeProductConfig(
        product_id=product.product_id,
        frontend_ids=tuple(frontend.frontend_id for frontend in frontends),
        frontends=frontends,
        scenario_ids=tuple(scenario.scenario_id for scenario in scenarios),
        scenarios=scenarios,
        quota_summary=_build_quota_summary(registry, product.quota_policy_ref),
        allowed_ui_capabilities=_allowed_ui_capabilities(scenarios),
    )


def _build_scenario_metadata(
    registry: ConfigRegistry,
    scenario_id: str,
) -> RuntimeScenarioMetadata | None:
    scenario = registry.get_scenario(scenario_id)
    if scenario is None:
        return None

    workflow = registry.get_workflow(scenario.workflow_id)
    if workflow is None:
        return None

    return RuntimeScenarioMetadata(
        scenario_id=scenario.scenario_id,
        version=scenario.version,
        allowed_next_actions=tuple(scenario.allowed_next_actions),
        input_renderer_hint=_renderer_hint(registry, workflow.input_schema_ref),
        output_renderer_hint=_renderer_hint(registry, workflow.output_schema_ref),
    )


def _renderer_hint(registry: ConfigRegistry, schema_ref: str) -> RuntimeRendererHint:
    schema = registry.get_schema(schema_ref)
    return RuntimeRendererHint(
        renderer=JSON_SCHEMA_RENDERER,
        schema_ref=schema_ref,
        schema_version=None if schema is None else schema.version,
    )


def _build_quota_summary(
    registry: ConfigRegistry,
    quota_policy_ref: str | None,
) -> RuntimeQuotaSummary | None:
    if quota_policy_ref is None:
        return None

    quota_policy = registry.get_quota_policy(quota_policy_ref)
    if quota_policy is None:
        return None

    return RuntimeQuotaSummary(
        quota_policy_id=quota_policy.quota_policy_id,
        unit=_safe_value(quota_policy.unit),
        limit_count=quota_policy.limit_count,
        period=_safe_value(quota_policy.period),
    )


def _allowed_ui_capabilities(
    scenarios: tuple[RuntimeScenarioMetadata, ...],
) -> tuple[str, ...]:
    capabilities = set(BASE_UI_CAPABILITIES)
    for scenario in scenarios:
        capabilities.update(scenario.allowed_next_actions)
    return tuple(sorted(capabilities))


def _safe_value(value: Any) -> str:
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return str(value)
