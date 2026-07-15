# Execution Plan: Test Action Runner Stable Event Assertions

## Status

- State: completed
- Owner: agent
- Created: 2026-07-07
- Last updated: 2026-07-07

## Goal

Stabilize `packages/backend/platform-core/tests/unit/test_action_runner.py` so event assertions no longer depend on UUID4 or timestamp tie-breaking while still verifying that the expected runtime events are emitted with correct correlation.

## Scope

### In scope

- Inspect the event log schema, emitter, and provider/action event insertion flow
- Update `test_action_runner.py` assertions to rely on stable runtime contracts only
- Run the targeted pytest file and the repo quick-check fallback command

### Out of scope

- Broad event-log schema redesign
- Adding new runtime ordering columns unless a tiny pre-existing contract clearly supports it
- Refactoring unrelated event-log tests

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/runtime-storage.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none expected
- Config: none
- Events: test assertions for action/provider/artifact event correlation
- Frontend: none

## Implementation steps

- [x] Step 1
- [x] Step 2
- [x] Step 3

## Validation

- [ ] `just quick-check`
- [ ] `just validate-configs`
- [ ] `just validate-architecture`
- [ ] `just kernel-smoke`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-07 | Keep the fix scoped to tests unless a stable event-order contract already exists | `event_id` is UUID4-based and `timestamp` is not a deterministic total-order contract |
| 2026-07-07 | Use documented shell-independent validation fallbacks when `just` is unavailable | Root `AGENTS.md` explicitly allows the Python fallback path |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-07 | Read required repo orientation and runtime docs; confirmed `just doctor` is unavailable in this shell | Update the test assertions to remove unstable ordering assumptions |
| 2026-07-07 | Rewrote action-runner event assertions to match by `event_type` and validate correlation fields instead of sorting by UUID/timestamp | Close out with validation results and handoff |

## Open questions

- None currently

## Follow-up debt

- Related event-log tests also sort by `timestamp` plus `event_id`; they may deserve a separate stabilization pass if flakes appear there too.
