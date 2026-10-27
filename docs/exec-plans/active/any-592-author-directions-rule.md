# Execution Plan: Author directions in freelancer prompt inputs (ANY-592)

## Status

- State: active
- Owner: agent
- Linear: ANY-592 (changes: ANY-619, ANY-620)
- Created: 2026-10-26
- Last updated: 2026-10-27
- Review date: 2026-11-02
- Next action: merge the ANY-619 and ANY-620 PRs; ANY-621 adds the analysis-prompt rule.
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

## Scope (ANY-620)

- The same bullet, verbatim, in `proposal_ai/prompts/compose_persuasive_text.v1.md`, in `Form:`
  right after the speaker-identity rule (ANY-629), the same place as in Client Update Writer.
- Not adapted to ProposalAI: "the goal of the text" and "the client's message" read correctly there,
  and the test requires one wording. The `task_text` exclusion and "decline it when the order says
  so" rules (ANY-628) and the meta-commentary ban stay unchanged.
- The test lists the ProposalAI path.
- After the first P01 live run the rule says "not even as your own plan or offer" in all four
  prompts (see the decision log).
- After the second P01 live run the ProposalAI `Price and terms:` closing-formula bullet also bans
  saying when or how price, cost or timing will be discussed or agreed (ProposalAI only).

## Out of scope

- Brief Decoder and Acceptance Builder (ANY-621).
- Other defects of the same QA cases: completeness and units in U01/U03/U05 (ANY-593, ANY-623),
  R05 actions (ANY-594, ANY-625), A02 payment terms (ANY-589, ANY-605), A04 (ANY-588).
- Form, schema and validator changes; live acceptance (ANY-624, ANY-627, ANY-608, ANY-604).

## Verification

- New test and the existing `test_client_update_writer_product.py` pass.
- `python scripts/agent/runner.py validate-configs`, `validate-docs` and `generate-docs --check`
  pass.
- `quick-check`: 2729 tests pass; the only failure is
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`, which needs
  passwordless `sudo -u nobody`. The ANY-629 exec plan records the same failure on `main` in a
  sandbox without sudo; it was not rerun on `main` here, so CI is the source of truth.
- Live acceptance in the follow-up issues: Update ANY-624 (U01, U03, U04, U05), Reply Draft ANY-627
  (R05, R01, R02, R04), Prepaid ANY-608 (A02, A03, A05) and ANY-604 (A04, A01).
- ProposalAI P01 live x3 (ANY-620, RU, warm, input verbatim from ANY-631), 2026-10-27:
  - First wording: the prompt was quoted in none of the 3 runs and no run named a price or a
    timeline, but run 2 retold the direction ("обсудить детали проекта без предварительного
    определения цены и сроков").
  - Refined wording: the prompt was quoted in none of the 3 runs and no run named a price or a
    timeline, but run 2 closed with "После этого можно согласовать стоимость и сроки": the
    direction surfaced as a next-step offer (PR review: blocking).
  - Refined wording plus the `Price and terms:` ban: the prompt was quoted in none of the 3 runs, no
    run named a price or a timeline, and none mentioned price, cost or timing or when they would be
    agreed. Out of scope, seen in passing: a long dash in run 2 ("Следующий шаг — созвон") and a
    gendered "я делал" in run 3.

## Decision log

- 2026-10-26: forms stay unchanged; the model tells a direction from a fact (parent decision).
- 2026-10-26: a request written by the client (Reply Draft `situation` is the client's message) is
  the client's, not a direction to the composer, following ANY-629's "a name or signature in the
  client's message is the client's".

- 2026-10-27: after P01 run 2 retold the direction as the freelancer's own plan, the rule adds
  "not even as your own plan or offer" in all four prompts; the test carries the new wording.

- 2026-10-27: the PR review rejected "После этого можно согласовать стоимость и сроки" as the
  direction surfacing as an offer. The fix extends ProposalAI's own closing-formula bullet in
  `Price and terms:` instead of the shared rule, so the Client Update Writer prompts and the
  verbatim test stay as they are.

## Risks

- The direction/fact boundary is the model's call. U05 ("this update is not a payment request") is
  borderline: it reads both as a fact and as a direction. ANY-624 shows the result.
- "The direction wins" could meet the ban on invented facts ("say it is all done" against contrary
  facts). The rule covers directions "about this text"; the truthfulness rules stay. U04 checks it.
- The Prepaid prompt is long (rules A–D); seven more lines may shift its behavior. ANY-608 and
  ANY-604 catch that live.
- ProposalAI `task_text` mixes the client's order with the freelancer's directions, so the model
  may answer a direction as the client's request ("as you asked, without a price"). P01 shows it.
- "These instructions" may be read as the freelancer's directions, not the prompt's. P01 did not
  quote the prompt in 6 runs; if it does later, the last sentence changes in every prompt.
- The refined wording reaches the Client Update Writer prompts without their own live rerun; their
  acceptance issues (ANY-624, ANY-627, ANY-608, ANY-604) run on it.
- Changing the wording after live touches every prompt that carries it; the test keeps them in sync.
