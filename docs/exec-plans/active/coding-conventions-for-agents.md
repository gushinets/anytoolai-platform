# Execution Plan: Coding Conventions For Agents

## Status

- State: active
- Owner: agent
- Created: 2026-08-19
- Last updated: 2026-09-04
- Review date: 2026-09-04
- Next action: obtain required human approval and merge PR #83.
- Blocker: none

## Goal

Give coding agents one operational conventions document, linked from the existing agent map, so new
and changed code stays typed, fail-fast, and reviewable without adding a root `rules.md`.

## Scope

### In scope

- `docs/agent/coding-conventions.md` with Shared / Backend / Frontend sections.
- Links from `AGENTS.md` Agent style, `docs/index.md`, `docs/agent/review-checklist.md`, and
  `.github/pull_request_template.md`.
- Add `agent/coding-conventions.md` to `REQUIRED_INDEX_LINKS` in `scripts/agent/validate_docs.py`.
- Keep the trusted PR metadata workflow on the current default-branch SHA for stale PR events.

### Out of scope

- Production runtime, API schemas, CE-kit parsers, OpenAPI regeneration.
- PydanticAI `output_type` binding.
- Ruff/mypy/frontend lint rollout.
- Config loader rewrite.
- Choosing a single Core/SDK enum owner.

## Relevant docs

- `../../core-beliefs.md`
- `../../adr/0003-short-agents-md.md`
- `../../architecture/structured-output.md`
- `../../architecture/llm-runtime.md`
- `../../architecture/package-layering.md`
- `../../architecture/frontend-boundaries.md`
- `../../architecture/config-model.md`
- `../template.md`

## Contracts touched

- API: none
- DB: none
- Config: trusted GitHub PR metadata workflow checkout only
- Events: none
- Frontend: none

## Implementation steps

- [x] Write `docs/agent/coding-conventions.md` as operational do/don't for new and changed code.
- [x] Link it from `AGENTS.md` Agent style, not the Start-here reading list.
- [x] Index it from `docs/index.md` and require the index link in `validate_docs.py`.
- [x] Add review-checklist and PR-template checks.
- [x] Run `validate-docs` and `generate-docs --check`.
- [x] Rebase PR #83 onto current `origin/main` without restoring stale pre-#98 metadata.
- [x] Update the PR body to the dedicated `## Linear issue` format.
- [x] Fix the stale-PR metadata workflow checkout exposed by the live canary.
- [x] Re-run current repository and GitHub validation.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] `python scripts/agent/runner.py validate-docs`
- [x] `python scripts/agent/runner.py generate-docs --check` — generated documentation is current
  in the repository-managed locked environment.
- [x] `python scripts/agent/runner.py quick-check` — 986 passed, 3 skipped, 397 deselected.
- [x] Focused documentation and PR metadata tests: 13 passed.
- [x] GitHub required checks, including `Linear PR metadata`.
- [x] Manual check: no production source files changed.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-19 | One document with Shared / Backend / Frontend; no root `rules.md`. | ADR 0003 keeps `AGENTS.md` as a map. |
| 2026-08-19 | Core/SDK enum duplication stays a checked mirror, not a new contracts package. | `platform-core` must not import `platform-sdk`; A01 already tests value equality. |
| 2026-08-19 | Do not name PydanticAI helpers such as `StructuredDict` in conventions. | Typed binding belongs in `llm-runtime.md` / ADR 0007. |
| 2026-08-19 | Field lists, A18 handoff parser deferral, and `closedEnums.ts` location stay out of this file. | Those are the second PR's execution plan, not durable style rules. |
| 2026-09-03 | Check out `github.sha` in the `pull_request_target` metadata job. | GitHub defines it as the current default-branch commit; the stale PR payload's historical `base.sha` predated the validator. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-19 | Plan created after the conventions review. | Write the document and authority links. |
| 2026-08-19 | Document, authority links, and `REQUIRED_INDEX_LINKS` landed. `validate-docs` and uv `generate-docs --check` passed. | Review and commit when requested. |
| 2026-09-03 | Rebased the two ANY-337 commits onto `a316d9a3` (`origin/main`, including PR #98); no conflicts occurred and the seven-file diff stayed in scope. | Update PR metadata and run current validation. |
| 2026-09-03 | Live metadata canary failed at historical base `337699a` because the validator did not exist there; switched the trusted checkout to current default-branch `github.sha`. | Push the rebased branch and verify the synchronize run. |
| 2026-09-03 | `doctor`, `validate-docs`, generated-doc check, 13 focused tests, and quick-check passed in the repository-managed environment; quick-check reported 986 passed, 3 skipped, and 397 deselected. | Verify GitHub after the final plan update. |
| 2026-09-04 | Required GitHub checks passed on the rebased PR, including metadata, full-check, atoms proof, PostgreSQL concurrency, Windows, and production Compose smoke. | Obtain required human approval and merge. |

## Open questions

None. Architectural blockers were closed in review; remaining HTTP enum work is a later plan.

## Follow-up debt

- Behavioral PR: Core enum on closed HTTP fields → OpenAPI enum → generated TS unions, last-mile
  CE-kit DTO/parser guards, OpenAPI enum tests, negative parser tests. Handoff stops at API/OpenAPI
  until A18 has a real client. Share quota closed-set aliases once.
- Later: PydanticAI typed output binding; Ruff config unification and gated rollout; real frontend
  lint; mypy; config-loader shape models.
