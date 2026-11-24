# Execution Plan: Client Update Writer tone and reply order (ANY-851)

## Status

- State: active
- Owner: agent
- Linear: ANY-851
- Created: 2026-11-23
- Last updated: 2026-11-24
- Review date: 2026-11-24
- Next action: review the first-round regression evidence, then verify the public release.
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

## First review follow-up

1. Establish the author's position from the reply goal before drafting. Acknowledge what the
   client experienced, expected or reported. Preserve admissions, apologies and commitments
   that the author explicitly supplies.
2. Make Reply Draft openings distinguish the three tones in the selected language. Keep the
   author's position, next step and scope context in the same order across tones.
3. Require the client-facing project name or description in Update. Check each S1 result
   against the original notes before comparing tones.
4. Preserve the original evidence. Rerun S1 and S4 pairs, the R05 supported-admission control,
   and S2/S7 request checks in Russian, English and Spanish.

Only Reply Draft receives a client message alongside a separately authored reply goal. Update
already has a source-attribution rule for disputed operational statuses. Proposal AI has an
explicit tone contract and writes from freelancer-authored inputs. Prepaid Request has
separate rules for disputed commercial terms. Brief Decoder and Acceptance Builder produce
analysis artifacts and have no reply tone selection.

The original English S1 results omitted the yoga studio in both tones. Their passing pair
comparison did not establish source fidelity. The original Russian S4 pair was also graded
without a separate tone-distinction criterion. The follow-up evaluates each source fact and
the paired tone difference separately.

The first Luna rerun preserved the client's attribution in S4 but put the explanation ahead
of the offer in several cases. Russian R05 acknowledged the typo while omitting the invoice
number. The prompt now requires the decision to begin immediately after the acknowledgement,
reserves background for a later sentence, and carries over identifiers for the subject of
the author's decision.

Update now preserves each status on the part it describes and assigns the request for
outstanding materials before drafting. The added resolved-material controls check that a
historical blocker still explains the delay and triggers no new request.

### Follow-up verification

- All six S1 runs kept the yoga studio landing page and the status of each part. All nine S4
  runs kept the author's position and put the two options before the brief context. The warm
  and firm openings differed in each language. All three R05 runs kept INV-104, admitted the
  typo and preserved the amount, commitment, scope and dates.
- All three resolved-material controls retained the earlier cause without requesting the
  photos again. In the nine outstanding-material runs, S7 neutral in Russian repeated the one
  request across both output fields. The other eight issued it once.
- The earlier comparison sample used eleven matching inputs each on Terra and Sol. Terra
  preserved the S4 order and attribution in all six sampled replies. Sol added an apology in
  the English warm reply. The comparison uses an earlier prompt revision and is exploratory.
- Config, architecture and docs validation passed. The Freelancer Suite and evaluator
  tests passed (1,932 tests).

The [review follow-up evidence](any-851-tone-and-reply-order-review-1.evidence.json) contains
the 30 final Luna runs and 22 comparison runs. It records the prompt fingerprints separately
for Update, Reply Draft and the comparison sample.
