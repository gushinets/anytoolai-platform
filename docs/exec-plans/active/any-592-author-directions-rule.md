# Execution Plan: Author directions in freelancer prompt inputs (ANY-592)

## Status

- State: active
- Owner: agent
- Linear: ANY-592 (this change: ANY-619)
- Created: 2026-10-26
- Last updated: 2026-10-26
- Review date: 2026-11-02
- Next action: review and merge the ANY-619 PR; ANY-620 copies the rule into ProposalAI, ANY-621
  adds the analysis-prompt rule.
- Blocker: none

## Goal

Form fields are free text where the freelancer mixes facts with directions to the composer. No
prompt says how to handle such directions, so in QA 2026-10-02 they reached the client as content:
"do not calculate tax" became "(do not include VAT or calculate tax)" (A02), "do not say it was
already sent" became "we cannot confirm the invoice was already sent" (R05), "do not call the work
complete" became "complete from an implementation standpoint" (U04), and "this update is not a
payment request" was sent verbatim (U05). Add one rule, in one wording, to every prompt that writes
to a client: follow the freelancer's directions without retelling them, let a direction win over
the goal of the text, and never quote the prompt's instructions to the client.

## Scope (ANY-619)

- One bullet, verbatim in `client_update_writer/prompts/` `update_compose_reply.v1.md`,
  `reply_draft_compose_reply.v1.md` and `prepaid_request_compose_persuasive_text.v1.md`, right after
  the speaker-identity rule (ANY-629).
- The wording says "the goal of the text" instead of a field name (`intent`, `objective`) so it is
  identical in every mode and in ProposalAI (ANY-620).
- Existing special cases stay: Reply Draft "Exclusions in `intent` always hold", Prepaid
  "`context.notes` take precedence" and its rules A–D.
- Prompt versions are not bumped (`v1` edited in place, as in ANY-629).
- Test `freelancer-suite/tests/test_prompt_author_directions_rule.py` keeps the wording identical;
  ANY-620 adds the ProposalAI path to its list.

## Out of scope

- ProposalAI (ANY-620), Brief Decoder and Acceptance Builder (ANY-621).
- Other defects of the same QA cases: completeness and units in U01/U03/U05 (ANY-593, ANY-623),
  R05 actions (ANY-594, ANY-625), A02 payment terms (ANY-589, ANY-605), A04 (ANY-588).
- Form, schema and validator changes; live acceptance (ANY-624, ANY-627, ANY-608, ANY-604).

## Verification

- New test and the existing `test_client_update_writer_product.py` pass.
- `python scripts/agent/runner.py quick-check`, `validate-configs` and `validate-docs` pass.
- Live acceptance in the follow-up issues: Update ANY-624 (U01, U03, U04, U05), Reply Draft ANY-627
  (R05, R01, R02, R04), Prepaid ANY-608 (A02, A03, A05) and ANY-604 (A04, A01).

## Decision log

- 2026-10-26: forms stay unchanged; the model tells a direction from a fact (parent decision).
- 2026-10-26: a request written by the client (Reply Draft `situation` is the client's message) is
  the client's, not a direction to the composer, following ANY-629's "a name or signature in the
  client's message is the client's".

## Risks

- The direction/fact boundary is the model's call. U05 ("this update is not a payment request") is
  borderline: it reads both as a fact and as a direction. ANY-624 shows the result.
- "The direction wins" could meet the ban on invented facts ("say it is all done" against contrary
  facts). The rule covers directions "about this text"; the truthfulness rules stay. U04 checks it.
- The Prepaid prompt is long (rules A–D); seven more lines may shift its behavior. ANY-608 and
  ANY-604 catch that live.
- Changing the wording after live touches every prompt that carries it; the test keeps them in sync.
