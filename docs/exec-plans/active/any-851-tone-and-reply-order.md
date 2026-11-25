# Execution Plan: Client Update Writer tone and reply order (ANY-851)

## Status

- State: active
- Owner: agent
- Linear: ANY-851
- Created: 2026-11-23
- Last updated: 2026-11-25
- Review date: 2026-11-25
- Next action: review the latest regression evidence, then verify the public release.
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

## Second review follow-up

1. Give Update and Reply Draft a single field for the complete client message, including any
   request. Select that A07 output layout through the existing workflow input mapping and
   enforce it through A07 cross-validation and validation retries.
2. Anchor subjective descriptions to the client in every tone. Reserve first-person empathy
   and appreciation for warm replies and use a plain acknowledgement in neutral replies.
3. Verify the output contract through the runtime and compare every S4 tone pair on the same
   input in RU, EN and ES. Repeat the S2/S7 outstanding and resolved-material cases.

The result API and renderer retain the optional action field for stored results. Kernel Demo
can still use two fields. Client Update Writer Prepaid Request already writes a single text
field through A06. Proposal AI, Brief Decoder and Acceptance Builder have no A07 output that
feeds this combined message renderer.

### Second-round verification

- All 34 live Luna runs on the local form returned only `text`. The saved result, displayed
  message and clipboard content matched in every run.
- All ten pending-material runs, including both Russian S7 neutral attempts, gave the delay
  reason and Tuesday date and asked for the photos once. The three resolved-material controls
  retained the delay history and asked for nothing.
- Both English firm S4 attempts attributed the perceived dullness to the client. Both Spanish
  neutral/warm pairs used distinct openings on the same input. All twelve S4 runs kept the
  two options within the first revision round and put the brief context after the offer.
- The six S1 runs retained the project, progress and Friday date. The three R05 runs kept
  INV-104, the admitted typo, the correction commitment, scope and dates.
- 2,782 Python tests and 90 Client Update Writer web tests passed, as did config, architecture
  and docs validation. The Python retry regression feeds A07 a rephrased duplicate in two
  fields and verifies that the second attempt returns the complete message in one field.

[Second-round live evidence](any-851-tone-and-reply-order-review-2.evidence.json)

## Third review follow-up

1. Preserve the actor, status and scope of each client claim in Reply Draft. Treat a request,
   the client's assessment of the result and a confirmed agreement as independent facts.
2. Determine speaker number from the freelancer's own words in the four prompts that share
   the speaker-identity rule. Use impersonal or work-centred phrasing for progress when the
   author's number is unstated. Brief Decoder and Acceptance Builder emit analysis artifacts
   without a freelancer-authored message.
3. Grade source relations in S4 and speaker number in S2/S7 independently of tone. Verify
   the original inputs and positive controls for an explicit agreement, singular author and
   plural author in each language. Keep the second-round raw outputs for comparison.

Acceptance checks:

- S4 preserves the client's request for brighter work and any reported disagreement about
  the current result with their original status. If the reply refers to either claim, it
  keeps the two separate and never recasts either as a prior agreement on brightness. The
  author-confirmed control states the agreement exactly as given in the reply goal.
- S2/S7 reports the missing materials impersonally on the original third-person notes. In
  the controls, it preserves an explicit singular or plural author voice. A pronoun or
  conjugated verb in a client quote does not change the freelancer's speaker number.

The second-round artifact retains the original S4 warm RU and S2 firm ES outputs. Those two
outputs fail the new criteria: one strengthened the client's claim about what was agreed,
and one added a plural freelancer voice to third-person notes. The prior PASS labels are
historical.

### Verification of claim status and speaker number

- All ten S4 runs on the original input kept the client's claims at their original status.
  The three author-confirmed controls stated the agreement and kept the two-version decision
  as an offer. The joint agreement did not create a team commitment.
- All ten S2/S7 runs on third-person notes described the missing photos impersonally. All
  six explicit-voice controls retained the speaker number for the wait, including the
  Russian singular and plural forms. Every delay run made one photo request.
- The six S1 runs kept the Friday date. The subsequent review found that two warm S1 runs
  omitted who would show the first version. The three R05 runs preserved the source facts,
  deadlines and commitments. All 38 Luna runs used the existing single-text result contract.
  The saved, displayed and copied message matched.
- Config, architecture and docs validation passed. The Freelancer Suite and evaluator
  tests passed (1,932 tests).

Terra and Sol each passed the six explicit-voice controls on the final Update prompt. The
comparative runs used the temporary test worker. Luna remains the default model.

[Third-round live evidence](any-851-tone-and-reply-order-review-3.evidence.json)

## Preserve the actor of each action

The third-round S1 warm replies in Russian and Spanish kept Friday but omitted the freelancer
as the actor who would show the first version. Both English replies and all three neutral
replies kept the actor. The two historical PASS labels missed the actor change.

1. Tie speaker number and known actors to each action in the four freelancer-voice prompts.
   Keep author commitments distinct from unnamed progress status, even within the same notes.
2. Add an independent S1 criterion for the stated actor of the Friday presentation. Grade the
   six neutral and warm replies against that criterion and against the existing tone and fact checks.
3. Recheck S2/S7, including explicit singular and plural waits and client-supplied materials, in
   Russian, English and Spanish. Preserve the earlier evidence and record corrected verdicts alongside
   the new results.

### Verification of action ownership

- All six original Luna S1 replies preserved the freelancer's first-person Friday commitment.
  Neutral and warm kept the same facts and used distinct delivery in each language.
- All six mixed-actor S1 controls preserved the status of the ready work, the author and designer's
  Thursday action, the author's Friday commitment and the client's Monday action.
- All nine Luna S2/S7 replies on the original notes attributed the missing photos to the client,
  retained the three-day shift and Tuesday date, and asked for the photos once. All six explicit
  speaker controls kept the source number. The three resolved-material controls kept the original
  sender in the delay history, reported the arrival and made no request.
- The three S4 warm spot checks preserved attribution, claim status and the order of the offer.
  The three R05 controls preserved the freelancer's commitment to send the corrected invoice.
- Config, architecture and docs validation passed. The Freelancer Suite and evaluator tests passed
  (1,933 tests).

Terra and Sol each passed the six original S1 cases in a comparison on the same prompt. The
saved result, browser display and clipboard matched in all 48 runs.

[Fourth-round live evidence](any-851-tone-and-reply-order-review-4.evidence.json)

## Preserve participants and relationships when rephrasing

1. In the four freelancer-voice prompts, resolve each statement from its original speaker's
   perspective. Preserve who made or reported it, each participant's role, its status and the
   relationships the source actually states. Keep roles local to the event they describe.
2. In Reply Draft, maintain the participants of a relayed claim independently of its
   attribution and the freelancer's position. In Update, keep a blocker, its history, its
   resolution and a revised date separate unless the source links them.
3. Grade participant fidelity and relationship fidelity separately. Recheck the original
   multilingual cases, plus controls with a third-party agreement, an explicit cause for a
   revised date and a resolution with no stated actor. Preserve the raw fourth-round evidence
   and correct the three historical verdicts in the follow-up.

The [fourth-round evidence](any-851-tone-and-reply-order-review-4.evidence.json) retains the
original outputs. S4 warm EN and ES fail the participant check. Resolved S2 ES fails both
the actor and relationship checks. The other checks recorded for those outputs are historical.

The Update tone matrix includes three resolved-material notes with no arrival actor or link
between arrival and date, and three notes where the designer delivers the photos and that
arrival explicitly enables an earlier date. For S4, use the original neutral, warm and firm
inputs, then require an explicit restatement of the client's account in the warm reply after
the offer. Check a claimed agreement involving the freelancer and a separate claim involving
only the client and a venue coordinator. In both controls, the author asks to relay the
client's account without confirming the substance of the agreement.

Config, architecture and docs validation passed. The Freelancer Suite and evaluator tests
passed before the main merge (1,934 tests) and after it (1,979 tests).
The isolated browser launched both workflows and the provider rejected
generation with HTTP 401 under both locally configured credentials. The semantic matrix and
model comparison still require a successful provider run.

## Honor the selected layout in the default A07 prompt

1. Make the default Atom Lab prompt put the complete request and any supplied URL in
   `text` when the caller selects `single_text`.
2. Verify the Atom Lab prompt binding and both validator paths. With the layout omitted,
   an optional separate action remains valid when it adds a useful next step.

The Atom Lab catalog loaded the updated default prompt. The validator accepted a scheduling
URL in `text` with `single_text` and rejected a separate action in that mode. It accepted
both representations when the layout was omitted. The 166 targeted tests passed.

## Keep requests with the party responsible for the next step

1. In Update, determine status and responsibility for each pending action before applying tone.
   A client request needs a still-pending action assigned to the client. Ownership of an item
   and its effect on the schedule do not establish who must provide it.
2. Preserve the stated next step when another party acts or a handoff is already arranged.
   Keep the delay, cause and new date even when the update has no client request.
3. Retain the original S2/S7 controls and add RU, EN and ES cases for a designer's handoff,
   mixed responsibilities and unassigned materials.

All 33 matrix inputs passed the Update schema, workflow mapping and A07 schema checks, with
11 inputs per language. The Freelancer Suite and evaluator passed 1,979 tests. Config,
architecture and docs validation passed.

The browser started the designer-handoff case in each language and the mixed English case
under the alternate configuration. The provider rejected generation with HTTP 401 under
both configurations. The generated text and model comparison still need live verification.

## Preserve the API length contract

1. Make `single_text` an explicit opt-in in both Update and Reply Draft. The web form selects
   it for its copy-ready result. API requests that omit it retain a separate optional action
   and apply `constraints.max_length` to `text`.
2. Give both prompts the corresponding layout rules. Exercise a scheduling URL longer than
   the body budget through the normal API and A07 workflow, and verify the web payloads.
3. Retry the provider-backed S1, S2/S7 and S4 acceptance cases against the final prompt
   fingerprints. Record the outcome of the provider check and keep semantic acceptance open
   if generation cannot run.

The API and worker tests passed for both modes. With a 50-character limit and a scheduling
URL longer than 50 characters, the default layout returned a short body and a separate action.
With explicit `single_text` and sufficient space, it returned the whole request in `text`.
All 19 API bundle tests, 1,991 Freelancer Suite and evaluator tests, and 90 web tests passed.
Config, architecture, docs and generated-doc checks passed, as did the web type check.

All 42 acceptance inputs passed scenario and A07 schema and mapping checks, with 14 inputs
per language. The browser submitted `single_text` for S1 warm RU, S4 firm EN and S2 firm ES
on the main local configuration, and for S4 warm ES on the alternate configuration. Both
configurations reached the provider and returned HTTP 401. Final-prompt semantic acceptance
still requires successful runs with the exact inputs, tones and full results.

### Live results after provider access was restored

The browser returned a successful single-text result for all 42 Luna cases, with 14 inputs
each in RU, EN and ES. The verified provider ledger matched the model and session. The
deployed Update and Reply Draft prompts matched the current prompt files. The stored,
displayed and copied text also matched on every run.

- **S1.** All six runs kept the first-person Friday commitment and showed a distinct
  neutral and warm delivery.
- **S2/S7.** Three Russian runs omitted the photo request. The remaining six original
  delay runs asked once, with some changing the sender or supplying an unstated recipient.
  All nine designer-handoff runs kept the designer responsible and made no request to the
  client. One had an ambiguous cause connector. The mixed Spanish case reported the
  client's pricing-sheet responsibility without asking for the sheet.
- **S4.** All nine runs kept the two-option offer in the first revision round before brief
  context. Some restated disputed claims before the offer or changed or obscured who asked
  for brightness. Only the English warm and firm runs met every assessed S4 criterion.

In all, 25 of 42 Luna runs met every assessed criterion. The 18 comparison runs used nine
of the same inputs per model. On the six original S2/S7 cases in that sample, Terra asked
for the photos in 6 of 6 runs, Sol in 5 of 6, and Luna in 4 of 6. The comparison did not
include the full matrix. The default model remains Luna.

[Final live evidence](any-851-tone-and-reply-order-final-live.evidence.json)

Live generation was available. The recorded failures left semantic acceptance open on
that profile.

## Build the reply from required actions and ordered content

1. In Update, decide which actions need a new request before drafting. Give each of those
   actions a direct request. Keep arranged handoffs as plans and unassigned dependencies
   as status. Preserve each handoff's participants and keep the delay and any later arrival
   distinct.
2. In Reply Draft, make the opening, decision and context distinct. Answer the client's
   concern and keep disputed history after the decision when it is needed. Keep the
   client-side requester distinct from any shared agreement.
3. Recheck the complete multilingual matrix and add controls that require relaying a
   shared and a third-party agreement, alongside the existing S2/S7 handoff cases.
4. Compare Terra and Sol on the cases where Luna changes roles or order. Verify all three
   modes if Client Update Writer moves to a different live model policy.

### Round 8 verification

On an intermediate prompt revision, Terra passed 26 of 27 identical comparison inputs and
Sol passed 27 of 27. Luna still added requests for scheduled handoffs or assigned materials
to the client when the notes named only the person waiting. The final Update prompt checks
whether each action needs a new request. Client Update Writer uses the existing Sol policy
in its live deployment profile.

The final Sol profile met the assessed acceptance criteria in 66 browser runs, 22 per
language in RU, EN and ES. The provider ledger confirmed Sol for every session. The
profile fingerprints matched at the API and worker, and the result, displayed text and
clipboard agreed for every run.

- **Update.** The nine original S2/S7 cases kept the client as sender and asked once for
  the photos without adding a recipient. The remaining Update cases verified a cleared
  blocker, a revised date caused by delivery, designer-only and mixed handoffs, unassigned
  materials, and first-person singular and plural. All six S1 neutral/warm pairs kept the
  named actors and Friday commitment, including the mixed-actor controls.
- **Reply Draft.** All nine S4 replies put the offer of two first-round variants directly
  after the acknowledgement. Six controls relayed both claims after the offer, retaining
  the client as requester and the original parties to shared or third-party agreements.
  Warm differs from firm in all three languages and from neutral in Spanish. Neutral and
  firm differed only in a short phrase in EN and one word in ES. The three R05 controls kept
  the invoice admission, identifier and promise to send the corrected invoice.
- **Prepaid Request.** Three controls retained the agreed amount, currency, due date and
  start-after-payment condition, with the requested payment and notice of sending.

The focused suite passed all 2,042 Python tests, including both API layouts and the
deployment policy check. Config, architecture and docs validation passed. Browser
verification used the local deployment profile.

The broader quick-check exposed three local runner test failures. Two mocks intercept
the production Compose environment probe before reaching the stack-status check. The
activation marker test requires passwordless `sudo` to switch to `nobody`. All three
failures reproduced in isolation.

[Round 8 live evidence](any-851-tone-and-reply-order-review-8.evidence.json)

## Distinguish neutral and firm replies

1. Give Reply Draft a distinct firm opening and a direct way to make an authorized offer.
   Preserve the author's scope, commitment and stated uncertainty in every tone.
2. Compare the S4 tones on identical inputs in RU, EN and ES. Recheck the order of the
   reply, the parties to reported claims, R05's admission and a tentative decision.

### Round 9 verification

The Sol profile returned 24 browser results, eight each in RU, EN and ES. The nine original
S4 replies distinguished the tones on identical inputs and kept two variants within the
first revision round. Neutral led with the client's expectation and presented the available
option. Firm led with the attributed issue and made the offer directly. Warm acknowledged
the client's reaction without adding a remedy. Brief context followed the offer in every
case.

Six controls kept the requesting party and the participants in a disputed agreement.
Six tentative-date controls kept Thursday unconfirmed and the Tuesday workload check.
Three R05 controls kept the admission and promised invoice correction. The provider
ledger confirmed Sol for all sessions, and the API, display and clipboard text matched.

The next review corrected three verdicts. Spanish S4 warm widened the individual
expectation to a group. English S4 warm took the client's judgment as a premise. English
firm added Thursday as a launch dependency. The saved results and corrected grades are
in the evidence below.

All 375 focused Python tests passed, including the API layout checks.

[Round 9 live evidence](any-851-tone-and-reply-order-review-9.evidence.json)

## Preserve the source before choosing tone

1. Build the Reply Draft from the client's stated concern and the author's authorized
   answer. Keep the experiencer, speaker number, assessment and stated relationships
   attached to each statement before choosing the opening and delivery.
   Apply the neutral and firm distinction to factual questions as well as evaluations.
2. Reassess the three round 9 findings against the saved outputs. Record separate verdicts
   for source attribution, number and unstated dependencies in the new runs.
3. Recheck RU, EN and ES across all three tones. Include individual and team perspectives,
   dated requests with and without an explicit prerequisite, S4's disputed claims, R05 and
   adjacent Update and Prepaid Request controls.

### Round 10 verification

Sol returned 63 browser results on the final local profile, 21 each in RU, EN and ES. The
matrix reused all 24 round 9 inputs and added 39 controls. The provider ledger confirmed
Sol for every session, and stored, rendered and copied text matched.

- **Reply Draft.** The individual expectation and offer addressee stayed singular in S4.
  Team controls retained the collective perspective. Each assessment stayed with the
  client, including in warm acknowledgements. The two-option first-round offer followed
  the concern and preceded brief context. Six retelling controls kept the original
  roles in shared and third-party claims. Nine R05 replies kept the admission and the
  correction commitment.
- **Dates and tone.** Nine cases kept launch planning separate from the Thursday
  question. Nine controls preserved Thursday as a prerequisite where the client stated
  it. In both sets Thursday remained unconfirmed and the Tuesday workload check stayed
  with the freelancer. Neutral and firm also differed on these factual questions.
- **Adjacent modes.** Three Update checks retained the single pricing-sheet request
  and the separate handoffs. Nine Prepaid Request checks covered direct requests,
  payment details arriving later and an explicitly unsettled method. An intermediate
  run on the ambiguous English note about missing payment instructions asked to confirm
  the method. The final run requested payment. The evidence includes that variation and
  both unambiguous controls.

All 2,043 focused Python tests passed, including the Freelancer Suite, evaluator,
deployment configuration and both API layouts.

[Round 10 live evidence](any-851-tone-and-reply-order-review-10.evidence.json)

## Preserve both actors in Russian and Spanish conditions

1. For Russian and Spanish firm replies, keep the issue first while expressing each event
   in a stated condition with its own known actor.
2. Compare all three tones on the original launch condition and a control with different
   actors for receipt and launch. Recheck the unrelated deadline questions and S4 on RU and ES.
3. Correct the Russian and Spanish round 10 verdicts against the saved outputs.

### Round 11 verification

Round 10's Russian and Spanish firm replies preserved the condition but left the
recipient and the launch actor implicit. The two corrected verdicts bring the recorded
round 10 total to 61 of 63 with its other verdicts preserved.

Sol passed 24 browser checks, 12 in Russian and 12 in Spanish. All three tones preserved
both actors in the original condition. In the control, the individual launched the
course and the team received the materials. The evidence records the expression for
each actor independently. The deadline and S4 controls kept the unconfirmed date,
the order of the reply and the two-option first-round offer. All 381 focused Python
tests passed.

[Round 11 live evidence](any-851-tone-and-reply-order-review-11.evidence.json)
