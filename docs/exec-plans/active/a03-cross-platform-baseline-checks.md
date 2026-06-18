# Execution Plan: Cross-Platform Baseline Checks

## Status

- State: in_progress
- Owner: agent
- Created: 2026-06-16
- Last updated: 2026-06-18

## Goal

Make baseline backend checks reproducible through one Python-owned command on Windows PowerShell and Linux CI, without manual `PYTHONPATH`.

## Scope

### In scope

- Add `scripts/agent/quick_check.py` as the canonical baseline implementation entrypoint.
- Make `runner.py`, shell wrappers, and GitHub Actions delegate to the same baseline logic.
- Replace quick-check `PYTHONPATH` injection with editable install bootstrap.
- Define and document the exact backend-only baseline pytest subset.
- Update agent/user docs to describe the canonical command surface and baseline scope.

### Out of scope

- Frontend typecheck/build as part of the blocking baseline.
- `tests/e2e`, kernel smoke, or DB-backed checks in quick-check.
- New package managers or a broad dev-tooling rewrite.
- Packaging `freelancer-suite` for inclusion in baseline.

## Relevant docs

- `AGENTS.md`
- `README.md`
- `docs/agent/harness-engineering-map.md`
- `docs/architecture/package-layering.md`

## Contracts touched

- API: none
- DB: none
- Config: CI/workflow command wiring only
- Events: none
- Frontend: docs only; frontend workflow remains separate

## Implementation steps

- [x] Add `scripts/agent/quick_check.py` to bootstrap editable installs and run baseline checks in a fixed order.
- [x] Update `scripts/agent/runner.py` quick-check handling so it delegates to the new entrypoint without `PYTHONPATH`.
- [x] Update CI workflows to run the same baseline command in a Linux/Windows matrix and remove split duplicate backend/config/architecture workflows.
- [x] Update `README.md` and `AGENTS.md` with baseline scope, fallback commands, and DB-free expectations.
- [x] Run baseline validation locally with the new command and record any environment blockers.

## Validation

- [x] `python3.12 scripts/agent/quick_check.py`
- [ ] `python3 scripts/agent/runner.py quick-check`
- [ ] `python3 scripts/agent/runner.py full-check`
- [ ] `python3 -m pytest tests/test_runner.py tests/test_quick_check.py`
- [ ] `just quick-check` blocked locally because `just` is not installed in this shell

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-16 | Keep quick-check backend-only. | Frontend reproducibility already has separate workflow concerns and would widen the P0 slice. |
| 2026-06-16 | Use editable installs instead of `PYTHONPATH`. | The task explicitly requires removing manual path injection while keeping one Python-owned flow. |
| 2026-06-16 | Keep `just quick-check` as the preferred human command. | `python` binary naming is not stable across platforms, while `just` is a simple human-facing wrapper. |
| 2026-06-18 | Preserve `runner_env()` path injection for legacy commands, but bypass it for `quick-check` and `full-check`. | The A03 contract is specifically about the canonical baseline and its direct wrappers proving editable installs work without `PYTHONPATH`. |
| 2026-06-18 | Strip `PYTHONPATH` inside `quick_check.py` itself, not only in `runner.py`. | Direct `just quick-check` and `make quick-check` must also prove the editable-install baseline works without caller-provided path injection. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-16 | Reviewed architecture docs, runner/wrappers, package metadata, and current workflows. Confirmed quick-check currently depends on `runner.py` `PYTHONPATH` and CI is split across duplicate workflows. | Implement the Python baseline entrypoint and rewire command surfaces. |
| 2026-06-16 | Ran `python3 scripts/agent/runner.py doctor`; local shell has Python 3.10 and lacks `pytest`/`pyyaml`. | Use the new quick-check bootstrap to install dependencies, then run validation. |
| 2026-06-16 | Implemented Python-owned quick-check, switched package installs to editable mode, added self-managed quick-check virtualenv, rewired runner/CI/docs, and updated `justfile` to use `python3` or `py -3` by platform. | Validate sequentially with the new entrypoint and close the plan. |
| 2026-06-16 | `python3.12 scripts/agent/quick_check.py`, `python3.12 scripts/agent/runner.py quick-check`, and `python3.12 scripts/agent/runner.py full-check` passed. Local `just quick-check` could not be executed here because `just` is not installed. | Move plan to completed. |
| 2026-06-16 | Follow-up review found two gaps: quick-check could stay inside an unrelated active virtualenv, and docs did not spell out the `full-check`/test DB contract. Tightened re-exec semantics and documented that `quick-check` stays DB-free while DB-backed e2e must use an explicit test-only DB contract. | Re-run validation and close the review follow-up. |
| 2026-06-16 | PR review found that narrowing `full-check` to `tests/e2e` dropped `freelancer-suite` bundle coverage. Added packaging metadata for the product bundle and restored that test to `full-check` without expanding baseline quick-check. | Re-run `full-check` and keep baseline scope unchanged. |
| 2026-06-16 | Additional review flagged two bootstrap hygiene issues: stale unsupported quick-check venvs could survive across Python upgrades, and editable installs left `*.egg-info` metadata visible in the worktree. Added Python-version validation/recreation behavior for the quick-check venv and ignored editable-install metadata. | Re-run quick-check/full-check and verify git status stays clean. |
| 2026-06-16 | Follow-up review flagged that nesting quick-check under `.venv/quick-check` confused `uv` by making `.venv` exist without being a real project virtualenv. Moved the bootstrap environment to `.quick-check-venv`, updated repo docs, and added cleanup of the legacy nested path. | Re-run quick-check/full-check and confirm the legacy nested path no longer remains after bootstrap. |
| 2026-06-16 | Another review found that architecture scans still skipped only `.venv`, so moving the bootstrap environment to `.quick-check-venv` could make repo scans recurse into third-party site-packages. Updated the provider-import architecture test to exclude `.quick-check-venv` explicitly. | Re-run the focused architecture test and keep future scan exclusions aligned with bootstrap path changes. |
| 2026-06-18 | Follow-up review found one remaining A03 mismatch: `runner.py quick-check` still inherited `PYTHONPATH` through `runner_env()`, and `just`/`make` still routed through that path. | Narrow the fix to baseline entrypoints, add a regression test, and leave other runner commands unchanged for now. |
| 2026-06-18 | Implemented the narrow follow-up: `quick-check` and `full-check` now run with a baseline env that strips `PYTHONPATH`, and `just`/`make` quick-check call `quick_check.py` directly. | Re-run the affected entrypoints once `uv` and `pytest` are available in the local environment. |
| 2026-06-18 | Additional MR review pointed out that direct `quick_check.py` invocation still inherited caller `PYTHONPATH` through `runtime_env()`. Updated `quick_check.py` to strip `PYTHONPATH` for all bootstrap/runtime subprocesses and added a focused regression test for the direct invocation path. | Re-run the focused regression tests and canonical baseline entrypoints when the bootstrap tools are available locally. |

## Open questions

- None at implementation start.

## Current blockers

- Local shell does not have `just`.
- Local shell does not have `uv`, so `quick_check.py` bootstrap stops before dependency install.
- Local `python3` and `python3.12` do not have `pytest`, so the focused regression tests could not be executed outside the bootstrap flow.

## Follow-up debt

- Decide later whether `freelancer-suite` should become an installable package and join the baseline.
- Revisit frontend blocking checks in a separate slice once dependency bootstrap is standardized.
