# Task: Workflow Started Scenario Correlation

## Brief task description

Ensure a worker-owned job persists scenario identity before emitting its first `workflow.started`
event, so lifecycle events have consistent correlation dimensions from the start.

## Implementation summary

The worker now loads the scenario before its conditional job claim and writes guest, user, and
scenario-chain identity into claimed-job metadata atomically with `workflow.started`. Provider event
context now preserves guest and user fields already present in the provider request metadata.
