# ANY-604: complete acceptance on the notes-priority prompt

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: see the subsequent A04 fix and rerun in the acceptance report; language work remains in ANY-771
- Blocker: historical series contains four FAILs; later fixes do not rewrite these results

## Goal

Complete the remaining acceptance cases on the exact prompt already checked by review round 3.
The user clarified that the missing scope is A01/A04/U1, not every platform atom.

## Implementation plan

1. Verify current prompt/workflow/router hashes against the preceding 18 U2/U3 attempts and
   deployed worker. Keep the same inputs, model, tone, dates and original language equivalents.
2. Run A01/A04/U1 three times per language (RU/EN/ES), 27 new browser attempts. Preserve every
   attempt and provider retry, full output, UI/clipboard proof, session/artifact IDs and trace hashes.
3. Read all outputs: A01 requires a direct request, unambiguous 50% of 30,000 RUB = 15,000 RUB,
   balance/invoice terms and no invented urgency. A04 only asks to confirm both amounts/dates,
   with no payment demand or sent-payment follow-up. U1 retains USD 800 and explicit urgency
   without inventing a date. Verify the requested language and text-only single A06 execution.
4. Combine with the earlier U2/U3 only if runtime hashes match, clearly separating 27 new runs
   from 18 earlier runs. Retain the U3-RU-3 spelling caveat and all historical failures.
5. Update local report/evidence and the attached Linear report, validate evidence/docs, and stop
   owned services. No product changes, new test suite, autonomous ticket acceptance or PR writes.

## Limits

Model semantics are assessed by reading outputs, not by keyword matching. Successful finite
samples do not guarantee future generation. Full code checks are not repeated for QA-only changes.

## Results

The 27 new attempts completed on the exact prompt/workflow/router hashes of the preceding
18 U2/U3 attempts. New series: 23/27 PASS. Combined current-prompt matrix: 41/45, FAIL.
A01: RU 3/3, EN 1/3, ES 3/3. A04: RU 2/3, EN 2/3, ES 3/3. U1: all languages 3/3.
The preceding U2/U3 remain 18/18 on the same prompt, with the known minor U3-RU-3 typo.

- A01-EN-2 and A01-EN-3 return Spanish text for English notes. Payment terms otherwise pass.
  Their remediation is assigned to [ANY-771](https://linear.app/paveldik/issue/ANY-771), whose
  scope and acceptance checks now include Client Update Writer. They remain observed FAILs;
  planned remediation is not proof that the language issue is already fixed.
- A04-RU-1 and A04-EN-2 ask to confirm terms but omit both amounts and both dates required by AC.
- Captured POST inputs match the intended notes/amount/date/tone; no language or length
  constraint is sent. Result and action session IDs match the started session. This rules out
  a collector input mix-up or attaching an unrelated response to these four attempts.
- All 27 outputs reached the UI and clipboard unchanged, with one successful A06 each.
  There are 29 physical calls: A01-1 and A01-2 each have an internal semantic retry. Both costs
  are included; the exact retry reason is unknown. Combined with U2/U3 there are 47 calls.
- No failed attempt was resubmitted or replaced. All earlier evidence and verdicts are unchanged.
  No prompt/product correction or model comparison was performed during this QA-only request.

Full raw responses, semantic assessments and sanitized failed-input audits are in the
[acceptance report](any-604-prepaid-request-live-acceptance.md) and its adjacent evidence JSON.
This result closes the coverage gap but does not establish acceptance. The four new failures are
separate from the older 41/45 series with different failures on an earlier prompt revision.

Final documentation, whitespace and evidence checks passed, including actual submitted inputs
and result/action session correspondence for all 27 new attempts. Owned live services were
stopped; database volumes and traces remain. No code tests were repeated for QA-only changes.

## Subsequent A04 correction

The confirmation-values prompt change was subsequently checked with nine fresh A04 attempts:
RU/EN/ES each 3/3 PASS for the disputed-value and confirmation criteria. Three outputs retain
a minor editorial-phrase caveat. See the [acceptance report](any-604-prepaid-request-live-acceptance.md)
for complete outputs and provenance. This plan's 41/45 matrix stays historical: the prompt hash
changed, and A01/U1/U2/U3 were not rerun on the new hash. Language remediation stays in ANY-771.
