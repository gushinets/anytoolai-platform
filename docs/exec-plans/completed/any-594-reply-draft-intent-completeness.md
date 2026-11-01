# Execution Plan: ANY-594 Reply Draft Keeps Every Action From the Reply Goal

## Status

- State: completed
- Owner: agent
- Created: 2026-10-28
- Last updated: 2026-10-30
- Review date: 2026-10-30
- Next action: none for implementation or acceptance; parent Linear closure awaits owner approval.
- Blocker: none

## Goal

Reply Draft (QA Q-003) dropped content the freelancer asked for: R05 lost "I will send a corrected
invoice", R04 ignored the client's "don't add pages". The reply must state every fact, decision
and promised action from `intent` (`reply_goal`) and address every constraint the client states.

## Scope

- ANY-625: completeness rule in `reply_draft_compose_reply.v1.md`. It draws the boundary with the
  author-directions rule (ANY-619/620): a fact, decision or promised action in `intent` is content
  for the client; only a direction about how to write the reply is followed without being stated.
  The `situation` rule now names constraints (R04). A test pins the rule text.
- ANY-626: Reply Draft names what the client asks about in the client's own words and scope (R01
  "testimonials" became "any new comments or requests"; R04 narrowed "approve it" to the German
  text). The frontend appends `call_to_action` to `text` after a blank line, so both prompts that
  emit `call_to_action` (Reply Draft and Update) now state that the two fields are one message and
  each request appears in only one of them (R01, R02 repeated the final request). Prepaid Request
  emits no `call_to_action`; the issue's reference to a prepaid rule at
  `prepaid_request_compose_reply.v1.md:26-27` is stale (no such file). Tests pin the rule text.

## Out of scope

Frontend deduplication of `text` and `call_to_action`, the author-directions and speaker-identity
rules (ANY-619/620/629), subject and unit distortions in Update (ANY-593/ANY-623), Prepaid Request,
live acceptance (ANY-627).

## Implementation plan

- [x] Verify the merged ANY-625/626 prompt rules on the existing task branch.
- [x] Record reported ANY-627 results, Spanish observations and evidence limits.
- [x] Mark this plan completed and move it to the completed directory.
- [x] Run repo doctor, documentation validation and whitespace checks.

## Verification

- Documentation closure, 2026-10-30: `python scripts/agent/runner.py doctor` and
  `python scripts/agent/runner.py validate-docs` passed; `git diff --check` passed.
  No source, prompt or config changed, so backend/frontend suites were not rerun.

- ANY-625 merged in [PR #222](https://github.com/gushinets/anytoolai-platform/pull/222),
  commit `5cd6d894`; ANY-626 merged in
  [PR #224](https://github.com/gushinets/anytoolai-platform/pull/224), commit `3c639c0a`.
  Both prompt rules are present at the current checkout, `331e086c`.
- ANY-627 reported live acceptance on 2026-10-29, using the Client Update Writer web form,
  Reply Draft mode, `main` at `3c639c0a`, and `gpt-6-luna`. The table records the reported
  acceptance, not a new run performed during this documentation closure.

| Case | Language / tone | Reported result | Acceptance checked |
|---|---|---|---|
| R05 | RU / firm | 3/3 | Admits the invoice typo, keeps EUR and promises to send the corrected invoice; no claim it was already sent, no inability-to-confirm phrase and no "оплатка". |
| R01 | RU / warm | 3/3 | Treats testimonials as separate new work, requests their texts and a separate estimate; does not generalize all comments into extra revisions. |
| R02 | EN / neutral | 3/3 | Requests the sample export and signup-form platform without duplicating the final request in the combined message. |
| R04 | EN / firm | 3/3 | Addresses the no-additional-pages constraint and keeps legal approval about the work rather than narrowing it to German text. |

The required RU/EN set passed **12/12** reported runs. ANY-627 holds the full outputs in its
acceptance comment (24 runs reported in total). Those outputs were not independently retrieved
during this documentation closure. No new live calls were made. Three repetitions per case do
not establish an error rate or eliminate the intermittent behavior seen in the original QA.

### Spanish observations and follow-up

- R04 in Spanish: reported 3/3 passing runs.
- R01 in Spanish: `gpt-6-luna` explicitly requested testimonial texts in only 1/3 runs, compared
  with 3/3 for `gpt-6.1-terra` and `gpt-6-sol`. This is a follow-up evaluation signal, not proof
  that a model switch fixes all Reply Draft behavior. Keep model choice in backend config.
  The owner can expand ANY-597 to compare the Spanish case alongside RU/EN evaluations; no new
  issue or model-policy change is part of this closure.
- All compared models described the logo change as included in the current price. The goal
  explicitly includes it in one agreed revision round and the client asks about price, so this
  was recorded as a compatible inference, not a confirmed defect.
- R03 and a separate R01R regression case were not included in ANY-627. R03 was acceptable in
  the original QA; an optional paid rerun requires owner approval. The required three repeats
  of R01 are included above.

## Closure

Implementation and the reported required live acceptance are complete. This plan is archived;
the parent ANY-594 remains pending administrative closure in Linear. A summary comment and
status change require owner approval, as do GitHub publication and any additional paid runs.

## Risks

Text tests do not prove model behavior; only live runs (ANY-627) do. Treating everything in
`intent` as content would leak author directions again (R05 "we cannot confirm it was sent");
the opposite drops promised actions. Naming client constraints must not make the model accept
them; the terms-status rule still forbids that. "The client's own words" must not turn into quoting
the client verbatim. The one-request rule could drop the request from both fields; the
`call_to_action` gate and the completeness rule hold it.
