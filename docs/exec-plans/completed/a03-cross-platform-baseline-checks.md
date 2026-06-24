# Execution Plan: Cross-Platform Baseline Checks

## Status

- State: completed
- Owner: agent
- Created: 2026-06-16
- Last updated: 2026-06-24

## Goal

Make the baseline backend checks reproducible through one canonical Python command on Windows PowerShell and Linux CI, without manual `PYTHONPATH`.

## Scope

### In scope

- Treat `python scripts/agent/quick_check.py` as the canonical baseline command.
- Keep `runner.py quick-check` as a thin compatibility wrapper, not the canonical path.
- Make wrappers and GitHub Actions call the same baseline implementation.
- Keep baseline scope limited to config validation, architecture validation, and the DB-free backend pytest subset.
- Align repo docs and execution-plan evidence with the actual command surface.

### Out of scope

- Frontend checks as part of the blocking baseline.
- DB-backed integration coverage in `quick-check`.
- Broad runner/tooling redesign beyond baseline command alignment.

## Relevant docs

- `README.md`
- `AGENTS.md`
- `docs/agent/codex-operating-model.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none
- Config: CI/workflow command wiring only
- Events: none
- Frontend: none

## Implementation steps

- [x] Keep `scripts/agent/quick_check.py` as the baseline implementation and source of truth.
- [x] Point `just` and `make` quick-check wrappers at `quick_check.py` directly.
- [x] Update backend GitHub Actions to run the canonical baseline command directly on Linux and Windows.
- [x] Add push coverage for `main` to the backend workflow.
- [x] Exclude nested virtualenv/cache directories from architecture scans and focused architecture tests.
- [x] Align `README.md`, `AGENTS.md`, and `docs/agent/codex-operating-model.md` with the canonical command.
- [x] Record final local validation evidence and move the plan to `completed/`.

## Validation

- [x] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py quick-check`
- [x] `.quick-check-venv\Scripts\python.exe -m pytest tests\test_quick_check.py tests\test_runner.py tests\architecture -q`
- [x] `.quick-check-venv\Scripts\python.exe scripts\agent\validate_architecture.py`
- [x] `python scripts/agent/runner.py full-check`
- [x] `.github/workflows/backend.yml` inspection confirms:
  - baseline matrix runs `python scripts/agent/quick_check.py` on `ubuntu-latest` and `windows-latest`
  - workflow triggers on both `pull_request` and `push` to `main`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-24 | Make `python scripts/agent/quick_check.py` the canonical baseline command. | A03 requires one human-facing command that matches CI and does not depend on wrapper-specific behavior. |
| 2026-06-24 | Keep `runner.py quick-check` as a supported wrapper only. | Existing users can keep the command, while docs and CI stay anchored on the direct baseline entrypoint. |
| 2026-06-24 | Add `push` coverage for `main` in the backend workflow. | The required green signal should exist for merged `main` commits, not only for PRs. |
| 2026-06-24 | Exclude nested venv/cache directories from architecture scans. | Local tooling output is not repo source and was causing false-positive baseline failures. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-24 | Confirmed the remaining A03 gaps: CI still used a runner-only baseline path, backend workflow was PR-only, and the active plan no longer reflected repo reality. | Rewire CI and docs to the canonical direct command. |
| 2026-06-24 | Found that local architecture validation still recursed into nested `.venv` and `.uv-cache` directories, causing false positives unrelated to repo source. | Tighten architecture scan exclusions and re-run focused validation. |
| 2026-06-24 | Updated wrappers, docs, workflow triggers, and architecture scan exclusions; re-ran focused tests plus the canonical baseline command and wrapper successfully. | Move plan to completed with final evidence. |

## Open questions

- None.

## Remaining limitation

- Remote GitHub Actions execution was not observed from this local workspace, so CI evidence here is limited to workflow-definition inspection plus successful local command parity.
