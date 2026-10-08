from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from anytoolai_platform_core.common.literal_source import (
    LITERAL_SOURCE_PREFIX as _LITERAL_SOURCE_PREFIX,
)
from anytoolai_platform_core.common.literal_source import (
    parse_strict_literal_json as _parse_strict_literal_json,
)
from anytoolai_platform_core.workflows.errors import (
    WorkflowConditionEvaluationError,
    WorkflowMappingResolutionError,
    WorkflowSourcePathAbsentError,
    WorkflowStepContractValidationError,
)

_OPTIONAL_SOURCE_PREFIX = "?"
_TEMPLATE_SOURCE_PREFIX = "template:"
_TEMPLATE_PLACEHOLDER = re.compile(r"\{(\??)([^{}\n]*)\}")


@dataclass(frozen=True)
class WorkflowSourcePath:
    root: str
    path: tuple[str, ...]
    step_id: str | None = None
    literal_value: Any = None
    template: str = ""


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
        is_optional, effective_source_path = _split_optional_source_path(source_path)
        if is_optional:
            try:
                value = resolve_source_path(
                    effective_source_path,
                    scenario_input=scenario_input,
                    step_outputs=step_outputs,
                    context=context,
                )
            except WorkflowSourcePathAbsentError:
                continue
        else:
            value = resolve_source_path(
                effective_source_path,
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
    _reject_literal_when_reference(parse_source_path(when))
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
    scenario_input: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not output_mapping:
        return {}

    step_outputs = {step_id: step_output}
    applied: dict[str, Any] = {}
    for target_path, source_path in output_mapping.items():
        reference = parse_source_path(source_path)
        if reference.root not in ("literal", "scenario_input") and (
            reference.root != "step_output" or reference.step_id != step_id
        ):
            raise WorkflowMappingResolutionError(
                "output_mapping sources must reference the current step output, the scenario "
                f"input, or a literal: constant: {source_path}"
            )
        value = resolve_source_path(
            source_path,
            scenario_input=scenario_input or {},
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
    if reference.root == "literal":
        return reference.literal_value
    if reference.root == "template":
        return _render_template(
            reference.template,
            scenario_input=scenario_input,
            step_outputs=step_outputs,
            context=context,
        )
    if reference.root == "scenario_input":
        current: Any = scenario_input
    elif reference.root == "context":
        current = context
    else:
        assert reference.step_id is not None
        if reference.step_id not in step_outputs:
            raise WorkflowSourcePathAbsentError(
                f"workflow step output not available: {reference.step_id}"
            )
        current = step_outputs[reference.step_id]
    return _walk_value(current, reference.path, source_path=source_path)


def parse_source_path(source_path: str) -> WorkflowSourcePath:
    if source_path.startswith(_LITERAL_SOURCE_PREFIX):
        payload = source_path[len(_LITERAL_SOURCE_PREFIX) :]
        try:
            literal_value = _parse_strict_literal_json(payload)
        except json.JSONDecodeError as exc:
            raise WorkflowMappingResolutionError(
                f"workflow literal source path is not valid JSON: {source_path}"
            ) from exc
        return WorkflowSourcePath(root="literal", path=(), literal_value=literal_value)
    if source_path.startswith(_TEMPLATE_SOURCE_PREFIX):
        template = source_path[len(_TEMPLATE_SOURCE_PREFIX) :]
        _template_placeholders(template)
        return WorkflowSourcePath(root="template", path=(), template=template)
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
        is_optional, effective_source_path = _split_optional_source_path(source_path)
        if is_optional and effective_source_path.startswith(_TEMPLATE_SOURCE_PREFIX):
            raise WorkflowMappingResolutionError(
                "`?template:` is not supported; mark individual placeholders optional with "
                f"`{{?path}}`: {source_path}"
            )
        reference = parse_source_path(effective_source_path)
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
        if reference.root in ("literal", "scenario_input"):
            continue
        if reference.root != "step_output" or reference.step_id != current_step_id:
            raise WorkflowMappingResolutionError(
                "output_mapping must map from the current step output, the scenario input, or "
                "a literal: constant to `context.*`."
            )


def _validate_when(when: Any, *, prior_step_ids: tuple[str, ...]) -> None:
    if when is None:
        return
    if not isinstance(when, str) or not when.strip():
        raise WorkflowConditionEvaluationError("`when` must be a non-empty string path.")
    reference = parse_source_path(when)
    _reject_literal_when_reference(reference)
    _validate_step_reference(reference, prior_step_ids=prior_step_ids)


def _validate_retry_count(retry_count: Any) -> None:
    if not isinstance(retry_count, int) or isinstance(retry_count, bool):
        raise WorkflowMappingResolutionError("`retry_count` must be an integer.")
    if retry_count < 0:
        raise WorkflowMappingResolutionError("`retry_count` must be greater than or equal to 0.")


def _reject_literal_when_reference(reference: WorkflowSourcePath) -> None:
    if reference.root in ("literal", "template"):
        raise WorkflowConditionEvaluationError(
            "`when` does not support literal: or template: sources."
        )


@lru_cache(maxsize=None)
def _template_placeholders(template: str) -> tuple[tuple[bool, str], ...]:
    """Parse `{path}` / `{?path}` placeholders; stray braces are a config error."""
    leftover = _TEMPLATE_PLACEHOLDER.sub("", template)
    if "{" in leftover or "}" in leftover:
        raise WorkflowMappingResolutionError(
            f"workflow template has an unbalanced or nested brace: {template}"
        )
    placeholders = tuple(
        (m.group(1) == "?", m.group(2)) for m in _TEMPLATE_PLACEHOLDER.finditer(template)
    )
    if not placeholders:
        raise WorkflowMappingResolutionError(
            f"workflow template must contain at least one placeholder: {template}"
        )
    for _, path in placeholders:
        if path.startswith((_LITERAL_SOURCE_PREFIX, _TEMPLATE_SOURCE_PREFIX)):
            raise WorkflowMappingResolutionError(
                f"workflow template placeholders must be plain paths: {path}"
            )
        parse_source_path(path)
    return placeholders


def _render_template(
    template: str,
    *,
    scenario_input: Mapping[str, Any],
    step_outputs: Mapping[str, Any],
    context: Mapping[str, Any],
) -> str:
    lines: list[str] = []
    for line in template.split("\n"):
        parts: list[str] = []
        position = 0
        for match in _TEMPLATE_PLACEHOLDER.finditer(line):
            optional, path = match.group(1) == "?", match.group(2)
            try:
                value = resolve_source_path(
                    path, scenario_input=scenario_input, step_outputs=step_outputs, context=context
                )
            except WorkflowSourcePathAbsentError:
                if not optional:
                    raise
                break
            if isinstance(value, bool) or not isinstance(value, str | int | float):
                raise WorkflowMappingResolutionError(
                    f"workflow template placeholder must resolve to a string or number: {path}"
                )
            parts.extend((line[position : match.start()], str(value)))
            position = match.end()
        else:
            parts.append(line[position:])
            lines.append("".join(parts))
    if not lines:
        raise WorkflowMappingResolutionError(
            "workflow template rendered empty: every line depends on an absent optional path"
        )
    return "\n".join(lines)


def _validate_step_reference(
    reference: WorkflowSourcePath,
    *,
    prior_step_ids: tuple[str, ...],
) -> None:
    if reference.root == "template":
        for _, placeholder_path in _template_placeholders(reference.template):
            _validate_step_reference(
                parse_source_path(placeholder_path), prior_step_ids=prior_step_ids
            )
        return
    if reference.root == "step_output" and reference.step_id not in prior_step_ids:
        raise WorkflowMappingResolutionError(
            "workflow step references must point to a previous step output."
        )


def _split_optional_source_path(source_path: str) -> tuple[bool, str]:
    if source_path.startswith(_OPTIONAL_SOURCE_PREFIX):
        return True, source_path[len(_OPTIONAL_SOURCE_PREFIX) :]
    return False, source_path


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
    if parts[0] in {"scenario", "steps"} or (len(parts) > 1 and parts[0] == "context"):
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
        if not isinstance(current, Mapping):
            raise WorkflowMappingResolutionError(
                f"workflow source path could not be resolved: {source_path}"
            )
        if segment not in current:
            raise WorkflowSourcePathAbsentError(
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
