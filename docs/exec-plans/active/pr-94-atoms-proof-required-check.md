# PR #94 Atoms Proof Required Check Implementation Plan

> **For agentic workers:** Execute the checked steps in order; keep the workflow change minimal.

**Goal:** Make PR #94 publish the required `atoms-proof` GitHub check instead of leaving it `Expected`.

**Architecture:** Add one independent backend workflow job that reuses the existing `dev-up` / `atoms-proof` / `dev-down` runner commands. Preserve failure diagnostics and proof evidence, and lock the workflow contract with one YAML-level regression test.

**Tech Stack:** GitHub Actions, Python 3.12, uv, pytest, Docker Compose.

**Spec:** `docs/product-specs/mvp-a-platform-kernel.md`

## Status

- State: active
- Owner: agent
- Created: 2026-08-29
- Last updated: 2026-08-29
- Review date: 2026-08-29
- Next action: run validation, commit, push, and verify the PR check
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
