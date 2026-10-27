# Execution Plan: Author directions in freelancer prompt inputs (ANY-592)

## Status

- State: active
- Owner: agent
- Linear: ANY-592 (changes: ANY-619, ANY-621)
- Created: 2026-10-26
- Last updated: 2026-10-27
- Review date: 2026-11-02
- Next action: ANY-620 copies the rule into ProposalAI (PR #219); review and merge the ANY-621 PR,
  then run B04 live three times.
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

## Scope (ANY-621)

- The client-text rule does not fit analysis prompts, which write no client text. B04 shows the
  defect: "we want the analysis to flag conflicts rather than silently choose one version" became an
  issue about the analysis itself. A second rule (the analysis-prompt rule), one bullet verbatim
  before the chain-of-thought bullet in `brief_decoder/prompts/` `extract_brief.v1.md`,
  `detect_issues.v1.md`, `generate_questions.v1.md`, `acceptance_builder/prompts/` `extract.v1.md`,
  `compare.v1.md` and `proposal_ai/prompts/detect_experience_gaps.v1.md`: follow directions about
  how to analyze the input; never extract or report them as facts, issues, questions or criteria;
  a requirement on the freelancer's own deliverable stays.
- Beyond the four prompts the issue names: `generate_questions` gets the brief as `context` (the
  same direction could become a question to the client) and `detect_experience_gaps` gets the
  freelancer's directions in `source_text` (a direction could become an experience gap and feed
  `claims_to_avoid`).
- Not touched: `generate_summary`, `draft_document` and `check_document` see only `data`, not the
  brief; Task Finder inputs carry no directions to the composer.
- The wording says "the input text" instead of a field name (`source_text`, `context`,
  `reference_text`) so it is identical in all six files. The same test file checks it.

## Out of scope

- ProposalAI client-text prompt (ANY-620).
- Other B04 defects (`deliverables`, quotes in `evidence`): ANY-590, acceptance ANY-614.
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
- ANY-621: B04 verbatim through the Brief Decoder web form, three runs. No issue, question or
  extracted value is about the analysis itself; the real contradictions are still found. Acceptance
  Builder was not QA'd, so it has no live criterion.
- ANY-621 live, 2026-10-27 (`dev-live-up`, web form, en-US):
  - B04 × 3: no issue, question or extracted value about the analysis; accounts/personal data,
    offline/Stripe and approval-before-15-October contradictions found in all three runs.
  - Acceptance Builder draft, B04 × 1: no "flag conflicts" criterion.
  - ProposalAI P01 × 1: gaps are mobile/desktop versions, schedule block and WhatsApp button; "no
    price or timeline before the discussion" is not a gap.
  - Brief Decoder, Acceptance Builder and ProposalAI smokes (fake provider) pass.
- Live acceptance in the follow-up issues: Update ANY-624 (U01, U03, U04, U05), Reply Draft ANY-627
  (R05, R01, R02, R04), Prepaid ANY-608 (A02, A03, A05) and ANY-604 (A04, A01).

## Decision log

- 2026-10-26: forms stay unchanged; the model tells a direction from a fact (parent decision).
- 2026-10-26: a request written by the client (Reply Draft `situation` is the client's message) is
  the client's, not a direction to the composer, following ANY-629's "a name or signature in the
  client's message is the client's".
- 2026-10-27: a direction to the analysis ("the analysis should flag conflicts") is not a
  requirement on the freelancer's deliverable ("the report must flag conflicts"); the rule names
  both so the model keeps the second (ANY-621).

## Risks

- The direction/fact boundary is the model's call. U05 ("this update is not a payment request") is
  borderline: it reads both as a fact and as a direction. ANY-624 shows the result.
- "The direction wins" could meet the ban on invented facts ("say it is all done" against contrary
  facts). The rule covers directions "about this text"; the truthfulness rules stay. U04 checks it.
- The Prepaid prompt is long (rules A–D); seven more lines may shift its behavior. ANY-608 and
  ANY-604 catch that live.
- Changing the wording after live touches every prompt that carries it; the test keeps them in sync.
- ANY-621: the analysis/deliverable boundary is the model's call. Leaning one way drops a real
  requirement; leaning the other leaves B04 as is. B04 live covers one side; the reverse case has no
  QA case.
