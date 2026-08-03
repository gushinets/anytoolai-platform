# A11 Preclaim Cancellation Scenario Identity

## Status

- State: active
- Owner: agent
- Created: 2026-08-03
- Last updated: 2026-08-03
- Review date: 2026-08-03
- Next action: rerun PostgreSQL-marked lifecycle coverage with
  `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` if local production-semantics proof is required.
- Blocker: no `ANYTOOLAI_POSTGRES_TEST_DATABASE_URL` was configured in this shell, so
  PostgreSQL-marked cancellation and claim selections collected but skipped locally.

## Task

Preserve scenario identity and scenario-chain correlation when canceling jobs that are still in
`created` before worker claim.

References:

- Linear: ANY-31
- GitHub PR: #24
- Follow-up: A11 follow-up: Preserve scenario identity on pre-claim cancellation

## Plan

- Load and validate the linked scenario session inside the pre-claim cancellation transaction.
- Reuse one helper for claim and cancel scenario identity metadata:
  `guest_id`, `user_id`, and `scenario_chain_id`.
- Persist enriched metadata in the same conditional `created -> canceled` update that sets
  `completed_at`.
- Continue emitting `workflow.canceled` through the canonical event emitter and job-derived
  execution context.
- Keep non-created cancellation attempts idempotent: no status change, metadata rewrite, or
  duplicate terminal event.
- Add PostgreSQL regression tests for guest identity, authenticated identity, missing/mismatched
  linkage, missing linkage, non-created status protection, event-persistence rollback, and
  claim/cancel contention.
- Update lifecycle/runtime/task documentation with the finalized behavior and validation evidence.

## Validation

- [x] `uv run python scripts/agent/runner.py doctor` passed.
- [x] `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py -k "cancel or cancellation or claim" -q` exited 0; PostgreSQL-marked cases skipped without a local maintenance database URL, and the selected non-PostgreSQL case passed.
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -k "cancel or claim" -q` exited 0; the selected PostgreSQL storage case skipped without a local maintenance database URL.
- [x] `uv run python -m pytest -m "postgresql" packages/backend/platform-core/tests apps/platform-api/tests apps/platform-worker/tests -k "cancel or cancellation or claim" -q` exited 0; PostgreSQL-marked cases collected but skipped without a local maintenance database URL.
- [x] `uv run python scripts/agent/runner.py validate-configs` passed.
- [x] `uv run python scripts/agent/runner.py validate-architecture` passed.
- [x] `uv run python scripts/agent/runner.py validate-docs` passed.
- [x] `uv run python scripts/agent/runner.py generate-docs --check` passed.
- [x] `uv run python scripts/agent/runner.py quick-check` passed on the final run: 219 passed, 293 deselected.
