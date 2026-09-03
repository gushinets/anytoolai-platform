from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Awaitable, Callable, Mapping

from pydantic_ai import Agent, ModelRetry, UnexpectedModelBehavior
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.output import PromptedOutput, StructuredDict
from pydantic_ai.tools import RunContext
from pydantic_ai.usage import RequestUsage

from anytoolai_platform_core.providers.models import (
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
)
from anytoolai_platform_core.actions.output_validation import ActionOutputCrossValidator
from anytoolai_platform_core.structured_output.errors import (
    StructuredOutputError,
    StructuredOutputValidationError,
)
from anytoolai_platform_core.structured_output.validator import (
    validate_structured_output_value,
)


@dataclass
class PydanticAIValidationState:
    request: ProviderRequest
    request_executor: Callable[[ProviderRequest], Awaitable[ProviderResponse]]
    last_response: ProviderResponse | None = None
    semantic_attempt_index: int = 0
    pydantic_run_id: str | None = None


@dataclass(frozen=True)
class PydanticAIValidationResult:
    output_text: str
    structured_output: Mapping[str, Any] | None
    last_response: ProviderResponse
    pydantic_run_id: str


class PydanticAIValidationExhaustedError(RuntimeError):
    def __init__(
        self,
        *,
        last_response: ProviderResponse,
        pydantic_run_id: str | None,
        cause: UnexpectedModelBehavior,
    ) -> None:
        super().__init__(str(cause))
        self.last_response = last_response
        self.pydantic_run_id = pydantic_run_id
        self.cause = cause


class PydanticAIStructuredRunner:
    async def run(
        self,
        request: ProviderRequest,
        *,
        request_executor: Callable[[ProviderRequest], Awaitable[ProviderResponse]],
        validation_max_attempts: int,
        input_payload: Mapping[str, Any] | None = None,
        cross_validator: ActionOutputCrossValidator | None = None,
    ) -> PydanticAIValidationResult:
        state = PydanticAIValidationState(
            request=request,
            request_executor=request_executor,
        )

        async def model_request(
            messages: list[ModelMessage],
            _agent_info: Any,
        ) -> ModelResponse:
            state.semantic_attempt_index += 1
            pydantic_run_id = _extract_run_id(messages)
            if pydantic_run_id is not None:
                state.pydantic_run_id = pydantic_run_id

            attempt_request = replace(
                state.request,
                messages=_messages_from_pydantic_history(messages),
                semantic_attempt_index=state.semantic_attempt_index,
                pydantic_run_id=state.pydantic_run_id,
            )
            response = await state.request_executor(attempt_request)
            state.last_response = response

            provider_details = (
                dict(response.metadata) if isinstance(response.metadata, Mapping) else {}
            )
            provider_details["gateway_backend"] = response.provider
            provider_details["gateway_model"] = response.model

            return ModelResponse(
                parts=[TextPart(response.output_text)],
                usage=RequestUsage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                ),
                provider_name=response.provider,
                provider_response_id=response.litellm_response_id,
                provider_details=provider_details,
                metadata={"provider_policy_ref": response.provider_policy_ref},
            )

        schema = request.response_schema
        output_type: Any = (
            str if schema is None else PromptedOutput(StructuredDict(dict(schema)), template=False)
        )

        agent = Agent[PydanticAIValidationState, Any](
            model=FunctionModel(
                function=model_request,
                model_name="function:anytoolai_provider_gateway",
            ),
            output_type=output_type,
            retries={"output": max(validation_max_attempts - 1, 0)},
            deps_type=PydanticAIValidationState,
            name="structured_llm_validation",
        )

        @agent.output_validator
        def _validate_output(
            ctx: RunContext[PydanticAIValidationState],
            data: Any,
        ) -> Any:
            ctx.deps.pydantic_run_id = ctx.run_id
            if ctx.deps.request.response_schema is None:
                return data
            try:
                validation_result = validate_structured_output_value(
                    data,
                    schema=dict(ctx.deps.request.response_schema),
                )
            except StructuredOutputError as exc:
                raise ModelRetry(str(exc)) from exc
            normalized_output = validation_result.normalized_output
            if cross_validator is not None:
                try:
                    cross_validator.validate(
                        input_payload=input_payload or {},
                        output=normalized_output,
                    )
                except StructuredOutputValidationError as exc:
                    # exc.reason is an internal, field-level correction hint for the
                    # model's next attempt; it is never the user-facing safe error
                    # (str(exc)/exc.details.safe_message stay generic for callers).
                    raise ModelRetry(exc.reason) from exc
            return normalized_output

        try:
            result = await agent.run(
                request.prompt,
                deps=state,
                infer_name=False,
            )
        except UnexpectedModelBehavior as exc:
            if state.last_response is None or state.pydantic_run_id is None:
                raise
            raise PydanticAIValidationExhaustedError(
                last_response=replace(
                    state.last_response,
                    pydantic_run_id=state.pydantic_run_id or state.last_response.pydantic_run_id,
                ),
                pydantic_run_id=state.pydantic_run_id,
                cause=exc,
            ) from exc
        if state.last_response is None:
            raise RuntimeError(
                "PydanticAI validation run completed without a provider response"
            )
        structured_output = None if request.response_schema is None else result.output
        return PydanticAIValidationResult(
            output_text=state.last_response.output_text,
            structured_output=structured_output,
            last_response=replace(
                state.last_response,
                structured_output=structured_output,
                pydantic_run_id=result.run_id,
            ),
            pydantic_run_id=result.run_id,
        )


def _messages_from_pydantic_history(
    messages: list[ModelMessage],
) -> tuple[ProviderMessage, ...]:
    provider_messages: list[ProviderMessage] = []
    for message in messages:
        if not isinstance(message, ModelRequest):
            continue
        if message.instructions:
            provider_messages.append(
                ProviderMessage(role="system", content=message.instructions)
            )
        for part in message.parts:
            if isinstance(part, UserPromptPart):
                provider_messages.append(
                    ProviderMessage(role="user", content=part.content)
                )
            elif isinstance(part, RetryPromptPart):
                provider_messages.append(
                    ProviderMessage(role="user", content=part.model_response())
                )
    return tuple(provider_messages)


def _extract_run_id(messages: list[ModelMessage]) -> str | None:
    for message in reversed(messages):
        run_id = getattr(message, "run_id", None)
        if isinstance(run_id, str) and run_id:
            return run_id
    return None
