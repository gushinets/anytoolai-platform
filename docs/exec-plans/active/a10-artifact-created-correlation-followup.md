# Execution Plan: A10 Artifact Created Correlation Follow-up

## Status

- State: active
- Owner: agent
- Created: 2026-07-27
- Last updated: 2026-07-27
- Review date: 2026-07-27
- Last run: 2026-07-27
- Next action: rerun repo validation and capture the remaining pre-existing docs-validation blocker.
- Blocker: unrelated active-plan doc `docs/exec-plans/active/repository-system-design-review.md` currently fails `validate-docs` in this worktree.

## Goal

Ensure `artifact.created` preserves the same applicable runtime correlation dimensions as the owning
workflow/action execution, including rollback-recovery replay paths, without introducing product-
specific artifact logic or unsafe event payloads.

## Scope

### In scope

- Inspect the ANY-15 workflow/action/provider correlation implementation and PR #23 follow-up review
- Preserve bounded runtime correlation metadata for action structured-output artifacts
- Preserve bounded runtime correlation metadata for workflow-result artifacts
- Preserve bounded runtime correlation metadata for debug artifacts
- Reconstruct `artifact.created` event context from canonical artifact-owned metadata in normal and
  replay emission paths
- Update focused docs and regression tests

### Out of scope

- Event taxonomy redesign
- Artifact schema migrations or new runtime tables
- Product-specific orchestration logic in the artifact layer
- Provider payload, prompt, or artifact-body propagation into event properties

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/architecture/action-runner.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/provider-gateway.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/runtime-storage.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/exec-plans/completed/a10-sequential-workflow-runner.md`

## Contracts touched

- API: none
- DB: no schema migration planned; reuse existing artifact `metadata`
- Config: none
- Events: `artifact.created` correlation context reconstruction
- Frontend: none

## Implementation steps

- [x] Preserve applicable runtime correlation metadata on artifact records at action/debug/workflow creation sites
- [x] Reconstruct `artifact.created` context from artifact-owned canonical metadata for normal emission and replay
- [x] Extend tests for action-output, workflow-result, debug-artifact, recovery, and safety behavior
- [x] Update docs and run targeted validation plus `quick-check`

## Validation

- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_action_runner.py -q --basetemp D:\Devpy\anytoolai-platform\.quick-check-tmp\action-runner`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q --basetemp D:\Devpy\anytoolai-platform\.quick-check-tmp\workflow-runner`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_artifact_service.py -q --basetemp D:\Devpy\anytoolai-platform\.quick-check-tmp\artifact-service`
- [x] `uv run python -m pytest packages/backend/platform-core/tests/unit/test_structured_output.py -q --basetemp D:\Devpy\anytoolai-platform\.quick-check-tmp\structured-output`
- [x] `uv run python -m pytest packages/backend/platform-actions/tests/test_structured_llm_executor.py -q --basetemp D:\Devpy\anytoolai-platform\.quick-check-tmp\structured-llm-executor`
- [ ] `python scripts/agent/runner.py quick-check` blocked by unrelated `validate-docs` failure in `docs/exec-plans/active/repository-system-design-review.md`
- [x] `D:\Devpy\anytoolai-platform\.quick-check-venv\Scripts\python.exe scripts/agent/validate_configs.py`
- [x] `python scripts/agent/runner.py validate-architecture`
- [ ] `python scripts/agent/runner.py validate-docs` blocked by unrelated `docs/exec-plans/active/repository-system-design-review.md`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-27 | Prefer persisting additional product-neutral correlation metadata on artifact records over reconstructing from linked job/action lookups only | `artifact.created` must survive transaction boundaries and replay paths, and artifact metadata already provides a bounded, compatibility-safe persistence surface without a schema change |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-27 | Read the required docs, ANY-15 completed plan, PR #23 review comments, and the workflow/action/provider/artifact/replay code paths | Patch artifact correlation preservation, then extend focused tests and docs |
| 2026-07-27 | Persisted bounded artifact correlation metadata, extended artifact/action/workflow/debug tests, and updated artifact/event/runtime docs | Record the remaining pre-existing docs-validation blocker and hand off the implementation summary |

## Open questions

- None currently

## Follow-up debt

- If more runtime surfaces need the same metadata extraction helpers, consolidate them in a separate cleanup slice instead of expanding this follow-up beyond artifact correlation.
