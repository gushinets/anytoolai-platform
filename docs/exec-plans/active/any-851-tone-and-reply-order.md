# Execution Plan: Client Update Writer tone and reply order (ANY-851)

## Status

- State: active
- Owner: agent
- Linear: ANY-851
- Created: 2026-11-23
- Last updated: 2026-11-23
- Review date: 2026-11-23
- Next action: review recorded live QA outputs, then rerun the release on the public form.
- Blocker: none

## Goal

Make neutral, warm and firm visibly distinct while preserving client-facing facts, commitments
and requests. Put the author's answer or next step directly after acknowledging the client's
concern, before any explanation.

## Scope

- Define the three tones in Update and Reply Draft. Keep their prompt versions at `v1` and
  `input_variables: []` because both workflows already supply `tone` in the input payload.
- Order Reply Draft around acknowledgement, decision or next step, and supplied context. Respect
  the existing rules for concrete intent facts, scope limits and speaker identity.
- Add Python prompt-contract checks and a tone evaluation suite. Keep the frozen screening fixture
  intact and exercise Reply Draft through the client form.

## Out of scope

- UI helper text under the tone selector and em-dash style.
- Provider Gateway and default model routing.

## Verification

- Run doctor, config and architecture validation, Freelancer Suite and evaluator pytest tests,
  then quick-check.
- Compare S1 neutral and warm. Compare the S2/S7 delay input across all three tones, retaining the
  reason and Tuesday date. Compare S4 firm and warm for order, offer and first-round limit.
- Capture exact submitted input, tone, full output and per-criterion verdict for each live QA run.
  Keep the original Russian inputs and evaluate equivalent English and Spanish variants.
- Managed Python 3.12 doctor, config, architecture and docs validation passed. The Freelancer
  Suite and evaluator tests passed (1,929 tests).
- Host quick-check recorded 4,275 passed, 12 skipped, 720 deselected and three failed runner
  tests. Two mocks picked up the local production env file, and the activation test required
  passwordless user switching. The same three failures reproduced on the base revision with
  those host conditions. All three passed in a clean validation container.
- The [live evidence](any-851-tone-and-reply-order.evidence.json) records 21 Luna browser runs
  and seven targeted runs each on Terra and Sol. The seven Russian QA cases met their criteria.
  All 21 Luna runs stayed in the source language. The worker's provider ledger confirmed each
  model, and the router was configured for medium effort. The ledger did not attest effort.
- Two English Luna outputs had caveats. S2 warm repeated the photo request across both output
  fields. S4 warm stated the client's disputed account as a fact while keeping the offer before
  the brief explanation. Both alternatives handled the English acknowledgement without that
  wording. Terra left the cause of the English delay implicit, and Sol's Russian S1 warm read
  close to neutral. Keep the existing model selection for this iteration.
- The browser used a local instance of the public form backed by the patched live runtime.
  Public release verification and product-owner acceptance are pending.

## Notes

- In the 11 November production rerun, S1 neutral and warm retained the Friday date and progress
  facts but mainly differed in word order and first-person phrasing.
- S2 firm requested the trainer photos; warm omitted the request. The S2/S7 screenshots use the
  same delay notes with three tones.
- Both S4 replies put the brief explanation before the offer. The warm reply also used a
  gendered first-person past-tense form despite the existing speaker-identity rule.
- The first live iteration still produced weak warmth in S1 and omitted the photo request in
  S2. The Update prompt now leads with a friendly, input-backed milestone when the notes report
  good progress and puts the request for missing materials in one output field.
- A multilingual run returned Russian for two English delay updates and repeated the request in
  one Spanish update. Update now applies every tone in the source or explicitly selected locale
  and describes the registers without language-specific examples.
