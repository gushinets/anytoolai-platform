# ANY-604: Prepaid Request live acceptance

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the bounded fix and Spanish wording caveat for ticket acceptance
- Blocker: no original live AC failure after the fix; additional Spanish ambiguity and local sudo test limitation remain

## Latest result after the authorized fix

**Original ANY-604 live criteria: PASS, 15/15.** The prompt now distinguishes the amount
requested now from the complete stated payment arrangement. All nine A01 outputs across
RU/EN/ES retain the amount, percentage, total, balance trigger and future separate invoice.
One additional Spanish output has ambiguous percentage wording and is marked REVIEW, not PASS.
No product-wide guarantee or autonomous ticket closure is claimed. See the post-fix evidence below.

## Historical result before the fix

**Original series acceptance: FAIL.** The bounded QA execution is complete; the product ticket is not accepted.

**Latest targeted recheck: 6/6 PASS.** Three new A01 outputs preserve 50%; three new U2 outputs
are delivered and copied successfully. The prompt, workflow, model configuration and inputs
are unchanged. Across both series, percentage omission occurred in 2 of 6 A01 outputs;
the prior omission is intermittent and has not been fixed. See the targeted recheck below.
Fifteen fresh browser submissions produced fifteen backend outputs. Fourteen were delivered and
copied successfully; one was recovered from the backend after the local web server stopped.
Two delivered A01 outputs omit the explicitly required 50%. No unagreed payment demand was found.

| Case | Semantic checks | Original browser delivery/Copy | Acceptance |
| --- | --- | --- | --- |
| A04 | 3/3 | 3/3 | PASS |
| A01 | 1/3 | 3/3 | FAIL: missing 50% in attempts 2 and 3 |
| U1 | 3/3 | 3/3 | PASS |
| U2 | 3/3 | 2/3 | FAIL: interrupted browser attempt 3 |
| U3 | 3/3 | 3/3 | PASS |

## Evidence and method

[Structured evidence](any-604-prepaid-request-live-acceptance.evidence.json) contains exact inputs,
all full outputs, session/artifact IDs, selected action/provider ledger fields, trace/screenshot
hashes and per-attempt semantic decisions. Secrets, guest identifiers and raw browser network
archives are excluded from the published evidence. Raw traces remain local for diagnosis.

Source revision: `e4fb6fa4e457595058b45a24287f7277ec4b5630`. Runtime source was unchanged; only QA documentation and
temporary orchestration were added. The managed Python 3.12 collector reused the existing
`tests/e2e/client-update-writer-smoke/collect-live-run.mjs` flow, adapting only Prepaid form
selectors and adding actual clipboard readback. The local Next development server served the
current source against the isolated live API/worker. No direct API scenario submissions.

Worker prompt, workflow and router bytes matched the checkout before both collection segments.
The generated live profile was verified by the canonical runner. Each of the fifteen sessions
has exactly one successful A06 action and one successful physical provider call, recorded as
`gpt-6-luna`. The worker router configures reasoning `medium`, but provider ledger reasoning_effort
is null for all calls; effective effort is not independently proven. Every backend result contains
only `text`; no `call_to_action`.
Fourteen results match displayed and copied text exactly. U2-3 retains its UI error and has no
claimed clipboard/visible-text proof, even though its recovered backend text passes semantics.

Ledger estimated cost for the fresh series: USD 0.004613435; median delivered UI latency: 4.66s.
Cost is the runtime ledger estimate, not a verified provider invoice; interrupted calls remain included.

## Findings

1. **A01 required percentage omitted (2/3).** Attempts 2 and 3 retain 15,000 RUB but omit 50%.
   Attempt 2 also omits the remaining balance and separate invoice; attempt 3 omits the balance.
   No urgency was invented. This is a reproducible failure within this sample, not an estimated
   population failure rate. No prompt or product fix was applied during acceptance.
2. **U2-3 browser delivery unverified.** The local web server stopped and the collector process
   terminated; the completed browser journal recorded “Lost connection while waiting for your
   result. Please try again.” Backend execution succeeded. The shutdown cause was not established.
   The journal and backend were reconciled without repeating the attempt. After restoring the
   server, only the remaining three U3 attempts were submitted.
3. **Non-blocking wording polish.** Some A04 outputs refer to an “amount field” or “listed” values
   and omit Pat’s name. They still clearly request confirmation without endorsing a payment demand.

## Prior setup and interrupted series

A temporary mode-selector diagnostic stopped before submission; its trace had no scenario-start
request. The selector was corrected to click the visible label. The first submitted A04 in the
earlier series failed provider authentication (AuthenticationError, then RouterRateLimitError).
It produced no text. The user replaced the key and explicitly requested a fresh start; that
failed session is retained separately in the evidence and is not silently replaced in this series.

## Execution plan completed

1. Read the current prompt, workflow, UI and reusable browser collector; run doctor.
2. Build and verify the isolated live profile using existing credentials.
3. Submit the five original inputs three times through the form; retain all failures.
4. Reconcile full outputs, action/provider ledger, visible text and clipboard; review semantics.
5. Save evidence and findings for owner review; run local checks and stop owned services.

## Validation

- Managed Python 3.12 doctor: passed.
- Config and architecture validation: passed.
- Generated documentation drift check: passed.
- Quick-check: **not green** — 3,326 passed, 12 skipped, 654 deselected, one failed.
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user` failed because
  `sudo -n -u nobody` returned “interactive authentication is required”. This environment
  requirement was not bypassed and the test was not disabled. Duration: 638.81 seconds.
  The run used `LITELLM_LOCAL_MODEL_COST_MAP=True`; the initial default docs attempt hit a
  LiteLLM remote-cost-map import failure, resolved by the existing local-cost-map option.
  An initial sandboxed dependency refresh failed DNS; the approved network-enabled run
  restored the managed environment before these checks.
- Final documentation and whitespace validation: passed.
- Evidence self-check: 15 unique sessions, exact inputs, one A06/successful provider call each,
  actual model, configured effort with null ledger effort disclosed, hashes, text-only outputs,
  fourteen UI/clipboard matches and explicit interrupted record.

Local acceptance services were stopped after collection; database volumes and raw diagnostic
evidence were retained. A repository scan found pre-existing prohibited local command references
in unrelated ANY-17/339/391/221/227 documents; these were left untouched.

## Scope and remaining limits

This is the original five-case acceptance scope, using the ticket’s EN/RU inputs and unchanged
dates. RU/EN/ES translations, new cases, six-model comparison, production rollout and prompt
improvements are deferred. Do not infer Spanish performance from this run. Owner review is
still required; no Linear/GitHub publication or ticket acceptance was performed.

## Full inputs and outputs

### A04

UI language: en; tone: firm; amount: USD 1,200; due date: 7 October 2026.

Billing notes:

Client Pat. Our draft says total fee USD 2,000 and a 50% deposit (USD 1,000), but the amount field says USD 1,200. The client has not accepted the change. Do not imply the higher amount is agreed. Highlight the mismatch and request confirmation of deposit terms before sending any payment demand. Due date field is 7 October 2026, but Pat requested payment after final delivery on 20 October 2026; this is unresolved. No penalties were agreed.

#### A04-1 — PASS

Session: `scenario_session_01793958245058802073_0000000002_d6bb0d958887497686e80ca51a86f296`.

Both amounts and both dates remain unresolved and are presented for confirmation; no payment demand or payment-sent closing.
Visible text and clipboard equal the canonical text.

```text
Please confirm the deposit amount and due date before I send a payment request. The draft lists a 50% deposit of USD 1,000 based on a USD 2,000 total, while the amount field lists USD 1,200; the change has not been accepted. The due date is also unresolved: the field says 7 October 2026, while you requested payment after final delivery on 20 October 2026. Please reply with the deposit terms and due date you confirm.
```

#### A04-2 — PASS

Session: `scenario_session_01793958261609408950_0000000008_16f316d969984b0692c5a4fa5b7cf7c9`.

Both amounts and both dates remain unresolved and are presented for confirmation; no payment demand or payment-sent closing.
Visible text and clipboard equal the canonical text.

```text
Please confirm the deposit amount and due date. The amount listed is USD 1,200, while the draft describes a 50% deposit (USD 1,000) on a USD 2,000 total; the change has not been accepted. The listed due date is 7 October 2026, while your requested timing is after final delivery on 20 October 2026. Please reply with the confirmed terms.
```

#### A04-3 — PASS

Session: `scenario_session_01793958272623390968_0000000014_6d850c40d0d0451191c12bb713fa2b89`.

Both amounts and both dates remain unresolved and are presented for confirmation; no payment demand or payment-sent closing.
Visible text and clipboard equal the canonical text.

```text
Please confirm the deposit amount and payment timing. The draft lists a 50% deposit of USD 1,000, while the amount listed for billing is USD 1,200. The due date is listed as 7 October 2026, while your request was for payment after final delivery on 20 October 2026. Please confirm the deposit terms before I send a payment request.
```

### A01

UI language: ru; tone: warm; amount: 15 000 RUB; due date: (empty).

Billing notes:

Елена, начинаем дизайн презентации на 12 слайдов. Согласованная общая цена 30 000 RUB, предоплата 50% перед стартом, остаток после передачи финального PDF и PPTX. Попросить предоплату вежливо; реквизиты будут в отдельном счёте. Не заявлять, что счёт уже отправлен.

#### A01-1 — PASS

Session: `scenario_session_01793958287537156544_0000000020_daca8ef6883749c5a03f27b8e37f116b`.

15,000 RUB and 50% retained; no invented urgency. Name, balance after final PDF/PPTX and separate future invoice also retained.
Visible text and clipboard equal the canonical text.

```text
Елена, для начала дизайна презентации на 12 слайдов прошу внести предоплату 15 000 RUB — 50% от согласованной общей стоимости 30 000 RUB. Остаток оплачивается после передачи финальных PDF и PPTX. Реквизиты будут указаны в отдельном счёте. Пожалуйста, сообщите, когда отправите предоплату.
```

#### A01-2 — FAIL

Session: `scenario_session_01793958302221874553_0000000026_5afdd90147e64604975f1ef3dd7a735f`.

15,000 RUB retained but required 50% omitted; no invented urgency.
Visible text and clipboard equal the canonical text.

```text
Елена, для начала дизайна презентации на 12 слайдов прошу внести предоплату 15 000 RUB. Пожалуйста, сообщите, когда отправите оплату.
```

#### A01-3 — FAIL

Session: `scenario_session_01793958314384935989_0000000032_d5302b6e462a4a8ba4f08886f1c56aba`.

15,000 RUB retained but required 50% omitted; no invented urgency.
Visible text and clipboard equal the canonical text.

```text
Елена, для начала дизайна презентации на 12 слайдов прошу внести предоплату 15 000 RUB. Реквизиты будут в отдельном счёте. Пожалуйста, сообщите, когда предоплата будет отправлена.
```

### U1

UI language: en; tone: firm; amount: USD 800; due date: (empty).

Billing notes:

Client Sam. Agreed deposit USD 800 for the site redesign. The payment is urgent, needed ASAP.

#### U1-1 — PASS

Session: `scenario_session_01793958327034540824_0000000038_7445828ad362465494a630618e642c28`.

USD 800 and ASAP retained from notes, with no invented date.
Visible text and clipboard equal the canonical text.

```text
Please send the agreed USD 800 deposit for the site redesign ASAP. This payment is urgent. Let me know once it has been sent.
```

#### U1-2 — PASS

Session: `scenario_session_01793958338274582030_0000000044_df8ca0da3ddc4a279023fac69e475254`.

USD 800 and ASAP retained from notes, with no invented date.
Visible text and clipboard equal the canonical text.

```text
Hi Sam, please send the agreed USD 800 deposit for the site redesign. The payment is needed ASAP. Let me know once it has been sent.
```

#### U1-3 — PASS

Session: `scenario_session_01793958350775362285_0000000050_092251aefa2a48128591f9d02543dcca`.

USD 800 and ASAP retained from notes, with no invented date.
Visible text and clipboard equal the canonical text.

```text
Sam, the USD 800 deposit for the site redesign is needed ASAP. Please send it and let me know once it’s been sent.
```

### U2

UI language: en; tone: firm; amount: USD 800; due date: Friday — ASAP.

Billing notes:

Client Sam. Agreed deposit USD 800 for the site redesign.

#### U2-1 — PASS

Session: `scenario_session_01793958362188920962_0000000056_e800b6b91f7a418e941c55cff6d767ca`.

USD 800, Friday and explicit urgency retained.
Visible text and clipboard equal the canonical text.

```text
Hi Sam, please send the agreed USD 800 deposit for the site redesign by Friday, as soon as possible. Let me know once it has been sent.
```

#### U2-2 — PASS

Session: `scenario_session_01793958371260247769_0000000062_25e74bdb8fde4a5c9fb6655da305c428`.

USD 800, Friday and explicit urgency retained.
Visible text and clipboard equal the canonical text.

```text
Please send the agreed USD 800 deposit for the site redesign by Friday — ASAP. Let me know once it has been sent.
```

#### U2-3 — FAIL

Session: `scenario_session_01793958380574554480_0000000068_1579776e84e84b9bb8eeaa7643844341`.

USD 800, Friday and explicit urgency retained.
Backend recovery only; original UI delivery failed.

```text
The agreed deposit of USD 800 for the site redesign is due Friday — ASAP. Please send it and let me know once it has been sent.
```

### U3

UI language: en; tone: firm; amount: USD 800; due date: Friday — ASAP.

Billing notes:

Client Sam. Agreed deposit USD 800 for the site redesign. Not urgent, no rush.

#### U3-1 — PASS

Session: `scenario_session_01793958505584461569_0000000073_fe1d3b1e4cc1483ba6a5249a71504a11`.

USD 800 and Friday retained; no urgency despite ASAP in due_date.
Visible text and clipboard equal the canonical text.

```text
Hi Sam, please send the agreed USD 800 deposit for the site redesign by Friday. Please let me know once it has been sent.
```

#### U3-2 — PASS

Session: `scenario_session_01793958514086681659_0000000079_922763538eb0410db55e160d7b764d98`.

USD 800 and Friday retained; no urgency despite ASAP in due_date.
Visible text and clipboard equal the canonical text.

```text
Please arrange the agreed USD 800 deposit for the site redesign by Friday. Let me know once the payment has been sent.
```

#### U3-3 — PASS

Session: `scenario_session_01793958524939896929_0000000085_51dd165fa5ae4a9ea9e6e52ed372fe30`.

USD 800 and Friday retained; no urgency despite ASAP in due_date.
Visible text and clipboard equal the canonical text.

```text
Please send the USD 800 deposit for the site redesign by Friday. Let me know once it has been sent.
```

## Targeted live recheck — 2026-11-06

User requested fresh live verification of the two reported problems. Six new browser attempts
were collected separately, without overwriting or rerunning any original attempt. Source prompt,
workflow and router hashes match the original series. No code or prompt changes. No parallel
repository tests ran during this series. Runtime remains gpt-6-luna with configured medium;
provider ledger reasoning_effort remains null.

| Case | New semantic results | New UI/Copy results | Conclusion |
| --- | --- | --- | --- |
| A01 | 3/3 | 3/3 | Missing 50% did not recur; historical omission remains 2/6 across both series |
| U2 | 3/3 | 3/3 | Connection failure did not recur; original failed attempt remains recorded |

All six results contain text only, with one successful A06 action and one successful provider call
each. Exact clipboard and visible text match the canonical result. Evidence self-check validates
unique sessions, unchanged inputs/config hashes, trace hashes, ledger and output consistency.
Runtime ledger estimated cost of this recheck: USD 0.001000910.

Additional observation: all three new A01 outputs omit the remaining balance after final PDF/PPTX.
That detail is outside the explicit A01 percentage/urgency AC, but remains a content-quality caveat.
A passing small repeat sample is not evidence of a fix or proof that intermittent omissions cannot recur.
Original quick-check results remain unchanged; no full rerun was needed for evidence-only edits.
Documentation and whitespace validation passed. Local services were stopped after collection.

### Recheck A01-1 — PASS

Session: `scenario_session_01793959368394983552_0000000002_0c772ea114654bbe88e5b2d915381249`.

15,000 RUB and 50% retained without invented urgency; balance after final PDF/PPTX omitted (outside explicit percentage AC).

```text
Елена, для начала дизайна презентации на 12 слайдов прошу внести предоплату 15 000 RUB — 50% от согласованной общей стоимости. Реквизиты будут в отдельном счёте. Пожалуйста, сообщите, когда отправите оплату.
```

### Recheck A01-2 — PASS

Session: `scenario_session_01793959381937681372_0000000008_1d41e967769f46adb5cf106a7f274065`.

15,000 RUB and 50% retained without invented urgency; balance after final PDF/PPTX omitted (outside explicit percentage AC).

```text
Елена, для начала дизайна презентации на 12 слайдов прошу внести предоплату 15 000 RUB — 50% от согласованной общей стоимости 30 000 RUB. Реквизиты будут в отдельном счёте. Пожалуйста, сообщите, когда отправите оплату.
```

### Recheck A01-3 — PASS

Session: `scenario_session_01793959392293951826_0000000014_290efdf4a21a4b87938ea2e52ffbfe19`.

15,000 RUB and 50% retained without invented urgency; balance after final PDF/PPTX omitted (outside explicit percentage AC).

```text
Елена, для начала дизайна презентации на 12 слайдов прошу внести предоплату 15 000 RUB — 50% от согласованной стоимости. Реквизиты будут в отдельном счёте. Пожалуйста, сообщите, когда отправите оплату.
```

### Recheck U2-1 — PASS

Session: `scenario_session_01793959400740277771_0000000020_ec5c998820a34eaa89d62c5bb18c5459`.

USD 800, Friday and ASAP retained; visible and copied text match canonical output.

```text
Sam, the agreed USD 800 deposit for the site redesign is due Friday and is needed ASAP. Please send it and let me know once it has been sent.
```

### Recheck U2-2 — PASS

Session: `scenario_session_01793959412034301726_0000000026_92f7010ca55b4f73b8fba90e198b4f87`.

USD 800, Friday and ASAP retained; visible and copied text match canonical output.

```text
Please send the agreed USD 800 deposit for the site redesign by Friday, ASAP. Let me know once it has been sent.
```

### Recheck U2-3 — PASS

Session: `scenario_session_01793959422744945228_0000000032_5caf697b5d5b4cc394da8c2f9a97e971`.

USD 800, Friday and ASAP retained; visible and copied text match canonical output.

```text
Sam, please send the agreed USD 800 deposit for the site redesign by Friday — ASAP. Let me know once it’s been sent.
```

## Post-fix live verification — 2026-11-06

The user authorized a bounded fix inside ANY-604. The Prepaid prompt now preserves the complete
explicit payment arrangement and clarifies that only the amount still owed is requested now.
One contract regression was added to the existing product tests; its partial-receipt wording
assertion was updated. Runtime, schema, mapping, model and fake-provider fixtures did not change.

| Cases | Attempts | Semantic result | UI and Copy |
| --- | --- | --- | --- |
| A04, A01 RU, U1, U2, U3 (original ticket scope) | 15 | 15 PASS | 15/15 |
| A01 EN | 3 | 3 PASS | 3/3 |
| A01 ES | 3 | 2 PASS, 1 REVIEW | 3/3 |

The extra EN/ES inputs are translations of A01; full inputs appear in the structured evidence.
Other cases were retained in their original ticket languages. This is targeted language coverage,
not a complete three-language model comparison. Each session has one successful A06 and one
successful gpt-6-luna call; each text-only result matches the visible and actually copied text.
Worker prompt/workflow/router readback matched the checkout in all three segments. Only the
prompt hash changed from the prior series. Source SHA identifies the base commit; the evidence
explicitly records working-tree prompt/test changes. Configured reasoning is medium; ledger
reasoning_effort remains null and is not claimed as independently verified.

Post-fix runtime ledger cost estimate: USD 0.007221540. Median UI delivery: 6.31s.

### Caveat for owner acceptance

A01-ES-2 says “anticipo del 50% de 15 000 RUB sobre el precio total acordado de 30 000 RUB”.
Although all supplied values and remaining payment conditions are present, the wording can be
read as applying 50% to the deposit instead of the total. It needs manual wording correction
before sending. This sample is REVIEW, not a silent PASS. The original ticket criteria passed;
the owner decides whether this additional language caveat is acceptable for this product iteration.
No further prompt loop or model rollout was performed. Small samples cannot guarantee retention.

### Post-fix validation

- Managed Python 3.12 doctor passed.
- Existing Client Update Writer product tests, including the new prompt contract test, passed.
- Ruff comparison against HEAD: zero new findings; nine pre-existing line-length findings remain.
- Config, architecture and generated-document validation passed within quick-check.
- Final quick-check: 3,326 passed, 12 skipped, 654 deselected, one environment failure
  (`sudo -n -u nobody`: interactive authentication required), 674.06 seconds. Same failure as
  before the prompt change; no test was bypassed. Product tests passed separately.
- Evidence self-check validates all 21 inputs, distinct sessions, trace hashes, text-only
  output, actual model, single actions/provider calls and UI/clipboard equality.

### Complete post-fix outputs

#### Post-fix A04-1 — PASS

Session: `scenario_session_01793961097893853434_0000000002_c3e4e63bb7ca4d0887cd65abaf9cc429`.

Both amounts and dates are presented for confirmation, without a payment demand or payment-sent closing.

```text
Before I send a payment request, please confirm the deposit terms: the amount is listed as USD 1,200, while the draft specifies a USD 1,000 deposit (50% of a USD 2,000 total), and the change has not been accepted. Please also confirm whether the due date is 7 October 2026 or after final delivery on 20 October 2026. Please reply with your confirmation.
```

#### Post-fix A04-2 — PASS

Session: `scenario_session_01793961116357593194_0000000008_3d8fccc359fe45e2a96f35c886335e9b`.

Both amounts and dates are presented for confirmation, without a payment demand or payment-sent closing.

```text
The deposit terms are unresolved: the draft lists a 50% deposit of USD 1,000 against a total fee of USD 2,000, while the amount field lists USD 1,200. The due date is also unresolved: the date field says 7 October 2026, while you requested payment after final delivery on 20 October 2026. Please confirm the deposit terms and payment timing.
```

#### Post-fix A04-3 — PASS

Session: `scenario_session_01793961129902176125_0000000014_a5e46d70e879429a929bffaabdcc0039`.

Both amounts and dates are presented for confirmation, without a payment demand or payment-sent closing.

```text
Before I send a payment request, please confirm the deposit terms: the draft lists a 50% deposit of USD 1,000 on a USD 2,000 total, while the billing amount is USD 1,200, and the change has not been accepted. Please also confirm when the deposit is due: 7 October 2026 or after final delivery on 20 October 2026. Please reply with your confirmation.
```

#### Post-fix A01-1 — PASS

Session: `scenario_session_01793961143386644437_0000000020_adef3897faad47868fecb61f5646f959`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Елена, для начала дизайна презентации на 12 слайдов прошу внести предоплату 15 000 RUB — это 50% от согласованной общей стоимости 30 000 RUB. Оставшаяся часть оплачивается после передачи финальных PDF и PPTX. Реквизиты будут в отдельном счёте. Пожалуйста, сообщите, когда отправите предоплату.
```

#### Post-fix A01-2 — PASS

Session: `scenario_session_01793961157703798001_0000000026_a3781bd458d34cb7ba0d450290d2c978`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Елена, пожалуйста, внесите предоплату 15 000 RUB за дизайн презентации на 12 слайдов — это 50% от согласованной общей стоимости 30 000 RUB. Предоплата вносится перед началом работы; реквизиты будут в отдельном счёте. Остаток оплачивается после передачи финальных PDF и PPTX. Пожалуйста, сообщите, когда отправите предоплату.
```

#### Post-fix A01-3 — PASS

Session: `scenario_session_01793961171213013095_0000000032_215b750b0f9a4ccdb346765b8dc956f2`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Елена, для начала дизайна презентации на 12 слайдов предусмотрена предоплата 50% от согласованной общей стоимости 30 000 RUB — 15 000 RUB. Остаток оплачивается после передачи финальных PDF и PPTX. Реквизиты будут в отдельном счёте. Пожалуйста, сообщите, когда отправите предоплату.
```

#### Post-fix U1-1 — PASS

Session: `scenario_session_01793961184864511730_0000000038_76e08a42e7084eb79ae4cb28e2bc2791`.

USD 800 and notes urgency preserved without an invented date.

```text
Sam, please send the USD 800 deposit for the site redesign ASAP, as the payment is urgent. Let me know once it has been sent.
```

#### Post-fix U1-2 — PASS

Session: `scenario_session_01793961195339579774_0000000044_d0f973d4b306451bb53dc1a8b791e829`.

USD 800 and notes urgency preserved without an invented date.

```text
Sam, the agreed USD 800 deposit for the site redesign is urgent and needed ASAP. Please send it and let me know once it has been sent.
```

#### Post-fix U1-3 — PASS

Session: `scenario_session_01793961204845926921_0000000050_949e0039127a4a8f9d633e7c62719e39`.

USD 800 and notes urgency preserved without an invented date.

```text
Sam, please send the USD 800 deposit for the site redesign. This payment is urgent and needed ASAP. Please let me know once it has been sent.
```

#### Post-fix U2-1 — PASS

Session: `scenario_session_01793961234223829053_0000000056_7ae58239e97744abae2461c9af71c051`.

USD 800, Friday and ASAP retained.

```text
Sam, the agreed USD 800 deposit for the site redesign is due Friday and is needed ASAP. Please send it and let me know once it has been sent.
```

#### Post-fix U2-2 — PASS

Session: `scenario_session_01793961243069343645_0000000062_07ced60e89e2484884e785a8365fee48`.

USD 800, Friday and ASAP retained.

```text
Sam, please send the agreed USD 800 deposit for the site redesign. It is due Friday — ASAP. Please let me know once you’ve sent the payment.
```

#### Post-fix U2-3 — PASS

Session: `scenario_session_01793961254285195929_0000000068_81327f73f2b743008fe3ed3d91fb24b4`.

USD 800, Friday and ASAP retained.

```text
Please send the agreed USD 800 deposit for the site redesign by Friday; it is needed ASAP. Please let me know once it has been sent.
```

#### Post-fix U3-1 — PASS

Session: `scenario_session_01793961265612641753_0000000074_26a5c223cfe147498aee65a7ace1477d`.

USD 800 and Friday retained; notes override ASAP and no urgency appears.

```text
Please send the agreed USD 800 deposit for the site redesign by Friday. Please let me know once it has been sent.
```

#### Post-fix U3-2 — PASS

Session: `scenario_session_01793961277569998260_0000000080_c0fd26e77812436bb2b48b8cbc2f58bc`.

USD 800 and Friday retained; notes override ASAP and no urgency appears.

```text
Please send the agreed USD 800 deposit for the site redesign by Friday. Let me know once it has been sent.
```

#### Post-fix U3-3 — PASS

Session: `scenario_session_01793961288999251706_0000000086_95c510017c6a44fea00eefec857b7f99`.

USD 800 and Friday retained; notes override ASAP and no urgency appears.

```text
Sam, please send the agreed USD 800 deposit for the site redesign by Friday. Let me know once the payment has been sent.
```

#### Post-fix A01-EN-1 — PASS

Session: `scenario_session_01793961325205346679_0000000092_494ec9ca335048239f4de3b73fd61001`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Hi Elena, for the 12-slide presentation design, the agreed total is RUB 30,000, with a 50% prepayment of RUB 15,000 before work starts. The remaining balance is due after delivery of the final PDF and PPTX. Payment details will be provided in a separate invoice. Could you please arrange the prepayment and let me know once it’s been sent? Thank you!
```

#### Post-fix A01-EN-2 — PASS

Session: `scenario_session_01793961336236274718_0000000098_3a5f91df83f84d0f808b0abc8ed5e9c7`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Hi Elena, we’re starting the design of your 12-slide presentation. The agreed total is 30,000 RUB, with a 50% prepayment of 15,000 RUB before work starts and the balance due after delivery of the final PDF and PPTX. Payment details will be in a separate invoice. Please let me know once you’ve sent the prepayment. Thank you!
```

#### Post-fix A01-EN-3 — PASS

Session: `scenario_session_01793961348184976842_0000000104_8e11c3cee9934b91a5d52d3460af3267`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Hi Elena, for the 12-slide presentation design, the agreed total is 30,000 RUB, with a 50% prepayment of 15 000 RUB before work starts. The balance is due after delivery of the final PDF and PPTX. Please arrange the prepayment; payment details will be provided in a separate invoice. Please let me know once the payment has been sent.
```

#### Post-fix A01-ES-1 — PASS

Session: `scenario_session_01793961359834971393_0000000110_0f1702e0f3074406a7aa7084e1948615`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Hola, Elena. Para el diseño de la presentación de 12 diapositivas, el precio total acordado es de 30 000 RUB. Te agradecería que realizaras el anticipo del 50% (15 000 RUB) antes de empezar. El saldo se abonará después de entregar los archivos PDF y PPTX finales. Los datos de pago estarán en una factura aparte. Avísame, por favor, cuando hayas enviado el anticipo.
```

#### Post-fix A01-ES-2 — REVIEW

Session: `scenario_session_01793961372786545963_0000000116_a9bd2288cf8f420bb83b9e1a3248072c`.

Terms retained, but “anticipo del 50% de 15 000 RUB” ambiguously attaches the percentage to the deposit amount. Manual wording correction required before sending; not an unconditional semantic PASS.

```text
Para el diseño de la presentación de 12 diapositivas, ¿podrías realizar el anticipo del 50% de 15 000 RUB sobre el precio total acordado de 30 000 RUB? El saldo se abonará después de entregar los archivos finales en PDF y PPTX. Los datos de pago estarán en una factura aparte. Por favor, avísame cuando hayas enviado el pago. ¡Muchas gracias!
```

#### Post-fix A01-ES-3 — PASS

Session: `scenario_session_01793961386374587600_0000000122_98d8ac871f7f48f689925dcb83463b2e`.

15,000 RUB, 50%, agreed 30,000 RUB total, balance after final PDF/PPTX and future separate invoice all retained; no invented urgency.

```text
Hola, Elena. Para el diseño de la presentación de 12 diapositivas, el precio total acordado es de 30 000 RUB, con un anticipo del 50% antes de empezar. ¿Podrías realizar el anticipo de 15 000 RUB? Los datos de pago estarán en una factura aparte. El saldo se abonará después de entregar los archivos finales en PDF y PPTX. Avísame, por favor, cuando hayas realizado el pago.
```
