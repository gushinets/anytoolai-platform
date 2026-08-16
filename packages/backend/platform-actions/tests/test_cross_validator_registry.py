from __future__ import annotations

from pathlib import Path

import pytest
from anytoolai_platform_actions.structured_llm.cross_validation import (
    ComposeReplyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
    ValidatorRefNotFoundError,
    build_input_validators,
    build_output_cross_validators,
)
from anytoolai_platform_core.actions.models import ActionDefinition, ActionExecutor
from anytoolai_platform_core.bootstrap.registry import build_config_registry

REPO_ROOT = Path(__file__).resolve().parents[4]
CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def _definition(
    action_type: str, *, cross_validator_ref: str, input_validator_ref: str
) -> ActionDefinition:
    return ActionDefinition(
        action_type=action_type,
        version=1,
        input_schema_ref="ref.in",
        output_schema_ref="ref.out",
        executor=ActionExecutor.structured_llm,
        cross_validator_ref=cross_validator_ref,
        input_validator_ref=input_validator_ref,
    )


def test_build_output_cross_validators_resolves_known_ref() -> None:
    definitions = {
        "text.extract_structured_fields": _definition(
            "text.extract_structured_fields",
            cross_validator_ref="text.extract_structured_fields",
            input_validator_ref="none",
        ),
        "text.compose_reply": _definition(
            "text.compose_reply",
            cross_validator_ref="text.compose_reply",
            input_validator_ref="none",
        ),
    }

    validators = build_output_cross_validators(definitions)

    assert isinstance(
        validators["text.extract_structured_fields"], ExtractStructuredFieldsCrossValidator
    )
    assert isinstance(validators["text.compose_reply"], ComposeReplyCrossValidator)


def test_build_input_validators_resolves_known_ref() -> None:
    definitions = {
        "text.extract_structured_fields": _definition(
            "text.extract_structured_fields",
            cross_validator_ref="none",
            input_validator_ref="text.extract_structured_fields",
        ),
    }

    validators = build_input_validators(definitions)

    assert isinstance(
        validators["text.extract_structured_fields"], ExtractStructuredFieldsInputValidator
    )


def test_build_output_cross_validators_skips_none_ref() -> None:
    definitions = {
        "text.compare_and_classify": _definition(
            "text.compare_and_classify", cross_validator_ref="none", input_validator_ref="none"
        ),
    }

    assert build_output_cross_validators(definitions) == {}
    assert build_input_validators(definitions) == {}


def test_build_output_cross_validators_raises_on_unknown_ref() -> None:
    definitions = {
        "text.compose_reply": _definition(
            "text.compose_reply",
            cross_validator_ref="text.compose_repl",
            input_validator_ref="none",
        ),
    }

    with pytest.raises(ValidatorRefNotFoundError):
        build_output_cross_validators(definitions)


def test_build_input_validators_raises_on_unknown_ref() -> None:
    definitions = {
        "text.compose_reply": _definition(
            "text.compose_reply",
            cross_validator_ref="none",
            input_validator_ref="text.compose_repl",
        ),
    }

    with pytest.raises(ValidatorRefNotFoundError):
        build_input_validators(definitions)


def test_real_config_registry_wiring_resolves_end_to_end() -> None:
    registry = build_config_registry(CONFIG_ROOT)

    cross_validators = build_output_cross_validators(registry.action_definitions)
    input_validators = build_input_validators(registry.action_definitions)

    assert set(cross_validators) == {
        "text.compare_and_classify",
        "text.compose_persuasive_text",
        "text.compose_reply",
        "text.detect_issues_by_taxonomy",
        "text.extract_structured_fields",
        "text.generate_clarifying_questions",
        "text.generate_gap_rewrites",
        "text.score_match_by_rubric",
        "text.synthesize_angle",
    }
    assert set(input_validators) == {
        "text.compare_and_classify",
        "text.extract_structured_fields",
        "text.score_match_by_rubric",
    }
