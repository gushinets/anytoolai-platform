# Execution Plan: A10 Step-Started Replay Signal

## Status

- State: active
- Owner: Codex
- Created: 2026-07-20
- Last updated: 2026-07-20
- Review date: 2026-07-20
- Next action: none; implementation and focused validation are complete.
- Blocker: `python scripts/agent/runner.py quick-check` reaches pytest but is blocked by the known Windows `.quick-check-tmp/pytest` PermissionError on this machine.

## Goal

Preserve normal workflow step-start semantics during escaped rollback recovery by replaying
`workflow.step_started` only when the failed step actually reached that transition.

## Scope

### In scope

- The explicit `started_event_emitted` recovery signal for failed workflow steps
- Regression coverage for condition failures before step start and mapping/action failures after step start
- Workflow recovery documentation for step-start replay semantics

### Out of scope

- Expression language changes
- Durable workflow-engine behavior
- Database migrations
- Broad workflow-state or recovery redesign

## Relevant Docs

- `docs/architecture/workflow-model.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/runtime-storage.md`

## Implementation Steps

- [x] Research normal step-start, `when`, input mapping, action failure, and rollback-recovery paths.
- [x] Add focused caught-path and escaped-rollback regression coverage.
- [x] Update workflow recovery docs to describe conditional `workflow.step_started` replay.
- [x] Run targeted workflow tests and appropriate repo checks.

## Validation

- [x] `$env:TEMP='D:\Devpy\anytoolai-platform\.tmp'; $env:TMP=$env:TEMP; uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [x] `$env:TEMP='D:\Devpy\anytoolai-platform\.tmp'; $env:TMP=$env:TEMP; uv run python -m pytest packages/backend/platform-core/tests -q`
- [ ] `$env:TEMP='D:\Devpy\anytoolai-platform\.tmp'; $env:TMP=$env:TEMP; python scripts/agent/runner.py quick-check`

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-07-20 | Confirmed the runner already carries `started_event_emitted` and gates recovery replay on it. | Add missing regression coverage and update stale docs wording. |
| 2026-07-20 | Added caught condition-failure and escaped input-mapping-failure tests, updated workflow recovery docs, and passed workflow/core tests. | None; quick-check is blocked by the known local pytest temp-root ACL issue after docs/config/architecture/generated-doc phases pass. |
