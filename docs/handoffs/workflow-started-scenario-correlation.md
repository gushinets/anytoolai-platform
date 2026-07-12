# Handoff: Workflow Started Scenario Correlation

## Status

Implementation complete; focused and baseline suites pass.

## Root cause

`RunWorkflowHandler._claim()` emitted `workflow.started` immediately after a plain job claim.
Scenario data was loaded only in the subsequent execution transaction, leaving the first event
without `guest_id`, `user_id`, and `scenario_chain_id` when the queued job metadata was empty.

## Implemented changes

- The worker loads the scenario before claiming a created job.
- The conditional job claim accepts metadata and atomically persists scenario identity before the
  `workflow.started` event is emitted.
- `WorkflowJobService.claim_created()` forwards that metadata while preserving existing callers.
- Provider event context now reads `guest_id` and `user_id` from existing request metadata, matching
  action/workflow event correlation.
- Worker tests cover successful and invalid-input failure flows; both assert first-event identity.

## Transaction and recovery behavior

The conditional job update and `workflow.started` event stay in the same transaction. If event
persistence fails, the claim and scenario metadata update roll back together. Existing recovery uses
persisted job metadata, so rebuilt workflow events retain the same dimensions.

## Validation

- Worker boot + workflow runner + event-log focused suites: 34 passed.
- Platform-core tests: 146 passed.
- Worker tests: 7 passed.
- `python scripts/agent/quick_check.py`: 204 passed.
- `python scripts/agent/runner.py quick-check`: 204 passed.
