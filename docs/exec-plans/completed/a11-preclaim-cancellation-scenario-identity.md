# A11 Preclaim Cancellation Scenario Identity

## Status

- State: completed
- Owner: agent
- Created: 2026-08-03
- Last updated: 2026-08-05
- Review date: 2026-08-03
- Next action: none; implementation and required production-dialect validation are complete.
- Blocker: none

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
- Historical targeted worker selection exited 0, but its PostgreSQL cases skipped without a local maintenance database URL; that skip is not counted as production-dialect evidence.
- Historical targeted runtime-storage selection collected but skipped the PostgreSQL case without a local maintenance database URL; that skip is not counted as production-dialect evidence.
- Historical PostgreSQL-marked selection collected but skipped without a local maintenance database URL; that skip is not counted as production-dialect evidence.
- [x] PR #54 required CI ran the canonical `python scripts/agent/runner.py postgresql-check` successfully against PostgreSQL, including the cancellation and claim regressions.
- [x] `uv run python scripts/agent/runner.py validate-configs` passed.
- [x] `uv run python scripts/agent/runner.py validate-architecture` passed.
- [x] `uv run python scripts/agent/runner.py validate-docs` passed.
- [x] `uv run python scripts/agent/runner.py generate-docs --check` passed.
- [x] `uv run python scripts/agent/runner.py quick-check` passed on the final run: 219 passed, 293 deselected.

## Progress Log

| Date | Progress | Next |
|---|---|---|
| 2026-08-05 | Reconciled the locally skipped PostgreSQL selections with PR #54's successful canonical PostgreSQL CI run. The merged implementation and production-dialect proof complete the plan scope. | None. |
