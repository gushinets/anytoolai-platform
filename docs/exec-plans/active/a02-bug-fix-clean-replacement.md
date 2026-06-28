# Execution Plan: A02 Bug Fix Clean Replacement Branch

## Status

- State: active
- Owner: agent
- Created: 2026-06-28
- Last updated: 2026-06-28

## Goal

Create a clean replacement branch for PR #16 from its current base, carrying only the final loader/config validation fixes and their supporting tests/docs without the old merge commit or transient CI/debug commits.

## Scope

### In scope

- Identify the current base commit for PR #16 from local git state.
- Recreate the final intended file state on a fresh branch.
- Keep commit history small and understandable.
- Run repo validation with the documented fallback commands.
- Push the replacement branch.

### Out of scope

- Rewriting `main`
- Repairing or force-pushing the existing `feature/a02-bug-fix` branch
- Changing the functional scope of the final fix

## Relevant docs

- `ARCHITECTURE.md`
- `docs/index.md`
- `docs/core-beliefs.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/package-layering.md`
- `docs/architecture/llm-runtime.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none
- Config: config loader manifests, product config references, provider/prompt/schema validation
- Events: none
- Frontend: none

## Implementation steps

- [x] Confirm PR #16 base and isolate the final net diff from `feature/a02-bug-fix`.
- [x] Create `feature/a02-bug-fix-clean` from the PR base and apply only the final required file changes.
- [x] Validate with `uv run python scripts/agent/runner.py doctor` and `uv run python scripts/agent/runner.py full-check`, then push the clean branch.
- [x] Harden missing-file diagnostics so `MissingConfigFileError` carries structured context and escaped config errors are preserved in `RegistryLoadError.errors`.
- [x] Reproduce PR #19's GitHub merge ref and verify the actual PR head branch at `b3a411c0b51b1d7515df47f4bd651828875a512d`.
- [x] Run `uv run python scripts/agent/runner.py full-check` on the PR #19 merge ref and patch the PR source branch if the merge ref fails.

## Validation

- [x] `uv run python scripts/agent/runner.py doctor`
- [x] `uv run python scripts/agent/runner.py full-check`
- [x] `.venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit/test_config_loader.py -q`
- [x] `.venv\Scripts\python.exe -m pytest packages/backend/platform-core/tests/unit -k config`
- [x] `.venv\Scripts\python.exe scripts/agent/validate_configs.py`
- [x] `python scripts/agent/quick_check.py`
- [x] `python scripts/agent/runner.py quick-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-28 | Rebuild the branch from the PR base instead of cleaning existing history. | The current feature branch contains a manual merge commit and transient commits that make the PR/CI state hard to reason about. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-28 | Read required repo orientation docs, inspected local git graph, and confirmed `pr-16-merge` merges `feature/a02-bug-fix` into `origin/main` commit `d3af7e0`. | Create the clean branch from `d3af7e0` and replay only the final file state. |
| 2026-06-28 | `just doctor` unavailable in this shell; `uv run ... quick-check` also hit a local `uv` cache permission error under `C:\\Users\\jackd\\AppData\\Local\\uv\\cache`. | Retry validation with escalation and a workspace-owned `UV_CACHE_DIR` if needed. |
| 2026-06-28 | User reported quick-check failures around missing-file diagnostics and constructor compatibility; focused loader tests currently pass under the repo virtualenv. | Patch the implementation to make the structured diagnostic behavior explicit and rerun the requested validation ladder. |
| 2026-06-28 | Added shared required-file helpers and hardened top-level registry error preservation; focused config tests, config validation, `quick_check.py`, and `runner.py quick-check` pass. | Commit and push the follow-up fix to the clean branch. |
| 2026-06-28 | User reported PR #19 CI still checks merge commit `75d9a76` from PR head `b3a411c`, not old `origin/feature/a02-bug-fix`. | Fetch and validate the PR #19 merge ref directly, then patch the actual PR source branch if needed. |
| 2026-06-28 | Fetched `pull/19/merge` as `pr-19-merge`, confirmed it resolves to `75d9a76ba935934ccf5806ef29c5982f1f7527b4`, and confirmed `origin/feature/a02-bug-fix-clean` points to `b3a411c0b51b1d7515df47f4bd651828875a512d`. | No source patch needed; `uv run python scripts/agent/runner.py full-check` passes on the PR #19 merge ref. |

## Open questions

- None currently; local git state is sufficient to determine the replacement branch base.

## Follow-up debt

- None for this cleanup branch beyond normal PR review.
