from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TypeVar

from anytoolai_platform_core.actions.input_validation import ActionInputValidator
from anytoolai_platform_core.actions.models import ActionDefinition
from anytoolai_platform_core.actions.output_validation import ActionOutputCrossValidator

from .compose_reply import ComposeReplyCrossValidator
from .detect_issues_by_taxonomy import DetectIssuesByTaxonomyCrossValidator
from .extract_structured_fields import (
    ExtractStructuredFieldsCrossValidator,
    ExtractStructuredFieldsInputValidator,
)
from .generate_clarifying_questions import GenerateClarifyingQuestionsCrossValidator
from .generate_gap_rewrites import GapRewritesCrossValidator
from .persuasive_text import PersuasiveTextCrossValidator
from .synthesize_angle import SynthesizeAngleCrossValidator

NONE_REF = "none"

_CROSS_VALIDATORS: dict[str, type[ActionOutputCrossValidator]] = {
    "text.extract_structured_fields": ExtractStructuredFieldsCrossValidator,
    "text.detect_issues_by_taxonomy": DetectIssuesByTaxonomyCrossValidator,
    "text.compose_reply": ComposeReplyCrossValidator,
    "text.generate_clarifying_questions": GenerateClarifyingQuestionsCrossValidator,
    "text.synthesize_angle": SynthesizeAngleCrossValidator,
    "text.compose_persuasive_text": PersuasiveTextCrossValidator,
    "text.generate_gap_rewrites": GapRewritesCrossValidator,
}

_INPUT_VALIDATORS: dict[str, type[ActionInputValidator]] = {
    "text.extract_structured_fields": ExtractStructuredFieldsInputValidator,
}


class ValidatorRefNotFoundError(LookupError):
    def __init__(self, *, ref: str, field_name: str, action_type: str) -> None:
        super().__init__(
            f"{field_name} {ref!r} declared on action_type {action_type!r} has no "
            "registered validator class"
        )
        self.ref = ref
        self.field_name = field_name
        self.action_type = action_type


_V = TypeVar("_V")


def _resolve_validators(
    action_definitions: Mapping[str, ActionDefinition],
    *,
    ref_getter: Callable[[ActionDefinition], str],
    lookup: Mapping[str, type[_V]],
    field_name: str,
) -> dict[str, _V]:
    validators: dict[str, _V] = {}
    for action_type, definition in action_definitions.items():
        ref = ref_getter(definition)
        if ref == NONE_REF:
            continue
        validator_cls = lookup.get(ref)
        if validator_cls is None:
            raise ValidatorRefNotFoundError(ref=ref, field_name=field_name, action_type=action_type)
        validators[action_type] = validator_cls()
    return validators


def build_output_cross_validators(
    action_definitions: Mapping[str, ActionDefinition],
) -> dict[str, ActionOutputCrossValidator]:
    return _resolve_validators(
        action_definitions,
        ref_getter=lambda definition: definition.cross_validator_ref,
        lookup=_CROSS_VALIDATORS,
        field_name="cross_validator_ref",
    )


def build_input_validators(
    action_definitions: Mapping[str, ActionDefinition],
) -> dict[str, ActionInputValidator]:
    return _resolve_validators(
        action_definitions,
        ref_getter=lambda definition: definition.input_validator_ref,
        lookup=_INPUT_VALIDATORS,
        field_name="input_validator_ref",
    )
