from __future__ import annotations

from anytoolai_platform_core.common.errors import PlatformError
from anytoolai_platform_core.scenarios.checkpoints import ScenarioCheckpointState


class ScenarioCheckpointConflictError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "scenario_checkpoint_conflict",
            "Scenario checkpoint no longer matches the requested action.",
        )


class ScenarioCheckpointNotActionableError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "scenario_checkpoint_not_actionable",
            "Scenario checkpoint does not allow next actions.",
        )


class ScenarioNextActionNotAllowedError(PlatformError):
    def __init__(self) -> None:
        super().__init__(
            "scenario_next_action_not_allowed",
            "Next action is not allowed for the current checkpoint.",
        )


def validate_next_action(
    *,
    expected_checkpoint_id: str,
    current_checkpoint: ScenarioCheckpointState,
    next_action_id: str,
) -> None:
    if expected_checkpoint_id != current_checkpoint.checkpoint_id:
        raise ScenarioCheckpointConflictError()
    if not current_checkpoint.actionable:
        raise ScenarioCheckpointNotActionableError()
    if next_action_id not in current_checkpoint.allowed_next_actions:
        raise ScenarioNextActionNotAllowedError()
