# Execution Plan: Cross-Platform Baseline Checks

## Status

- State: completed
- Owner: agent
- Created: 2026-06-16
- Last updated: 2026-06-16

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
- [x] `python3.12 scripts/agent/runner.py quick-check`
- [ ] `just quick-check` blocked locally because `just` is not installed in this shell

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-16 | Keep quick-check backend-only. | Frontend reproducibility already has separate workflow concerns and would widen the P0 slice. |
| 2026-06-16 | Use editable installs instead of `PYTHONPATH`. | The task explicitly requires removing manual path injection while keeping one Python-owned flow. |
| 2026-06-16 | Keep `just quick-check` as the preferred human command. | `python` binary naming is not stable across platforms, while `just` is a simple human-facing wrapper. |

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

## Open questions

- None at implementation start.

## Follow-up debt

- Decide later whether `freelancer-suite` should become an installable package and join the baseline.
- Revisit frontend blocking checks in a separate slice once dependency bootstrap is standardized.
