from __future__ import annotations

import asyncio
from typing import Any

import pytest
from anytoolai_platform_actions.structured_llm import pydanticai_runner
from anytoolai_platform_actions.structured_llm.pydanticai_runner import (
    PydanticAIStructuredRunner,
    PydanticAIValidationExhaustedError,
)
from anytoolai_platform_core.actions.output_validation import ActionOutputCrossValidator
from anytoolai_platform_core.providers.models import (
    ProviderCallStatus,
    ProviderRequest,
    ProviderResponse,
)
from anytoolai_platform_core.structured_output.errors import StructuredOutputValidationError

SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string"}},
    "required": ["name"],
}


def _base_request(**overrides: Any) -> ProviderRequest:
    fields: dict[str, Any] = {
        "provider_policy_ref": "default_fake_provider_v1",
        "tenant_id": "tenant_demo",
        "region": "eu-central",
        "product_id": "kernel_demo",
        "frontend_id": "kernel_demo_ce",
        "scenario_session_id": "scenario_session_demo",
        "job_id": "job_demo",
        "workflow_id": "wf_demo",
        "workflow_version": 1,
        "step_id": "step_1",
        "action_run_id": "action_run_demo",
        "action_type": "text.extract_structured_fields",
        "action_config_id": "kernel_demo.extract_structured_fields_v1",
        "prompt": "Prompt text",
    }
    fields.update(overrides)
    return ProviderRequest(**fields)


def _fixed_executor(output_text: str) -> Any:
    async def request_executor(request: ProviderRequest) -> ProviderResponse:
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text=output_text,
            status=ProviderCallStatus.succeeded,
        )

    return request_executor


def _capture_agent_infos(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Wrap `FunctionModel` so the `AgentInfo` PydanticAI builds for each attempt is
    recorded -- this is the request PydanticAI actually sends the model, carrying
    `model_request_parameters.output_mode`/`.output_object`, which is what the
    schema-binding fix changes."""
    captured: list[Any] = []
    real_function_model = pydanticai_runner.FunctionModel

    def capturing_function_model(*, function: Any, model_name: str | None = None) -> Any:
        async def wrapped(messages: Any, agent_info: Any) -> Any:
            captured.append(agent_info)
            return await function(messages, agent_info)

        return real_function_model(function=wrapped, model_name=model_name)

    monkeypatch.setattr(pydanticai_runner, "FunctionModel", capturing_function_model)
    return captured


def test_schema_bound_request_takes_plain_text_so_our_own_parser_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PydanticAI's JSON parser rejects a raw newline in a string, or a reply without the JSON
    wrapper, before any output validator runs. The agent therefore takes plain text and the
    platform's own validator (tolerant parser, own retry message) is the one that decides. The
    schema still reaches the model through the adapter's guidance message, not PydanticAI's."""
    captured = _capture_agent_infos(monkeypatch)
    runner = PydanticAIStructuredRunner()
    request = _base_request(response_schema=SCHEMA)

    result = asyncio.run(
        runner.run(
            request,
            request_executor=_fixed_executor('{"name": "Ada"}'),
            validation_max_attempts=2,
        )
    )

    assert result.structured_output == {"name": "Ada"}
    params = captured[-1].model_request_parameters
    assert params.output_mode == "text"
    assert params.output_object is None


def test_a_raw_newline_inside_a_json_string_is_accepted() -> None:
    runner = PydanticAIStructuredRunner()
    request = _base_request(response_schema=SCHEMA)

    result = asyncio.run(
        runner.run(
            request,
            request_executor=_fixed_executor('{"name": "Ada\n\nLovelace"}'),
            validation_max_attempts=1,
        )
    )

    assert result.structured_output == {"name": "Ada\n\nLovelace"}


def test_a_reply_without_the_json_wrapper_gets_our_retry_message_and_can_recover() -> None:
    runner = PydanticAIStructuredRunner()
    request = _base_request(response_schema=SCHEMA)
    seen_prompts: list[str] = []

    async def request_executor(attempt: ProviderRequest) -> ProviderResponse:
        seen_prompts.append(" ".join(message.content for message in attempt.messages))
        output = "Ada Lovelace" if len(seen_prompts) == 1 else '{"name": "Ada"}'
        return ProviderResponse(
            provider_policy_ref=attempt.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text=output,
            status=ProviderCallStatus.succeeded,
        )

    result = asyncio.run(
        runner.run(request, request_executor=request_executor, validation_max_attempts=2)
    )

    assert result.structured_output == {"name": "Ada"}
    assert len(seen_prompts) == 2
    assert "Reply with exactly one JSON object" in seen_prompts[1]


def test_schema_less_request_stays_on_text_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = _capture_agent_infos(monkeypatch)
    runner = PydanticAIStructuredRunner()
    request = _base_request(response_schema=None)

    result = asyncio.run(
        runner.run(
            request,
            request_executor=_fixed_executor("plain text output"),
            validation_max_attempts=2,
        )
    )

    assert result.structured_output is None
    assert result.output_text == "plain text output"
    params = captured[-1].model_request_parameters
    assert params.output_mode == "text"
    assert params.output_object is None


def test_schema_mismatch_retries_and_then_exhausts() -> None:
    attempts: list[ProviderRequest] = []

    async def request_executor(request: ProviderRequest) -> ProviderResponse:
        attempts.append(request)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text='{"other": 1}',
            status=ProviderCallStatus.succeeded,
        )

    runner = PydanticAIStructuredRunner()
    request = _base_request(response_schema=SCHEMA)

    with pytest.raises(PydanticAIValidationExhaustedError) as exc_info:
        asyncio.run(
            runner.run(
                request,
                request_executor=request_executor,
                validation_max_attempts=3,
            )
        )

    assert len(attempts) == 3
    assert exc_info.value.last_response.output_text == '{"other": 1}'


def test_malformed_json_retries_and_then_exhausts() -> None:
    attempts: list[ProviderRequest] = []

    async def request_executor(request: ProviderRequest) -> ProviderResponse:
        attempts.append(request)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text="not json at all",
            status=ProviderCallStatus.succeeded,
        )

    runner = PydanticAIStructuredRunner()
    request = _base_request(response_schema=SCHEMA)

    with pytest.raises(PydanticAIValidationExhaustedError) as exc_info:
        asyncio.run(
            runner.run(
                request,
                request_executor=request_executor,
                validation_max_attempts=2,
            )
        )

    assert len(attempts) == 2
    assert exc_info.value.last_response.output_text == "not json at all"


def test_schema_missing_top_level_object_type_fails_fast_with_clear_error() -> None:
    """StructuredDict requires a top-level `"type": "object"` (or a directly resolvable $ref)
    to bind as PydanticAI's output contract. A config schema missing it is an authoring defect,
    not a per-request failure retrying would fix -- assert it surfaces as a clear RuntimeError
    naming the action_config_id instead of pydantic_ai's internal UserError leaking out."""

    async def request_executor(_request: ProviderRequest) -> ProviderResponse:
        raise AssertionError("request_executor should not be called for a malformed schema")

    runner = PydanticAIStructuredRunner()
    request = _base_request(
        action_config_id="kernel_demo.bad_schema_v1",
        response_schema={"properties": {"name": {"type": "string"}}},
    )

    with pytest.raises(RuntimeError, match="kernel_demo.bad_schema_v1"):
        asyncio.run(
            runner.run(
                request,
                request_executor=request_executor,
                validation_max_attempts=2,
            )
        )


def test_schema_with_old_style_ref_fails_fast_with_clear_error() -> None:
    """StructuredDict's own "type": "object" guard passes for a schema using the old-style
    "definitions"/"$ref" pair instead of "$defs", but Agent construction then raises a raw
    KeyError from pydantic's JSON-schema generator -- a different internal exception for the
    same underlying "cannot bind this schema" condition the previous test covers. Assert it
    surfaces as the same kind of clear RuntimeError, not the raw KeyError."""

    async def request_executor(_request: ProviderRequest) -> ProviderResponse:
        raise AssertionError("request_executor should not be called for a malformed schema")

    runner = PydanticAIStructuredRunner()
    request = _base_request(
        action_config_id="kernel_demo.old_style_ref_v1",
        response_schema={
            "type": "object",
            "properties": {"child": {"$ref": "#/definitions/Foo"}},
            "definitions": {"Foo": {"type": "string"}},
        },
    )

    with pytest.raises(RuntimeError, match="kernel_demo.old_style_ref_v1"):
        asyncio.run(
            runner.run(
                request,
                request_executor=request_executor,
                validation_max_attempts=2,
            )
        )


def test_non_finite_numeric_value_retries_and_then_exhausts() -> None:
    """pydantic-core and jsonschema.validate() both silently accept a bare NaN/Infinity in an
    already-decoded value, unlike the raw-text parser AnyToolAI's final validation uses -- assert
    it is rejected inside PydanticAI's own retry loop instead of reaching a false "success"."""
    attempts: list[ProviderRequest] = []

    async def request_executor(request: ProviderRequest) -> ProviderResponse:
        attempts.append(request)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text='{"name": NaN}',
            status=ProviderCallStatus.succeeded,
        )

    runner = PydanticAIStructuredRunner()
    request = _base_request(response_schema=SCHEMA)

    with pytest.raises(PydanticAIValidationExhaustedError) as exc_info:
        asyncio.run(
            runner.run(
                request,
                request_executor=request_executor,
                validation_max_attempts=2,
            )
        )

    assert len(attempts) == 2
    assert exc_info.value.last_response.output_text == '{"name": NaN}'


def test_cross_validator_retry_then_succeeds() -> None:
    class RejectOnceValidator(ActionOutputCrossValidator):
        def __init__(self) -> None:
            self.calls = 0

        def validate(self, *, input_payload: Any, output: Any) -> None:
            self.calls += 1
            if self.calls == 1:
                raise StructuredOutputValidationError(
                    reason="needs fix", error_type="cross_validation"
                )

    attempts: list[ProviderRequest] = []

    async def request_executor(request: ProviderRequest) -> ProviderResponse:
        attempts.append(request)
        return ProviderResponse(
            provider_policy_ref=request.provider_policy_ref,
            provider="fake",
            model="fake-json-v1",
            output_text='{"name": "Ada"}',
            status=ProviderCallStatus.succeeded,
        )

    runner = PydanticAIStructuredRunner()
    validator = RejectOnceValidator()
    request = _base_request(response_schema=SCHEMA)

    result = asyncio.run(
        runner.run(
            request,
            request_executor=request_executor,
            validation_max_attempts=3,
            cross_validator=validator,
        )
    )

    assert len(attempts) == 2
    assert result.structured_output == {"name": "Ada"}
