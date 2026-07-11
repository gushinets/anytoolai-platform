# A11 Job Lifecycle And Worker Review Remediation Handoff

## Outcome

A11 now has a runnable DB-backed worker composition and polling loop. Job claim/start and
cancel/event persistence are atomic, failed-job fields are complete and safe, and production-like
integration coverage reaches the real workflow runner, action runner, provider gateway, artifact
service, event log, and repositories.

## Review finding disposition

| Finding | Verified state | Resolution |
|---|---|---|
| Production worker was not runnable | Valid: `main.py` only printed a message and the worker container had no runtime install/DB environment. | Added production composition, DB polling, environment settings, console entrypoint, locked worker dependencies, and runnable container/compose wiring. |
| Claim and `workflow.started` were not atomic | Valid: repository claim committed before runner-side event emission. | `WorkflowJobService.claim_created` conditionally claims and emits inside one transaction; the claimed runner no longer emits a second start event. |
| Handler failures lacked `completed_at` | Valid. | Handler, service, and repository failure paths now guarantee `completed_at`, `error_code`, and `error_message_safe`. |
| Cancel had no event | Valid. | Added `workflow.canceled` to the taxonomy/generated catalog and persist it in the cancel transaction. |
| Integration was facade-only | Valid. | Added a production-composed worker test covering job/session/action/provider/artifact/event correlation and final result linkage. |
| A11 completion was overstated | Valid. | Added a remediation execution plan and corrected the original A11 plan with the review gap and final remediation evidence. |

## Runtime contracts preserved

- Every job remains linked to `scenario_session_id`.
- Conditional `created -> running` claim remains idempotent.
- Success persists `completed_at` and `result_artifact_id`.
- Failure persists safe terminal fields and `workflow.failed`; raw provider output is not copied into
  job errors.
- Job/session ids propagate to action runs, provider calls, artifacts, and events.
- Cancellation remains pre-claim only; running workflows are not interrupted.
- No new database tables, migrations, external queues, leases, Celery, Temporal, or distributed
  locks were introduced.

## Validation

- Focused worker/workflow/storage/event tests: 61 passed.
- Worker + platform-core + platform-actions tests: 159 passed.
- Provider-boundary architecture regression plus worker tests: 9 passed.
- Config validation: passed.
- Architecture validation: passed.
- Worker Ruff checks: passed.
- Worker dependency lock check: passed.
- Canonical quick-check config and architecture phases: passed.
- Canonical quick-check pytest phase: environment-blocked by stale ACLs at
  `.quick-check-tmp/pytest/pytest-of-jackd`; the exact target list passed (202 tests) in the same
  quick-check environment with a workspace-owned `--basetemp`.
- Docker Compose configuration rendering: passed.
- Docker image build: environment-blocked because the local Docker daemon is not running
  (`//./pipe/docker_engine` is absent); no Dockerfile build assertion ran.

## Operational entrypoint

The worker resolves `ANYTOOLAI_DATABASE_URL`, then `DATABASE_URL`, polls the existing jobs table for
the oldest created job id, and relies on the conditional claim for coordination. LiteLLM router
construction is lazy, so fake-provider kernel work does not require production provider credentials
at worker boot.

## Follow-up

A12 still owns scenario-start API creation of scenario-session input and initial jobs. Running-job
interruption, leases, external queues, and queue scaling remain explicitly outside A11.
