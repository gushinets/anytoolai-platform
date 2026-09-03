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


def test_schema_bound_request_binds_json_schema_into_output_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    assert params.output_mode == "prompted"
    assert params.output_object is not None
    assert params.output_object.json_schema == SCHEMA
    # template=False is required: the LiteLLM adapter already injects its own schema
    # guidance message, so PromptedOutput must not inject a second one.
    assert params.prompted_output_template is False


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
