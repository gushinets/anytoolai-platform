# Execution Plan: Action Runner Workflow Version Validation

## Status

- State: completed
- Owner: agent
- Created: 2026-07-07
- Last updated: 2026-07-07

## Goal

Ensure `ActionRunner` never creates an action run or emits action lifecycle events without a
validated `workflow_version`.

## Scope

### In scope

- Validate `ExecutionContext.workflow_version` before `ActionRunService.start()`.
- Persist only the validated `workflow_version` in `ActionRunRecord.metadata`.
- Cover missing-workflow-version and early-input-validation paths in action-runner tests.
- Run the requested backend test suites and quick-check.

### Out of scope

- Changing event contracts to make `workflow_version` optional.
- Refactoring `ActionRunService` or event-emission architecture beyond this validation fix.
- Product-specific logic, endpoint changes, or unrelated cleanup.

## Relevant docs

- `AGENTS.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/event-taxonomy.md`
- `docs/core-beliefs.md`

## Contracts touched

- Runtime: `ActionRunner` validation and `ActionRunRecord.metadata.workflow_version`
- Events: `action.started` and `action.failed` required `workflow_version` dimension
- Tests: action-runner validation and lifecycle event coverage

## Implementation steps

- [x] Inspect runner flow, current validation order, and affected tests.
- [x] Move or reuse `workflow_version` validation before action-run creation/event emission.
- [x] Add tests for missing workflow version and early failure behavior.
- [x] Run requested validation commands and record outcomes.

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests -q`
- [x] `python -m pytest packages/backend/platform-actions/tests -q`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-07 | Reuse the existing `_require_workflow_version()` helper and move its result earlier in `ActionRunner.run()`. | This is the smallest fix that closes the gap before action-run creation without changing the event contract or adding duplicate validation rules. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-07 | Confirmed `ActionRunner` currently stores nullable `context.workflow_version` in action-run metadata before calling `_require_workflow_version()`, so `action.started` can be emitted with a missing required dimension. | Validate earlier in the runner and extend the action-runner tests around missing and early-failure paths. |
| 2026-07-07 | Moved workflow-version validation ahead of action-run creation, reused the validated value for action-run metadata and executor requests, and added tests proving missing workflow version fails before any action row/event is created while early input-validation failures still carry workflow version on both action events. | No further work for this fix. |

## Open questions

- None currently.

## Follow-up debt

- None currently.
