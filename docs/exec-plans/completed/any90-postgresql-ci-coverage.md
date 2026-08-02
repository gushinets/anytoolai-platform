# Execution Plan: ANY-90 PostgreSQL CI Coverage

## Status

- State: completed
- Owner: Codex
- Created: 2026-07-31
- Last updated: 2026-07-31
- Review date: 2026-07-31
- Next action: hand off the validated CI coverage change for review.
- Blocker: none.

## Goal

Make pull-request CI execute the PostgreSQL-backed acceptance tests that prove `artifact.created`
retains applicable runtime correlation dimensions for action, final workflow-result, debug/failed,
and rollback-recovered artifacts without exposing sensitive or oversized payloads.

## Scope

### In scope

- PostgreSQL GitHub Actions coverage for the artifact, structured-output, workflow-runner, and
  relevant action/worker runtime tests
- `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` wiring for that suite
- Targeted acceptance-test additions only if the requested dimensions or redaction behavior are not
  already asserted
- Required-job and pull-request trigger verification

### Out of scope

- Reclassifying existing `slow` / `postgresql` tests unless the baseline is proven safe
- Weakening, skipping, or removing assertions
- Unrelated quota, handoff, migration, logging, or test-harness refactors
- Splitting historical PR #42 changes that are not present as uncommitted work in this checkout

## Relevant docs

- `docs/architecture/event-taxonomy.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/llm-runtime.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none expected
- DB: PostgreSQL-backed test execution only; no schema change expected
- Config: GitHub Actions PostgreSQL service and test database URL
- Events: `artifact.created` correlation and safe bounded properties
- Frontend: none

## Implementation steps

- [x] Inspect current workflow jobs, markers, and selected test paths.
- [x] Map existing assertions to every requested correlation and redaction acceptance criterion.
- [x] Add the smallest required PostgreSQL CI job or extend the appropriate required job.
- [x] Add only missing acceptance assertions/tests.
- [x] Run targeted PostgreSQL tests and repository validation.

## Validation

- [x] `python scripts/agent/runner.py doctor` (known system-Python dependency failure; validation
  continues through the repository-managed `uv` environment)
- [x] Targeted artifact-correlation PostgreSQL suite (`50 passed`)
- [x] All dedicated PostgreSQL CI commands (artifact suite `50 passed`; quota suite `6 passed`)
- [x] `python scripts/agent/runner.py quick-check` (`209 passed`, `257 deselected`)
- [x] `python scripts/agent/runner.py full-check` (`209 passed`, `257 deselected`; frontend
  install/typecheck/build passed; freelancer suite `2 passed`)
- [x] `python scripts/agent/runner.py validate-architecture`
- [x] `python scripts/agent/runner.py validate-docs`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-31 | Keep this follow-up limited to CI coverage and demonstrably missing assertions. | The requested risk is an unexecuted acceptance suite; unrelated cleanup would increase merge risk. |
| 2026-07-31 | Extend `postgresql-quota-concurrency` instead of adding a new job. | This preserves the existing status-check identity while making the already-required PostgreSQL path prove artifact correlation. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-31 | Read the repository contracts and created the task plan. | Run doctor, inspect workflows and tests, then implement the CI coverage. |
| 2026-07-31 | Extended PostgreSQL CI across artifact, action, workflow, and worker paths; made rollback lineage and non-copy assertions explicit. | Run targeted collection/tests and the full validation ladder. |
| 2026-07-31 | The artifact PostgreSQL suite passed 50 tests, quota PostgreSQL passed 6, quick-check passed, and full-check passed end to end. | Complete final diff review and hand off. |

## Open questions

- None. The existing suite contained the runtime assertions; this follow-up added CI selection and
  made rollback provider-lineage and non-copy assertions explicit.

## Follow-up debt

- Split unrelated historical PR #42 changes into separate PRs where practical; this task will not
  manufacture a history rewrite without explicit authorization.
