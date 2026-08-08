from __future__ import annotations

from anytoolai_platform_core.common.errors import PlatformError


class WorkflowExecutionError(PlatformError):
    """Base user-safe workflow execution error."""


class WorkflowStepContractValidationError(PlatformError):
    def __init__(self, message: str) -> None:
        super().__init__("workflow_step_contract_invalid", message)


class WorkflowInputValidationError(WorkflowExecutionError):
    def __init__(self, message: str = "Workflow input validation failed.") -> None:
        super().__init__("workflow_input_validation_failed", message)


class WorkflowMappingResolutionError(WorkflowExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__("workflow_mapping_resolution_failed", message)


class WorkflowSourcePathAbsentError(WorkflowMappingResolutionError):
    """Raised only when a path segment key is genuinely missing from its parent mapping --
    as opposed to an intermediate value existing with an incompatible (non-mapping) shape.
    Only this specific case is tolerated by optional (`?`) input_mapping sources; malformed
    intermediate data must still fail loudly even when the target is optional."""


class WorkflowConditionEvaluationError(WorkflowExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__("workflow_condition_evaluation_failed", message)


class WorkflowOutputValidationError(WorkflowExecutionError):
    def __init__(self, message: str = "Workflow output validation failed.") -> None:
        super().__init__("workflow_output_validation_failed", message)
