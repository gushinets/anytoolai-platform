# ANY-604: keep notes authoritative over deadline urgency

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the local change and targeted U2/U3 evidence
- Blocker: none

## Goal

Remove ambiguity between the new ASAP/deadline explanation and the existing rule that no-rush
notes override urgency in due_date. This is a contract and coverage risk, not an observed U3 failure.

## Implementation plan

1. Qualify the existing ASAP explanation with the notes exception. Keep the later urgency rule
   authoritative, preserve due-by meaning, and extend the existing deadline contract test.
2. Freeze the unchanged U2/U3 RU/EN/ES inputs. Run each three times through the live form,
   retaining every attempt and provider retry. Verify the deployed prompt against the checkout.
3. Read all 18 outputs: USD 800 payment request, Friday due-by deadline, U2 urgency retained,
   U3 urgency absent, correct language, one A06, text-only output and actual UI/clipboard equality.
4. Preserve earlier evidence and verdicts; record this prompt revision separately. Run relevant
   product/config/architecture/docs checks, update local reports and stop owned live services.

## Scope and limits

One existing Prepaid prompt consumer; no schema, workflow, UI, runtime, dependency or model change.
Sibling products do not share this due_date/ASAP instruction. No failure in an untested product
is claimed. A01/A04/U1 are not part of this rerun. Do not combine different prompt revisions into
a full-matrix PASS. Current request covers implementation and live verification, not publication.

## Results

The deadline paragraph now qualifies ASAP with the explicit not-urgent/no-rush notes exception.
The existing urgency rule is unchanged. The existing deadline contract test requires the
qualification inside that paragraph; a regression control confirms it is absent before the fix.
All 70 product tests passed. Managed Python 3.12 doctor, config, architecture and generated-doc
checks passed; there are no new Ruff findings.

Fresh U2/U3 RU/EN/ES: 18/18 semantic PASS (three repetitions of each of six unchanged inputs).
U2 preserves urgency; U3 removes it. Every response requests USD 800 and preserves the Friday
due-by relation. Each attempt has one successful A06 and one physical gpt-6-luna call, with
text-only output equal to the displayed text and actual clipboard. Prompt hash differs from
review round 2; workflow/router hashes match. No earlier evidence or verdict was rewritten.

Minor quality caveat: U3-RU-3 says "согласанную" instead of "согласованную". Its amount, deadline
and urgency criteria pass; the typo should be corrected before sending. The raw text is retained.
No observed U3 failure on the preceding prompt is claimed. A01/A04/U1 were not rerun on this
revision. Full quick-check/frontend checks were not repeated; previous CI results are historical.

Full inputs, outputs, hashes and quoted semantic assessments are in the adjacent
[acceptance report](any-604-prepaid-request-live-acceptance.md) and its evidence JSON. Local
reporting only; no commit, push, GitHub or Linear writes were performed in this round.
Documentation, whitespace and evidence consistency checks passed. Owned live services were
stopped; database volumes and diagnostic traces are retained.
