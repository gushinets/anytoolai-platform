# Execution Plan: ANY-485 Stage 1 AI PR Review

## Status

- State: active
- Owner: agent
- Created: 2026-09-13
- Last updated: 2026-09-13
- Review date: 2026-09-13
- Next action: receive human merge approval, merge the exact reviewed PR head, then run the real automatic Stage 1 smoke.
- Blocker: human merge approval.
- Live smoke: incomplete until the workflow exists on main and a post-merge pull request can trigger workflow_run.

## Goal

Add an informational AI PR Review workflow for Stage 1 that runs after the existing baseline-backend workflow on pull requests, or manually for a supplied PR number, without making AI PR Review a required check.

## Scope

### In scope

- Add .github/ai-review.yml with the existing agent policy docs as always-read context.
- Add .github/workflows/ai-pr-review.yml as a thin caller of the reusable AI PR Review workflow pinned to 660525298b8785158fc8339add65f0e5cd87e749.
- Forward only QWEN_TOKEN_PLAN_API_KEY, LINEAR_CLIENT_ID, and LINEAR_CLIENT_SECRET.
- Validate static invariants, repository checks, secret-name readiness, and PR CI.
- After merge approval and merge, run a real automatic Stage 1 smoke from baseline-backend to AI PR Review.

### Out of scope

- Changes to .github/workflows/backend.yml.
- Branch protection, rulesets, or required-check configuration.
- Duplicating the AI PR Review engine architecture in this repo.
- Moving this plan to completed/ before post-merge live smoke evidence exists.

## Relevant docs

- AGENTS.md
- docs/agent/coding-conventions.md
- docs/agent/review-checklist.md

## Contracts touched

- API: none
- DB: none
- Config: .github/ai-review.yml
- Events: none
- Frontend: none
- CI: .github/workflows/ai-pr-review.yml

## Implementation steps

- [x] Add AI Review config.
- [x] Add thin workflow caller pinned to the frozen engine SHA.
- [x] Run local static and repo validation.
- [x] Verify secret-name readiness.
- [x] Push the integration branch.
- [x] Open PR #116.
- [x] Verify exact-head GitHub CI.
- [ ] Receive human merge approval.
- [ ] Merge the exact reviewed PR head.
- [ ] Run or observe a real automatic Stage 1 smoke after merge.

## Validation

- [x] Static invariant checks for engine SHA, forbidden refs/secrets, and forwarded secret names.
- [x] python scripts/agent/runner.py doctor passed.
- [x] python scripts/agent/runner.py quick-check passed: 1238 passed, 3 skipped, 451 deselected.
- [x] python scripts/agent/runner.py validate-configs passed.
- [x] python scripts/agent/runner.py validate-architecture passed.
- [x] YAML parse for .github/ai-review.yml and .github/workflows/ai-pr-review.yml passed.
- [x] gh secret list -R gushinets/anytoolai-platform confirmed the required secret names are present.
- [x] GitHub CI on PR head ed17fba1d4ad05f3a4abbc99474ac5deaea05c21 completed successfully.
- [ ] Post-merge live automatic Stage 1 smoke.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-13 | Keep the consumer workflow as a thin reusable-workflow caller. | Stage 1 should integrate the existing engine without duplicating review logic or central architecture. |
| 2026-09-13 | Trigger only after baseline-backend plus manual dispatch. | This keeps AI PR Review informational and avoids changing the primary backend gate. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-13 | Created the Stage 1 plan before workflow/config edits. | Add files and validate. |
| 2026-09-13 | Added .github/ai-review.yml and .github/workflows/ai-pr-review.yml. | Verify local and remote gates. |
| 2026-09-13 | Static validation, doctor, quick-check, validate-configs, validate-architecture, secret-name readiness, PR #116, and exact-head GitHub CI are complete. | Wait for human merge approval, then run post-merge automatic Stage 1 smoke. |

## Open questions

- None.

## Follow-up debt

- Move this plan to completed/ only after the PR lands and live smoke evidence is recorded.
