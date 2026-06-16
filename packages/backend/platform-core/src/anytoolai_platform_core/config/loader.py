"""Deterministic config loader for MVP-A."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from anytoolai_platform_core.actions.models import (
    ActionConfiguration,
    ActionDefinition,
    ActionExecutor,
)
from anytoolai_platform_core.config.errors import (
    BrokenReferenceError,
    ConfigError,
    DuplicateConfigIdError,
    InvalidConfigShapeError,
    MissingConfigFileError,
    RegistryLoadError,
)
from anytoolai_platform_core.config.registry import (
    ConfigRegistry,
    PromptDefinition,
    RegionDefinition,
    SchemaDefinition,
    TenantDefinition,
)
from anytoolai_platform_core.handoffs.models import HandoffDefinition
from anytoolai_platform_core.products.models import (
    FrontendDefinition,
    FrontendType,
    ProductDefinition,
)
from anytoolai_platform_core.providers.models import (
    ProviderPolicy,
    StructuredOutputMode,
)
from anytoolai_platform_core.quotas.models import QuotaPeriod, QuotaPolicy, QuotaUnit
from anytoolai_platform_core.scenarios.models import ScenarioDefinition
from anytoolai_platform_core.workflows.models import (
    WorkflowDefinition,
    WorkflowStepDefinition,
)

VERSION_SUFFIX_PATTERN = re.compile(r"(?P<separator>[._])v(?P<version>\d+)$")


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load and parse a YAML file."""
    if not path.exists():
        raise MissingConfigFileError(path)

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise InvalidConfigShapeError(
            path,
            "Expected a YAML mapping at root level",
        )
    return data


def load_json_file(path: Path) -> dict[str, Any]:
    """Load and parse a JSON file."""
    if not path.exists():
        raise MissingConfigFileError(path)

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise InvalidConfigShapeError(
            path,
            "Expected a JSON object at root level",
        )
    return data


class ConfigLoader:
    """Build an immutable ``ConfigRegistry`` from the repo config tree."""

    def __init__(self, config_root: Path) -> None:
        self.config_root = config_root
        self.tenants: dict[str, TenantDefinition] = {}
        self.regions: dict[str, RegionDefinition] = {}
        self.provider_policies: dict[str, ProviderPolicy] = {}
        self.action_definitions: dict[str, ActionDefinition] = {}
        self.action_configurations: dict[str, ActionConfiguration] = {}
        self.workflows: dict[str, WorkflowDefinition] = {}
        self.scenarios: dict[str, ScenarioDefinition] = {}
        self.products: dict[str, ProductDefinition] = {}
        self.prompts: dict[str, PromptDefinition] = {}
        self.schemas: dict[str, SchemaDefinition] = {}
        self.quotas: dict[str, QuotaPolicy] = {}
        self.handoffs: dict[str, HandoffDefinition] = {}
        self.errors: list[ConfigError] = []
        self.product_dirs: dict[str, Path] = {}
        self.source_paths: dict[tuple[str, str], Path] = {}

    def load(self) -> ConfigRegistry:
        """Load the config tree and return an immutable registry."""
        try:
            self._load_tenants()
            self._load_regions()
            self._load_provider_policies()
            self._load_action_definitions()
            self._load_products()
            self._load_prompts()
            self._load_schemas()
            self._validate_cross_references()

            if self.errors:
                raise RegistryLoadError(
                    f"Config registry load failed with {len(self.errors)} error(s)",
                    errors=self.errors,
                )

            return ConfigRegistry(
                loaded_from=self.config_root.resolve(),
                tenants=dict(self.tenants),
                regions=dict(self.regions),
                provider_policies=dict(self.provider_policies),
                action_definitions=dict(self.action_definitions),
                action_configurations=dict(self.action_configurations),
                workflows=dict(self.workflows),
                scenarios=dict(self.scenarios),
                products=dict(self.products),
                prompts=dict(self.prompts),
                schemas=dict(self.schemas),
                quotas=dict(self.quotas),
                handoffs=dict(self.handoffs),
            )
        except ConfigError:
            raise
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise RegistryLoadError(
                "Unexpected error during config load",
                context=str(exc),
            ) from exc

    def _remember_source(self, config_type: str, config_id: str, file_path: Path) -> None:
        self.source_paths[(config_type, config_id)] = file_path

    def _source_for(
        self,
        config_type: str,
        config_id: str,
        fallback: Path,
    ) -> Path:
        return self.source_paths.get((config_type, config_id), fallback)

    def _append_error(self, error: ConfigError) -> None:
        self.errors.append(error)

    def _load_tenants(self) -> None:
        path = self.config_root / "default_tenant.yaml"
        try:
            data = load_yaml_file(path)
            tenant_id = data.get("tenant_id")
            display_name = data.get("display_name")

            if not tenant_id or not display_name:
                raise InvalidConfigShapeError(
                    path,
                    "Missing required fields: tenant_id, display_name",
                )

            self.tenants[tenant_id] = TenantDefinition(
                tenant_id=tenant_id,
                display_name=display_name,
                metadata={"_file_path": str(path)},
            )
            self._remember_source("tenant", tenant_id, path)
        except ConfigError as error:
            self._append_error(error)

    def _load_regions(self) -> None:
        path = self.config_root / "regions.yaml"
        try:
            data = load_yaml_file(path)
            for region_data in data.get("regions", []):
                region = region_data.get("region")
                display_name = region_data.get("display_name")

                if not region or not display_name:
                    raise InvalidConfigShapeError(
                        path,
                        f"Region entry missing required fields: {region_data}",
                    )

                if region in self.regions:
                    raise DuplicateConfigIdError(
                        "region",
                        region,
                        self._source_for("region", region, path),
                        path,
                    )

                self.regions[region] = RegionDefinition(
                    region=region,
                    display_name=display_name,
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("region", region, path)
        except ConfigError as error:
            self._append_error(error)

    def _load_provider_policies(self) -> None:
        path = self.config_root / "provider_policies.yaml"
        try:
            data = load_yaml_file(path)
            for policy_data in data.get("provider_policies", []):
                policy_id = policy_data.get("provider_policy_id")
                provider = policy_data.get("provider")
                model = policy_data.get("model")

                if not all([policy_id, provider, model]):
                    raise InvalidConfigShapeError(
                        path,
                        f"Provider policy missing required fields: {policy_data}",
                    )

                if policy_id in self.provider_policies:
                    raise DuplicateConfigIdError(
                        "provider_policy_id",
                        policy_id,
                        self._source_for("provider_policy", policy_id, path),
                        path,
                    )

                self.provider_policies[policy_id] = ProviderPolicy(
                    provider_policy_id=policy_id,
                    provider=provider,
                    model=model,
                    temperature=policy_data.get("temperature", 0.3),
                    timeout_seconds=policy_data.get("timeout_seconds", 60),
                    max_retries=policy_data.get("max_retries", 2),
                    fallback_policy=policy_data.get("fallback_policy"),
                    structured_output_mode=StructuredOutputMode(
                        policy_data.get(
                            "structured_output_mode",
                            StructuredOutputMode.json_schema,
                        )
                    ),
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("provider_policy", policy_id, path)
        except ConfigError as error:
            self._append_error(error)

    def _load_action_definitions(self) -> None:
        action_dir = self.config_root / "action_definitions"
        if not action_dir.exists():
            self._append_error(
                MissingConfigFileError(
                    action_dir,
                    "Expected action_definitions directory",
                )
            )
            return

        for path in sorted(action_dir.glob("*.yaml")):
            try:
                data = load_yaml_file(path)
                action_type = data.get("action_type")
                version = data.get("version")
                executor = data.get("executor")
                input_schema_ref = data.get("input_schema_ref")
                output_schema_ref = data.get("output_schema_ref")

                if not all(
                    [
                        action_type,
                        version is not None,
                        executor,
                        input_schema_ref,
                        output_schema_ref,
                    ]
                ):
                    raise InvalidConfigShapeError(
                        path,
                        (
                            "Missing required fields: action_type, version, executor, "
                            "input_schema_ref, output_schema_ref"
                        ),
                    )

                if action_type in self.action_definitions:
                    raise DuplicateConfigIdError(
                        "action_type",
                        action_type,
                        self._source_for("action_definition", action_type, path),
                        path,
                    )

                self.action_definitions[action_type] = ActionDefinition(
                    action_type=action_type,
                    version=version,
                    input_schema_ref=input_schema_ref,
                    output_schema_ref=output_schema_ref,
                    executor=ActionExecutor(executor),
                    emits_events=data.get("emits_events", []),
                    description=data.get("description"),
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("action_definition", action_type, path)
            except ConfigError as error:
                self._append_error(error)

    def _load_products(self) -> None:
        products_dir = self.config_root / "products"
        if not products_dir.exists():
            self._append_error(
                MissingConfigFileError(
                    products_dir,
                    "Expected products directory",
                )
            )
            return

        for product_dir in sorted(products_dir.iterdir()):
            if product_dir.is_dir():
                self._load_product(product_dir)

    def _load_product(self, product_dir: Path) -> None:
        product_file = product_dir / "product.yaml"
        try:
            product_data = load_yaml_file(product_file)
            product_id = product_data.get("product_id")
            product_platform = product_data.get("product_platform")
            display_name = product_data.get("display_name")

            if not all([product_id, product_platform, display_name]):
                raise InvalidConfigShapeError(
                    product_file,
                    "Missing required fields: product_id, product_platform, display_name",
                )

            if product_id in self.products:
                raise DuplicateConfigIdError(
                    "product_id",
                    product_id,
                    self._source_for("product", product_id, product_file),
                    product_file,
                )

            self.product_dirs[product_id] = product_dir

            self._load_action_configs(product_dir / "action_configs.yaml")
            self._load_workflows(product_dir / "workflows.yaml")
            self._load_scenarios(product_dir / "scenarios.yaml")

            quota_refs = self._load_quotas(product_dir / "quotas.yaml")
            self._load_handoffs(product_dir / "handoffs.yaml")

            frontends = self._load_frontends(
                product_dir / "frontends.yaml",
                fallback_frontends=product_data.get("frontends", []),
            )
            analytics = self._load_analytics(
                product_dir / "analytics.yaml",
                fallback_analytics=product_data.get("analytics", {}),
            )

            quota_policy_ref = product_data.get("quota_policy_ref")
            if quota_policy_ref is None and len(quota_refs) == 1:
                quota_policy_ref = quota_refs[0]
            if quota_policy_ref is None and len(quota_refs) > 1:
                raise InvalidConfigShapeError(
                    product_file,
                    "Multiple quota policies found; product.yaml must set quota_policy_ref",
                    config_id=product_id,
                )

            scenarios = product_data.get("scenarios", [])
            if not isinstance(scenarios, list):
                raise InvalidConfigShapeError(
                    product_file,
                    "Expected scenarios to be a list",
                    config_id=product_id,
                )

            self.products[product_id] = ProductDefinition(
                product_id=product_id,
                product_platform=product_platform,
                display_name=display_name,
                frontends=frontends,
                scenarios=scenarios,
                quota_policy_ref=quota_policy_ref,
                analytics=analytics,
                metadata={"_file_path": str(product_file)},
            )
            self._remember_source("product", product_id, product_file)
        except ConfigError as error:
            self._append_error(error)

    def _load_frontends(
        self,
        path: Path,
        fallback_frontends: list[dict[str, Any]],
    ) -> list[FrontendDefinition]:
        frontends_data = fallback_frontends
        source_path = path

        if path.exists():
            data = load_yaml_file(path)
            frontends_data = data.get("frontends", [])
        else:
            source_path = path.parent / "product.yaml"

        frontends: list[FrontendDefinition] = []
        for frontend_data in frontends_data:
            frontend_id = frontend_data.get("frontend_id")
            frontend_type = frontend_data.get("type")
            if not frontend_id or not frontend_type:
                raise InvalidConfigShapeError(
                    source_path,
                    f"Frontend missing required fields: {frontend_data}",
                )

            frontends.append(
                FrontendDefinition(
                    frontend_id=frontend_id,
                    type=FrontendType(frontend_type),
                    enabled=frontend_data.get("enabled", True),
                    metadata={"_file_path": str(source_path)},
                )
            )
        return frontends

    def _load_analytics(
        self,
        path: Path,
        fallback_analytics: dict[str, Any],
    ) -> dict[str, Any]:
        if path.exists():
            return load_yaml_file(path)
        return fallback_analytics

    def _load_action_configs(self, path: Path) -> None:
        try:
            data = load_yaml_file(path)
            for config_data in data.get("action_configs", []):
                config_id = config_data.get("action_config_id")
                action_type = config_data.get("action_type")
                prompt_ref = config_data.get("prompt_ref")
                provider_policy_ref = config_data.get("provider_policy_ref")

                if not all([config_id, action_type, prompt_ref, provider_policy_ref]):
                    raise InvalidConfigShapeError(
                        path,
                        f"Action config missing required fields: {config_data}",
                    )

                if config_id in self.action_configurations:
                    raise DuplicateConfigIdError(
                        "action_config_id",
                        config_id,
                        self._source_for("action_config", config_id, path),
                        path,
                    )

                self.action_configurations[config_id] = ActionConfiguration(
                    action_config_id=config_id,
                    action_type=action_type,
                    prompt_ref=prompt_ref,
                    provider_policy_ref=provider_policy_ref,
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("action_config", config_id, path)
        except ConfigError as error:
            self._append_error(error)

    def _load_workflows(self, path: Path) -> None:
        try:
            data = load_yaml_file(path)
            for workflow_data in data.get("workflows", []):
                workflow_id = workflow_data.get("workflow_id")
                version = workflow_data.get("version")
                input_schema_ref = workflow_data.get("input_schema_ref")
                output_schema_ref = workflow_data.get("output_schema_ref")

                if not all(
                    [
                        workflow_id,
                        version is not None,
                        input_schema_ref,
                        output_schema_ref,
                    ]
                ):
                    raise InvalidConfigShapeError(
                        path,
                        f"Workflow missing required fields: {workflow_data}",
                    )

                if workflow_id in self.workflows:
                    raise DuplicateConfigIdError(
                        "workflow_id",
                        workflow_id,
                        self._source_for("workflow", workflow_id, path),
                        path,
                    )

                steps: list[WorkflowStepDefinition] = []
                for step_data in workflow_data.get("steps", []):
                    step_id = step_data.get("step_id")
                    action_config_id = step_data.get("action_config_id")
                    if not all([step_id, action_config_id]):
                        raise InvalidConfigShapeError(
                            path,
                            f"Workflow step missing required fields: {step_data}",
                            config_id=workflow_id,
                        )

                    steps.append(
                        WorkflowStepDefinition(
                            step_id=step_id,
                            action_config_id=action_config_id,
                            input_mapping=step_data.get("input_mapping", {}),
                            output_mapping=step_data.get("output_mapping", {}),
                            when=step_data.get("when"),
                            metadata={"_file_path": str(path)},
                        )
                    )

                self.workflows[workflow_id] = WorkflowDefinition(
                    workflow_id=workflow_id,
                    version=version,
                    input_schema_ref=input_schema_ref,
                    output_schema_ref=output_schema_ref,
                    steps=steps,
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("workflow", workflow_id, path)
        except ConfigError as error:
            self._append_error(error)

    def _load_scenarios(self, path: Path) -> None:
        try:
            data = load_yaml_file(path)
            for scenario_data in data.get("scenarios", []):
                scenario_id = scenario_data.get("scenario_id")
                version = scenario_data.get("version")
                workflow_id = scenario_data.get("workflow_id")

                if not all([scenario_id, version is not None, workflow_id]):
                    raise InvalidConfigShapeError(
                        path,
                        f"Scenario missing required fields: {scenario_data}",
                    )

                if scenario_id in self.scenarios:
                    raise DuplicateConfigIdError(
                        "scenario_id",
                        scenario_id,
                        self._source_for("scenario", scenario_id, path),
                        path,
                    )

                self.scenarios[scenario_id] = ScenarioDefinition(
                    scenario_id=scenario_id,
                    version=version,
                    workflow_id=workflow_id,
                    allowed_next_actions=scenario_data.get("allowed_next_actions", []),
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("scenario", scenario_id, path)
        except ConfigError as error:
            self._append_error(error)

    def _load_quotas(self, path: Path) -> list[str]:
        if not path.exists():
            return []

        quota_refs: list[str] = []
        try:
            data = load_yaml_file(path)
            for quota_data in data.get("quota_policies", []):
                quota_id = quota_data.get("quota_policy_id")
                unit = quota_data.get("unit", "scenario_run")
                limit_count = quota_data.get("limit_count")
                period = quota_data.get("period", "lifetime")

                if not all([quota_id, limit_count is not None]):
                    raise InvalidConfigShapeError(
                        path,
                        f"Quota policy missing required fields: {quota_data}",
                    )

                if quota_id in self.quotas:
                    raise DuplicateConfigIdError(
                        "quota_policy_id",
                        quota_id,
                        self._source_for("quota_policy", quota_id, path),
                        path,
                    )

                self.quotas[quota_id] = QuotaPolicy(
                    quota_policy_id=quota_id,
                    unit=QuotaUnit(unit),
                    limit_count=limit_count,
                    period=QuotaPeriod(period),
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("quota_policy", quota_id, path)
                quota_refs.append(quota_id)
        except ConfigError as error:
            self._append_error(error)

        return quota_refs

    def _load_handoffs(self, path: Path) -> None:
        if not path.exists():
            return

        try:
            data = load_yaml_file(path)
            for handoff_data in data.get("handoffs", []):
                handoff_id = handoff_data.get("handoff_id")
                source_product_id = handoff_data.get("source_product_id")
                source_scenario_id = handoff_data.get("source_scenario_id")
                target_product_id = handoff_data.get("target_product_id")
                target_scenario_id = handoff_data.get("target_scenario_id")

                if not all(
                    [
                        handoff_id,
                        source_product_id,
                        source_scenario_id,
                        target_product_id,
                        target_scenario_id,
                    ]
                ):
                    raise InvalidConfigShapeError(
                        path,
                        f"Handoff missing required fields: {handoff_data}",
                    )

                if handoff_id in self.handoffs:
                    raise DuplicateConfigIdError(
                        "handoff_id",
                        handoff_id,
                        self._source_for("handoff", handoff_id, path),
                        path,
                    )

                self.handoffs[handoff_id] = HandoffDefinition(
                    handoff_id=handoff_id,
                    source_product_id=source_product_id,
                    source_scenario_id=source_scenario_id,
                    target_product_id=target_product_id,
                    target_scenario_id=target_scenario_id,
                    consent_required=handoff_data.get("consent_required", True),
                    context_mapping=handoff_data.get("context_mapping", {}),
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("handoff", handoff_id, path)
        except ConfigError as error:
            self._append_error(error)

    def _load_prompts(self) -> None:
        for product_id, product_dir in sorted(self.product_dirs.items()):
            prompt_dir = product_dir / "prompts"
            if not prompt_dir.exists():
                continue

            for path in sorted(prompt_dir.glob("*.md")):
                if path.name.lower() == "readme.md":
                    continue

                try:
                    prompt_ref = self._prompt_ref_from_path(product_id, path)
                    version = self._parse_version_from_name(path.stem)

                    if prompt_ref in self.prompts:
                        raise DuplicateConfigIdError(
                            "prompt_ref",
                            prompt_ref,
                            self._source_for("prompt", prompt_ref, path),
                            path,
                        )

                    with path.open("r", encoding="utf-8") as handle:
                        content = handle.read()

                    self.prompts[prompt_ref] = PromptDefinition(
                        prompt_ref=prompt_ref,
                        version=version,
                        content=content,
                        input_variables=[],
                        output_schema_ref=self._infer_prompt_output_schema_ref(
                            prompt_ref
                        ),
                        metadata={"_file_path": str(path)},
                    )
                    self._remember_source("prompt", prompt_ref, path)
                except ConfigError as error:
                    self._append_error(error)

    def _load_schemas(self) -> None:
        self._load_schema_directory(
            scope="kernel",
            schema_dir=self.config_root / "schemas",
        )

        for product_id, product_dir in sorted(self.product_dirs.items()):
            self._load_schema_directory(
                scope=product_id,
                schema_dir=product_dir / "schemas",
            )

    def _load_schema_directory(self, scope: str, schema_dir: Path) -> None:
        if not schema_dir.exists():
            return

        for path in sorted(schema_dir.glob("*.json")):
            try:
                schema_ref, version = self._schema_ref_from_path(scope, path)

                if schema_ref in self.schemas:
                    raise DuplicateConfigIdError(
                        "schema_ref",
                        schema_ref,
                        self._source_for("schema", schema_ref, path),
                        path,
                    )

                self.schemas[schema_ref] = SchemaDefinition(
                    schema_ref=schema_ref,
                    version=version,
                    schema=load_json_file(path),
                    metadata={"_file_path": str(path)},
                )
                self._remember_source("schema", schema_ref, path)
            except ConfigError as error:
                self._append_error(error)

    def _prompt_ref_from_path(self, product_id: str, path: Path) -> str:
        return f"{product_id}.{path.stem}"

    def _schema_ref_from_path(self, scope: str, path: Path) -> tuple[str, int]:
        base_name = path.name
        if base_name.endswith(".schema.json"):
            base_name = base_name[: -len(".schema.json")]
        elif base_name.endswith(".json"):
            base_name = base_name[:-len(".json")]

        version = self._parse_version_from_name(base_name)
        stem = self._strip_version_suffix(base_name)
        if scope == "kernel":
            return (f"kernel.schemas.{stem}_v{version}", version)
        return (f"{scope}.{stem}_v{version}", version)

    def _parse_version_from_name(self, name: str) -> int:
        match = VERSION_SUFFIX_PATTERN.search(name)
        if not match:
            return 1
        return int(match.group("version"))

    def _strip_version_suffix(self, name: str) -> str:
        match = VERSION_SUFFIX_PATTERN.search(name)
        if not match:
            return name
        return name[: match.start()]

    def _infer_prompt_output_schema_ref(self, prompt_ref: str) -> str | None:
        for action_config in self.action_configurations.values():
            if action_config.prompt_ref != prompt_ref:
                continue

            action_definition = self.action_definitions.get(action_config.action_type)
            if action_definition is not None:
                return action_definition.output_schema_ref
        return None

    def _validate_cross_references(self) -> None:
        for action_type, action_def in self.action_definitions.items():
            source_path = self._source_for(
                "action_definition",
                action_type,
                self.config_root / "action_definitions",
            )
            self._validate_schema_ref(
                config_id=action_type,
                file_path=source_path,
                ref_type="input_schema_ref",
                ref_value=action_def.input_schema_ref,
            )
            self._validate_schema_ref(
                config_id=action_type,
                file_path=source_path,
                ref_type="output_schema_ref",
                ref_value=action_def.output_schema_ref,
            )

        for config_id, action_config in self.action_configurations.items():
            source_path = self._source_for(
                "action_config",
                config_id,
                self.config_root,
            )
            self._validate_reference(
                config_id=config_id,
                file_path=source_path,
                ref_type="action_type",
                ref_value=action_config.action_type,
                target_registry=self.action_definitions,
                target_type="action_definition",
            )
            self._validate_reference(
                config_id=config_id,
                file_path=source_path,
                ref_type="prompt_ref",
                ref_value=action_config.prompt_ref,
                target_registry=self.prompts,
                target_type="prompt",
            )
            self._validate_reference(
                config_id=config_id,
                file_path=source_path,
                ref_type="provider_policy_ref",
                ref_value=action_config.provider_policy_ref,
                target_registry=self.provider_policies,
                target_type="provider_policy",
            )

        for workflow_id, workflow in self.workflows.items():
            source_path = self._source_for("workflow", workflow_id, self.config_root)
            self._validate_schema_ref(
                config_id=workflow_id,
                file_path=source_path,
                ref_type="input_schema_ref",
                ref_value=workflow.input_schema_ref,
            )
            self._validate_schema_ref(
                config_id=workflow_id,
                file_path=source_path,
                ref_type="output_schema_ref",
                ref_value=workflow.output_schema_ref,
            )
            for step in workflow.steps:
                self._validate_reference(
                    config_id=workflow_id,
                    file_path=source_path,
                    ref_type="action_config_id",
                    ref_value=step.action_config_id,
                    target_registry=self.action_configurations,
                    target_type="action_configuration",
                )

        for scenario_id, scenario in self.scenarios.items():
            source_path = self._source_for("scenario", scenario_id, self.config_root)
            self._validate_reference(
                config_id=scenario_id,
                file_path=source_path,
                ref_type="workflow_id",
                ref_value=scenario.workflow_id,
                target_registry=self.workflows,
                target_type="workflow",
            )

        for product_id, product in self.products.items():
            source_path = self._source_for("product", product_id, self.config_root)
            for scenario_id in product.scenarios:
                self._validate_reference(
                    config_id=product_id,
                    file_path=source_path,
                    ref_type="scenario_id",
                    ref_value=scenario_id,
                    target_registry=self.scenarios,
                    target_type="scenario",
                )
            if product.quota_policy_ref:
                self._validate_reference(
                    config_id=product_id,
                    file_path=source_path,
                    ref_type="quota_policy_ref",
                    ref_value=product.quota_policy_ref,
                    target_registry=self.quotas,
                    target_type="quota_policy",
                )

        for handoff_id, handoff in self.handoffs.items():
            source_path = self._source_for("handoff", handoff_id, self.config_root)
            self._validate_reference(
                config_id=handoff_id,
                file_path=source_path,
                ref_type="source_product_id",
                ref_value=handoff.source_product_id,
                target_registry=self.products,
                target_type="product",
            )
            self._validate_reference(
                config_id=handoff_id,
                file_path=source_path,
                ref_type="target_product_id",
                ref_value=handoff.target_product_id,
                target_registry=self.products,
                target_type="product",
            )
            self._validate_reference(
                config_id=handoff_id,
                file_path=source_path,
                ref_type="source_scenario_id",
                ref_value=handoff.source_scenario_id,
                target_registry=self.scenarios,
                target_type="scenario",
            )
            self._validate_reference(
                config_id=handoff_id,
                file_path=source_path,
                ref_type="target_scenario_id",
                ref_value=handoff.target_scenario_id,
                target_registry=self.scenarios,
                target_type="scenario",
            )

        for prompt_ref, prompt in self.prompts.items():
            if prompt.output_schema_ref is None:
                continue
            source_path = self._source_for("prompt", prompt_ref, self.config_root)
            self._validate_schema_ref(
                config_id=prompt_ref,
                file_path=source_path,
                ref_type="output_schema_ref",
                ref_value=prompt.output_schema_ref,
            )

    def _validate_reference(
        self,
        *,
        config_id: str,
        file_path: Path,
        ref_type: str,
        ref_value: str,
        target_registry: dict[str, Any],
        target_type: str,
    ) -> None:
        if ref_value in target_registry:
            return
        self._append_error(
            BrokenReferenceError(
                ref_type=ref_type,
                ref_value=ref_value,
                config_id=config_id,
                file_path=file_path,
                target_type=target_type,
            )
        )

    def _validate_schema_ref(
        self,
        *,
        config_id: str,
        file_path: Path,
        ref_type: str,
        ref_value: str,
    ) -> None:
        self._validate_reference(
            config_id=config_id,
            file_path=file_path,
            ref_type=ref_type,
            ref_value=ref_value,
            target_registry=self.schemas,
            target_type="schema",
        )
