# Execution Plan: A11 Job Lifecycle And Worker Review Remediation

## Status

- State: completed
- Owner: agent
- Created: 2026-07-11
- Last updated: 2026-07-11

## Goal

Close the verified A11 review gaps so the DB-backed worker is runnable, job lifecycle state and
events are transactionally consistent, every failed job has complete safe terminal fields, and a
production-composed worker path is covered end to end.

## Scope

### In scope

- A runnable worker composition root and DB-backed polling entrypoint.
- Atomic `created -> running` plus `workflow.started` persistence.
- Complete failed-job terminal fields on runner and handler failure paths.
- A durable cancellation lifecycle event and taxonomy/documentation support.
- Production-composed worker integration coverage through workflow, action, provider, artifact,
  event, and job storage.
- A11 status, architecture documentation, handoff report, and short task document.

### Out of scope

- Celery, Temporal, external queue infrastructure, leases, distributed locks, parallel workflow
  execution, or running-job interruption.
- Database schema changes.
- Scenario-start API work assigned to A12.

## Relevant docs

- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/architecture/job-lifecycle.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/llm-runtime.md`
- `docs/exec-plans/completed/a11-job-lifecycle-and-worker-integration.md`

## Contracts touched

- API: none.
- DB: existing `platform.jobs` and `platform.event_log` rows; no migration.
- Config: add the cancellation event to the platform event taxonomy.
- Events: `workflow.started` becomes claim-transaction-owned; add `workflow.canceled`.
- Worker: compose DB, registry, provider gateway, structured executor, action runner, workflow
  runner, and a minimal DB polling loop.

## Implementation steps

- [x] Read required and A11-specific architecture/product documentation.
- [x] Inspect the affected worker/runtime/storage/event/test/infra integration surface.
- [x] Verify each review finding against the current branch.
- [x] Make claim/start and cancel/event transitions atomic.
- [x] Enforce complete safe failed-job terminal fields.
- [x] Implement the runnable production worker composition and polling entrypoint.
- [x] Add production-composed integration and lifecycle regression tests.
- [x] Update taxonomy, generated docs, A11 status, handoff report, and task document.
- [x] Run targeted tests and canonical baseline checks.

## Validation

- [x] Worker tests.
- [x] Workflow, runtime-storage, and event-log tests.
- [x] Config validation.
- [x] Architecture validation.
- [x] Canonical quick-check target list (ACL-safe `--basetemp`).

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-11 | Emit `workflow.started` in the same caller-owned transaction as the conditional job claim. | This prevents durable `running` jobs without their start event while preserving idempotent conditional claim semantics. |
| 2026-07-11 | Add `workflow.canceled` rather than document an exception. | Cancellation is an important terminal runtime transition and the event log is a core contract. |
| 2026-07-11 | Use minimal DB polling over created job IDs for the worker entrypoint. | It makes the existing container/application runnable without adding an external queue or scaling subsystem; conditional claims remain the concurrency primitive. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-11 | Verified all six review findings against the uncommitted A11 branch state. `just doctor` is unavailable because `just` is missing; direct doctor reports the system Python lacks repo modules, while `uv run` initially hit the host UV cache ACL. | Implement lifecycle and worker composition fixes, then validate with workspace-owned temp/cache paths. |
| 2026-07-11 | Implemented atomic lifecycle events, complete safe failure fields, the production worker graph/poller/container entrypoint, cancellation taxonomy, and end-to-end production-composed coverage. | Run broad and canonical validation. |
| 2026-07-11 | Focused 61-test and broad 159-test suites passed; config/architecture/lint/lock/compose checks passed; exact canonical quick-check targets passed 202 tests with an ACL-safe base temp. | Completed. |
| 2026-07-11 | Docker image build could not start because the local Docker daemon was not running; Compose rendering and the locked project/entrypoint checks passed. | Record as an environment-only validation limitation. |

## Open questions

- None.

## Follow-up debt

- A12 remains responsible for scenario-start API creation of session-owned input and jobs.
