# Execution Plan: Action Runner Provider Call And Artifact Linking Fix

## Status

- State: completed
- Owner: agent
- Created: 2026-07-08
- Last updated: 2026-07-08

## Goal

Fix the current ActionRunner/provider/artifact inconsistencies so escaped action failures still preserve provider-call ledger rows, success-path artifact pointers only reference real normalized artifacts, and failed actions never point `output_artifact_id` at debug raw artifacts.

## Scope

### In scope

- Inspect current docs, runtime code paths, and tests for action runner, provider gateway, structured output, artifacts, storage, and events
- Preserve provider-call ledger rows for escaped-exception rollback recovery
- Tighten canonical artifact-link validation for action success/failure paths
- Update focused unit coverage and run targeted validation

### Out of scope

- Unrelated architecture-test noise under `tmp/review-any50-a08`
- Broad transaction subsystem redesign
- New schema migrations unless clearly required

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/llm-runtime.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none
- DB: none expected
- Config: none
- Events: action/provider rollback-recovery consistency where applicable
- Frontend: none

## Implementation steps

- [x] Step 1
- [x] Step 2
- [x] Step 3

## Validation

- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_provider_gateway.py -q`
- [x] `python -m pytest packages/backend/platform-core/tests/unit/test_structured_output.py -q`
- [x] `python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-08 | Keep the fix set coherent across ActionRunner, ProviderGateway, artifacts, and tests | The three reported issues come from one runtime inconsistency around rollback recovery and canonical artifact linkage |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-08 | Verified docs and code paths: provider-call ledger contract is stronger than current escaped-failure recovery, success artifact ids are currently unvalidated, and failed actions can still pick debug raw artifacts by recency | Implement the smallest aligned rollback-recovery and artifact-link validation changes |
| 2026-07-08 | Added gateway-owned rollback recovery for provider-call rows plus runner-side canonical artifact validation for success and failure paths | Validate focused suites and repo quick-check, then hand off the final contract |

## Open questions

- None currently

## Follow-up debt

- If provider request events also need durable replay on escaped rollback beyond the ledger row contract, that should be handled as a deliberate follow-up once the desired event-history semantics are explicitly documented.
