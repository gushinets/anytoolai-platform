# Execution Plan: Quick-Check Bootstrap Reproducibility

## Status

- State: completed
- Owner: agent
- Created: 2026-07-13
- Last updated: 2026-07-13

## Goal

Make the canonical quick-check bootstrap reproducible from an empty managed environment by using the
repo's locked dependency set instead of re-resolving floating third-party versions during the root
install.

## Scope

### In scope

- `scripts/agent/quick_check.py` bootstrap/install flow.
- Focused quick-check bootstrap regression coverage.
- Fresh-environment validation for `quick_check.py` and `runner.py quick-check`.

### Out of scope

- Broad dependency upgrades or lockfile refresh.
- CI-only workarounds that do not fix the canonical bootstrap path.
- Runtime behavior changes outside the quick-check harness.

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/agent/codex-operating-model.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none
- Config: none
- Events: none
- Frontend: none
- Tooling: quick-check must bootstrap deterministically from repository-managed dependency state

## Implementation steps

- [x] Inspect quick-check bootstrap, runner wrapper, root dependency declarations, and lock usage.
- [x] Replace floating root install bootstrap with a lock-driven install path.
- [x] Update focused bootstrap regression tests.
- [x] Recreate the managed quick-check environment from empty and run the canonical validation commands.
- [x] Record summary and handoff details.

## Validation

- [x] `uv run python -m pytest tests/test_quick_check.py -q` (with workspace-owned `UV_CACHE_DIR` because the local global uv cache ACL is broken)
- [x] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-07-13 | Prefer a lock-driven quick-check bootstrap over adding more ad hoc build requirements. | The reported failure is caused by fresh dependency resolution drifting away from the repo's pinned `uv.lock`, so the most reliable fix is to stop re-resolving the root graph during bootstrap. |
| 2026-07-13 | Export `VIRTUAL_ENV` from the managed quick-check process before invoking `uv sync --active`. | Quick-check re-enters the venv by executing its Python directly, which updates `sys.prefix` but does not set the shell variable `VIRTUAL_ENV` that `uv sync --active` uses to target the intended environment. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-07-13 | Confirmed `quick_check.py` still uses `uv pip install --no-build-isolation -e .`, which bypasses the root `uv.lock` and can resolve `litellm==1.92.0` instead of the pinned `1.89.3`. | Patch the bootstrap to sync from the lock, then validate from a fresh managed environment. |
| 2026-07-13 | Replaced the floating root install with `uv sync --locked --no-default-groups --group dev`, kept repo packages as editable `--no-deps` installs, and added focused regression coverage for the locked bootstrap plus managed-venv export. | Recreate `.quick-check-venv` from empty and run both canonical quick-check entrypoints. |
| 2026-07-13 | Fresh `python scripts/agent/quick_check.py` and `python scripts/agent/runner.py quick-check` both passed from a rebuilt `.quick-check-venv`, and the cold bootstrap installed `litellm==1.89.3` from the root lock instead of drifting to `1.92.0`. | No further work for this task. |

## Open questions

- None at the moment.

## Follow-up debt

- If the repo later adopts a workspace-wide lock-driven install for local packages too, re-evaluate whether the extra editable-package bootstrap loop is still necessary.
