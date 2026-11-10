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
