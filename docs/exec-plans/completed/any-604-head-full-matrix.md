# ANY-604: complete the live matrix at 87e1bb64

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the A01-ES-3 status finding and complete evidence
- Blocker: no confirmed critical defect; owner acceptance with a low-severity caveat pending

## Goal and scope

Complete coverage of the current committed prompt. Older successful generations do not verify
this version. This is verification and reporting only; do not change product code, prompts,
models, configuration or tests to repair findings during the run.

## Implementation plan

1. Verify clean product sources at 87e1bb64 and byte-identical prompt/workflow/router hashes to
   the latest nine A04 attempts. Freeze the existing A01/U1/U2/U3 inputs in RU/EN/ES.
2. Run three browser attempts per input: 36 new submissions. Preserve every result and physical
   provider call. Check actual POST inputs, action/result/session correlation, text-only output,
   one A06 and exact backend/UI/clipboard equality.
3. Read all full outputs. A01: explicit 15,000 RUB request, 50% of 30,000 RUB, remaining balance
   after PDF/PPTX and a future separate invoice, no invented urgency. U1: USD 800 urgently with
   no invented deadline. U2: USD 800 ASAP and no later than Friday. U3: USD 800 no later than
   Friday with no urgency despite ASAP in the date field. Check language in every response.
4. Combine the 36 new results with the nine latest A04 only on identical runtime hashes. Keep
   prior series immutable, report failures honestly, preserve ANY-771 language ownership, update
   local evidence and stop owned services. No automatic fixes, publication or ticket acceptance.

## Results

Coverage is complete at 87e1bb64: 36 fresh A01/U1/U2/U3 attempts and nine preceding A04
with identical runtime prompt/workflow/router hashes. New series 35/36 PASS; combined 44/45.
A01: RU 3/3, EN 3/3, ES 2/3. A04/U1/U2/U3: each language 3/3. The original ticket language
subset (A01 RU; other four cases EN) is 15/15; this does not replace the 44/45 full regression result.
No language failure occurred in the new series; historical language failures remain in ANY-771.

A01-ES-3 preserves amount, percentage, total, balance, future invoice and no-urgency requirements,
but adds “ya está en marcha” and says prepayment “debía abonarse antes de empezar”. The input
says the design is starting with prepayment before starting; it does not explicitly establish
already-started work without payment or a late prepayment. This stronger, retrospective payment
status is recorded as a semantic FAIL. No code/prompt change or replacement generation was made.

Every new attempt has one successful A06, a text-only result, matching backend/UI/clipboard,
correct actual POST input and correlated action/result/session IDs. There are 36 physical calls
for the new series, with no internal retries, and 47 calls across the combined matrix (A04 had 11).
Complete outputs, semantic assessments, input audits and hashes are in the adjacent
[acceptance report](any-604-prepaid-request-live-acceptance.md) and evidence JSON. All earlier
series and verdicts remain unchanged. No full-matrix PASS or automatic ticket acceptance is claimed.

Doctor passed. Product tests and full quick-check were not repeated for this verification-only
pass; product source/model/configuration/tests are unchanged. No external publication or GitHub
write is part of this pass.

Final documentation, whitespace and evidence-consistency checks passed. Owned web/API/worker/PostgreSQL services stopped; database volumes and raw traces retained. Reports were local at completion of verification; the user subsequently authorized publication, commit and push.

## Severity clarification

A01-ES-3 is low severity and is not recommended as a blocker for this iteration. The source
“empezamos” is ambiguous; the response makes a stronger statement about work/payment status.
All financial amounts, percentage, balance, invoice and urgency checks pass. Recommend owner
acceptance with a wording caveat, correcting it before sending when necessary. The conservative
FAIL and 44/45 remain unchanged; no new generation or source fix was performed.
