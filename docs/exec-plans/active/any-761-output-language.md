# ANY-761: Brief Decoder and Acceptance Builder output language

## Status

- State: active
- Owner: agent
- Created: 2026-11-10
- Last updated: 2026-11-10
- Review date: 2026-11-10
- Next action: Required CI and owner review for the reviewed follow-up revision.
- Blocker: Current-revision CI and owner approval pending.
- Current PR: https://github.com/gushinets/anytoolai-platform/pull/265
- Experiment and AC report: [issue comment](https://linear.app/paveldik/issue/ANY-761#comment-2c6c63bc-f1da-4494-9c29-aca4c8310ef1); duplicated in the PR description.
- Raw experiment captures are retained locally outside git; they are not a repository deliverable.

## Goal and actual acceptance scope

Keep all authored result prose in the source brief's language unless the client explicitly
requests another analysis language. UI locale and deliverable language are independent.
Preserve quotations, brands, technical identifiers, facts and structured verdict/status.
Regress full canonical output, including hidden fields, and preserve unsuccessful experimental
outcomes in the published report. A date/budget need not appear specifically in criteria.
Missing historical QA originals are a non-blocking evidence limit per the owner.

## Implementation plan

- [x] Apply one product-owned language policy to every BD/AB LLM step. Each step uses the
  original brief, including BD's final document via the existing open data mapping.
- [x] Keep the existing pre-production AB v1 contract. Require analysis-language metadata;
  remove AB's independent model document and its two A10 calls. Draft uses A01, Check A01+A11.
- [x] Generate AB recap and Copy from the same structured authority and language metadata.
  Preserve upstream items/evidence/rationale; enforce verdict/status and missing-list invariants.
  Do not restore English prose constraints. Wording covers seven app languages, with neutral
  markers for others. Development artifacts without language metadata are unsupported.
- [x] Add RU/EN/ES canonical fixtures and workflow/API/client regressions for weak extraction,
  quotes, mixed input, explicit overrides, hidden fields, Copy and contradictory recap.
- [x] Compare corrected AB Luna with Sol before model selection. Keep Sol/medium for AB through
  backend deployment generation/activation; BD and other products retain default Luna.
- [x] Run bounded synthetic live experiments and real RU-analysis/EN-UI browser/clipboard checks.
  Keep initial FAIL, candidate comparison and final evidence distinct in the published report.
- [x] Publish the complete experiment and remaining caveats in the issue comment and PR,
  rather than committing raw JSON/ledger/screenshot directories.
- [ ] Require CI and owner approval for the reviewed follow-up revision.

## Verification and limits

Latest contract correction: 375 Python tests, 467 web tests, web lint/typecheck passed.
Final read-only review: 286 targeted API/language/profile/activation tests passed. These test
sets overlap; counts are not additive. Earlier canonical frontend-check passed lint/typecheck,
generated API-contract check, builds and frontend/browser tests. Config/architecture/docs/
generated/whitespace checks passed. Full local baseline was delegated to CI by the owner.
The earlier green PR checks belong to head 0f273b8e and do not validate this follow-up.

Final selected language evidence: BD Luna24/24 plus AB Sol48/48 and three additional live AB
browser/clipboard journeys. Changing temporary v2 names back to v1 did not change schema bodies
or prompts: all75 saved AB payloads replayed against current schemas. This was offline contract
replay, not a new live deployment. Full experiment stages, failures, costs, selection rationale
and AC mapping belong in the external report, not this execution plan.

Additional budget/date omissions, BD renovation-budget semantics, mixed HTML judgment and
the earlier no-question runtime failure remain outside the authorized language correction.
Agent semantic assessment is finite; independent human QA and production rollout are unclaimed.
Isolated stack stopped with volumes retained; router restored and checked against the repository.


## Implementation plan — SonarCloud path traversal

The CLI currently interpolates suite case IDs and manifest run keys into filesystem paths.
Use one product-evidence filename boundary in both run/report: permit only the existing ASCII
JSON filename format, resolve it beneath the chosen output directory, and reject escapes before
reading/writing evidence. Preflight all planned run names before Docker/provider calls or output
directory creation. Keep JSON content as data through json.dump, and create evidence files
exclusively so failures/duplicates cannot overwrite captures. Add negative CLI regressions for
POSIX/Windows traversal, absolute names and malformed names, plus a normal run/review/report
round trip and overwrite protection. No prompt/model/output-contract changes or paid live runs.
Verify targeted tests, lint/docs/config checks, commit and push on feature/ANY-761; inspect the
new Sonar result without suppressing or resolving the finding manually.

Path traversal correction validated:96 targeted collector/product tests passed, including
unsafe suite IDs, manifest keys, ordinary review flow, overwrite protection and resolved-path
escapes. Real filesystem symlink checks passed locally for manifest/result/review. Ruff and
config/architecture/docs/generated/whitespace checks passed. No provider calls or product/prompt
changes; full baseline delegated to CI. Commit/push authorized; Sonar reanalysis remains pending.


## Implementation plan — mobile smoke recap states

The first text match now belongs to the collapsed structured recap. Scope the mobile long-token
assertion to the result region's copy paragraph, assert the recap starts collapsed, and verify
page width before and after opening the recap. Assert that the recap token becomes visible so
the expanded-width check cannot pass while content stays hidden. Keep product styling unchanged.
Run lint/typecheck and the complete canonical acceptance-builder-smoke against an isolated fake
provider dev stack, stop that stack with volumes retained, then commit/push on feature/ANY-761.
No new experiment directories or paid model calls.

Mobile smoke correction validated: canonical acceptance-builder-smoke passed11/11 in headless
Chromium against the isolated fake-provider stack, with no skips/retries. The long-token test
checked page width with recap collapsed and expanded and confirmed expanded token visibility.
Smoke-package lint/typecheck and web production build passed. Stack stopped with volumes
retained; no paid model calls or product styling changes. Commit/push authorized.
