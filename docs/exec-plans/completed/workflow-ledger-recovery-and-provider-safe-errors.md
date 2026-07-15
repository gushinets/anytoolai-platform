# Execution Plan: Workflow Ledger Recovery And Provider Safe Errors

## Status

- State: completed
- Owner: agent
- Created: 2026-07-13
- Last updated: 2026-07-13

## Goal

Preserve a coherent durable workflow execution ledger across rollback recovery and tighten provider failure handling so safe runtime fields never leak raw provider or user content.

## Scope

### In scope

- Inspect workflow runner, worker handler, transaction recovery, action/provider/artifact persistence, and runtime event emission
- Verify whether rollback currently loses successful step history, artifacts, provider-event correlation, or leaves dangling references
- Verify how unknown provider adapter exceptions flow into provider calls, jobs, workflow failure state, and events
- Implement the smallest coherent fix set that preserves runtime, storage, and event contracts
- Update focused tests for rollback durability and provider safe-error handling

### Out of scope

- Product-specific changes
- New runtime tables or broad workflow-engine redesign
- Relaxing runtime or event contracts to match current behavior

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/job-lifecycle.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/runtime-storage.md`
- `docs/architecture/workflow-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`

## Contracts touched

- API: none expected
- DB: no schema change expected unless inspection proves one is required
- Config: none expected
- Events: workflow, action, provider, artifact durability and safe failure metadata
- Frontend: none

## Implementation steps

- [x] Verify current rollback-recovery and provider safe-error behavior against docs and tests
- [x] Implement coherent durability and safe-error fixes across workflow, worker, provider, and event surfaces
- [x] Update targeted tests and run focused validation plus baseline checks

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_action_runner.py packages/backend/platform-core/tests/unit/test_workflow_runner.py packages/backend/platform-core/tests/unit/test_provider_gateway.py --basetemp .quick-check-tmp/pytest-finding-fix -q`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_event_log.py --basetemp .quick-check-tmp/pytest-event-log-finding-fix -q`
- [x] `uv run python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py packages/backend/platform-core/tests/unit/test_structured_output.py --basetemp .quick-check-tmp/pytest-structured-finding-fix -q`
- [x] `uv run python -m pytest apps/platform-worker/tests/test_worker_boot.py --basetemp .quick-check-tmp/pytest-worker-finding-fix -q`
- [x] `python scripts/agent/quick_check.py`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-13 | Treat rollback durability and safe provider errors as one coherent remediation | The review findings cross transaction recovery, provider-call correlation, event history, and worker failure persistence |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-13 | Read the core architecture/runtime docs and confirmed `just` is unavailable in the shell | Inspect the current code and tests to verify each reported finding against the branch state |
| 2026-07-13 | Verified both findings against current code: workflow rollback still collapsed durable history, and gateway safe-error handling still defaulted to raw exception text for unknown adapter failures | Implement recovery across artifact/action/provider/workflow surfaces and replace provider safe-message defaults |
| 2026-07-13 | Added rollback recovery for successful action runs, artifacts, provider lifecycle events, and full workflow step state/event replay; replaced provider safe-message defaults with code-based generic messages and updated worker propagation/tests | Run focused suites plus baseline quick check and close out the handoff |
| 2026-07-13 | Verified claimed-job rollback recovery still used `update()` for `running -> failed`, which breaks after the claim transaction commits, then switched recovery to a lifecycle-safe failure transition and added claimed-job worker coverage | Run full backend/worker suites plus quick-check wrappers |

## Open questions

- None yet

## Follow-up debt

- None yet
