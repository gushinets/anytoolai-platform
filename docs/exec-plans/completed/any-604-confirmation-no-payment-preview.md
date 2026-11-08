# ANY-604: omit editorial payment-request sequencing

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the fix and fresh A04 evidence
- Blocker: none

## Goal and scope

The preceding A04 series retained all disputed values but three responses echoed the editorial
sequence “before sending a payment request”. Distinguish message-selection instructions from
client-relevant business terms in rule B itself. One Prepaid workflow uses this prompt. Generic
editorial non-reporting instructions also exist in other Client Update Writer modes and ProposalAI,
but they do not contain this payment-confirmation decision rule; no failure there is established.
No schema, workflow, runtime, UI, dependency or model change is needed.

## Implementation plan

1. Explain that directions about when to ask for payment choose the message kind, not a future
   client-facing action. Omit announcements/promises of later payment requests from confirmation;
   retain actual invoice, delivery and payment terms and every disputed candidate value.
2. Add a focused prompt contract test and run product/config/architecture/docs checks.
3. Repeat frozen A04 RU/EN/ES inputs three times each through the live form. Assess complete
   outputs for both amounts/dates, timing meaning, confirmation only, no payment-request preview,
   matching language, one A06, text-only result and exact UI/clipboard equality.
4. Verify runtime hashes, actual POST inputs and action/result/session correspondence. Preserve
   all historical evidence, append full fresh results, and stop owned services. Keep ANY-771
   language ownership and separate prompt revisions; no full-matrix or ticket-acceptance claim.

## Results

Rule B now treats payment-request sequencing as a message-selection instruction, not a
client-facing future action. It explicitly omits announcements/promises of later requests and
preserves actual invoice/delivery/payment terms. The earlier candidate-value safeguards remain.
The new focused contract test and all 72 product tests pass. Doctor, config, architecture,
documentation and generated-doc checks pass. Ruff has no new findings (nine existing line-length
findings); the preceding prompt lacks the new message-selection rule used by the regression test.

Fresh live A04: RU 3/3, EN 3/3, ES 3/3 PASS, now including the no-preview criterion. All nine
outputs preserve both USD 1,000 / USD 1,200 and 7 / 20 October 2026 with the after-delivery
relation, ask only for confirmation and omit the editorial payment-request sequence. No additional
wording caveat was found in this sample. Actual POST inputs match the frozen cases, action/result
sessions correlate, and text-only backend/UI/clipboard outputs are equal. Nine unique sessions
and successful A06 actions; 11 physical gpt-6-luna calls, estimated total USD 0.00477517.
A04-ES-1 and A04-ES-2 each have two internal semantic attempts; exact retry reasons are not
established by the captured evidence. All calls and costs are retained, with no browser resubmission.

Runtime prompt matches the checkout with a new hash; workflow/router/model are unchanged. All
preceding series and assessments remain unchanged in the [acceptance report](any-604-prepaid-request-live-acceptance.md)
and evidence JSON. A01/U1/U2/U3 were not rerun on this hash; no full-matrix acceptance is claimed.
Language failures remain assigned to ANY-771. No full quick-check/frontend suite or model
comparison was run; the bounded prompt change meets the requested criteria on the existing model.
No external publication, commit, push or ticket acceptance occurred.

Final evidence, documentation and whitespace checks passed. Owned web/API/worker/PostgreSQL services stopped; database volumes and raw traces retained. Existing forbidden review-command wording in five unrelated files was left untouched; changed files contain none.
