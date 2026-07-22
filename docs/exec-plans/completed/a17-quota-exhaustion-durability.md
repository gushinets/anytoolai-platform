# Execution Plan: A17 Immediate Handoff Quota-Exhaustion Durability

## Status

- State: completed
- Owner: agent
- Created: 2026-07-22
- Last updated: 2026-07-22
- Review date: 2026-07-22
- Next action: none
- Blocker: none

## Goal

Keep target quota usage state and `quota.checked` / `quota.exhausted` events durable when immediate
handoff acceptance rolls back, while returning the existing safe `429 quota_exhausted` response and
persisting the handoff as failed.

## Research completed

- Compared `ScenarioRuntimeService.start_session()` and the scenario-start router with immediate
  `create_linked_session()`, `HandoffService.accept()`, and handoff-router failure recovery.
- Inspected `GuestQuotaService`, `QuotaUsageRepository`, the event emitter, caller-owned transaction
  boundary, phased rollback callbacks, handoff/quota/API tests, and quota/handoff architecture docs.
- Confirmed scenario start commits the exhausted quota path by deferring its safe API error until
  after the transaction exits normally; handoff acceptance must instead roll back its prior accept
  claim and target-session orchestration.

## Contracts touched

- Quota: exhausted attempts must retain the same ensured usage state and safe checked/exhausted
  event pair as ordinary scenario start.
- Handoff: acceptance remains rolled back and is then marked `failed` with safe
  `quota_exhausted`; no target session, target job, or quota consumption is committed.
- Events: recovered quota events retain target product/frontend/scenario/session-chain and runtime
  `handoff_id` correlation.
- API: response remains safe HTTP 429 with `quota_exhausted`.

## Implementation steps

- [x] Add a quota-exhaustion rollback recovery callback using the existing transaction recovery
  architecture.
- [x] Preserve handoff correlation when linked-session quota enforcement emits or recovers events.
- [x] Add quota-service rollback durability coverage and immediate handoff service/API regression
  tests.
- [x] Update quota/handoff transaction documentation.
- [x] Run requested package tests and canonical quick checks; move this plan to completed.

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests -q`
- [x] `python -m pytest apps/platform-api/tests -q`
- [x] `python scripts/agent/quick_check.py` attempted; product gates passed, while aggregate pytest
  hit the pre-existing protected `.quick-check-tmp/pytest/pytest-of-jackd` Windows ACL.
- [x] `python scripts/agent/runner.py quick-check` verified with the same ACL-only wrapper failure.
- [x] The wrapper's exact aggregate selection passed with an explicit writable base temp:
  325 passed, 3 deselected.
- [x] Config, architecture, docs, generated-doc freshness, Ruff, and diff checks passed.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-22 | Register recovery only after a quota consume is rejected, then recreate/ensure the quota row and replay checked/exhausted in an independent transaction if the caller rolls back. | This matches scenario-start durable state/events without committing a half-accepted handoff or inventing a second quota contract. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-22 | Root cause confirmed and smallest coherent recovery design selected. | Implement and test. |
| 2026-07-22 | Added exhaustion-only rollback recovery, handoff correlation, regression tests, and architecture documentation. All code gates pass; both quick-check wrappers remain blocked only by the known hard-coded Windows pytest temp ACL. | Complete. |
