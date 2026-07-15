# Execution Plan: UV Agent Instructions And CI Alignment

## Status

- State: completed
- Owner: agent
- Created: 2026-06-22
- Last updated: 2026-06-22

## Goal

Make `uv` the explicit Python package-management rule for agents, remove contradictory repo guidance, align Python CI setup with the repo's `uv` workflow, and keep quick-check bootstrap aligned with the same `dependency-groups.dev` contract.

## Scope

### In scope

- Update agent-facing docs to require `uv` for Python dependency management and repo check commands.
- Add durable `uv` operating guidance to `docs/agent/codex-operating-model.md`.
- Update GitHub backend workflows to use `uv` environment setup and `uv run`.
- Re-scan repo guidance for stale `pip` package-management instructions.
- Make `scripts/agent/quick_check.py` install dev tooling from `[dependency-groups].dev` instead of `.[dev]`.

### Out of scope

- Dependency version changes unrelated to documentation and CI command alignment.
- Lockfile edits outside normal `uv` command output.
- Backend, DB, frontend, or product behavior changes.

## Relevant docs

- `AGENTS.md`
- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/package-layering.md`
- `docs/agent/codex-operating-model.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none

## Implementation steps

- [x] Add concise `uv` policy to `AGENTS.md`.
- [x] Add durable `uv` operating guidance to `docs/agent/codex-operating-model.md`.
- [x] Align repo-facing guidance files with the same command policy.
- [x] Update backend CI workflows to use `uv sync` and `uv run`.
- [x] Re-scan for stale `pip` instructions and run available validation commands.
- [x] Align quick-check bootstrap with the documented `uv add --dev` dependency-group workflow.

## Validation

- [x] Stale Python package-manager guidance scan across agent docs, repo docs, workflows, and scripts. Only the explicit "should not generate `pip install` commands" guidance remains.
- [ ] `uv run python scripts/agent/runner.py doctor` (`uv` is not installed in the local shell environment)
- [ ] `uv run python scripts/agent/runner.py quick-check` (`uv` is not installed in the local shell environment)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-22 | Keep the change scoped to agent guidance plus CI command alignment. | The user asked for a durable operational rule and removal of contradictory instructions, not a broader packaging redesign. |
| 2026-06-22 | Make quick-check consume `[dependency-groups].dev` directly instead of teaching docs about `.[dev]`. | Repo docs already standardize on `uv add --dev`, so the bootstrap should follow the documented source of truth rather than maintain a parallel extras-based contract. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-22 | Read the required architecture/docs set, confirmed `just` is unavailable locally, and inspected current agent docs plus GitHub workflows for Python command usage. | Patch the docs and workflows, then re-run repo scans and available validation. |
| 2026-06-22 | Updated `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/agent/codex-operating-model.md`, and `.github/workflows/backend.yml` to standardize on `uv` for Python dependency management and repo checks. | Finish validation; local `uv run` commands remain blocked until `uv` exists in the shell environment. |
| 2026-06-22 | Follow-up review pointed out that `quick-check` still bootstrapped `.[dev]`, which could drift from `uv add --dev` writes to `[dependency-groups].dev`. Updated the bootstrap path and its regression test to consume the dependency group directly. | Re-run the focused bootstrap regression and the canonical `uv` validation commands once `uv` is available locally. |

## Open questions

- Should local validation be rerun after `uv` is installed on this machine, or is CI alignment sufficient for this task?

## Follow-up debt

- Local validation depends on `uv` being installed in the shell environment; if absent after doc/CI alignment, keep that blocker documented rather than inventing a non-`uv` fallback.
