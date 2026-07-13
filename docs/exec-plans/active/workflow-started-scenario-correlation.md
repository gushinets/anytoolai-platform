# Execution Plan: Workflow Started Scenario Correlation

## Status

- State: completed
- Owner: agent
- Created: 2026-07-12
- Last updated: 2026-07-12

## Goal

The first `workflow.started` event for a worker-owned job contains the same applicable scenario
identity and correlation dimensions as later workflow, action, and provider events.

## Scope

### In scope

- Worker claim-time scenario lookup and job metadata enrichment.
- Atomic job claim/start-event persistence.
- Worker correlation and rollback regression tests.

### Out of scope

- New event dimensions or taxonomy changes.
- Workflow runner architecture changes.
- Scenario schema changes.

## Relevant docs

- `docs/architecture/event-taxonomy.md`
- `docs/architecture/job-lifecycle.md`
- `docs/architecture/runtime-storage.md`

## Implementation steps

- [x] Trace workflow claim/start, scenario load, event context, metadata, and recovery paths.
- [x] Enrich worker job metadata from the scenario before emitting `workflow.started`.
- [x] Preserve atomic claim/start rollback behavior.
- [x] Add worker regression coverage for first-event correlation and recovery.
- [x] Run focused and baseline validation.
- [x] Write task and handoff records.

## Validation

- [x] platform-core tests
- [x] worker tests
- [x] quick-check and runner quick-check

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-12 | Pass scenario-enriched metadata into the conditional worker job claim. | The claim and `workflow.started` event remain one transaction, and the event is built from a persisted job record with scenario dimensions. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-12 | Added atomic scenario metadata enrichment to worker claims and provider guest/user event context. Core and worker suites passed; direct and runner quick-check both passed all 204 checks. | None. |
