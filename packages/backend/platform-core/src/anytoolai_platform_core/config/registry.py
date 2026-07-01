"""Immutable, read-only config registry for MVP-A."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from anytoolai_platform_core.actions.models import (
    ActionConfiguration,
    ActionDefinition,
)
from anytoolai_platform_core.handoffs.models import HandoffDefinition
from anytoolai_platform_core.products.models import FrontendDefinition, ProductDefinition
from anytoolai_platform_core.providers.models import ProviderPolicy
from anytoolai_platform_core.quotas.models import QuotaPolicy
from anytoolai_platform_core.scenarios.models import ScenarioDefinition
from anytoolai_platform_core.workflows.models import (
    WorkflowDefinition,
    WorkflowStepDefinition,
)


@dataclass(frozen=True)
class TenantDefinition:
    """Immutable tenant configuration."""

    tenant_id: str
    display_name: str
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RegionDefinition:
    """Immutable region configuration."""

    region: str
    display_name: str
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SchemaDefinition:
    """Immutable JSON schema definition."""

    schema_ref: str
    version: int
    schema: dict[str, Any]
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PromptDefinition:
    """Immutable prompt definition."""

    prompt_ref: str
    version: int
    content: str
    input_variables: list[str] = field(default_factory=list)
    output_schema_ref: str | None = None
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return value
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


def _freeze_frontend(definition: FrontendDefinition) -> FrontendDefinition:
    return replace(definition, metadata=_freeze_value(definition.metadata))


def _freeze_product(definition: ProductDefinition) -> ProductDefinition:
    return replace(
        definition,
        frontends=tuple(_freeze_frontend(frontend) for frontend in definition.frontends),
        scenarios=tuple(definition.scenarios),
        analytics=_freeze_value(definition.analytics),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_action_definition(definition: ActionDefinition) -> ActionDefinition:
    return replace(
        definition,
        emits_events=tuple(definition.emits_events),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_action_configuration(
    definition: ActionConfiguration,
) -> ActionConfiguration:
    return replace(definition, metadata=_freeze_value(definition.metadata))


def _freeze_workflow_step(
    definition: WorkflowStepDefinition,
) -> WorkflowStepDefinition:
    return replace(
        definition,
        input_mapping=_freeze_value(definition.input_mapping),
        output_mapping=_freeze_value(definition.output_mapping),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_workflow(definition: WorkflowDefinition) -> WorkflowDefinition:
    return replace(
        definition,
        steps=tuple(_freeze_workflow_step(step) for step in definition.steps),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_scenario(definition: ScenarioDefinition) -> ScenarioDefinition:
    return replace(
        definition,
        allowed_next_actions=tuple(definition.allowed_next_actions),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_provider_policy(definition: ProviderPolicy) -> ProviderPolicy:
    return replace(definition, metadata=_freeze_value(definition.metadata))


def _freeze_quota_policy(definition: QuotaPolicy) -> QuotaPolicy:
    return replace(definition, metadata=_freeze_value(definition.metadata))


def _freeze_handoff(definition: HandoffDefinition) -> HandoffDefinition:
    return replace(
        definition,
        context_mapping=_freeze_value(definition.context_mapping),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_prompt(definition: PromptDefinition) -> PromptDefinition:
    return replace(
        definition,
        input_variables=tuple(definition.input_variables),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_schema(definition: SchemaDefinition) -> SchemaDefinition:
    return replace(
        definition,
        schema=_freeze_value(definition.schema),
        metadata=_freeze_value(definition.metadata),
    )


def _freeze_tenant(definition: TenantDefinition) -> TenantDefinition:
    return replace(definition, metadata=_freeze_value(definition.metadata))


def _freeze_region(definition: RegionDefinition) -> RegionDefinition:
    return replace(definition, metadata=_freeze_value(definition.metadata))


def _freeze_mapping(
    definitions: Mapping[str, Any],
    freezer: Callable[[Any], Any],
) -> Mapping[str, Any]:
    return MappingProxyType(
        {config_id: freezer(definition) for config_id, definition in definitions.items()}
    )


@dataclass(frozen=True)
class ConfigRegistry:
    """
    Immutable, read-only registry of all MVP-A configuration definitions.

    This is the single source of truth for:
    - Tenants and regions
    - Provider policies
    - Action definitions and configurations
    - Workflow, scenario, and product definitions
    - Prompt and schema definitions
    - Quota and handoff policies
    - Analytics event mappings

    All mappings are frozen (immutable) via MappingProxyType.

    Attributes:
        loaded_from: Path to the config root that was loaded (for logging/debugging)
        tenants: Immutable mapping of tenant_id -> TenantDefinition
        regions: Immutable mapping of region -> RegionDefinition
        provider_policies: Immutable mapping of provider_policy_ref -> ProviderPolicy
        action_definitions: Immutable mapping of action_type -> ActionDefinition
        action_configurations: Immutable mapping of action_config_id -> ActionConfiguration
        workflows: Immutable mapping of workflow_id -> WorkflowDefinition
        scenarios: Immutable mapping of scenario_id -> ScenarioDefinition
        products: Immutable mapping of product_id -> ProductDefinition
        prompts: Immutable mapping of prompt_ref -> PromptDefinition
        schemas: Immutable mapping of schema_ref -> SchemaDefinition
        quotas: Immutable mapping of quota_policy_id -> QuotaPolicy
        handoffs: Immutable mapping of handoff_id -> HandoffDefinition
    """

    loaded_from: Path
    tenants: Mapping[str, TenantDefinition]
    regions: Mapping[str, RegionDefinition]
    provider_policies: Mapping[str, ProviderPolicy]
    action_definitions: Mapping[str, ActionDefinition]
    action_configurations: Mapping[str, ActionConfiguration]
    workflows: Mapping[str, WorkflowDefinition]
    scenarios: Mapping[str, ScenarioDefinition]
    products: Mapping[str, ProductDefinition]
    prompts: Mapping[str, PromptDefinition]
    schemas: Mapping[str, SchemaDefinition]
    quotas: Mapping[str, QuotaPolicy]
    handoffs: Mapping[str, HandoffDefinition]
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Ensure all mappings are immutable."""
        object.__setattr__(
            self, "tenants", _freeze_mapping(dict(self.tenants), _freeze_tenant)
        )
        object.__setattr__(
            self, "regions", _freeze_mapping(dict(self.regions), _freeze_region)
        )
        object.__setattr__(
            self,
            "provider_policies",
            _freeze_mapping(dict(self.provider_policies), _freeze_provider_policy),
        )
        object.__setattr__(
            self,
            "action_definitions",
            _freeze_mapping(dict(self.action_definitions), _freeze_action_definition),
        )
        object.__setattr__(
            self,
            "action_configurations",
            _freeze_mapping(
                dict(self.action_configurations), _freeze_action_configuration
            ),
        )
        object.__setattr__(
            self, "workflows", _freeze_mapping(dict(self.workflows), _freeze_workflow)
        )
        object.__setattr__(
            self, "scenarios", _freeze_mapping(dict(self.scenarios), _freeze_scenario)
        )
        object.__setattr__(
            self, "products", _freeze_mapping(dict(self.products), _freeze_product)
        )
        object.__setattr__(
            self, "prompts", _freeze_mapping(dict(self.prompts), _freeze_prompt)
        )
        object.__setattr__(
            self, "schemas", _freeze_mapping(dict(self.schemas), _freeze_schema)
        )
        object.__setattr__(
            self, "quotas", _freeze_mapping(dict(self.quotas), _freeze_quota_policy)
        )
        object.__setattr__(
            self, "handoffs", _freeze_mapping(dict(self.handoffs), _freeze_handoff)
        )
        object.__setattr__(self, "metadata", _freeze_value(self.metadata))

    def get_action_definition(self, action_type: str) -> ActionDefinition | None:
        """Look up action definition by type."""
        return self.action_definitions.get(action_type)

    def get_action_configuration(self, action_config_id: str) -> ActionConfiguration | None:
        """Look up action configuration by ID."""
        return self.action_configurations.get(action_config_id)

    def get_action_config(self, action_config_id: str) -> ActionConfiguration | None:
        """Look up action configuration by ID using MVP-A naming."""
        return self.get_action_configuration(action_config_id)

    def get_workflow(self, workflow_id: str) -> WorkflowDefinition | None:
        """Look up workflow definition by ID."""
        return self.workflows.get(workflow_id)

    def get_scenario(self, scenario_id: str) -> ScenarioDefinition | None:
        """Look up scenario definition by ID."""
        return self.scenarios.get(scenario_id)

    def get_product(self, product_id: str) -> ProductDefinition | None:
        """Look up product definition by ID."""
        return self.products.get(product_id)

    def get_provider_policy(self, provider_policy_ref: str) -> ProviderPolicy | None:
        """Look up provider policy by ID."""
        return self.provider_policies.get(provider_policy_ref)

    def get_prompt(self, prompt_ref: str) -> PromptDefinition | None:
        """Look up prompt definition by ref."""
        return self.prompts.get(prompt_ref)

    def get_schema(self, schema_ref: str) -> SchemaDefinition | None:
        """Look up schema definition by ref."""
        return self.schemas.get(schema_ref)

    def get_quota_policy(self, quota_policy_id: str) -> QuotaPolicy | None:
        """Look up quota policy by ID."""
        return self.quotas.get(quota_policy_id)

    def get_handoff(self, handoff_id: str) -> HandoffDefinition | None:
        """Look up handoff definition by ID."""
        return self.handoffs.get(handoff_id)
