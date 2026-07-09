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


class WorkflowConditionEvaluationError(WorkflowExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__("workflow_condition_evaluation_failed", message)


class WorkflowOutputValidationError(WorkflowExecutionError):
    def __init__(self, message: str = "Workflow output validation failed.") -> None:
        super().__init__("workflow_output_validation_failed", message)
