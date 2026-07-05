from __future__ import annotations

from dataclasses import dataclass

from anytoolai_platform_core.common.errors import PlatformError

STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE = "structured_output_validation_failed"
STRUCTURED_OUTPUT_VALIDATION_FAILURE_KIND = "validation"
STRUCTURED_OUTPUT_VALIDATION_SAFE_MESSAGE = (
    "Structured output validation failed."
)


class StructuredOutputError(ValueError):
    """Base error for platform-owned structured output parsing/validation."""


class StructuredOutputMalformedJsonError(StructuredOutputError):
    """Raised when raw text is not valid JSON."""


class StructuredOutputNonObjectJsonError(StructuredOutputError):
    """Raised when JSON is valid but the top-level value is not an object."""


class StructuredOutputSchemaMismatchError(StructuredOutputError):
    """Raised when parsed JSON does not satisfy the declared schema."""


@dataclass(frozen=True)
class StructuredOutputFailureDetails:
    reason: str
    error_type: str
    error_code: str = STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE
    failure_kind: str = STRUCTURED_OUTPUT_VALIDATION_FAILURE_KIND
    safe_message: str = STRUCTURED_OUTPUT_VALIDATION_SAFE_MESSAGE


class StructuredOutputValidationError(PlatformError):
    """User-safe structured output validation failure."""

    def __init__(
        self,
        *,
        reason: str,
        error_type: str,
        message: str = STRUCTURED_OUTPUT_VALIDATION_SAFE_MESSAGE,
    ) -> None:
        super().__init__(STRUCTURED_OUTPUT_VALIDATION_ERROR_CODE, message)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "error_type", error_type)
        object.__setattr__(
            self,
            "failure_kind",
            STRUCTURED_OUTPUT_VALIDATION_FAILURE_KIND,
        )

    @property
    def details(self) -> StructuredOutputFailureDetails:
        return StructuredOutputFailureDetails(
            reason=self.reason,
            error_type=self.error_type,
        )


def to_safe_validation_error(
    error: StructuredOutputError,
) -> StructuredOutputValidationError:
    if isinstance(error, StructuredOutputMalformedJsonError):
        return StructuredOutputValidationError(
            reason="malformed_json",
            error_type=type(error).__name__,
        )
    if isinstance(error, StructuredOutputNonObjectJsonError):
        return StructuredOutputValidationError(
            reason="non_object_json",
            error_type=type(error).__name__,
        )
    if isinstance(error, StructuredOutputSchemaMismatchError):
        return StructuredOutputValidationError(
            reason="schema_mismatch",
            error_type=type(error).__name__,
        )
    return StructuredOutputValidationError(
        reason="validation_failed",
        error_type=type(error).__name__,
    )
