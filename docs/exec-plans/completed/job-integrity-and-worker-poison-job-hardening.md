# Execution Plan: Job Integrity And Worker Poison-Job Hardening

## Status

- State: completed
- Owner: agent
- Created: 2026-07-13
- Last updated: 2026-07-13

## Goal

Ensure invalid or orphaned jobs cannot block the worker forever, and enforce critical successful terminal-state invariants for jobs at the repository/runtime boundary.

## Scope

### In scope

- Inspect schema integrity around `jobs.scenario_session_id`
- Inspect worker claim/load/error flow for poison-job behavior
- Inspect job repository lifecycle APIs and success-path invariants
- Implement the smallest coherent fix set that preserves current worker and storage contracts
- Update targeted tests for worker poison jobs and job success invariants

### Out of scope

- New queue semantics or distributed workflow engines
- Product-specific changes
- Broad storage-layer redesign beyond the critical lifecycle integrity gap

## Relevant docs

- `docs/architecture/job-lifecycle.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/event-taxonomy.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none expected
- DB: runtime job/scenario integrity, possibly migration-level constraints
- Config: none expected
- Events: workflow failed/canceled poison-job handling where applicable
- Frontend: none

## Implementation steps

- [x] Verify the review findings against current schema, repositories, worker code, and tests
- [x] Implement integrity and poison-job safeguards with repository-enforced success invariants
- [x] Update targeted tests and run focused validation plus baseline checks

## Validation

- [x] targeted runtime storage / worker / workflow pytest suites
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-13 | Treat schema integrity, worker poison-job handling, and success invariants as one patch set | The findings cross storage, lifecycle methods, and worker liveness rather than a single module |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-13 | Re-read worker/runtime architecture docs and traced the likely code surfaces | Verify the findings against current implementation and tests before deciding the fix shape |
| 2026-07-13 | Verified both findings on the branch, hardened repository and worker behavior, and updated rollback/success-path tests | Baseline validation and handoff |

## Open questions

- None remaining for this patch set

## Follow-up debt

- Consider a future migration path for database-level composite integrity if the team wants the schema itself to enforce the same scoped scenario-session linkage already enforced by the repository/runtime layer
