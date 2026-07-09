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
