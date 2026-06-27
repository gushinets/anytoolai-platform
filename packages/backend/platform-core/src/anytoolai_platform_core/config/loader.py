"""Deterministic config loader for MVP-A."""

from __future__ import annotations

import json
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
    ProviderRetryHardLimits,
    ProviderRetryPolicy,
    ProviderTransportRetryPolicy,
    ProviderValidationRetryPolicy,
    StructuredOutputMode,
    TransportRetryOwner,
    ValidationRetryOwner,
)
from anytoolai_platform_core.quotas.models import QuotaPeriod, QuotaPolicy, QuotaUnit
from anytoolai_platform_core.scenarios.models import ScenarioDefinition
from anytoolai_platform_core.workflows.models import (
    WorkflowDefinition,
    WorkflowStepDefinition,
)

VERSION_SUFFIX_PATTERN = re.compile(r"(?P<separator>[._])v(?P<version>\d+)$")
PROMPT_FRONT_MATTER_PATTERN = re.compile(
    r"\A---\r?\n(?P<front_matter>.*?)\r?\n---\r?\n(?P<body>.*)\Z",
    re.DOTALL,
)

FORBIDDEN_RAW_LLM_FIELDS = frozenset(
    {
        "api_base",
        "base_url",
        "fallback_policy",
        "gateway_backend",
        "gateway_model",
        "max_retries",
        "max_tokens",
        "model",
        "model_ref",
        "num_retries",
        "presence_penalty",
        "provider",
        "reasoning_effort",
        "response_format",
        "response_schema",
        "retry_policy",
        "seed",
        "stop",
        "stream",
        "structured_output",
        "structured_output_mode",
        "temperature",
        "timeout_seconds",
        "tool_choice",
        "tools",
        "top_p",
    }
)
FORBIDDEN_RAW_LLM_PREFIXES = ("litellm_",)
LEGACY_PROVIDER_POLICY_RETRY_FIELDS = frozenset(
    {
        "litellm_num_retries_per_attempt",
        "max_physical_provider_calls_per_action",
        "max_retries",
        "transport_max_attempts",
        "transport_owner",
        "validation_max_attempts",
        "validation_owner",
    }
)
PROVIDER_RETRY_POLICY_FIELDS = frozenset({"transport", "validation", "hard_limits"})
PROVIDER_TRANSPORT_RETRY_POLICY_FIELDS = frozenset(
    {"owner", "max_attempts", "litellm_num_retries_per_attempt"}
)
PROVIDER_VALIDATION_RETRY_POLICY_FIELDS = frozenset({"owner", "max_attempts"})
PROVIDER_RETRY_HARD_LIMIT_FIELDS = frozenset(
    {"max_physical_provider_calls_per_action"}
)


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


def parse_enum_value(
    enum_type: type[Any],
    raw_value: Any,
    *,
    field_name: str,
    file_path: Path,
    config_id: str | None = None,
    ref_type: str | None = None,
) -> Any:
    """Parse an enum value and raise a structured config error on failure."""
    try:
        return enum_type(raw_value)
    except ValueError as exc:
        allowed_values = ", ".join(member.value for member in enum_type)
        raise InvalidConfigShapeError(
            file_path,
            (
                f"Invalid {field_name} value {raw_value!r}; "
                f"expected one of: {allowed_values}"
            ),
            config_id=config_id,
            ref_type=ref_type or field_name,
            ref_value=str(raw_value),
        ) from exc


def _stringify_config_value(value: Any) -> str:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return str(value)
    try:
        return json.dumps(value, sort_keys=True)
    except TypeError:
        return repr(value)


def _is_forbidden_raw_llm_field(field_name: str) -> bool:
    if field_name in FORBIDDEN_RAW_LLM_FIELDS:
        return True
    return any(field_name.startswith(prefix) for prefix in FORBIDDEN_RAW_LLM_PREFIXES)


def _find_forbidden_raw_llm_field(
    payload: Any,
    *,
    current_path: str = "",
    recursive: bool = False,
) -> tuple[str, Any] | None:
    if isinstance(payload, dict):
        for field_name, value in payload.items():
            field_path = f"{current_path}.{field_name}" if current_path else field_name
            if _is_forbidden_raw_llm_field(field_name):
                return field_path, value
            if recursive:
                found = _find_forbidden_raw_llm_field(
                    value,
                    current_path=field_path,
                    recursive=True,
                )
                if found is not None:
                    return found
        return None

    if recursive and isinstance(payload, list):
        for index, item in enumerate(payload):
            item_path = f"{current_path}[{index}]"
            found = _find_forbidden_raw_llm_field(
                item,
                current_path=item_path,
                recursive=True,
            )
            if found is not None:
                return found
        return None

    return None


def _split_prompt_front_matter(path: Path, content: str) -> tuple[dict[str, Any], str]:
    match = PROMPT_FRONT_MATTER_PATTERN.match(content)
    if match is None:
        if content.startswith("---"):
            raise InvalidConfigShapeError(
                path,
                "Prompt front matter started with '---' but closing '---' was not found",
            )
        return {}, content

    try:
        front_matter = yaml.safe_load(match.group("front_matter")) or {}
    except yaml.YAMLError as exc:
        raise InvalidConfigShapeError(
            path,
            "Prompt front matter contains invalid YAML",
        ) from exc
    if not isinstance(front_matter, dict):
        raise InvalidConfigShapeError(
            path,
            "Prompt front matter must be a YAML mapping",
        )

    return front_matter, match.group("body")


def _parse_positive_int_field(
    raw_value: Any,
    *,
    field_name: str,
    file_path: Path,
    config_id: str,
    ref_type: str,
) -> int:
    if not isinstance(raw_value, int) or isinstance(raw_value, bool) or raw_value < 1:
        raise InvalidConfigShapeError(
            file_path,
            f"{field_name} must be an integer greater than or equal to 1",
            config_id=config_id,
            ref_type=ref_type,
            ref_value=_stringify_config_value(raw_value),
    )
    return raw_value


def _reject_unexpected_mapping_keys(
    mapping: dict[str, Any],
    *,
    allowed_keys: set[str],
    field_name: str,
    file_path: Path,
    config_id: str,
) -> None:
    unexpected_keys = sorted(set(mapping) - allowed_keys)
    if not unexpected_keys:
        return

    unexpected_key = unexpected_keys[0]
    raise InvalidConfigShapeError(
        file_path,
        f"{field_name} contains unsupported field '{unexpected_key}'",
        config_id=config_id,
        ref_type=unexpected_key,
        ref_value=_stringify_config_value(mapping[unexpected_key]),
    )


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

    def _reject_forbidden_raw_llm_fields(
        self,
        *,
        payload: Any,
        file_path: Path,
        config_kind: str,
        config_id: str | None = None,
        recursive: bool = False,
    ) -> None:
        found = _find_forbidden_raw_llm_field(payload, recursive=recursive)
        if found is None:
            return

        field_path, field_value = found
        raise InvalidConfigShapeError(
            file_path,
            (
                f"{config_kind} configs must not define raw provider/model/LiteLLM "
                f"field '{field_path}'; keep provider/model routing and request "
                "settings in provider policy/model registry files and use "
                "`provider_policy_ref` instead"
            ),
            config_id=config_id,
            ref_type=field_path,
            ref_value=_stringify_config_value(field_value),
        )

    def _parse_provider_retry_policy(
        self,
        *,
        policy_data: dict[str, Any],
        file_path: Path,
        policy_id: str,
    ) -> ProviderRetryPolicy:
        retry_policy = policy_data.get("retry_policy")
        if not isinstance(retry_policy, dict):
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy must define retry_policy as a mapping",
                config_id=policy_id,
                ref_type="retry_policy",
                ref_value=_stringify_config_value(retry_policy),
            )

        for legacy_field in LEGACY_PROVIDER_POLICY_RETRY_FIELDS:
            if legacy_field in policy_data:
                raise InvalidConfigShapeError(
                    file_path,
                    (
                        f"Provider policy uses legacy retry field '{legacy_field}'; "
                        "use the ADR 0007 split retry_policy contract"
                    ),
                    config_id=policy_id,
                    ref_type=legacy_field,
                    ref_value=_stringify_config_value(policy_data.get(legacy_field)),
                )
            if legacy_field in retry_policy:
                raise InvalidConfigShapeError(
                    file_path,
                    (
                        f"Provider policy uses legacy retry field "
                        f"'retry_policy.{legacy_field}'; use transport, validation, "
                        "and hard_limits sections instead"
                    ),
                    config_id=policy_id,
                    ref_type=legacy_field,
                    ref_value=_stringify_config_value(retry_policy.get(legacy_field)),
                )

        _reject_unexpected_mapping_keys(
            retry_policy,
            allowed_keys=PROVIDER_RETRY_POLICY_FIELDS,
            field_name="Provider policy retry_policy",
            file_path=file_path,
            config_id=policy_id,
        )

        transport = retry_policy.get("transport")
        if not isinstance(transport, dict):
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy retry_policy.transport must be a mapping",
                config_id=policy_id,
                ref_type="transport",
                ref_value=_stringify_config_value(transport),
            )

        _reject_unexpected_mapping_keys(
            transport,
            allowed_keys=PROVIDER_TRANSPORT_RETRY_POLICY_FIELDS,
            field_name="Provider policy retry_policy.transport",
            file_path=file_path,
            config_id=policy_id,
        )

        validation = retry_policy.get("validation")
        if not isinstance(validation, dict):
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy retry_policy.validation must be a mapping",
                config_id=policy_id,
                ref_type="validation",
                ref_value=_stringify_config_value(validation),
            )

        _reject_unexpected_mapping_keys(
            validation,
            allowed_keys=PROVIDER_VALIDATION_RETRY_POLICY_FIELDS,
            field_name="Provider policy retry_policy.validation",
            file_path=file_path,
            config_id=policy_id,
        )

        hard_limits = retry_policy.get("hard_limits")
        if not isinstance(hard_limits, dict):
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy retry_policy.hard_limits must be a mapping",
                config_id=policy_id,
                ref_type="hard_limits",
                ref_value=_stringify_config_value(hard_limits),
            )

        _reject_unexpected_mapping_keys(
            hard_limits,
            allowed_keys=PROVIDER_RETRY_HARD_LIMIT_FIELDS,
            field_name="Provider policy retry_policy.hard_limits",
            file_path=file_path,
            config_id=policy_id,
        )

        transport_owner = transport.get("owner")
        if transport_owner is None:
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy retry_policy.transport.owner is required",
                config_id=policy_id,
                ref_type="owner",
                ref_value=_stringify_config_value(transport_owner),
            )

        transport_attempts_raw = transport.get("max_attempts")
        if transport_attempts_raw is None:
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy retry_policy.transport.max_attempts is required",
                config_id=policy_id,
                ref_type="max_attempts",
                ref_value=_stringify_config_value(transport_attempts_raw),
            )
        transport_attempts = _parse_positive_int_field(
            transport_attempts_raw,
            field_name="retry_policy.transport.max_attempts",
            file_path=file_path,
            config_id=policy_id,
            ref_type="max_attempts",
        )

        litellm_num_retries = transport.get("litellm_num_retries_per_attempt")
        if litellm_num_retries is None:
            raise InvalidConfigShapeError(
                file_path,
                (
                    "Provider policy "
                    "retry_policy.transport.litellm_num_retries_per_attempt is required"
                ),
                config_id=policy_id,
                ref_type="litellm_num_retries_per_attempt",
            )
        if not isinstance(litellm_num_retries, int) or isinstance(
            litellm_num_retries,
            bool,
        ):
            raise InvalidConfigShapeError(
                file_path,
                (
                    "retry_policy.transport.litellm_num_retries_per_attempt must be "
                    "an integer"
                ),
                config_id=policy_id,
                ref_type="litellm_num_retries_per_attempt",
                ref_value=_stringify_config_value(litellm_num_retries),
            )
        if litellm_num_retries != 0:
            raise InvalidConfigShapeError(
                file_path,
                (
                    "MVP-A requires "
                    "retry_policy.transport.litellm_num_retries_per_attempt to be 0"
                ),
                config_id=policy_id,
                ref_type="litellm_num_retries_per_attempt",
                ref_value=_stringify_config_value(litellm_num_retries),
            )

        validation_owner = validation.get("owner")
        if validation_owner is None:
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy retry_policy.validation.owner is required",
                config_id=policy_id,
                ref_type="owner",
                ref_value=_stringify_config_value(validation_owner),
            )

        validation_attempts_raw = validation.get("max_attempts")
        if validation_attempts_raw is None:
            raise InvalidConfigShapeError(
                file_path,
                "Provider policy retry_policy.validation.max_attempts is required",
                config_id=policy_id,
                ref_type="max_attempts",
                ref_value=_stringify_config_value(validation_attempts_raw),
            )
        validation_attempts = _parse_positive_int_field(
            validation_attempts_raw,
            field_name="retry_policy.validation.max_attempts",
            file_path=file_path,
            config_id=policy_id,
            ref_type="max_attempts",
        )

        max_physical_provider_calls_raw = hard_limits.get(
            "max_physical_provider_calls_per_action"
        )
        if max_physical_provider_calls_raw is None:
            raise InvalidConfigShapeError(
                file_path,
                (
                    "Provider policy "
                    "retry_policy.hard_limits.max_physical_provider_calls_per_action "
                    "is required"
                ),
                config_id=policy_id,
                ref_type="max_physical_provider_calls_per_action",
                ref_value=_stringify_config_value(max_physical_provider_calls_raw),
            )
        max_physical_provider_calls = _parse_positive_int_field(
            max_physical_provider_calls_raw,
            field_name="retry_policy.hard_limits.max_physical_provider_calls_per_action",
            file_path=file_path,
            config_id=policy_id,
            ref_type="max_physical_provider_calls_per_action",
        )

        return ProviderRetryPolicy(
            transport=ProviderTransportRetryPolicy(
                owner=parse_enum_value(
                    TransportRetryOwner,
                    transport_owner,
                    field_name="transport retry owner",
                    file_path=file_path,
                    config_id=policy_id,
                    ref_type="owner",
                ),
                max_attempts=transport_attempts,
                litellm_num_retries_per_attempt=litellm_num_retries,
                metadata={"_file_path": str(file_path)},
            ),
            validation=ProviderValidationRetryPolicy(
                owner=parse_enum_value(
                    ValidationRetryOwner,
                    validation_owner,
                    field_name="validation retry owner",
                    file_path=file_path,
                    config_id=policy_id,
                    ref_type="owner",
                ),
                max_attempts=validation_attempts,
                metadata={"_file_path": str(file_path)},
            ),
            hard_limits=ProviderRetryHardLimits(
                max_physical_provider_calls_per_action=max_physical_provider_calls,
                metadata={"_file_path": str(file_path)},
            ),
            metadata={"_file_path": str(file_path)},
        )

    def _load_tenants(self) -> None:
        path = self.config_root / "default_tenant.yaml"
        try:
            data = self._require_mapping_file(
                path,
                config_id="kernel",
                ref_type="default_tenant_file",
                ref_value=path.name,
                reason="default_tenant.yaml is required because it owns the default tenant definition",
            )
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
            data = self._require_mapping_file(
                path,
                config_id="kernel",
                ref_type="regions_file",
                ref_value=path.name,
                reason="regions.yaml is required because it owns region definitions",
            )
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
            data = self._require_mapping_file(
                path,
                config_id="kernel",
                ref_type="provider_policies_file",
                ref_value=path.name,
                reason="provider_policies.yaml is required because it owns provider policy definitions",
            )
            for policy_data in data.get("provider_policies", []):
                policy_id = policy_data.get("provider_policy_id")
                provider = policy_data.get("provider")
                model = policy_data.get("model")
                required_fields = (
                    "provider_policy_id",
                    "provider",
                    "model",
                    "temperature",
                    "timeout_seconds",
                    "max_retries",
                    "structured_output_mode",
                )
                missing_fields = [
                    field_name
                    for field_name in required_fields
                    if field_name not in policy_data or policy_data[field_name] is None
                ]

                if not all([policy_id, provider, model]) or missing_fields:
                    raise InvalidConfigShapeError(
                        path,
                        (
                            "Provider policy missing required fields: "
                            f"{', '.join(missing_fields) or policy_data}"
                        ),
                        config_id=policy_id,
                        ref_type=missing_fields[0] if missing_fields else None,
                        ref_value="<missing>" if missing_fields else None,
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
                    retry_policy=self._parse_provider_retry_policy(
                        policy_data=policy_data,
                        file_path=path,
                        policy_id=policy_id,
                    ),
                    fallback_policy=policy_data.get("fallback_policy"),
                    structured_output_mode=parse_enum_value(
                        StructuredOutputMode,
                        policy_data["structured_output_mode"],
                        field_name="structured_output_mode",
                        file_path=path,
                        config_id=policy_id,
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
                self._missing_required_file_error(
                    action_dir,
                    config_id="kernel",
                    ref_type="action_definitions_dir",
                    ref_value=action_dir.name,
                    reason="action_definitions directory is required because it owns action definitions",
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

                self._reject_forbidden_raw_llm_fields(
                    payload=data,
                    file_path=path,
                    config_kind="Action definition",
                    config_id=action_type,
                    recursive=True,
                )

                self.action_definitions[action_type] = ActionDefinition(
                    action_type=action_type,
                    version=version,
                    input_schema_ref=input_schema_ref,
                    output_schema_ref=output_schema_ref,
                    executor=parse_enum_value(
                        ActionExecutor,
                        executor,
                        field_name="executor",
                        file_path=path,
                        config_id=action_type,
                    ),
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
                self._missing_required_file_error(
                    products_dir,
                    config_id="kernel",
                    ref_type="products_dir",
                    ref_value=products_dir.name,
                    reason="products directory is required because it owns product definition directories",
                )
            )
            return

        for product_dir in sorted(products_dir.iterdir()):
            if product_dir.is_dir():
                self._load_product(product_dir)

    def _load_product(self, product_dir: Path) -> None:
        product_file = product_dir / "product.yaml"
        try:
            product_data = self._require_mapping_file(
                product_file,
                config_id=product_dir.name,
                ref_type="product_file",
                ref_value=product_file.name,
                reason="product.yaml is required because it owns the product definition",
            )
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

            self._reject_forbidden_raw_llm_fields(
                payload=product_data,
                file_path=product_file,
                config_kind="Product",
                config_id=product_id,
                recursive=True,
            )

            self.product_dirs[product_id] = product_dir

            if "frontends" in product_data:
                raise InvalidConfigShapeError(
                    product_file,
                    "Frontend definitions must be declared in frontends.yaml; product.yaml must not embed frontends",
                    config_id=product_id,
                    ref_type="frontends",
                    ref_value="product.yaml.frontends",
                )
            if "analytics" in product_data:
                raise InvalidConfigShapeError(
                    product_file,
                    "Analytics definitions must be declared in analytics.yaml; product.yaml must not embed analytics",
                    config_id=product_id,
                    ref_type="analytics",
                    ref_value="product.yaml.analytics",
                )

            self._load_action_configs(product_dir / "action_configs.yaml", product_id)
            self._load_workflows(product_dir / "workflows.yaml", product_id)
            self._load_scenarios(product_dir / "scenarios.yaml", product_id)

            quota_refs = self._load_quotas(product_dir / "quotas.yaml")
            self._load_handoffs(product_dir / "handoffs.yaml")

            frontends = self._load_frontends(product_dir / "frontends.yaml", product_id)
            analytics = self._load_analytics(product_dir / "analytics.yaml")

            quota_policy_ref = product_data.get("quota_policy_ref")
            if quota_policy_ref is None and quota_refs:
                raise InvalidConfigShapeError(
                    product_file,
                    "quota_policy_ref is required when quotas.yaml defines quota policies",
                    config_id=product_id,
                    ref_type="quota_policy_ref",
                    ref_value="<missing>",
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
        product_id: str,
    ) -> list[FrontendDefinition]:
        data = self._require_mapping_file(
            path,
            config_id=product_id,
            ref_type="frontends_file",
            ref_value=path.name,
            reason="frontends.yaml is required because it is the exclusive source of frontend definitions",
        )
        frontends_data = data.get("frontends", [])

        frontends: list[FrontendDefinition] = []
        for frontend_data in frontends_data:
            frontend_data = self._require_mapping_entry(
                frontend_data,
                file_path=path,
                config_id=product_id,
                entry_type="frontend",
                ref_type="frontends_entry",
            )
            frontend_id = frontend_data.get("frontend_id")
            frontend_type = frontend_data.get("type")
            if not frontend_id or not frontend_type:
                raise InvalidConfigShapeError(
                    path,
                    f"Frontend missing required fields: {frontend_data}",
                    config_id=product_id,
                )

            self._reject_forbidden_raw_llm_fields(
                payload=frontend_data,
                file_path=source_path,
                config_kind="Frontend",
                config_id=frontend_id,
                recursive=True,
            )

            frontends.append(
                FrontendDefinition(
                    frontend_id=frontend_id,
                    type=parse_enum_value(
                        FrontendType,
                        frontend_type,
                        field_name="frontend type",
                        file_path=path,
                        config_id=frontend_id,
                        ref_type="type",
                    ),
                    enabled=frontend_data.get("enabled", True),
                    metadata={"_file_path": str(path)},
                )
            )
        return frontends

    def _load_analytics(self, path: Path) -> dict[str, Any]:
        if path.exists():
            return load_yaml_file(path)
        return {}

    def _load_action_configs(self, path: Path, product_id: str) -> None:
        try:
            data = self._require_product_mapping_file(
                path,
                product_id=product_id,
                ref_type="action_configs_file",
                reason="action_configs.yaml is required because it owns action configuration definitions",
            )
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

                self._reject_forbidden_raw_llm_fields(
                    payload=config_data,
                    file_path=path,
                    config_kind="Action",
                    config_id=config_id,
                    recursive=True,
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

    def _load_workflows(self, path: Path, product_id: str) -> None:
        try:
            data = self._require_product_mapping_file(
                path,
                product_id=product_id,
                ref_type="workflows_file",
                reason="workflows.yaml is required because it owns workflow definitions",
            )
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

                self._reject_forbidden_raw_llm_fields(
                    payload=workflow_data,
                    file_path=path,
                    config_kind="Workflow",
                    config_id=workflow_id,
                    recursive=True,
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

                    self._reject_forbidden_raw_llm_fields(
                        payload=step_data,
                        file_path=path,
                        config_kind="Workflow",
                        config_id=workflow_id,
                        recursive=True,
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

    def _load_scenarios(self, path: Path, product_id: str) -> None:
        try:
            data = self._require_product_mapping_file(
                path,
                product_id=product_id,
                ref_type="scenarios_file",
                reason="scenarios.yaml is required because it owns scenario definitions",
            )
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

                self._reject_forbidden_raw_llm_fields(
                    payload=scenario_data,
                    file_path=path,
                    config_kind="Scenario",
                    config_id=scenario_id,
                    recursive=True,
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
                unit = quota_data.get("unit")
                limit_count = quota_data.get("limit_count")
                period = quota_data.get("period")

                if not all([quota_id, limit_count is not None, unit, period]):
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
                    unit=parse_enum_value(
                        QuotaUnit,
                        unit,
                        field_name="quota unit",
                        file_path=path,
                        config_id=quota_id,
                        ref_type="unit",
                    ),
                    limit_count=limit_count,
                    period=parse_enum_value(
                        QuotaPeriod,
                        period,
                        field_name="quota period",
                        file_path=path,
                        config_id=quota_id,
                        ref_type="period",
                    ),
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
            manifest_path = product_dir / "prompts.yaml"
            try:
                data = self._require_mapping_file(
                    manifest_path,
                    config_id=product_id,
                    ref_type="prompt_manifest",
                    ref_value=manifest_path.name,
                    reason="prompts.yaml is required because it owns prompt definitions",
                )
                for prompt_data in data.get("prompts", []):
                    prompt_data = self._require_mapping_entry(
                        prompt_data,
                        file_path=manifest_path,
                        config_id=product_id,
                        entry_type="prompt manifest",
                        ref_type="prompt_manifest_entry",
                    )
                    prompt_ref = prompt_data.get("prompt_ref")
                    template_path = prompt_data.get("template_path")
                    version = prompt_data.get("version")
                    output_schema_ref = prompt_data.get("output_schema_ref")
                    input_variables = prompt_data.get("input_variables")

                    if not all(
                        [
                            prompt_ref,
                            template_path,
                            version is not None,
                            output_schema_ref,
                            input_variables is not None,
                        ]
                    ):
                        raise InvalidConfigShapeError(
                            manifest_path,
                            f"Prompt manifest entry missing required fields: {prompt_data}",
                            config_id=prompt_ref or product_id,
                        )

                    if prompt_ref in self.prompts:
                        raise DuplicateConfigIdError(
                            "prompt_ref",
                            prompt_ref,
                            self._source_for("prompt", prompt_ref, manifest_path),
                            manifest_path,
                        )

                    asset_path = product_dir / template_path
                    if not asset_path.exists():
                        raise self._missing_required_file_error(
                            asset_path,
                            reason=f"Prompt asset referenced from {manifest_path} was not found",
                            config_id=prompt_ref,
                            ref_type="prompt_asset",
                            ref_value=template_path,
                        )

                    with path.open("r", encoding="utf-8") as handle:
                        raw_content = handle.read()

                    prompt_metadata, content = _split_prompt_front_matter(
                        path,
                        raw_content,
                    )
                    self._reject_forbidden_raw_llm_fields(
                        payload=prompt_metadata,
                        file_path=path,
                        config_kind="Prompt",
                        config_id=prompt_ref,
                        recursive=True,
                    )

                    self.prompts[prompt_ref] = PromptDefinition(
                        prompt_ref=prompt_ref,
                        version=version,
                        content=content,
                        input_variables=input_variables,
                        output_schema_ref=output_schema_ref,
                        metadata={
                            "_file_path": str(asset_path),
                            "_manifest_path": str(manifest_path),
                            "template_path": template_path,
                        },
                    )
                    self._remember_source("prompt", prompt_ref, asset_path)
            except ConfigError as error:
                self._append_error(error)

    def _load_schemas(self) -> None:
        self._load_schema_manifest(
            owner_id="kernel",
            manifest_path=self.config_root / "schemas.yaml",
            base_dir=self.config_root,
        )

        for product_id, product_dir in sorted(self.product_dirs.items()):
            self._load_schema_manifest(
                owner_id=product_id,
                manifest_path=product_dir / "schemas.yaml",
                base_dir=product_dir,
            )

    def _load_schema_manifest(
        self,
        *,
        owner_id: str,
        manifest_path: Path,
        base_dir: Path,
    ) -> None:
        try:
            data = self._require_mapping_file(
                manifest_path,
                config_id=owner_id,
                ref_type="schema_manifest",
                ref_value=manifest_path.name,
                reason="schemas.yaml is required because it owns schema definitions",
            )
            for schema_data in data.get("schemas", []):
                schema_data = self._require_mapping_entry(
                    schema_data,
                    file_path=manifest_path,
                    config_id=owner_id,
                    entry_type="schema manifest",
                    ref_type="schema_manifest_entry",
                )
                schema_ref = schema_data.get("schema_ref")
                version = schema_data.get("version")
                file_path_value = schema_data.get("file_path")

                if not all([schema_ref, version is not None, file_path_value]):
                    raise InvalidConfigShapeError(
                        manifest_path,
                        f"Schema manifest entry missing required fields: {schema_data}",
                        config_id=schema_ref or owner_id,
                    )

                if schema_ref in self.schemas:
                    raise DuplicateConfigIdError(
                        "schema_ref",
                        schema_ref,
                        self._source_for("schema", schema_ref, manifest_path),
                        manifest_path,
                    )

                asset_path = base_dir / file_path_value
                if not asset_path.exists():
                    raise self._missing_required_file_error(
                        asset_path,
                        reason=f"Schema asset referenced from {manifest_path} was not found",
                        config_id=schema_ref,
                        ref_type="schema_asset",
                        ref_value=file_path_value,
                    )

                self.schemas[schema_ref] = SchemaDefinition(
                    schema_ref=schema_ref,
                    version=version,
                    schema=load_json_file(asset_path),
                    metadata={
                        "_file_path": str(asset_path),
                        "_manifest_path": str(manifest_path),
                        "file_path": file_path_value,
                    },
                )
                self._remember_source("schema", schema_ref, asset_path)
        except ConfigError as error:
            self._append_error(error)

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

        for policy_id, provider_policy in self.provider_policies.items():
            if provider_policy.fallback_policy is None:
                continue
            source_path = self._source_for(
                "provider_policy",
                policy_id,
                self.config_root / "provider_policies.yaml",
            )
            self._validate_reference(
                config_id=policy_id,
                file_path=source_path,
                ref_type="fallback_policy",
                ref_value=provider_policy.fallback_policy,
                target_registry=self.provider_policies,
                target_type="provider_policy",
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
