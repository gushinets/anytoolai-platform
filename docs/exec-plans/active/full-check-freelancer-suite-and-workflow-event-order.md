# Execution Plan: Full-Check Freelancer Suite and Workflow Event Order

## Status

- State: completed
- Owner: agent
- Created: 2026-07-13
- Last updated: 2026-07-13

## Goal

Verify the reported `full-check` freelancer-suite editable-install failure and the workflow rollback
event-order assertion failure against the current branch, then apply the smallest coherent fixes for
any still-valid issues.

## Scope

### In scope

- `scripts/agent/runner.py` full-check bootstrap/install path.
- `packages/backend/product-platforms/freelancer-suite/pyproject.toml` packaging contract.
- Workflow rollback recovery event emission and the claimed-job workflow runner test.
- Targeted validation plus the canonical quick-check/full-check commands.

### Out of scope

- Broad packaging redesign across unrelated packages.
- Changes to runtime event contracts unless the current implementation clearly violates them.
- CI-only workarounds.

## Relevant docs

- `docs/agent/codex-operating-model.md`
- `docs/architecture/workflow-model.md`
- `docs/architecture/event-taxonomy.md`
- `docs/architecture/package-layering.md`

## Contracts touched

- Tooling: full-check must be able to install and test `freelancer-suite` in the managed check environment.
- Events: workflow rollback recovery tests must assert stable, documented guarantees only.

## Implementation steps

- [x] Read relevant docs and inspect current bootstrap/test/runtime paths.
- [x] Verify whether each reported failure still reproduces on the current branch.
- [x] Implement the smallest coherent fix set for still-valid issues.
- [x] Run the requested validation commands.
- [x] Record summary and handoff details.

## Validation

- [x] `D:\Devpy\anytoolai-platform\.quick-check-venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_workflow_runner.py -q`
- [x] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-13 | Keep `full-check` on the existing `--no-build-isolation` freelancer-suite install path, but seed the managed environment from the package's own `build-system.requires` first. | The failure is real in the current branch, and this keeps the repo check aligned with first-party packaging metadata instead of hardcoding package-specific build tools in CI. |
| 2026-07-13 | Treat the workflow rollback report as a test-contract issue, not a runtime ordering bug. | The claimed-job rollback recovery implementation still emits recovered step events before `workflow.failed`, and the test passes on the current branch; the brittle part is the assertion that orders persisted rows by timestamp/UUID tie-breaks. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-13 | Read the workflow/event/check-runner docs and inspected `runner.py`, `freelancer-suite` packaging metadata, and the claimed-job rollback recovery test. | Reproduce both failures against the current branch before changing code. |
| 2026-07-13 | Reproduced the freelancer-suite failure directly in `.quick-check-venv`: the non-isolated editable install failed with `ModuleNotFoundError: No module named 'setuptools'`. | Update `full-check` to install the package's declared build requirements before the editable install and cover that path in `tests/test_runner.py`. |
| 2026-07-13 | The claimed-job rollback workflow test did not fail on this branch, but its event-order assertion relied on `timestamp,event_id` sorting rather than a documented event-order contract. | Replace the fragile ordering checks with durable correlation and error-metadata assertions. |
| 2026-07-13 | Targeted runner/workflow tests passed, the freelancer-suite editable install succeeded after preinstalling declared build requirements, and both `quick_check.py` and `runner.py full-check` passed. | No further work for this task. |

## Open questions

- None yet.

## Follow-up debt

- None yet.
