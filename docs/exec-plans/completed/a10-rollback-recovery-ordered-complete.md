# Execution Plan: A10 Ordered And Complete Rollback Recovery

## Status

- State: completed
- Owner: agent
- Created: 2026-07-17
- Last updated: 2026-07-17
- Review date: 2026-07-17
- Last run: 2026-07-17
- Next action: none; implementation, docs, and validation are complete.
- Blocker: none

## Goal

Make escaped rollback recovery causally ordered and complete so durable workflow, action,
provider, artifact, and event-log history stays aligned with persisted runtime state.

## Scope

### In scope

- Shared rollback-recovery orchestration in `storage.transactions`
- Workflow/action/provider/artifact rollback recovery contracts
- Event-log timestamp replay and duplicate detection
- Ordered workflow-level event backfill for escaped workflow failures
- Core and worker regression coverage for later-step provider failures
- Architecture/runtime docs describing the new recovery contract

### Out of scope

- New runtime tables or migrations
- Durable workflow-engine features
- Queue leases, replay workers, or product-surface changes

## Relevant docs

- `ARCHITECTURE.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/job-lifecycle.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/runtime-storage.md`

## Contracts touched

- Runtime: rollback recovery registration/execution and event replay ordering
- Events: replay timestamps and missing-event backfill
- Tests: exact durable event order for escaped later-step failures
- Docs: workflow/action/provider/job/event/runtime storage recovery contract

## Implementation steps

- [x] Introduce typed rollback-recovery phases and coordinated execution.
- [x] Split row recovery from event recovery across workflow/action/provider/artifact layers.
- [x] Add workflow-owned ordered event backfill with idempotent event existence checks.
- [x] Extend event emitter/repository support for replay timestamps and event existence lookups.
- [x] Add regression and idempotence tests, then update docs and validate.

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_artifact_service.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py -q`
- [x] `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -q`
- [x] `python scripts/agent/runner.py quick-check`

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-17 | Reviewed A10/A11 branch history, later recovery follow-ups, current runtime/docs/tests, and wrote the implementation plan. | Patch rollback orchestration and event replay together so ordering and completeness change coherently. |
| 2026-07-17 | Implemented phased rollback recovery, workflow-owned ordered event backfill, explicit replay timestamps, provider failure-event completion, and core/worker regression coverage. | Finish doc updates, run the remaining targeted suites, and validate with quick-check. |
| 2026-07-17 | Updated architecture docs, fixed execution-plan metadata for doc validation, and passed focused suites plus repo quick-check. | None. |
