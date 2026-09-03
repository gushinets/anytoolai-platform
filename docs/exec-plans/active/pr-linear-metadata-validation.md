# Execution Plan: PR Linear Metadata Validation

## Status

- State: active
- Owner: agent
- Created: 2026-09-03
- Last updated: 2026-09-03
- Review date: 2026-09-03
- Next action: merge PR #98 after review.
- Blocker: none

## Goal

Make PR-to-Linear issue resolution deterministic from a canonical PR title and one full Linear URL.

## Scope

### In scope

- Require `ANY-<number> - <summary>` PR titles.
- Require one full Linear issue URL in the PR template's Linear issue section.
- Compare the title and URL ticket identifiers in a credential-free GitHub Actions check.
- Add focused parser and validator tests.

### Out of scope

- Linear API access, AI review, comments, approvals, secrets, rulesets, and application behavior.

## Relevant docs

- Linear: `https://linear.app/paveldik/issue/ANY-409/enforce-deterministic-pr-to-linear-metadata-contract`
- `AGENTS.md`
- `docs/agent/harness-engineering-map.md`

## Contracts touched

- API: none
- DB: none
- Config: GitHub PR template and workflow metadata only
- Events: none
- Frontend: none

## Implementation steps

- [x] Add failing tests for valid metadata and each required invalid case.
- [x] Implement the minimum standard-library validator and make focused tests pass.
- [x] Update the PR template and add the PR metadata workflow.
- [x] Run focused tests and the repository baseline.

## Validation

- [x] `python scripts/agent/runner.py doctor`
- [x] focused PR metadata tests: 10 passed
- [x] Clean GitHub baseline: Ubuntu, Windows, `full-check`, PostgreSQL, atoms proof, and both
  Compose smoke jobs passed on PR #98.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-09-03 | Parse exactly one valid URL from the dedicated `## Linear issue` section. | Keeps the PR-ticket contract deterministic while allowing unrelated Linear links in follow-up debt. |
| 2026-09-03 | Use only Python's standard library. | The validation is small, deterministic, and needs no new dependency. |
| 2026-09-03 | Do not rewrite open PRs; validate them on their next edited, synchronize, or reopened event. | The workflow changes enforcement without mutating existing PR metadata or rulesets. |
| 2026-09-03 | Run the workflow via `pull_request_target` and check out only the base SHA. | PR-head code must not be able to weaken its own metadata gate. |
| 2026-09-03 | Ignore fenced Markdown and require exactly one rendered Linear section. | Code examples and duplicate sections must not create ambiguous metadata. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-09-03 | Design approved; repository and payments-portal precedent inspected. | Run doctor and start the failing-test cycle. |
| 2026-09-03 | Added the template contract, stdlib validator, workflow, and focused tests; scoped checks pass. | Rerun the full baseline from a clean checkout. |
| 2026-09-03 | Clean GitHub CI passed; review identified three metadata bypasses. Added trusted-base execution and two parser regressions. | Merge after review. |

## Open questions

None.

## Follow-up debt

None.
