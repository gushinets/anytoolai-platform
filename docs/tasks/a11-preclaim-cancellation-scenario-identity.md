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

Invalid or missing linkage is caught and terminalizes the job as `failed` with
`error_code="job_scenario_session_invalid"`, emitting `workflow.failed` instead of leaking the
domain error to the caller (mirroring the same poison-job handling already used by claim). Non-created
jobs remain rejected idempotently: no status change, metadata rewrite, or duplicate cancellation
event.

## Test cases added

- `test_cancel_created_job_preserves_guest_scenario_identity`
- `test_cancel_created_job_preserves_authenticated_scenario_identity`
- `test_cancel_created_job_terminalizes_missing_scenario_session_as_failed`
- `test_cancel_created_job_terminalizes_missing_scenario_session_linkage_as_failed`
- `test_cancel_created_job_terminalizes_mismatched_scenario_session_as_failed`
- `test_cancel_job_rejects_non_created_status_idempotently`
- `test_cancel_created_job_rolls_back_when_event_persistence_fails`
- `test_cancel_and_claim_race_allows_only_one_created_transition`

## Validation results

- `uv run python scripts/agent/runner.py doctor` passed.
- `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -k "cancel or cancellation or claim" -q` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 22 passed, 0 skipped. Approved exception to the canonical `scripts/agent/runner.py` wrapper: `postgresql-check` only exposes its fixed four-directory target list (`packages/backend/platform-core/tests`, `packages/backend/platform-actions/tests`, `apps/platform-api/tests`, `apps/platform-worker/tests`), with no flag to narrow to a single file, so a single-file targeted run has no wrapper equivalent. The canonical-wrapper run below uses the same `-k` filter across the full target set and covers this file's matching tests as a subset.
- `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -k "cancel or claim" -q` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 1 passed, 0 skipped. Same approved exception as above (single-file target, no wrapper equivalent).
- `PYTEST_ADDOPTS='-k "cancel or cancellation or claim"' uv run python scripts/agent/runner.py postgresql-check` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 34 passed, 0 skipped. Replaces the previous direct `-m "postgresql"` invocation with the canonical wrapper: same fixed four-directory target set `postgresql-check` uses internally, with the `-k` filter passed through via `PYTEST_ADDOPTS` (a standard pytest mechanism; `runner.py` inherits the caller's environment unmodified, so this needs no code change). Count is 34, not 33, because a regression test added in a later review pass (`test_handle_terminalizes_scenario_invalidated_between_claim_and_reload_as_failed`) now also matches this filter.
- `uv run python scripts/agent/runner.py postgresql-check` run against a real `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL`: 293 passed, 0 skipped, 0 failed (the full `postgresql`-marked suite, not just the cancel/claim slice above). The entries above previously ran the same `-m "postgresql"` selections with no database URL configured, so every PostgreSQL-marked case collected but silently skipped -- `postgresql-check` exists specifically to fail loudly on that gap instead of passing green on a no-op. This run is the first genuine execution of PostgreSQL production semantics for this change; the guest/authenticated identity, race, and rollback behavior described above is now actually verified, not just asserted.
- `uv run python scripts/agent/runner.py validate-configs` passed.
- `uv run python scripts/agent/runner.py validate-architecture` passed.
- `uv run python scripts/agent/runner.py validate-docs` passed.
- `uv run python scripts/agent/runner.py generate-docs --check` passed.
- `uv run python scripts/agent/runner.py quick-check` passed on the final run: 219 passed, 293 deselected.
