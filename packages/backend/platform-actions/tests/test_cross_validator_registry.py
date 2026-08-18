from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

import pytest
from anytoolai_platform_actions.structured_llm import cross_validation
from anytoolai_platform_actions.structured_llm.cross_validation import (
    ComposeReplyCrossValidator,
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
    ValidatorRefNotFoundError,
    build_input_validators,
    build_output_cross_validators,
)
from anytoolai_platform_actions.structured_llm.cross_validation import (
    registry as cross_validator_registry,
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
        "document.generate_from_template": _definition(
            "document.generate_from_template",
            cross_validator_ref="none",
            input_validator_ref="none",
        ),
    }

    assert build_output_cross_validators(definitions) == {}
    assert build_input_validators(definitions) == {}


def test_build_output_cross_validators_raises_on_none_ref_with_registered_class() -> None:
    definitions = {
        "text.compare_and_classify": _definition(
            "text.compare_and_classify", cross_validator_ref="none", input_validator_ref="none"
        ),
    }

    with pytest.raises(ValidatorRefNotFoundError):
        build_output_cross_validators(definitions)


def test_build_input_validators_raises_on_none_ref_with_registered_class() -> None:
    definitions = {
        "text.compare_and_classify": _definition(
            "text.compare_and_classify", cross_validator_ref="none", input_validator_ref="none"
        ),
    }

    with pytest.raises(ValidatorRefNotFoundError):
        build_input_validators(definitions)


def test_build_output_cross_validators_raises_on_ref_for_different_action_type() -> None:
    definitions = {
        "text.extract_structured_fields": _definition(
            "text.extract_structured_fields",
            cross_validator_ref="text.compose_reply",
            input_validator_ref="none",
        ),
    }

    with pytest.raises(ValidatorRefNotFoundError) as exc_info:
        build_output_cross_validators(definitions)

    error = exc_info.value
    assert error.mismatched_owner is True
    assert "is registered for 'text.compose_reply', not 'text.extract_structured_fields'" in str(
        error
    )


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

    # Structural, not a frozen snapshot: every action_type with a registered class in
    # registry.py's lookup dicts must resolve, and vice versa. If a merge lands a new
    # validator class but leaves its YAML ref at "none", _resolve_validators now raises
    # ValidatorRefNotFoundError instead of silently under-populating this set - so this
    # assertion holding is itself proof the real config tree is fully wired, without
    # needing a human to update a hardcoded expected list.
    assert set(cross_validators) == set(cross_validator_registry._CROSS_VALIDATORS)
    assert set(input_validators) == set(cross_validator_registry._INPUT_VALIDATORS)


def test_every_validator_class_defined_in_cross_validation_is_registered() -> None:
    """Guards against the recurring merge hazard where a new atom's validator module lands
    (e.g. via a main merge) but registry.py's lookup dicts aren't updated to reference it -
    the class exists and is importable, yet no action_type can ever resolve to it. Runs without
    a DB, unlike the ActionRunner tests that would otherwise catch this end-to-end."""
    registered_cross_validators = set(cross_validator_registry._CROSS_VALIDATORS.values())
    registered_input_validators = set(cross_validator_registry._INPUT_VALIDATORS.values())

    for module_info in pkgutil.iter_modules(cross_validation.__path__):
        if module_info.name in {"registry", "_shared", "_markup"}:
            continue
        module = importlib.import_module(
            f"{cross_validation.__name__}.{module_info.name}"
        )
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            if cls.__name__.endswith("CrossValidator"):
                assert cls in registered_cross_validators, (
                    f"{cls.__name__} in {module.__name__} is not wired into "
                    "registry.py's _CROSS_VALIDATORS"
                )
            elif cls.__name__.endswith("InputValidator"):
                assert cls in registered_input_validators, (
                    f"{cls.__name__} in {module.__name__} is not wired into "
                    "registry.py's _INPUT_VALIDATORS"
                )
