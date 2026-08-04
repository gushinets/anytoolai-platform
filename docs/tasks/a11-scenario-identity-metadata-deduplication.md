# A11 scenario identity metadata deduplication

## Problem

The A11 pre-claim cancellation follow-up centralized scenario identity extraction in
`build_scenario_identity_metadata`, but `RunWorkflowHandler._execution_context()` still read
`guest_id`, `user_id`, and `scenario_chain_id` directly from the scenario session. Claim and
pre-claim cancellation also repeated the same metadata merge expression.

## Relevance assessment

- Finding 1 was valid: execution-context construction had a second manual identity definition.
- Finding 2 was valid and worth a narrow helper: claim and cancellation share the same
  orchestration-level metadata enrichment semantics, and the repository should continue only
  persisting supplied metadata.

## Implementation summary

`build_scenario_identity_metadata` remains the canonical scenario identity source. A small
`enrich_job_metadata_with_scenario_identity` helper now preserves existing job metadata, overlays
canonical scenario identity values, preserves current `None` handling, and returns a new mapping.

`RunWorkflowHandler` now uses these helpers for claim, pre-claim cancellation, and execution
context construction.

## Validation results

- `uv run python scripts/agent/runner.py doctor` passed.
- `uv run python -m pytest packages/backend/platform-core/tests/unit/test_scenario_correlation.py apps/platform-worker/tests/test_run_workflow_context.py -q` passed: 5 passed.
- `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -k "identity or claim or cancel or execution_context" -q` exited 0; PostgreSQL-marked cases skipped locally without a maintenance database URL, and the selected non-PostgreSQL case passed.
- `uv run python scripts/agent/runner.py validate-architecture` passed.
- `uv run python scripts/agent/runner.py validate-docs` passed.
- `$env:UV_CACHE_DIR='D:\Devpy\anytoolai-platform\.quick-check-tmp\outer-uv-cache'; uv run python scripts/agent/runner.py quick-check` passed: 224 passed, 293 deselected.
