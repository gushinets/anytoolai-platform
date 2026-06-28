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

- [ ] Confirm PR #16 base and isolate the final net diff from `feature/a02-bug-fix`.
- [ ] Create `feature/a02-bug-fix-clean` from the PR base and apply only the final required file changes.
- [ ] Validate with `uv run python scripts/agent/runner.py doctor` and `uv run python scripts/agent/runner.py full-check`, then push the clean branch.

## Validation

- [ ] `uv run python scripts/agent/runner.py doctor`
- [ ] `uv run python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-28 | Rebuild the branch from the PR base instead of cleaning existing history. | The current feature branch contains a manual merge commit and transient commits that make the PR/CI state hard to reason about. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-06-28 | Read required repo orientation docs, inspected local git graph, and confirmed `pr-16-merge` merges `feature/a02-bug-fix` into `origin/main` commit `d3af7e0`. | Create the clean branch from `d3af7e0` and replay only the final file state. |
| 2026-06-28 | `just doctor` unavailable in this shell; `uv run ... quick-check` also hit a local `uv` cache permission error under `C:\\Users\\jackd\\AppData\\Local\\uv\\cache`. | Retry validation with escalation and a workspace-owned `UV_CACHE_DIR` if needed. |

## Open questions

- None currently; local git state is sufficient to determine the replacement branch base.

## Follow-up debt

- None for this cleanup branch beyond normal PR review.
