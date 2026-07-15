# Execution Plan: Action Runner Failure Persistence Outside Transaction

## Status

- State: completed
- Owner: agent
- Created: 2026-07-07
- Last updated: 2026-07-07

## Goal

Ensure `ActionRunner` failure state and `action.failed` event persist when an exception escapes `transaction_boundary()`, while preserving exception propagation and normal in-transaction behavior.

## Scope

### In scope

- Inspect `ActionRunner`, `ActionRunService`, event emission, and `transaction_boundary()`
- Add unit coverage for both in-transaction catch and escaped-exception paths
- Implement the smallest safe durability fix for failed action state and `action.failed`

### Out of scope

- Broad redesign of transaction handling across the runtime
- Provider failure durability changes beyond what this action-runner fix requires
- Schema migrations unless clearly required

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
- Events: `action.failed` durability on escaped exceptions
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
| 2026-07-07 | Treat escaped exceptions as a real production path, not just a test gap | `transaction_boundary()` uses `session.begin()` so escaped exceptions roll back action failure persistence today |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-07 | Confirmed that `action_run` create, failed update, and `action.failed` all roll back if the exception crosses `transaction_boundary()` | Implement a rollback-recovery path that persists failed action state durably |
| 2026-07-07 | Added rollback-recovery callbacks to `transaction_boundary()` and registered durable failed-action replay from `ActionRunner` | Validate the escaped-exception path and document the final contract |

## Open questions

- None currently

## Follow-up debt

- Provider-attempt rows and provider failure events still follow the outer transaction; if durable failure telemetry is needed there too, it should be handled as a separate contract decision.
