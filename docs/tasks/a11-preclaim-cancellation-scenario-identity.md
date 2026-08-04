# A11 follow-up: Preserve scenario identity on pre-claim cancellation

Reference:

- Linear: ANY-31
- GitHub PR: #24

## Problem

Pre-claim cancellation previously changed a job directly from `created` to `canceled` and emitted
`workflow.canceled` from the job row as it stood. If job metadata had not already been enriched,
the event could omit scenario identity that was available on the linked scenario session:
`guest_id`, `user_id`, and `scenario_chain_id`.

## Implementation summary

Pre-claim cancellation now loads and validates the linked scenario session inside the same
transaction as the terminal job update and event persistence. Valid cancellation merges the
session's identity and scenario-chain values into job metadata, preserves existing metadata keys,
then emits `workflow.canceled` through the canonical event emitter and job-derived context.

Invalid or missing linkage raises the established safe domain error, leaves the job `created`,
preserves metadata, and emits no cancellation event. Non-created jobs remain rejected
idempotently: no status change, metadata rewrite, or duplicate cancellation event.

## Test cases added

- `test_cancel_created_job_preserves_guest_scenario_identity`
- `test_cancel_created_job_preserves_authenticated_scenario_identity`
- `test_cancel_created_job_rejects_missing_scenario_session_without_event`
- `test_cancel_created_job_rejects_missing_scenario_session_linkage`
- `test_cancel_created_job_rejects_mismatched_scenario_session`
- `test_cancel_job_rejects_non_created_status_idempotently`
- `test_cancel_created_job_rolls_back_when_event_persistence_fails`
- `test_cancel_and_claim_race_allows_only_one_created_transition`

## Validation results

- `uv run python scripts/agent/runner.py doctor` passed.
- `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -k "cancel or cancellation or claim" -q` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 21 passed, 0 skipped.
- `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -k "cancel or claim" -q` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 1 passed, 0 skipped.
- `uv run python -m pytest -m "postgresql" packages/backend/platform-core/tests apps/platform-api/tests apps/platform-worker/tests -k "cancel or cancellation or claim" -q` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 33 passed, 0 skipped.
- `uv run python scripts/agent/runner.py postgresql-check` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 293 passed, 0 skipped, 0 failed (the full `postgresql`-marked suite, not just the cancel/claim slice above). The entries above previously ran the same `-m "postgresql"` selections with no database URL configured, so every PostgreSQL-marked case collected but silently skipped -- `postgresql-check` exists specifically to fail loudly on that gap instead of passing green on a no-op. This run is the first genuine execution of PostgreSQL production semantics for this change; the guest/authenticated identity, race, and rollback behavior described above is now actually verified, not just asserted.
- `uv run python scripts/agent/runner.py validate-configs` passed.
- `uv run python scripts/agent/runner.py validate-architecture` passed.
- `uv run python scripts/agent/runner.py validate-docs` passed.
- `uv run python scripts/agent/runner.py generate-docs --check` passed.
- `uv run python scripts/agent/runner.py quick-check` passed on the final run: 219 passed, 293 deselected.
