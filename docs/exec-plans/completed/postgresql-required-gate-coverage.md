# Execution Plan: PostgreSQL Required-Gate Coverage

## Status

- State: completed
- Owner: Codex
- Created: 2026-07-31
- Last updated: 2026-07-31
- Review date: 2026-07-31
- Next action: observe the expanded job duration on GitHub-hosted Ubuntu after review.
- Blocker: none.

## Goal

Ensure every PostgreSQL-marked backend, API, and worker test is automatically selected by one
required PostgreSQL CI command, while keeping DB-free baseline coverage intentional and fast.

## Scope

### In scope

- Complete marker and collection inventory across backend core/actions, API, and worker tests
- Coverage matrix for quick-check, full-check, and required PostgreSQL workflow execution
- Marker-driven PostgreSQL CI selection rooted at all relevant test directories
- A lightweight regression guard for the workflow selection contract
- Documentation and handoff/task records for the resulting coverage

### Out of scope

- Running PostgreSQL concurrency semantics against SQLite
- Removing markers merely to increase baseline selection
- Unrelated runtime, migration, quota, handoff, or worker behavior changes
- Duplicating the PostgreSQL suite across multiple required jobs

## Relevant docs

- `AGENTS.md`
- `docs/agent/codex-operating-model.md`
- `docs/agent/review-checklist.md`
- `docs/agent/harness-engineering-map.md`
- `docs/architecture/runtime-storage.md`
- `.github/workflows/backend.yml`
- `scripts/agent/quick_check.py`
- `scripts/agent/runner.py`

## Contracts touched

- API: none
- DB: test-only disposable PostgreSQL databases
- Config: required backend GitHub Actions workflow
- Events: no runtime behavior change
- Frontend: none

## Pre-edit coverage matrix

All rows use the same current marker expression: `slow and postgresql`. Every database-backed
fixture reads `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`, creates a UUID-suffixed disposable database,
applies the requested Alembic revision (normally `head`), and drops the database in `finally`.
`quick-check` and the backend phase of `full-check` exclude every row with `-m "not slow"`.

| Test file | Collected | Required environment | Current required execution | Uncovered | Baseline decision |
|---|---:|---|---|---:|---|
| `platform-core/tests/unit/test_action_runner.py` | 13 | Migrated disposable PostgreSQL | Artifact-correlation step, whole file | 0 | PostgreSQL gate is sufficient for persistence/recovery integration. |
| `platform-core/tests/unit/test_artifact_service.py` | 1 | Migrated disposable PostgreSQL | Artifact-correlation step, whole file | 0 | PostgreSQL gate is sufficient for rollback recovery. |
| `platform-core/tests/unit/test_event_log.py` | 20 | Migrated PostgreSQL plus migration revisions | None | 20 | PostgreSQL gate is required for event persistence/migration semantics. |
| `platform-core/tests/unit/test_handoffs.py` | 44 | Migrated disposable PostgreSQL | None | 44 | PostgreSQL gate is sufficient for transactional handoff behavior. |
| `platform-core/tests/unit/test_provider_gateway.py` | 19 | Migrated disposable PostgreSQL | None | 19 | PostgreSQL gate is sufficient for provider ledger/event recovery. |
| `platform-core/tests/unit/test_quota_service.py` | 6 | Migrated disposable PostgreSQL | None | 6 | PostgreSQL gate is required for quota persistence and rollback recovery. |
| `platform-core/tests/unit/test_runtime_storage.py` | 42 | PostgreSQL migration chain and repositories | None | 42 | PostgreSQL-only; SQLite cannot prove production schema/locking behavior. |
| `platform-core/tests/unit/test_scenario_runtime.py` | 31 | Migrated disposable PostgreSQL | None | 31 | PostgreSQL gate is sufficient for idempotency and transaction integration. |
| `platform-core/tests/unit/test_structured_output.py` | 6 | Migrated disposable PostgreSQL | Artifact-correlation step, whole file | 0 | PostgreSQL gate is sufficient for artifact persistence. |
| `platform-core/tests/unit/test_workflow_runner.py` | 20 | Migrated disposable PostgreSQL | Artifact-correlation step, whole file | 0 | PostgreSQL gate is sufficient for workflow persistence/recovery. |
| `platform-actions/tests/test_structured_llm_executor.py` | 8 | Migrated disposable PostgreSQL | Artifact-correlation step, whole file | 0 | PostgreSQL gate is sufficient for structured-action persistence. |
| `platform-api/tests/test_handoffs_api.py` | 5 | Migrated disposable PostgreSQL and composed worker | One node ID | 4 | PostgreSQL gate is required for API transaction/handoff recovery. |
| `platform-api/tests/test_identity_quota_api.py` | 4 | Migrated disposable PostgreSQL | None | 4 | PostgreSQL gate is sufficient for API persistence/event integration. |
| `platform-api/tests/test_migrate.py` (marked cases) | 2 | PostgreSQL maintenance DB and Alembic CLI | None | 2 | PostgreSQL-only; these cases prove real migration execution. |
| `platform-api/tests/test_quota_concurrency_postgresql.py` | 6 | Migrated PostgreSQL with concurrent clients | Quota-concurrency step, whole file | 0 | PostgreSQL-only row-lock/`ON CONFLICT` semantics. |
| `platform-api/tests/test_scenario_runtime_api.py` | 15 | Migrated disposable PostgreSQL and composed worker | One node ID | 14 | PostgreSQL gate is required for API/worker transaction integration. |
| `platform-worker/tests/test_worker_boot.py` | 15 | Migrated disposable PostgreSQL and worker composition | None | 15 | PostgreSQL gate is required for claim, cancellation, and recovery semantics. |

Pre-edit totals: **257 marked**, **56 covered**, **201 uncovered**. The required Compose smoke jobs
exercise one kernel-demo path but are not equivalent assertions for these files. No markers or
runtime behaviors are changed by this task, so no additional DB-neutral test is needed merely to
replace coverage; existing fast contract/config/unit tests remain in `quick-check`, while every
marked integration test will move under the required PostgreSQL gate.

## Implementation steps

- [x] Enumerate marked tests through source search and pytest collection.
- [x] Record a pre-edit coverage matrix and identify uncovered suites.
- [x] Replace hand-picked PostgreSQL CI nodes with coherent marker-driven root selection.
- [x] Add a regression test for the marker-driven required-job contract.
- [x] Update testing documentation and create the requested task/handoff records.
- [x] Run exact PostgreSQL, baseline, workflow, and repository validation.

## Validation

- [x] `python scripts/agent/runner.py doctor` (global Python reported the already-documented
  missing-package warning; managed runner environments were used for validation)
- [x] PostgreSQL `--collect-only` command across all required roots: 257 tests across 17 files
- [x] Exact PostgreSQL CI pytest command against a disposable PostgreSQL maintenance URL: 257 passed
  in 12m20s; zero databases leaked
- [x] `python scripts/agent/runner.py quick-check`: 211 passed, 257 intentionally deselected
- [x] `python scripts/agent/runner.py full-check`: passed in 6m02s, including frontend and product
  suites
- [x] Workflow YAML validation: parsed and contract-tested in `tests/test_runner.py`; `actionlint`
  was unavailable locally
- [x] `python scripts/agent/runner.py validate-docs` (via quick/full check)
- [x] `python scripts/agent/runner.py validate-architecture` (via quick/full check)

## Decision log

| Date | Decision | Why |
|---|---|---|

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-31 | Read the initial CI/runner guidance and created the scoped plan. | Complete the marker inventory and pre-edit matrix before changing CI. |
| 2026-07-31 | Collected 257 PostgreSQL tests across 17 files; current required PostgreSQL steps cover 56 and leave 201 uncovered. | Implement one marker-driven runner command and required workflow step. |
| 2026-07-31 | Added canonical marker-driven CI selection and fast regression guards. The first expanded run exposed four stale quota-service tests; fixed their validate-then-consume contract and replaced retained handoff DB contexts with per-test cleanup. Final PostgreSQL gate passed 257 tests in 12m20s with zero leaked databases. | Run canonical baseline/full checks and final workflow/docs validation. |
| 2026-07-31 | Quick-check and full-check passed; workflow contract/YAML parsing, docs, generated docs, architecture, frontend, and product checks all passed. The isolated PostgreSQL cluster was stopped and its disposable data removed. | Plan complete; observe CI runtime after review. |
| 2026-07-31 | Added `PGTEST001` fail-fast guard so an unset PostgreSQL URL cannot silently skip the canonical gate; focused runner tests passed. | Plan complete. |

## Open questions

- None: collection and source search found no `slow`-only or `postgresql`-only tests, and every
  PostgreSQL marker is under the four requested backend/API/worker roots.

## Follow-up debt

- Measure the expanded job on GitHub-hosted Ubuntu; optimize repeated migration setup only if its
  observed duration materially harms required-gate feedback time.
