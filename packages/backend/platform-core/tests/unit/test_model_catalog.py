from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from anytoolai_platform_core.providers.catalog import (
    ModelCapabilityOverride,
    build_openai_gpt_catalog,
    deserialize_catalog_item,
    load_model_capability_overrides,
)
from anytoolai_platform_core.providers.models import (
    ModelCatalogCompatibility,
    ReasoningEffort,
)

FETCHED_AT = datetime(2026, 9, 15, 10, 0, tzinfo=UTC)


def _metadata(**overrides: object) -> dict[str, object]:
    return {
        "litellm_provider": "openai",
        "mode": "chat",
        "supported_output_modalities": ["text"],
        **overrides,
    }


def test_real_litellm_chat_shape_without_output_modalities_is_compatible() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-4o-mini"],
        litellm_metadata={
            "gpt-4o-mini": {
                "litellm_provider": "openai",
                "mode": "chat",
                "supports_response_schema": True,
            }
        },
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.compatibility is ModelCatalogCompatibility.compatible


@pytest.mark.parametrize(
    "model_id, metadata",
    [
        (
            "gpt-audio-mini",
            {
                "litellm_provider": "openai",
                "mode": "chat",
                "supports_audio_output": True,
            },
        ),
        (
            "gpt-realtime",
            {
                "litellm_provider": "openai",
                "mode": "realtime",
                "supported_output_modalities": ["text", "audio"],
            },
        ),
        (
            "gpt-image-1",
            {"litellm_provider": "openai", "mode": "image_generation"},
        ),
    ],
)
def test_confirmed_specialized_models_are_excluded(
    model_id: str, metadata: dict[str, object]
) -> None:
    catalog = build_openai_gpt_catalog(
        account_model_ids=[model_id],
        litellm_metadata={model_id: metadata},
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert catalog == ()


def test_catalog_uses_only_current_account_model_ids() -> None:
    catalog = build_openai_gpt_catalog(
        account_model_ids=["gpt-new"],
        litellm_metadata={
            "gpt-removed": _metadata(),
            "gpt-new": _metadata(),
        },
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert [item.model_id for item in catalog] == ["gpt-new"]


def test_reasoning_support_does_not_invent_effort_list() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-reasoning"],
        litellm_metadata={"gpt-reasoning": _metadata(supports_reasoning=True)},
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.reasoning_supported is True
    assert item.allowed_reasoning_efforts is None


def test_current_litellm_reasoning_effort_list_is_published() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-reasoning"],
        litellm_metadata={
            "gpt-reasoning": _metadata(
                supports_reasoning=True,
                reasoning_effort_levels=["minimal", "low", "medium", "high"],
            )
        },
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.reasoning_supported is True
    assert item.allowed_reasoning_efforts == (
        ReasoningEffort.minimal,
        ReasoningEffort.low,
        ReasoningEffort.medium,
        ReasoningEffort.high,
    )


def test_current_litellm_reasoning_effort_flags_are_resolved_conservatively() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-reasoning"],
        litellm_metadata={
            "gpt-reasoning": _metadata(
                supports_none_reasoning_effort=False,
                supports_minimal_reasoning_effort=False,
                supports_low_reasoning_effort=True,
                supports_xhigh_reasoning_effort=True,
                supports_max_reasoning_effort=False,
            )
        },
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.reasoning_supported is True
    assert item.allowed_reasoning_efforts == (
        ReasoningEffort.low,
        ReasoningEffort.medium,
        ReasoningEffort.high,
        ReasoningEffort.xhigh,
    )


def test_unknown_litellm_reasoning_effort_keeps_support_but_makes_list_unknown() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-reasoning"],
        litellm_metadata={
            "gpt-reasoning": _metadata(
                supports_reasoning=True,
                reasoning_effort_levels=["low", "future-effort"],
            )
        },
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.reasoning_supported is True
    assert item.allowed_reasoning_efforts is None


def test_known_absence_of_reasoning_has_empty_effort_list() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-non-reasoning"],
        litellm_metadata={"gpt-non-reasoning": _metadata(supports_reasoning=False)},
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.reasoning_supported is False
    assert item.allowed_reasoning_efforts == ()


def test_native_response_schema_is_not_required_for_prompted_compatibility() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-prompted"],
        litellm_metadata={
            "gpt-prompted": _metadata(supports_response_schema=False),
        },
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.compatibility is ModelCatalogCompatibility.compatible


def test_override_has_priority_and_records_exact_reasoning_efforts() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-overridden"],
        litellm_metadata={"gpt-overridden": _metadata(supports_reasoning=False)},
        overrides={
            "gpt-overridden": ModelCapabilityOverride(
                compatibility=ModelCatalogCompatibility.compatible,
                reasoning_supported=True,
                allowed_reasoning_efforts=(ReasoningEffort.low, ReasoningEffort.high),
                source="https://developers.openai.com/api/docs/models/gpt-overridden",
                checked_at="2026-09-15",
            )
        },
        fetched_at=FETCHED_AT,
    )

    assert item.reasoning_supported is True
    assert item.allowed_reasoning_efforts == (ReasoningEffort.low, ReasoningEffort.high)
    assert item.provenance["reasoning_supported"]["source"] == "override"


def test_missing_metadata_is_unknown_not_unsupported() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-unmapped"],
        litellm_metadata={},
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.compatibility is ModelCatalogCompatibility.unknown
    assert item.reasoning_supported is None
    assert item.allowed_reasoning_efforts is None


def test_partial_metadata_is_unknown_not_unsupported() -> None:
    [item] = build_openai_gpt_catalog(
        account_model_ids=["gpt-partial"],
        litellm_metadata={"gpt-partial": {"litellm_provider": "openai"}},
        overrides={},
        fetched_at=FETCHED_AT,
    )

    assert item.compatibility is ModelCatalogCompatibility.unknown
    assert item.reason == "litellm_compatibility_incomplete"


def test_override_loader_requires_source_date_and_rejects_unknown_effort(tmp_path: Path) -> None:
    path = tmp_path / "overrides.yaml"
    path.write_text(
        """
models:
  gpt-example:
    compatibility: compatible
    reasoning_supported: true
    allowed_reasoning_efforts: [turbo]
    source: https://example.invalid/model
    checked_at: 2026-09-15
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="turbo"):
        load_model_capability_overrides(path)


@pytest.mark.parametrize(
    ("source", "checked_at"),
    [
        ("null", "2026-09-15"),
        ('""', "2026-09-15"),
        ("42", "2026-09-15"),
        ("https://example.invalid/model", '"not-a-date"'),
        ("https://example.invalid/model", "null"),
    ],
)
def test_override_loader_rejects_invalid_source_or_checked_at(
    tmp_path: Path, source: str, checked_at: str
) -> None:
    path = tmp_path / "overrides.yaml"
    path.write_text(
        f"""
models:
  gpt-example:
    compatibility: compatible
    source: {source}
    checked_at: {checked_at}
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="source|checked_at"):
        load_model_capability_overrides(path)


def test_override_rejects_efforts_without_confirmed_reasoning_support() -> None:
    with pytest.raises(ValueError, match="reasoning efforts require reasoning_supported=true"):
        ModelCapabilityOverride(
            compatibility=None,
            reasoning_supported=None,
            allowed_reasoning_efforts=(ReasoningEffort.low,),
            source="https://example.invalid/model",
            checked_at="2026-09-15",
        )


def test_override_loader_parses_closed_capability_contract(tmp_path: Path) -> None:
    path = tmp_path / "overrides.yaml"
    path.write_text(
        """
models:
  gpt-example:
    compatibility: compatible
    reasoning_supported: true
    allowed_reasoning_efforts: [low, medium, high]
    source: https://developers.openai.com/api/docs/models/gpt-example
    checked_at: 2026-09-15
""".strip(),
        encoding="utf-8",
    )

    overrides = load_model_capability_overrides(path)

    assert overrides["gpt-example"].allowed_reasoning_efforts == (
        ReasoningEffort.low,
        ReasoningEffort.medium,
        ReasoningEffort.high,
    )


def test_cached_catalog_parser_rejects_malformed_provenance() -> None:
    with pytest.raises(ValueError, match="provenance entry"):
        deserialize_catalog_item(
            {
                "model_id": "gpt-example",
                "compatibility": "compatible",
                "reason": "confirmed_openai_text_gpt",
                "reasoning_supported": None,
                "allowed_reasoning_efforts": None,
                "provenance": {"availability": "not-a-mapping"},
            }
        )


def test_cached_catalog_parser_rejects_unknown_reason_code() -> None:
    with pytest.raises(ValueError, match="future_reason"):
        deserialize_catalog_item(
            {
                "model_id": "gpt-example",
                "compatibility": "compatible",
                "reason": "future_reason",
                "reasoning_supported": None,
                "allowed_reasoning_efforts": None,
                "provenance": {"availability": {"source": "openai_models_api"}},
            }
        )
