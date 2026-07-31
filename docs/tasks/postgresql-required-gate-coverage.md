# Task: PostgreSQL Required-Gate Coverage

## Problem

`quick-check` and `full-check` exclude `slow` tests, while the required PostgreSQL backend job
previously selected only 56 of 257 `postgresql`-marked tests through file and node-ID lists. That
left 201 production-semantics tests outside every required pytest gate.

## Implementation

- Added canonical `python scripts/agent/runner.py postgresql-check` execution.
- Made that command fail with `PGTEST001` when the PostgreSQL maintenance URL is absent, preventing
  fixture-level skips from reporting a false-green gate.
- Selected `-m "postgresql"` across platform core/actions, platform API, and platform worker roots.
- Replaced both hand-picked PostgreSQL workflow steps with that single marker-driven command.
- Added fast runner/workflow contract tests so the marker, roots, PR trigger, required-job status,
  and maintenance URL cannot drift silently.
- Replaced handoff tests' `atexit` database retention with per-test fixture cleanup.
- Updated four stale quota-service tests to use the required validate-then-consume contract.

## PostgreSQL suites covered

The required job now executes runtime storage/migrations, action/workflow/scenario runners,
structured output, artifacts/events/providers, quota and handoff services/concurrency/recovery,
identity/quota/scenario/handoff APIs, migration CLI cases, structured LLM execution, and worker
claim/execution/cancellation/recovery tests.

## Validation

- PostgreSQL collection: 257 tests across 17 files.
- Exact required command: 257 passed in 12m20s on local PostgreSQL 18.
- Handoff fixture lifecycle: 44 passed; zero leaked databases.
- Quota-service contract: 6 passed.
- Maintenance database after the full gate: zero non-template test databases.
- Fast runner/workflow guard tests: passed.
- `quick-check`: 211 passed, 257 intentionally deselected.
- `full-check`: passed in 6m02s, including frontend checks and the 2-test product suite.
- Workflow YAML parsed and its required-job contract passed in `tests/test_runner.py` (`actionlint`
  was unavailable locally).
