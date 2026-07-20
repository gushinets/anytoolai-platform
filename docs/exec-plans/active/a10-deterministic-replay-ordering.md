# Execution Plan: A10 Deterministic Replay Ordering

## Status

- State: active
- Owner: Codex
- Created: 2026-07-20
- Last updated: 2026-07-20
- Review date: 2026-07-20
- Next action: none; implementation and validation are complete.
- Blocker: none

## Goal

Make rollback-recovered workflow events persist in deterministic causal order across platforms even
when source row timestamps collide or regress.

## Scope

### In scope

- Workflow-owned rollback event replay ordering
- In-memory replay timestamp clamping for recovered workflow/action/provider/artifact events
- Same-status `jobs.completed_at` adjustment when terminal replay is clamped
- Focused recovery tests and ordering docs

### Out of scope

- Durable workflow engine
- Event-log ordinal/schema migration
- Expression language behavior
- Weakened ordering assertions or sleeps

## Relevant docs

- `docs/architecture/workflow-model.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/action-runner.md`

## Contracts touched

- Events: recovered workflow event timestamps become monotonic in documented causal sequence.
- DB: no schema change; `jobs.completed_at` may be same-status adjusted during recovery.
- API/Config/Frontend: unchanged.

## Implementation steps

- [x] Research docs, replay code, timestamp helpers, and existing recovery tests.
- [x] Add small replay timestamp sequencer.
- [x] Thread sequencer through workflow-owned action/provider/artifact replay.
- [x] Adjust recovered job terminal timestamp when replay clamps terminal event.
- [x] Add or strengthen exact-order regression tests.
- [x] Update workflow/event docs.

## Validation

- [x] Focused workflow recovery tests repeated on Windows-friendly timing paths.
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests -q`
- [x] `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py::test_production_worker_cancellation_recovers_inflight_action_and_provider_ledger apps/platform-worker/tests/test_worker_boot.py::test_production_worker_provider_failure_preserves_claimed_job_recovery_state -q`
- [x] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-20 | Use an in-memory monotonic replay timestamp sequencer instead of a durable ordinal field. | Workflow recovery already owns the causal replay sequence, and a schema-level ordering contract is unnecessary for MVP-A. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-20 | Confirmed current replay emits in causal call order but raw timestamps can collide/regress, allowing `timestamp,event_id` sorting to violate causality. | Implement monotonic timestamp clamping in the existing replay path. |
| 2026-07-20 | Added monotonic replay timestamp sequencing, threaded it through workflow-owned child replay, tightened exact-order tests, updated docs, and passed focused/core/worker/quick-check validation. | None. |

## Open questions

None.

## Follow-up debt

None expected.
