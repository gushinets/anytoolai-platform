# ANY-604: preserve payment meaning after review

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the two fixes and completed 45-run multilingual matrix
- Blocker: none

## Goal

Address ambiguous Spanish percentage/base wording and missing explicit payment requests found
in saved live outputs. Correct semantic verdicts without overwriting generated text or provenance.

## Implementation plan

1. Require an explicit polite request to pay the amount in rule D; a notification request alone
   is insufficient. Preserve the existing A–C prohibition on payment demands.
2. Require the percentage to modify the agreed total; name the deposit amount separately.
3. Extend existing prompt-contract tests. No new runtime parser, UI gate, schema, DSL or model.
4. Reassess historical A01-3, A01-EN-2 and A01-ES-2 with explicit reasons, preserving old verdicts
   as audit data. Review all post-fix payment requests for the same gaps.
5. Run A01 RU/EN/ES three times each through the live form. Check direct payment action, correct
   percentage base, amount/total/balance/invoice preservation, no invented urgency and UI/Copy.
6. Save full evidence and run product/config/docs/architecture checks and quick-check.

## Scope

The confirmed defects reach users through the existing text renderer and Copy path. There is
only one Prepaid prompt consumer. Proposal AI uses different commercial-term rules; Acceptance
Builder and Brief Decoder extraction prompts do not share this rule. No sibling changes required.
The baseline's known passwordless-sudo failure must remain visible if it recurs.

## Results

- Rule D explicitly requires a polite payment request; the payment-sent notification is additional.
- Percentage wording explicitly attaches the share to the agreed total and names the deposit
  amount separately. Existing A–C prohibitions remain unchanged.
- Historical A01-3 and A01-EN-2 are now FAIL for missing a direct request; A01-ES-2 is FAIL
  for an ambiguous amount relationship. Prior assessments remain in the JSON audit history.
- All 21 first-fix raw outputs, session/artifact IDs, traces and provider data are unchanged.
- Fresh A01 RU/EN/ES: nine attempts, nine PASS. Each has a direct payment request, unambiguous
  percentage/total relation, stated deposit/total/balance/delivery/invoice terms and no added urgency.
- All nine: one successful A06 and provider call, text-only result, actual UI/clipboard equality.
  Quoted semantic evidence for both findings is recorded per output. These quotes are not an
  automated language classifier. Model remains gpt-6-luna, configured medium; ledger effort is null.
- Full inputs/outputs and revised assessments are in the adjacent
  `any-604-prepaid-request-live-acceptance.evidence.json` and human-readable report.

## Checks and limits

Doctor and all 69 product tests passed. New tests pin both prompt rules and the unchanged A–C
payment prohibition. No new Ruff findings; prior nine line-length findings remain unchanged.
Config, architecture, generated docs and documentation checks passed. Whitespace and evidence
consistency checks passed. Owned live services stopped, evidence and database volumes retained.

The initial requested live rerun covered A01 only. The subsequent authorized series below
completes A04 and U1–U3 coverage on the same prompt revision. No deterministic guarantee
of future generated wording is implied. No commit, push, external comment or review resolution
was performed as part of this implementation. Final quick-check result is appended below.

Final quick-check: 3,326 passed, 12 skipped, 654 deselected, one environment failure in 583.42s.
`test_activation_marker_is_readable_by_non_root_api_user` still fails because `sudo -n -u nobody`
requires interactive authentication. This is the same failure recorded before this change;
no tests or assertions were bypassed. All 69 product tests passed separately.

## Additional multilingual verification

A04 and U1–U3 were each repeated three times in RU/EN/ES: 36/36 PASS. A04 only asks to
confirm conflicting amounts and dates; U1/U2 preserve the specified urgency, while U3 honors
the no-rush notes. All applicable messages explicitly request USD 800. All outputs stay in the
requested language and match both the displayed result and actual clipboard contents.

The worker prompt, workflow and router hashes match the preceding nine A01 runs. Together
the two series cover all five cases in all three languages, three times each: 45/45 PASS.
The new series contains 37 physical provider calls: A04-RU-3 has two semantic attempts inside
one successful A06 action. Both calls and costs are retained; the exact retry reason is unknown.
Full inputs, outputs, ledger data and historical failures remain in the adjacent acceptance report
and evidence JSON. No source changes in this batch; product tests and quick-check were not rerun.
Documentation, whitespace and evidence consistency checks passed. Owned services were stopped
with database volumes and diagnostic traces retained. No external publication was performed.
