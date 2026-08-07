from __future__ import annotations

import pytest

from anytoolai_platform_core.workflows.errors import (
    WorkflowConditionEvaluationError,
    WorkflowMappingResolutionError,
    WorkflowStepContractValidationError,
)
from anytoolai_platform_core.workflows.mappings import (
    apply_output_mapping,
    parse_source_path,
    resolve_step_input,
    resolve_when_condition,
    validate_step_contract,
)


def test_validate_step_contract_raises_dedicated_validation_error() -> None:
    with pytest.raises(WorkflowStepContractValidationError) as exc_info:
        validate_step_contract(
            step_id="extract",
            prior_step_ids=(),
            input_mapping={},
            output_mapping={},
            when=None,
            retry_count=-1,
        )

    assert "retry_count" in str(exc_info.value)


def test_resolve_step_input_maps_from_supported_sources() -> None:
    resolved = resolve_step_input(
        input_mapping={
            "source_text": "scenario.input.source_text",
            "issues": "steps.detect_issues.output.issues",
            "summary": "context.workflow_output.summary",
        },
        scenario_input={"source_text": "hello"},
        step_outputs={"detect_issues": {"issues": ["one", "two"]}},
        context={"workflow_output": {"summary": "done"}},
    )

    assert resolved == {
        "source_text": "hello",
        "issues": ["one", "two"],
        "summary": "done",
    }


def test_apply_output_mapping_requires_context_targets() -> None:
    with pytest.raises(WorkflowMappingResolutionError) as exc_info:
        apply_output_mapping(
            {"workflow_output": "steps.extract.output"},
            step_id="extract",
            step_output={"title": "Extracted"},
            context={},
        )

    assert "context.*" in str(exc_info.value)


def test_resolve_when_condition_uses_source_path_truthiness() -> None:
    assert (
        resolve_when_condition(
            "scenario.input.run_optional_step",
            scenario_input={"run_optional_step": 1},
            step_outputs={},
            context={},
        )
        is True
    )
    assert (
        resolve_when_condition(
            "context.skip_flag",
            scenario_input={},
            step_outputs={},
            context={"skip_flag": ""},
        )
        is False
    )


def test_parse_source_path_rejects_bracket_syntax() -> None:
    with pytest.raises(WorkflowMappingResolutionError) as exc_info:
        parse_source_path("scenario.input.items[0]")

    assert "bracket syntax" in str(exc_info.value)


def test_validate_step_contract_rejects_forward_references() -> None:
    with pytest.raises(WorkflowStepContractValidationError) as exc_info:
        validate_step_contract(
            step_id="extract",
            prior_step_ids=(),
            input_mapping={"source_text": "steps.detect_issues.output.issues"},
            output_mapping={},
            when=None,
            retry_count=0,
        )

    assert "previous step output" in str(exc_info.value)


def test_validate_step_contract_rejects_non_context_output_targets() -> None:
    with pytest.raises(WorkflowStepContractValidationError) as exc_info:
        validate_step_contract(
            step_id="extract",
            prior_step_ids=(),
            input_mapping={},
            output_mapping={"workflow_output": "steps.extract.output"},
            when=None,
            retry_count=0,
        )

    assert "context.*" in str(exc_info.value)


def test_resolve_step_input_omits_optional_source_when_scenario_input_key_absent() -> None:
    resolved = resolve_step_input(
        input_mapping={
            "source_text": "scenario.input.source_text",
            "strict": "?scenario.input.strict",
        },
        scenario_input={"source_text": "hello"},
        step_outputs={},
        context={},
    )

    assert resolved == {"source_text": "hello"}


def test_resolve_step_input_uses_optional_source_when_present() -> None:
    resolved = resolve_step_input(
        input_mapping={"strict": "?scenario.input.strict"},
        scenario_input={"strict": True},
        step_outputs={},
        context={},
    )

    assert resolved == {"strict": True}


def test_resolve_step_input_still_raises_for_required_missing_source() -> None:
    with pytest.raises(WorkflowMappingResolutionError):
        resolve_step_input(
            input_mapping={"source_text": "scenario.input.source_text"},
            scenario_input={},
            step_outputs={},
            context={},
        )


def test_resolve_step_input_resolves_literal_json_constant() -> None:
    resolved = resolve_step_input(
        input_mapping={"fields": 'literal:[{"name":"deadline"}]'},
        scenario_input={},
        step_outputs={},
        context={},
    )

    assert resolved == {"fields": [{"name": "deadline"}]}


def test_parse_source_path_rejects_malformed_literal_json() -> None:
    with pytest.raises(WorkflowMappingResolutionError) as exc_info:
        parse_source_path("literal:{not json}")

    assert "not valid JSON" in str(exc_info.value)


def test_parse_source_path_rejects_non_finite_literal_constants() -> None:
    for payload in ("literal:NaN", "literal:Infinity", "literal:-Infinity"):
        with pytest.raises(WorkflowMappingResolutionError) as exc_info:
            parse_source_path(payload)

        assert "not valid JSON" in str(exc_info.value)


def test_validate_step_contract_accepts_optional_source_with_valid_shape() -> None:
    validate_step_contract(
        step_id="extract",
        prior_step_ids=(),
        input_mapping={"strict": "?scenario.input.strict"},
        output_mapping={},
        when=None,
        retry_count=0,
    )


def test_resolve_step_input_allows_bare_reserved_word_as_target_field_name() -> None:
    resolved = resolve_step_input(
        input_mapping={"context": "scenario.input.context"},
        scenario_input={"context": "extra background"},
        step_outputs={},
        context={},
    )

    assert resolved == {"context": "extra background"}


def test_validate_step_contract_rejects_literal_when_condition() -> None:
    with pytest.raises(WorkflowStepContractValidationError) as exc_info:
        validate_step_contract(
            step_id="extract",
            prior_step_ids=(),
            input_mapping={},
            output_mapping={},
            when="literal:false",
            retry_count=0,
        )

    assert "literal:" in str(exc_info.value)


def test_resolve_when_condition_rejects_literal_source() -> None:
    with pytest.raises(WorkflowConditionEvaluationError):
        resolve_when_condition(
            "literal:false",
            scenario_input={},
            step_outputs={},
            context={},
        )


def test_validate_step_contract_still_rejects_bare_scenario_or_steps_target() -> None:
    for target_path in ("scenario", "steps"):
        with pytest.raises(WorkflowStepContractValidationError) as exc_info:
            validate_step_contract(
                step_id="extract",
                prior_step_ids=(),
                input_mapping={target_path: "scenario.input.source_text"},
                output_mapping={},
                when=None,
                retry_count=0,
            )

        assert "not rooted source paths" in str(exc_info.value)


def test_validate_step_contract_still_rejects_multi_segment_rooted_target() -> None:
    with pytest.raises(WorkflowStepContractValidationError) as exc_info:
        validate_step_contract(
            step_id="extract",
            prior_step_ids=(),
            input_mapping={"context.nested": "scenario.input.context"},
            output_mapping={},
            when=None,
            retry_count=0,
        )

    assert "not rooted source paths" in str(exc_info.value)


def test_validate_step_contract_still_validates_shape_under_optional_prefix() -> None:
    with pytest.raises(WorkflowStepContractValidationError) as exc_info:
        validate_step_contract(
            step_id="extract",
            prior_step_ids=(),
            input_mapping={"source_text": "?scenario.input.items[0]"},
            output_mapping={},
            when=None,
            retry_count=0,
        )

    assert "bracket syntax" in str(exc_info.value)
