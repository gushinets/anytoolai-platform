from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from anytoolai_platform_core.providers.models import (
    ModelCatalogCompatibility,
    ReasoningEffort,
)


@dataclass(frozen=True)
class ModelCapabilityOverride:
    compatibility: ModelCatalogCompatibility | None
    reasoning_supported: bool | None
    allowed_reasoning_efforts: tuple[ReasoningEffort, ...] | None
    source: str
    checked_at: str

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.checked_at.strip():
            raise ValueError("model capability override requires source and checked_at")
        if self.allowed_reasoning_efforts is not None and self.reasoning_supported is None:
            raise ValueError("reasoning efforts require reasoning_supported=true")
        if self.reasoning_supported is False and self.allowed_reasoning_efforts not in (None, ()):
            raise ValueError("non-reasoning override cannot declare reasoning efforts")


@dataclass(frozen=True)
class ModelCatalogItem:
    model_id: str
    compatibility: ModelCatalogCompatibility
    reason: str
    reasoning_supported: bool | None
    allowed_reasoning_efforts: tuple[ReasoningEffort, ...] | None
    provenance: Mapping[str, Mapping[str, str]]


_OVERRIDE_FIELDS = {
    "compatibility",
    "reasoning_supported",
    "allowed_reasoning_efforts",
    "source",
    "checked_at",
}


def default_model_capability_overrides_path(config_root: Path | None = None) -> Path:
    root = config_root or Path(__file__).resolve().parents[6] / "configs" / "kernel"
    return root / "openai_model_capability_overrides.yaml"


def load_model_capability_overrides(path: Path) -> dict[str, ModelCapabilityOverride]:
    with path.open("r", encoding="utf-8") as handle:
        document = yaml.safe_load(handle)
    if not isinstance(document, Mapping) or set(document) != {"models"}:
        raise ValueError("model capability overrides require only a models mapping")
    models = document["models"]
    if not isinstance(models, Mapping):
        raise ValueError("model capability overrides models must be a mapping")

    result: dict[str, ModelCapabilityOverride] = {}
    for raw_model_id, raw_override in models.items():
        if not isinstance(raw_model_id, str) or not raw_model_id.strip():
            raise ValueError("model capability override model id must be a non-empty string")
        if not isinstance(raw_override, Mapping):
            raise ValueError(f"model capability override for {raw_model_id} must be a mapping")
        unknown_fields = set(raw_override) - _OVERRIDE_FIELDS
        if unknown_fields:
            raise ValueError(
                f"model capability override for {raw_model_id} has unknown fields: "
                f"{sorted(unknown_fields)}"
            )
        if "source" not in raw_override or "checked_at" not in raw_override:
            raise ValueError(
                f"model capability override for {raw_model_id} requires source and checked_at"
            )
        raw_efforts = raw_override.get("allowed_reasoning_efforts")
        if raw_efforts is not None and not isinstance(raw_efforts, list):
            raise ValueError(f"allowed_reasoning_efforts for {raw_model_id} must be null or a list")
        raw_reasoning = raw_override.get("reasoning_supported")
        if raw_reasoning is not None and not isinstance(raw_reasoning, bool):
            raise ValueError(f"reasoning_supported for {raw_model_id} must be boolean or null")
        source = raw_override["source"]
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"source for {raw_model_id} must be a non-empty string")
        checked_at_value = raw_override["checked_at"]
        if isinstance(checked_at_value, datetime) or not isinstance(checked_at_value, (str, date)):
            raise ValueError(f"checked_at for {raw_model_id} must be an ISO date")
        try:
            checked_at = date.fromisoformat(
                checked_at_value
                if isinstance(checked_at_value, str)
                else checked_at_value.isoformat()
            ).isoformat()
        except ValueError as exc:
            raise ValueError(f"checked_at for {raw_model_id} must be an ISO date") from exc
        result[raw_model_id] = ModelCapabilityOverride(
            compatibility=(
                None
                if raw_override.get("compatibility") is None
                else ModelCatalogCompatibility(raw_override["compatibility"])
            ),
            reasoning_supported=raw_reasoning,
            allowed_reasoning_efforts=(
                None
                if raw_efforts is None
                else tuple(ReasoningEffort(value) for value in raw_efforts)
            ),
            source=source.strip(),
            checked_at=checked_at,
        )
    return result


def serialize_catalog_item(item: ModelCatalogItem) -> dict[str, Any]:
    return {
        "model_id": item.model_id,
        "compatibility": item.compatibility.value,
        "reason": item.reason,
        "reasoning_supported": item.reasoning_supported,
        "allowed_reasoning_efforts": (
            None
            if item.allowed_reasoning_efforts is None
            else [effort.value for effort in item.allowed_reasoning_efforts]
        ),
        "provenance": {key: dict(value) for key, value in item.provenance.items()},
    }


def deserialize_catalog_item(value: Mapping[str, Any]) -> ModelCatalogItem:
    efforts = value.get("allowed_reasoning_efforts")
    if efforts is not None and not isinstance(efforts, list):
        raise ValueError("catalog allowed_reasoning_efforts must be null or a list")
    provenance = value.get("provenance")
    if not isinstance(provenance, Mapping):
        raise ValueError("catalog provenance must be a mapping")
    if not all(isinstance(item, Mapping) for item in provenance.values()):
        raise ValueError("catalog provenance entry must be a mapping")
    reasoning_supported = value.get("reasoning_supported")
    if reasoning_supported is not None and not isinstance(reasoning_supported, bool):
        raise ValueError("catalog reasoning_supported must be boolean or null")
    return ModelCatalogItem(
        model_id=str(value["model_id"]),
        compatibility=ModelCatalogCompatibility(value["compatibility"]),
        reason=str(value["reason"]),
        reasoning_supported=reasoning_supported,
        allowed_reasoning_efforts=(
            None if efforts is None else tuple(ReasoningEffort(item) for item in efforts)
        ),
        provenance={
            str(key): {str(inner_key): str(inner_value) for inner_key, inner_value in item.items()}
            for key, item in provenance.items()
        },
    )


def build_openai_gpt_catalog(
    *,
    account_model_ids: Sequence[str],
    litellm_metadata: Mapping[str, Any],
    overrides: Mapping[str, ModelCapabilityOverride],
    fetched_at: datetime,
) -> tuple[ModelCatalogItem, ...]:
    items: list[ModelCatalogItem] = []
    for model_id in sorted(set(account_model_ids)):
        if not _is_gpt_model_id(model_id):
            continue
        metadata = _metadata_for(model_id, litellm_metadata)
        override = overrides.get(model_id)
        compatibility_result = _compatibility(
            model_id=model_id,
            metadata=metadata,
            override=override,
            fetched_at=fetched_at,
        )
        if compatibility_result is None:
            continue
        compatibility, reason, compatibility_provenance = compatibility_result
        reasoning_supported, efforts, reasoning_provenance = _reasoning(
            metadata=metadata,
            override=override,
            fetched_at=fetched_at,
        )
        items.append(
            ModelCatalogItem(
                model_id=model_id,
                compatibility=compatibility,
                reason=reason,
                reasoning_supported=reasoning_supported,
                allowed_reasoning_efforts=efforts,
                provenance={
                    "availability": {
                        "source": "openai_models_api",
                        "fetched_at": fetched_at.isoformat(),
                    },
                    "compatibility": compatibility_provenance,
                    "reasoning_supported": reasoning_provenance,
                },
            )
        )
    return tuple(items)


def _is_gpt_model_id(model_id: object) -> bool:
    return isinstance(model_id, str) and model_id.startswith(("gpt-", "chatgpt-"))


def _metadata_for(model_id: str, metadata: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = metadata.get(model_id)
    if value is None:
        value = metadata.get(f"openai/{model_id}")
    return value if isinstance(value, Mapping) else None


def _compatibility(
    *,
    model_id: str,
    metadata: Mapping[str, Any] | None,
    override: ModelCapabilityOverride | None,
    fetched_at: datetime,
) -> tuple[ModelCatalogCompatibility, str, Mapping[str, str]] | None:
    if override is not None and override.compatibility is not None:
        return (
            override.compatibility,
            f"override_{override.compatibility.value}",
            _override_provenance(override),
        )
    if metadata is None:
        return (
            ModelCatalogCompatibility.unknown,
            "litellm_metadata_missing",
            {"source": "unknown"},
        )

    provider = metadata.get("litellm_provider")
    mode = metadata.get("mode")
    output_modalities = metadata.get("supported_output_modalities")
    if not isinstance(provider, str) or not isinstance(mode, str):
        return (
            ModelCatalogCompatibility.unknown,
            "litellm_compatibility_incomplete",
            {
                "source": "litellm_metadata",
                "model_id": model_id,
                "fetched_at": fetched_at.isoformat(),
            },
        )
    specialized_output = metadata.get("supports_audio_output") is True or (
        isinstance(output_modalities, list)
        and ("text" not in output_modalities or "audio" in output_modalities)
    )
    if provider != "openai" or mode != "chat" or specialized_output:
        return None
    return (
        ModelCatalogCompatibility.compatible,
        "confirmed_openai_text_gpt",
        {
            "source": "litellm_metadata",
            "model_id": model_id,
            "fetched_at": fetched_at.isoformat(),
        },
    )


def _reasoning(
    *,
    metadata: Mapping[str, Any] | None,
    override: ModelCapabilityOverride | None,
    fetched_at: datetime,
) -> tuple[bool | None, tuple[ReasoningEffort, ...] | None, Mapping[str, str]]:
    if override is not None and override.reasoning_supported is not None:
        efforts = override.allowed_reasoning_efforts
        if override.reasoning_supported is False:
            efforts = ()
        return override.reasoning_supported, efforts, _override_provenance(override)
    if metadata is None or not isinstance(metadata.get("supports_reasoning"), bool):
        return None, None, {"source": "unknown"}
    reasoning_supported = bool(metadata["supports_reasoning"])
    efforts: tuple[ReasoningEffort, ...] | None = None
    if not reasoning_supported:
        efforts = ()
    else:
        declared_efforts = metadata.get("supported_reasoning_efforts")
        if isinstance(declared_efforts, list):
            try:
                efforts = tuple(ReasoningEffort(value) for value in declared_efforts)
            except (TypeError, ValueError):
                efforts = None
    return (
        reasoning_supported,
        efforts,
        {
            "source": "litellm_metadata",
            "fetched_at": fetched_at.isoformat(),
        },
    )


def _override_provenance(override: ModelCapabilityOverride) -> Mapping[str, str]:
    return {
        "source": "override",
        "reference": override.source,
        "checked_at": override.checked_at,
    }
