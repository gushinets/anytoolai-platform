# Execution Plan: UV Agent Instructions And CI Alignment

## Status

- State: active
- Owner: agent
- Created: 2026-06-22
- Last updated: 2026-06-22

## Goal

Make `uv` the explicit Python package-management rule for agents, remove contradictory repo guidance, and align Python CI setup with the repo's `uv` workflow.

## Scope

### In scope

- Update agent-facing docs to require `uv` for Python dependency management and repo check commands.
- Add durable `uv` operating guidance to `docs/agent/codex-operating-model.md`.
- Update GitHub backend workflows to use `uv` environment setup and `uv run`.
- Re-scan repo guidance for stale `pip` package-management instructions.

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

## Validation

- [x] Stale Python package-manager guidance scan across agent docs, repo docs, workflows, and scripts. Only the explicit "should not generate `pip install` commands" guidance remains.
- [ ] `uv run python scripts/agent/runner.py doctor` (`uv` is not installed in the local shell environment)
- [ ] `uv run python scripts/agent/runner.py quick-check` (`uv` is not installed in the local shell environment)

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-22 | Keep the change scoped to agent guidance plus CI command alignment. | The user asked for a durable operational rule and removal of contradictory instructions, not a broader packaging redesign. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-22 | Read the required architecture/docs set, confirmed `just` is unavailable locally, and inspected current agent docs plus GitHub workflows for Python command usage. | Patch the docs and workflows, then re-run repo scans and available validation. |
| 2026-06-22 | Updated `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `docs/agent/codex-operating-model.md`, and `.github/workflows/backend.yml` to standardize on `uv` for Python dependency management and repo checks. | Finish validation; local `uv run` commands remain blocked until `uv` exists in the shell environment. |

## Open questions

- Should local validation be rerun after `uv` is installed on this machine, or is CI alignment sufficient for this task?

## Follow-up debt

- Local validation depends on `uv` being installed in the shell environment; if absent after doc/CI alignment, keep that blocker documented rather than inventing a non-`uv` fallback.
