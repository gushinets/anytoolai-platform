# Execution Plan: A10 Sequential Workflow Runner

## Status

- State: complete
- Owner: agent
- Created: 2026-07-09
- Last updated: 2026-07-10

## Goal

Implement config-defined sequential workflow execution in `platform-core` with explicit mapping,
conditional skip, workflow-owned retry, final artifact creation, and workflow step events while
preserving MVP-A architecture boundaries and existing simple YAML compatibility.

## Scope

### In scope

- Extend workflow step contracts with optional `retry_count`
- Validate workflow mapping and condition config shape
- Implement sequential workflow execution from config
- Persist workflow/job state, skipped steps, final artifacts, and workflow lifecycle events
- Update kernel demo workflow examples, workflow docs, and focused tests

### Out of scope

- Parallel branches
- Nested workflows or subworkflows
- Durable workflow engine behavior
- Webhooks or external step types
- Product-specific runtime semantics

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/config-model.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/action-model.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/structured-output.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- API: none directly
- DB: no migration planned; use existing `jobs`, `action_runs`, `artifacts`, `event_log`
- Config: workflow step schema and kernel demo workflow examples
- Events: add workflow-step lifecycle events
- Frontend: none directly

## Implementation steps

- [x] Add the workflow contract, loader validation, and mapping helpers
- [x] Implement the sequential workflow runner, skip/retry semantics, and final artifact handling
- [x] Update docs/config examples, add tests, and run requested validation
- [x] Repair escaped-rollback recovery so failed workflow state and workflow lifecycle events stay internally consistent after late multi-step failures
- [x] Preserve cross-scenario workflow correlation dimensions through job-context reconstruction and rollback recovery

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests -q`
- [x] `python -m pytest packages/backend/platform-actions/tests -q`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [ ] `python scripts/agent/quick_check.py` blocked by stale Windows ACL ownership on `.quick-check-tmp\pytest\pytest-of-jackd`
- [ ] `python scripts/agent/runner.py quick-check` blocked by the same quick-check temp-directory ACL issue

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-09 | Keep step state inside existing `jobs.metadata` and per-attempt `action_runs` rows instead of adding a workflow-step table | The task is MVP-A simple, and runtime storage already provides durable job/action/artifact/event surfaces without requiring a migration |
| 2026-07-09 | Treat `retry_count` as workflow-runner-owned retries around `ActionRunner.run()` only | This preserves the documented split between workflow retry, provider transport retry, PydanticAI validation retry, and gateway hard caps |
| 2026-07-09 | Add explicit workflow-step events instead of overloading action events for skips | The user requested step lifecycle events, while action events should remain tied to real action executions only |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-09 | Read the required architecture and runtime docs, inspected workflow/action/runtime/event/artifact/config code, and confirmed the current workflow runner is still a skeleton | Patch contracts and loader validation first so runtime code has an explicit contract to implement |
| 2026-07-09 | Implemented the sequential runner, contract validation, workflow-step events, workflow docs/examples, and focused/full backend tests | Capture final validation results and document the environment-specific quick-check blocker |
| 2026-07-09 | Added rollback-recovery persistence for failed workflow jobs and workflow.failed events when exceptions escape the transaction boundary | Re-run focused/full backend validation and confirm the quick-check blocker is still environment-specific |
| 2026-07-10 | Investigating escaped multi-step rollback recovery because recovered failed jobs can still reference rolled-back successful steps, artifacts, and missing workflow events | Sanitize or rebuild recovered workflow state/events from only the rows that actually survive rollback, then add a regression test |
| 2026-07-10 | Rebuilt escaped multi-step rollback recovery around only post-rollback durable rows, replayed workflow.started/step_started/step_failed/workflow.failed, and added a regression test for sanitized failed workflow state | Keep the active plan complete unless a later workflow slice revisits provider-event recovery or the external quick-check ACL blocker |
| 2026-07-10 | Following up on missing `scenario_chain_id`, `handoff_id`, and `acquisition_source` in workflow job-context reconstruction and recovery | Persist the dimensions in job metadata, reconstruct them through `_context_from_record()`, and add event assertions for normal and rollback paths |
| 2026-07-10 | Preserved workflow correlation dimensions through workflow, action, and provider event paths by threading them through job metadata, action metadata, and provider request context | Keep the plan complete; the only remaining validation blocker is the external quick-check temp-directory ACL issue |

## Open questions

- None currently

## Follow-up debt

- If scenario/job APIs need to invoke the new workflow runner directly, wire that in a separate slice once the worker/job lifecycle task lands.
