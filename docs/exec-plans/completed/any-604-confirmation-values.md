# ANY-604: retain concrete values in terms confirmation

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the targeted A04 fix and evidence
- Blocker: none

## Goal and scope

Fix observed A04-RU-1 and A04-EN-2 omissions of both disputed amounts and dates.
The existing confirmation rule names conditions without explicitly requiring their known
candidates; its length fallback also needs an explicit supplied-limit prerequisite.
One Prepaid prompt and its contract test change. The existing workflow is its only consumer;
sibling products do not contain this confirmation/fallback rule. No schema, UI, model or
runtime change. Preserve confidentiality, unknown-value handling and the ban on payment demands.

## Implementation plan

1. Require all concrete current candidate values, with currency and timing relations, in rule B.
   Gate the omission fallback on an explicitly supplied length limit; retain privacy precedence.
2. Add a focused prompt contract regression and run product/config/architecture/docs checks.
3. Reuse unchanged A04 RU/EN/ES inputs, three browser attempts each. Verify runtime hashes,
   both USD 1,000 / USD 1,200 and 7 / 20 October 2026, after-delivery meaning, confirmation only,
   language, one A06, text-only result and actual UI/clipboard equality.
4. Preserve prior failures and complete outputs, report the fresh series separately, and stop
   owned services. Language failures remain assigned to ANY-771. Do not combine prompt hashes
   into a full-matrix claim; A01/U1/U2/U3 are outside this requested rerun.

## Results

The new focused regression and all 71 product tests pass. Managed doctor, configuration,
architecture, documentation and generated-doc checks pass; no new Ruff findings (nine existing
line-length findings remain). The old prompt lacks both new safeguards, confirming the contract
regression covers this change. No workflow/router/model changes were needed.

Fresh live A04: RU 3/3, EN 3/3, ES 3/3 PASS for financial/confirmation/language criteria.
Each result preserves USD 1,000 / USD 1,200 and 7 / 20 October 2026, including after-delivery
meaning, without asking for payment or asserting disputed agreement. Nine unique sessions,
nine successful A06 actions and nine physical gpt-6-luna calls; estimated total USD 0.00412640.
All actual POST inputs match the frozen cases, result/action/session IDs correlate, and backend
text equals visible text and actual clipboard. Worker hashes match checkout; historical prompt
evidence is kept separately. Full inputs, outputs and assessments are in the adjacent
[acceptance report](any-604-prepaid-request-live-acceptance.md) and its evidence JSON.

A04-RU-3 / ES-1 / ES-3 repeat the editorial phrase “before sending a payment request”.
This is a minor instruction-following caveat, not a payment demand or missing financial term;
retain it for iterative wording polish. No claim of complete prompt compliance is made.

A01/U1/U2/U3 were not rerun on this hash; the old 41/45 matrix remains historical. Language
failures remain assigned to ANY-771, and the historical U3-RU-3 typo is unchanged. No full
quick-check/frontend suite or model comparison was run; the bounded fix meets the requested
A04 criteria without changing models. No external publication or ticket acceptance occurred.

Final evidence/docs/whitespace checks passed. Owned web/API/worker/PostgreSQL services stopped; database volumes and diagnostic traces retained.

The repository-wide forbidden review-command wording scan still finds pre-existing references
in other tickets (including ANY-17, ANY-220 and ANY-227); none occur in files changed here.
Those unrelated historical documents were left untouched.
