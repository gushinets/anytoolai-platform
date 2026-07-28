# Execution Plan: Quick-Check Merge Repair

## Status

- State: active
- Owner: agent
- Created: 2026-07-27
- Last updated: 2026-07-27
- Review date: 2026-07-27
- Last run: 2026-07-27
- Next action: repair the shared merge artifacts in workflow finalization, quota recovery, and handoff migrations; then rerun targeted suites and `quick-check`.
- Blocker: none

## Goal

Restore the repository to an internally consistent post-merge state where the A10 artifact
correlation follow-up and the A17 handoff/quota contracts both hold and `quick-check` passes again.

## Scope

### In scope

- Inspect the conflict-prone files against both recent change sets.
- Repair the workflow final-artifact metadata merge so final artifacts preserve the canonical
  correlation contract.
- Repair quota-exhaustion rollback recovery so quota state, audit events, and handoff terminal
  failure finalize atomically and durably.
- Repair the handoff compatibility migration so `0008` recreates the full canonical schema.
- Rerun targeted suites for workflow, handoff/quota, migration, API, and worker paths.

### Out of scope

- Unrelated feature work.
- Weakening tests or changing documented contracts just to hide merge fallout.

## Relevant docs

- `docs/architecture/event-taxonomy.md`
- `docs/architecture/handoff-model.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/runtime-storage.md`
- `docs/product-specs/mvp-a-platform-kernel.md`

## Contracts touched

- API: handoff quota-exhaustion response and durable side effects
- DB: canonical `platform.product_handoffs` compatibility schema
- Config: none
- Events: artifact/quota/handoff correlation and durability
- Frontend: none

## Implementation steps

- [x] Inspect current failures, docs, and conflict-resolution diff to group root causes.
- [ ] Repair the shared workflow artifact metadata implementation.
- [ ] Repair quota-exhaustion recovery/finalization and confirm idempotence.
- [ ] Repair the compatibility migration to recreate the full canonical handoff schema.
- [ ] Rerun targeted suites and `python scripts/agent/runner.py quick-check`.

## Validation

- [x] `python scripts/agent/runner.py validate-docs`
- [x] `uv run python scripts/agent/validate_configs.py`
- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_handoffs.py apps/platform-api/tests/test_handoffs_api.py -q`
- [ ] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_runtime_storage.py -q`
- [ ] `uv run python -m pytest apps/platform-api/tests/test_scenario_runtime_api.py apps/platform-worker/tests/test_worker_boot.py -q`
- [ ] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-27 | Use the current A10/A17 docs as the contract source when the merged code paths disagree. | The failures are semantic merge artifacts between already-reviewed follow-up implementations. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-27 | Reproduced 11 `quick-check` failures and grouped them into workflow metadata, quota recovery, and migration mismatch clusters. | Compare the affected files against the recent pre-conflict revisions and patch the shared causes. |

## Open questions

- Whether the rollback-recovery `job scenario session link is invalid` message disappears once the workflow `NameError` is removed, or indicates a separate recovery bug.

## Follow-up debt

None expected if the merged contracts are restored cleanly.
