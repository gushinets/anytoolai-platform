# Task: Worker Cancellation Recovery

## Brief task description

Prevent a claimed worker job from remaining `running` when execution is cancelled during shutdown.

## Implementation summary

Added a `running -> canceled` repository/service transition and `workflow.canceled` event for
post-claim task cancellation. The worker persists that terminal state, then re-raises
`asyncio.CancelledError`; ordinary exception failure handling is unchanged.
