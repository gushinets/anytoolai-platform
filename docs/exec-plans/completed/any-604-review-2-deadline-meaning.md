# ANY-604: preserve payment deadline meaning

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the targeted U2 result and corrected historical acceptance
- Blocker: none

## Goal

Preserve a due-by deadline across languages instead of changing it into an instruction to pay
only on that day. Correct four false PASS assessments and replace outdated PR reporting.

## Implementation plan

1. Keep one product-owned prompt rule: preserve the temporal relation, not just the date token.
   A due-by date allows earlier payment; explicit on/after/before conditions must retain their
   meaning. Notes retain precedence and ASAP must not become a request to wait until the due day.
2. Extend the existing prompt-contract tests. No parser, schema, workflow, UI or model changes.
3. Reassess U2-RU-2 and U2-ES-1/2/3 as FAIL, preserving raw outputs and previous assessments.
   Mark the preceding matrix 41/45. Do not combine samples from different prompt revisions.
4. Run the same frozen U2 RU/EN/ES inputs through the live form three times each. Review amount,
   due-by meaning, urgency, language, text-only output, one A06 and actual UI/clipboard equality.
5. Run product/config/architecture/docs checks, retain full new evidence, update local reports
   and the PR, and stop owned services. Publish the corrected result to the existing Linear
   report thread as part of updating the authorized reports. Preserve historical failures.

## Scope and limits

The existing Prepaid form reaches one prompt consumer. Sibling products were searched; they do
not share this due_date instruction. This is a confirmed Prepaid defect, not evidence of failures
in untested products. The live scope is nine U2 attempts; A01/A04/U1/U3 are historical on the
previous prompt. If the bounded clarification fails, compare models instead of looping on prompts.
The previous quick-check sudo environment failure must remain visible if not rerun or resolved.

## Results

- Deadline semantics clarified in the existing prompt; one contract regression added.
- All 70 product tests pass; regression control confirms the previous prompt lacked the rule.
- All nine fresh U2 RU/EN/ES outputs explicitly request USD 800 as soon as possible and no later
  than Friday. Earlier payment is permitted. Every output matches UI and actual clipboard;
  each session has one successful A06 and one physical gpt-6-luna call.
- U2-RU-2 and U2-ES-1/2/3 from the preceding series are FAIL, with original text and earlier
  assessments preserved. The prior full matrix is 41/45; the current U2 series is 9/9.
- The prompt hash changed; workflow/router hashes did not. Other cases have not been rerun on
  this revision. Historical U2/U3 outputs were also read; no additional same-class failures found.
- Managed Python 3.12 doctor, config, architecture and generated-doc checks passed. System
  Python 3.14 doctor initially lacked pytest/pydantic. No new Ruff findings (nine pre-existing).
- The first live bootstrap stopped because source changed during build; no submissions occurred.
  The restart verified canonical source and deployed profile before any browser attempt.
- Full quick-check was not repeated. Its prior passwordless-sudo failure remains historical;
  no current baseline or CI pass is claimed. No assertions or tests were bypassed.

Full new inputs, outputs, session/ledger evidence and quoted temporal assessments are in the
[acceptance report](any-604-prepaid-request-live-acceptance.md) and its adjacent JSON. Reports
explicitly separate the two prompt revisions. Final documentation, whitespace and evidence
consistency checks passed. Owned live services were stopped; database volumes and traces remain.
