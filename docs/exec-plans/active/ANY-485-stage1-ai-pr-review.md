# Execution Plan: ANY-485 Stage 1 AI PR Review

## Status

- State: active
- Owner: agent
- Created: 2026-09-13
- Last updated: 2026-09-13
- Review date: 2026-09-13
- Next action: add workflow/config files and verify the PR checks stay informational.
- Blocker: none

## Goal

Add an informational AI PR Review workflow for Stage 1 that runs after the existing
`baseline-backend` workflow on pull requests, or manually for a supplied PR number, without making
AI PR Review a required check.

## Scope

### In scope

- Add `.github/ai-review.yml` with the existing agent policy docs as always-read context.
- Add `.github/workflows/ai-pr-review.yml` as a thin caller of the reusable AI PR Review workflow
  pinned to `660525298b8785158fc8339add65f0e5cd87e749`.
- Forward only `QWEN_TOKEN_PLAN_API_KEY`, `LINEAR_CLIENT_ID`, and `LINEAR_CLIENT_SECRET`.
- Validate static invariants, repository checks, secret-name readiness, and PR CI.

### Out of scope

- Changes to `.github/workflows/backend.yml`.
- Branch protection, rulesets, or required-check configuration.
- Duplicating the AI PR Review engine architecture in this repo.

## Relevant docs

- `AGENTS.md`
- `docs/agent/coding-conventions.md`
- `docs/agent/review-checklist.md`

## Contracts touched

- API: none
- DB: none
- Config: `.github/ai-review.yml`
- Events: none
- Frontend: none
- CI: `.github/workflows/ai-pr-review.yml`

## Implementation steps

- [ ] Add AI Review config.
- [ ] Add thin workflow caller pinned to the frozen engine SHA.
- [ ] Run local static and repo validation.
- [ ] Push a PR and verify CI against the exact PR head SHA.
- [ ] Run or observe a live PR smoke of AI PR Review, if secrets and workflow permissions allow it.

## Validation

- [ ] Static invariant checks for engine SHA, forbidden refs/secrets, and forwarded secret names.
- [ ] `python scripts/agent/runner.py doctor`
- [ ] `python scripts/agent/runner.py quick-check`
- [ ] `python scripts/agent/runner.py validate-configs`
- [ ] `python scripts/agent/runner.py validate-architecture`
- [ ] Repo-supported YAML/workflow validation.
- [ ] `gh secret list -R gushinets/anytoolai-platform` confirms required secret names are present.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-13 | Keep the consumer workflow as a thin reusable-workflow caller. | Stage 1 should integrate the existing engine without duplicating review logic or central architecture. |
| 2026-09-13 | Trigger only after `baseline-backend` plus manual dispatch. | This keeps AI PR Review informational and avoids changing the primary backend gate. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-13 | Created the Stage 1 plan before workflow/config edits. | Add files and validate. |

## Open questions

- None.

## Follow-up debt

- Move this plan to `completed/` after the PR lands and live smoke evidence is recorded.
