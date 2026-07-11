# Execution Plan: A11 Job Lifecycle And Worker Integration

## Status

- State: completed
- Owner: agent
- Created: 2026-07-11
- Last updated: 2026-07-11

The initial completion assessment was reopened by review because the production entrypoint,
claim/start atomicity, failed timestamps, cancellation event, and production-composed integration
coverage were incomplete. Those gaps were remediated under
`a11-job-lifecycle-worker-review-remediation.md` before this plan was considered complete again.

## Goal

Connect the DB-backed job lifecycle to the worker and the A10 sequential workflow runner while
preserving scenario-session, action, artifact, event, and provider-call correlation.

## Scope

### In scope

- Atomic `created` job claiming and terminal transitions.
- Claimed-job workflow execution through the existing sequential runner.
- Scenario-session input loading from `metadata["input"]`.
- Safe failure persistence and worker integration coverage.
- Runtime and worker documentation.

### Out of scope

- Queue engines, leases, distributed locks, Celery, Temporal, and scaling mechanics.
- Interrupting already-running workflows.
- New database migrations.

## Relevant docs

- `docs/architecture/runtime-storage.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/scenario-session-model.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/structured-output.md`
- `docs/exec-plans/active/a10-sequential-workflow-runner.md`

## Contracts touched

- DB: existing `platform.jobs` lifecycle fields and status values.
- Runtime: `JobRepository`, `SequentialWorkflowRunner`, worker handler.
- Events: existing workflow lifecycle events with durable job/session dimensions.
- Scenario input: `scenario_session.metadata["input"]` is the worker input mapping.

## Implementation steps

- [x] Add atomic repository claim and terminal lifecycle operations.
- [x] Add claimed-job runner execution and safe failure classification.
- [x] Implement worker handler and façade.
- [x] Add storage, runner, and worker integration tests.
- [x] Update architecture and execution documentation.
- [x] Run focused tests and canonical checks.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-11 | Worker input is loaded from linked scenario-session metadata under `input`. | The task explicitly keeps workflow input session-owned; the existing job row has no input payload contract. |
| 2026-07-11 | Claims and `workflow.started` commit together before workflow execution. | An execution rollback must not return a claimed job to `created`, and event failure must not leave a running job without its lifecycle event. |
| 2026-07-11 | Cancellation is limited to `created -> canceled` and emits `workflow.canceled` atomically. | This provides a durable terminal path without interrupting running work or adding queue semantics. |
| 2026-07-11 | The production worker polls PostgreSQL for created job ids. | This makes the application/container runnable while leaving the conditional claim as the idempotent coordination primitive and avoiding external queue infrastructure. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-11 | Reviewed A10 runner, runtime storage, recovery callbacks, worker placeholders, and correlation contracts. | Implement repository lifecycle operations. |
| 2026-07-11 | Implemented atomic claims, guarded terminal transitions, claimed-job runner execution, session-owned input loading, safe worker failure handling, cancellation, integration tests, and runtime documentation. | Completed. |
| 2026-07-11 | Review found the worker entrypoint and several lifecycle/event contracts incomplete; reopened A11 and implemented the remediation plan. | Revalidate production composition and canonical checks. |
| 2026-07-11 | Added the real worker composition/polling path, atomic lifecycle events, complete safe failure fields, cancellation taxonomy, and production-composed end-to-end coverage. | Completed after remediation. |

## Validation results

- Passed: focused worker/workflow/storage/event suite (61 tests).
- Passed: worker + platform-core + platform-actions suite (159 tests).
- Passed: config validation and architecture validation.
- Passed: worker lint and worker dependency lock check.
- Passed: canonical quick-check config and architecture phases.
- Canonical quick-check pytest invocation remains environment-blocked by stale ACLs on
  `.quick-check-tmp/pytest/pytest-of-jackd`; the same targets are validated with a workspace-owned
  `--basetemp` (202 tests passed).

## Open questions

- None.

## Follow-up debt

- Scenario-start API creation of session-owned input and jobs remains part of A12.
