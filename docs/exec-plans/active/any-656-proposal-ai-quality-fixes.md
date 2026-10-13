# Execution Plan: ANY-656 ProposalAI Quality, Honest Gaps, Form and Reliability Fixes

## Status

- State: active
- Owner: agent
- Created: 2026-10-13
- Last updated: 2026-10-13
- Review date: 2026-10-20
- Next action: the blind tone check (`tmp/proposal-ai-blind-tone-check.md`), real postings if available, and F.1 latency from the production logs.
- Blocker: none for code; live runs and the production checks (E.4, E.6, F.1 log analysis) cannot
  run from the agent sandbox.

## Goal

The 2026-10-06 QA report found ProposalAI texts that are not sendable as-is: distorted profile
facts, invented prices, placeholders, a drifting language, boilerplate shape, and no warning when
the order asks for something the profile lacks. Fix the product and the generic A06 contract so the
result is honest and send-ready, add a separate gaps block, and close the form and reliability
findings.

## Scope

- Block C: A06 `constraints` gain `forbidden_patterns`, `plain_text_lists`,
  `numbers_must_appear_in_context`, `claims_to_avoid`; cross-validator enforces the first three, a
  failure is a PydanticAI validation retry.
- Block A: prompt v2 (facts, language, no placeholders, no invented price or terms, opening, form,
  three real tone profiles, gender-neutral Russian); `constraints.length` 4000 -> 1800.
- Block D: workflow v2 = A04 `detect_gaps` (taxonomy `experience_gap`) then A06; output schema
  `{text, gaps[]}`; renderer contract in `parts` form; UI block "What your experience lacks".
- Block B: "Proposal language" select (auto + 7 locales), sent only when explicit.
- Block E: required marker, `maxLength` and counter, honest hint, one field name, Italian register,
  trim instead of reject, phone field height.
- Block F: one safe retry of an ambiguous `/start` failure with the same idempotency key, longer
  start timeout; clipboard fallback.
- Block 0.2: DB-free eval checker for the automatic checks of the 20-order protocol.

## Decisions

- Gaps reach A06 as `constraints.claims_to_avoid`, not `context.gaps`: the mapping DSL rejects a
  dotted `context.*` input target, and changing the DSL needs two real users (it has one).
- A04 gets `source_text` = task text and `context` = positioning (its own two fields), so no string
  concatenation is needed in the DSL.
- Length cap 1800, 7 language locales, Block D and Block C in this task: decided 2026-10-13.

## Progress

Done and covered by tests: blocks A, B, C, D, E (except E.4 and E.6 measurements), F (code), 0.2
(`scripts/agent/proposal_ai_eval.py`, 10 synthetic orders in `tests/fixtures/proposal_ai_eval`).
Block 0.1 changed the default text model to `openai/gpt-6-luna` (`reasoning_effort: medium`) in `configs/kernel/litellm_router.yaml`;
that alias is shared by every product.

Open, needs the live stack or the deployed site:

- 0.1 and G are done for the 10 synthetic orders (table above). Add the 10 real orders to the
  fixture and rerun `python scripts/agent/proposal_ai_eval.py --api-url ...`.
- F.1: latency tail of `POST /scenario-sessions/start` from the API or proxy logs; the client change
  (20 s timeout, one automatic retry with the same idempotency key) is already in.

## Live results on gpt-6-luna (2026-10-13, 10 synthetic orders, automatic checks only)

| Check | Before (main) | After |
|---|---|---|
| Runs that finished | 10 of 10 | 30 of 30 (3 tones) |
| Long dashes | 3 | 0 |
| Meta phrases about the profile inside the text | 3 | 0 |
| Gap shown to the user where the order needs missing experience | 0 of 3 | 3 of 3 |
| Average words (warm) | 84 | 118 |
| Average words (neutral / firm) | n/a | 122 / 90 |

Before, the text itself said "my listed experience does not include HubSpot". After, the gap is a
separate block and the text claims nothing about it. Not covered by the automatic checks and read by
hand on the warm run: profile facts stay as written, no amounts or terms were invented, a similar
case stands in the first sentence when the order asks for it. Still manual and open: blind tone
distinction (firm is about a third shorter than neutral by length, the rest needs a human) and the
10 real orders.

The set now has 20 orders: the 10 above plus 10 written in the style of Freelancer postings
(`fl-*`; real postings were not available). All 20 pass the automatic checks in the warm tone; the
second pass over them also trimmed padding (the text no longer lists the whole profile) and
over-granular gaps ("remove duplicates" is a step of the work, not a missing skill).

Found and fixed during the live run:

- LiteLLM does not know `gpt-6-luna` and rejected `reasoning_effort`: `allowed_openai_params` in
  `litellm_router.yaml`.
- The model wrote paragraph breaks as raw newlines inside the JSON string and the strict parser
  failed both attempts on 4 of 10 orders. The schema instruction now asks for an escaped newline,
  and the parser of provider output (not config literals) accepts raw control characters. This
  affected every multi-paragraph product, not only ProposalAI.
- The prompt itself invited "I will confirm the estimate and timeline", which ended 8 of 10 texts.
  The sentence is removed from the prompt (0 of 9 afterwards).
- A very short English order ("Need an automation expert...") got a Russian text in the firm tone,
  the original D-02 defect with a Russian profile. The prompt now says to decide the language from
  the order first, even when it is one sentence (9 of 9 correct afterwards).
- Two retries in a row failed a run over an em dash. A long dash is now a style rule only: the
  prompt forbids it and the eval script counts it, validation does not reject it. Placeholders,
  brackets and meta phrases still fail validation.
- A reasoning model sometimes answered in plain text without the JSON wrapper, and the retry prompt
  said only "Malformed JSON". The retry now spells out what to return. After the last rebuild
  there were no failed runs in 45 targeted and 129 total jobs.

## Measured in Chrome on the production build of web-mirror (local, against the live stack)

- E.4: both textareas keep their own minimum (144 px and 120 px, 6 and 5 lines at 16 px with a 24 px
  line height) in a 348 px wide column, `field-sizing: content` is active, and a 960 character text
  grows the field to its 480 px cap. The shared-ui 44 px minimum no longer wins.
- E.6: the submit button shows a solid 2 px outline in the accent colour with a 2 px offset on
  keyboard focus (`:focus-visible`), not `outline: none`; the QA finding does not hold for this build.
  Contrast against the page and card backgrounds: ring 6.4 and 5.4, secondary text and placeholder
  (0.75 token) 9.5 and 8.6. Requirements are 3 and 4.5.
- Not measured: the deployed site itself (it still runs the old build), and F.1 latency, which needs
  the production API or proxy logs.

## Out of scope

Live runs on the new model and production measurements: they need credentials or the deployed site and are
listed under Progress as open, not simulated.

## Risks

Prompt rules and fixtures do not prove model behavior; only the live acceptance does. The second
model call per run costs about 30-50% more tokens and a few seconds.
