# Execution Plan: A11 Scenario Identity Metadata Deduplication

## Status

- State: completed
- Owner: agent
- Created: 2026-08-04
- Last updated: 2026-08-05
- Review date: 2026-08-05
- Next action: none; implementation and validation are complete.
- Blocker: none. Plain `uv run python scripts/agent/runner.py quick-check` in this shell placed
  outer `uv` dependency archives under `.tmp/uv-cache`, which repository architecture tests scan;
  the final `uv run` validation passed with `UV_CACHE_DIR` pointed at `.quick-check-tmp`, a
  scanner-skipped cache root.

## Goal

Keep scenario identity construction for worker claim, pre-claim cancellation, and workflow execution
context aligned behind one canonical helper.

## Scope

### In scope

- Replace manual execution-context identity field extraction with `build_scenario_identity_metadata`.
- Add a narrow metadata-enrichment helper for the identical claim/cancel metadata merge.
- Add focused tests for execution-context identity and metadata enrichment behavior.
- Add a short task document and validation results.

### Out of scope

- Repository-owned scenario loading or identity inference.
- Workflow-context redesign.
- New lifecycle states or cancellation behavior.

## Relevant Docs

- `docs/architecture/job-lifecycle.md`
- `docs/architecture/runtime-storage.md`
- `docs/tasks/a11-preclaim-cancellation-scenario-identity.md`

## Contracts Touched

- API: none
- DB: none
- Config: none
- Events: no event contract change; this keeps identity extraction aligned.
- Frontend: none

## Implementation Steps

- [x] Verify current branch state and duplicate identity construction.
- [x] Classify duplicate metadata merge as valid and worth a narrow helper.
- [x] Patch the scenario correlation helper and worker handler.
- [x] Add focused unit tests.
- [x] Run focused tests and repository validation.

## Validation

- [x] `uv run python scripts/agent/runner.py doctor` passed.
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_scenario_correlation.py apps/platform-worker/tests/test_run_workflow_context.py -q` passed: 5 passed.
- [x] `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -k "identity or claim or cancel or execution_context" -q` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 22 passed, 0 skipped (2026-08-05 re-run; the original entry only collected these PostgreSQL-marked cases without a database URL configured, so they skipped instead of executing).
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 24 passed, 0 skipped (2026-08-05, covering the `runner.py` extension in the progress log above).
- [x] `uv run python scripts/agent/runner.py validate-architecture` passed.
- [x] `uv run python scripts/agent/runner.py validate-docs` passed.
- [x] `$env:UV_CACHE_DIR='D:\Devpy\anytoolai-platform\.quick-check-tmp\outer-uv-cache'; uv run python scripts/agent/runner.py quick-check` passed: 224 passed, 293 deselected.

## Decision Log

| Date | Decision | Why |
|---|---|---|
| 2026-08-04 | Keep scenario identity helpers in `platform-core.scenarios.correlation`. | Claim, cancellation, and execution context all consume scenario-session identity, while repositories should persist supplied metadata rather than load unrelated aggregates. |

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-08-04 | Confirmed `_execution_context()` manually extracted identity and claim/cancel repeated the same metadata merge. | Patch code and tests. |
| 2026-08-04 | Routed claim, cancellation, and execution context through shared scenario identity helpers; focused tests and quick-check pass. | None. |
| 2026-08-05 | Third-pass ANY-171 branch review found this dedup was incomplete: `SequentialWorkflowRunner.run()`/`run_claimed_job()` (`workflows/runner.py`) still built the `guest_id`/`user_id`/`scenario_chain_id` triplet inline from `ExecutionContext` instead of `build_scenario_identity_metadata()`. Widened `build_scenario_identity_metadata()`/`enrich_job_metadata_with_scenario_identity()` in `scenarios/correlation.py` to a structural `ScenarioIdentitySource` `Protocol` (matching both `ScenarioSessionRecord` and `ExecutionContext`) and routed both `runner.py` call sites through it. | None. |

## Open Questions

None.

## Follow-Up Debt

None currently. (The `runner.py` gap noted in the 2026-08-05 progress log is closed, not deferred.)
