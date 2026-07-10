from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from anytoolai_platform_core.workflows.errors import (
    WorkflowConditionEvaluationError,
    WorkflowMappingResolutionError,
    WorkflowStepContractValidationError,
)


@dataclass(frozen=True)
class WorkflowSourcePath:
    root: str
    path: tuple[str, ...]
    step_id: str | None = None


def validate_step_contract(
    *,
    step_id: str,
    prior_step_ids: tuple[str, ...],
    input_mapping: Any,
    output_mapping: Any,
    when: Any,
    retry_count: Any,
) -> None:
    try:
        _validate_retry_count(retry_count)
        _validate_input_mapping(input_mapping, prior_step_ids=prior_step_ids)
        _validate_output_mapping(output_mapping, current_step_id=step_id)
        _validate_when(when, prior_step_ids=prior_step_ids)
    except (WorkflowMappingResolutionError, WorkflowConditionEvaluationError) as exc:
        raise WorkflowStepContractValidationError(str(exc)) from exc


def resolve_step_input(
    *,
    input_mapping: Mapping[str, str],
    scenario_input: Mapping[str, Any],
    step_outputs: Mapping[str, Any],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    if not input_mapping:
        return _normalize_mapping(scenario_input)

    resolved: dict[str, Any] = {}
    for target_path, source_path in input_mapping.items():
        value = resolve_source_path(
            source_path,
            scenario_input=scenario_input,
            step_outputs=step_outputs,
            context=context,
        )
        _set_target_value(resolved, _parse_target_path(target_path), _normalize_value(value))
    return resolved


def resolve_when_condition(
    when: str,
    *,
    scenario_input: Mapping[str, Any],
    step_outputs: Mapping[str, Any],
    context: Mapping[str, Any],
) -> bool:
    try:
        return bool(
            resolve_source_path(
                when,
                scenario_input=scenario_input,
                step_outputs=step_outputs,
                context=context,
            )
        )
    except WorkflowMappingResolutionError as exc:
        raise WorkflowConditionEvaluationError(str(exc)) from exc


def apply_output_mapping(
    output_mapping: Mapping[str, str],
    *,
    step_id: str,
    step_output: Mapping[str, Any] | list[Any] | Any,
    context: dict[str, Any],
) -> dict[str, Any]:
    if not output_mapping:
        return {}

    step_outputs = {step_id: step_output}
    applied: dict[str, Any] = {}
    for target_path, source_path in output_mapping.items():
        reference = parse_source_path(source_path)
        if reference.root != "step_output" or reference.step_id != step_id:
            raise WorkflowMappingResolutionError(
                "output_mapping sources must reference the current step output: "
                f"{source_path}"
            )
        value = resolve_source_path(
            source_path,
            scenario_input={},
            step_outputs=step_outputs,
            context=context,
        )
        context_segments = _parse_context_target_path(target_path)
        _set_target_value(context, context_segments, _normalize_value(value))
        applied[target_path] = _normalize_value(value)
    return applied


def resolve_source_path(
    source_path: str,
    *,
    scenario_input: Mapping[str, Any],
    step_outputs: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Any:
    reference = parse_source_path(source_path)
    if reference.root == "scenario_input":
        current: Any = scenario_input
    elif reference.root == "context":
        current = context
    else:
        assert reference.step_id is not None
        if reference.step_id not in step_outputs:
            raise WorkflowMappingResolutionError(
                f"workflow step output not available: {reference.step_id}"
            )
        current = step_outputs[reference.step_id]
    return _walk_value(current, reference.path, source_path=source_path)


def parse_source_path(source_path: str) -> WorkflowSourcePath:
    _require_plain_dotted_path(source_path)
    parts = source_path.split(".")
    if parts[:2] == ["scenario", "input"]:
        return WorkflowSourcePath(root="scenario_input", path=tuple(parts[2:]))
    if parts[:1] == ["context"]:
        return WorkflowSourcePath(root="context", path=tuple(parts[1:]))
    if len(parts) >= 3 and parts[0] == "steps" and parts[2] == "output":
        return WorkflowSourcePath(
            root="step_output",
            step_id=parts[1],
            path=tuple(parts[3:]),
        )
    raise WorkflowMappingResolutionError(
        "unsupported workflow source path. Expected "
        "`scenario.input`, `steps.<step_id>.output`, or `context.*`."
    )


def _validate_input_mapping(
    input_mapping: Any,
    *,
    prior_step_ids: tuple[str, ...],
) -> None:
    mapping = _require_mapping_of_strings("input_mapping", input_mapping)
    for target_path, source_path in mapping.items():
        _parse_target_path(target_path)
        reference = parse_source_path(source_path)
        _validate_step_reference(reference, prior_step_ids=prior_step_ids)


def _validate_output_mapping(
    output_mapping: Any,
    *,
    current_step_id: str,
) -> None:
    mapping = _require_mapping_of_strings("output_mapping", output_mapping)
    for target_path, source_path in mapping.items():
        _parse_context_target_path(target_path)
        reference = parse_source_path(source_path)
        if reference.root != "step_output" or reference.step_id != current_step_id:
            raise WorkflowMappingResolutionError(
                "output_mapping must map from the current step output to `context.*`."
            )


def _validate_when(when: Any, *, prior_step_ids: tuple[str, ...]) -> None:
    if when is None:
        return
    if not isinstance(when, str) or not when.strip():
        raise WorkflowConditionEvaluationError("`when` must be a non-empty string path.")
    reference = parse_source_path(when)
    _validate_step_reference(reference, prior_step_ids=prior_step_ids)


def _validate_retry_count(retry_count: Any) -> None:
    if not isinstance(retry_count, int) or isinstance(retry_count, bool):
        raise WorkflowMappingResolutionError("`retry_count` must be an integer.")
    if retry_count < 0:
        raise WorkflowMappingResolutionError("`retry_count` must be greater than or equal to 0.")


def _validate_step_reference(
    reference: WorkflowSourcePath,
    *,
    prior_step_ids: tuple[str, ...],
) -> None:
    if reference.root == "step_output" and reference.step_id not in prior_step_ids:
        raise WorkflowMappingResolutionError(
            "workflow step references must point to a previous step output."
        )


def _require_mapping_of_strings(field_name: str, value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise WorkflowMappingResolutionError(f"`{field_name}` must be a mapping of string paths.")

    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise WorkflowMappingResolutionError(
                f"`{field_name}` keys must be non-empty strings."
            )
        if not isinstance(raw_value, str) or not raw_value.strip():
            raise WorkflowMappingResolutionError(
                f"`{field_name}` values must be non-empty string source paths."
            )
        normalized[raw_key] = raw_value
    return normalized


def _parse_target_path(target_path: str) -> tuple[str, ...]:
    _require_plain_dotted_path(target_path)
    parts = tuple(target_path.split("."))
    if not parts or any(not part for part in parts):
        raise WorkflowMappingResolutionError("workflow target paths must be non-empty.")
    if parts[0] in {"scenario", "steps", "context"}:
        raise WorkflowMappingResolutionError(
            "step input target paths must be relative field paths, not rooted source paths."
        )
    return parts


def _parse_context_target_path(target_path: str) -> tuple[str, ...]:
    _require_plain_dotted_path(target_path)
    parts = target_path.split(".")
    if len(parts) < 2 or parts[0] != "context":
        raise WorkflowMappingResolutionError(
            "workflow output targets must use the `context.*` path contract."
        )
    if any(not part for part in parts[1:]):
        raise WorkflowMappingResolutionError("workflow context target paths must be non-empty.")
    return tuple(parts[1:])


def _walk_value(current: Any, path: tuple[str, ...], *, source_path: str) -> Any:
    for segment in path:
        if not isinstance(current, Mapping) or segment not in current:
            raise WorkflowMappingResolutionError(
                f"workflow source path could not be resolved: {source_path}"
            )
        current = current[segment]
    return current


def _set_target_value(target: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = target
    for segment in path[:-1]:
        next_value = current.get(segment)
        if next_value is None:
            next_value = {}
            current[segment] = next_value
        if not isinstance(next_value, dict):
            raise WorkflowMappingResolutionError(
                f"workflow target path collides with a non-object value: {'.'.join(path)}"
            )
        current = next_value
    current[path[-1]] = value


def _require_plain_dotted_path(value: str) -> None:
    if "[" in value or "]" in value:
        raise WorkflowMappingResolutionError(
            "workflow paths do not support array indexing or bracket syntax."
        )
    if value.startswith(".") or value.endswith(".") or ".." in value:
        raise WorkflowMappingResolutionError("workflow paths must use plain dotted segments.")


def _normalize_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {str(key): _normalize_value(item) for key, item in value.items()}


def _normalize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _normalize_mapping(value)
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value
