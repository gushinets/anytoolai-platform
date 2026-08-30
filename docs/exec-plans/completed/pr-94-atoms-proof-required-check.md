# PR #94 Atoms Proof Required Check Implementation Plan

> **For agentic workers:** Execute the checked steps in order; keep the workflow change minimal.

**Goal:** Make PR #94 publish the required `atoms-proof` GitHub check instead of leaving it `Expected`.

**Architecture:** Add one independent backend workflow job that reuses the existing `dev-up` / `atoms-proof` / `dev-down` runner commands. Preserve failure diagnostics and proof evidence, and lock the workflow contract with one YAML-level regression test.

**Tech Stack:** GitHub Actions, Python 3.12, uv, pytest, Docker Compose.

**Spec:** `docs/product-specs/mvp-a-platform-kernel.md`

## Status

- State: completed
- Owner: agent
- Created: 2026-08-29
- Last updated: 2026-08-30
- Review date: 2026-08-30
- Next action: none -- superseded by the `atoms-proof` job in `docs/exec-plans/active/any-391-atoms-proof-required-ci-gate.md`
- Blocker: none

## Global Constraints

- `atoms-proof` must run on pull requests and pushes to `main`.
- The job must remain credential-free and use the canonical runner commands.
- Teardown and evidence upload must run even when the proof fails.

## Task 1: Required workflow gate

**Files:**

- Modify: `tests/test_runner.py`
- Modify: `.github/workflows/backend.yml`
- Modify: `AGENTS.md`

**Interfaces:**

- Consumes: `python scripts/agent/runner.py dev-up`, `atoms-proof`, and `dev-down`.
- Produces: GitHub check context `atoms-proof` and evidence artifact `atoms-proof-evidence`.

- [x] Add a workflow-contract test that requires the `atoms-proof` job, canonical proof command, always-on evidence upload, and always-on teardown.
- [x] Run the test and confirm it fails because `jobs.atoms-proof` is absent.
- [x] Add the minimal independent workflow job using the established Compose smoke pattern.
- [x] Document the active required-check set in `AGENTS.md`.
- [x] Run the targeted test and `python scripts/agent/runner.py quick-check`.
- [ ] Commit and push `ANY-392`, then verify the PR publishes the `atoms-proof` check.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-29 | Fix the workflow, not the ruleset. | The ruleset intentionally requires the runtime proof; the PR workflow is the missing producer. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-29 | Confirmed ruleset `protect main` requires `atoms-proof`, while PR head `4c82984` publishes no check with that name. Baseline quick-check: 971 passed, 3 skipped. | Add the failing contract test. |
| 2026-08-29 | Added the job and regression contract. Targeted RED/green verified; quick-check: 972 passed, 3 skipped. | Push and verify the live PR check. |
| 2026-08-29 | First live job exposed `ENV001`: ordinary `uv sync` does not create the managed proof environment. Added the existing `quick-check --bootstrap-only` prerequisite from `live-canary.yml` and verified RED/green coverage. | Push the follow-up and verify the live proof. |
| 2026-08-30 | Merging `main` (this PR's `812e789`) into `feature/ANY-391` produced two `jobs.atoms-proof` keys in `backend.yml` (this plan's standalone job plus ANY-391's `compose-stack-check`-based job) and two conflicting workflow-contract tests -- `yaml.safe_load` silently kept only the second job body, so this plan's own `test_required_backend_workflow_runs_atoms_proof_with_evidence_and_teardown` started failing with `KeyError`. Resolved by keeping the ANY-391 composite-action job (fail-closed evidence upload, checksum-verified `setup-uv` pin, `timeout-minutes`, shared with `live-canary`) and removing this plan's standalone job and test as redundant. | None -- superseded. |
