# ANY-604: preserve the stated payment arrangement

## Status

- State: completed
- Owner: agent
- Created: 2026-11-06
- Last updated: 2026-11-06
- Review date: 2026-11-06
- Next action: owner reviews the subsequent review fixes and completed multilingual acceptance
- Blocker: none

## Goal

Address the observed intermittent percentage omission and repeated balance-condition omission
within ANY-604, without widening the runtime or creating another issue.

## Implementation plan

1. Clarify that requesting only the amount still due does not mean dropping the stated
   payment arrangement: percentage, agreed total, later balance trigger and invoice timing.
2. Add a contract test alongside existing Prepaid prompt tests and update the narrowed
   partial-receipt wording assertion. Existing fixtures contain no percentage/balance and stay valid.
3. Run product tests and canonical checks, then a separate live browser series:
   original five inputs three times plus A01 EN/ES translations three times each.
4. Retain full outputs and all failures, report remaining caveats, stop owned runtime services.

## Scope and decisions

The one A06 consumer and whole billing_context mapping stay unchanged. Other three products
were searched: Proposal AI has its own commercial-term rules; extraction prompts in Acceptance
Builder and Brief Decoder do not share this payment-request rule. No equivalent shared instance
was found. No new dependency, DSL, schema or model change. If one bounded prompt change fails,
report evidence before expanding into model comparison.

## Validation

Prompt-text tests protect the instruction contract only. Live review must verify retained terms
and guard against regressions in A04 and urgency. The prior quick-check environment failure
(passwordless sudo for nobody) must be reported if it remains; never bypass the test.

## Review correction

The first-fix aggregate below described numeric/urgency retention only. Review round 1 found
A01-3 and A01-EN-2 missing the explicit payment request, and classified the Spanish percentage
ambiguity as FAIL rather than an acceptable caveat. Full semantic acceptance is therefore
14/15 for the original cases and 18/21 overall for this historical first-fix series.
Original texts remain unchanged; prior verdicts are retained in the evidence audit history.
The subsequent multilingual series was initially marked 45/45. Review round 2 corrected four
U2 deadline-meaning failures, making that historical series 41/45. The deadline fix is verified
separately on U2; other cases have not been rerun on its prompt revision;
see [the current acceptance report](any-604-prepaid-request-live-acceptance.md).

## Historical first-fix result

One prompt paragraph now distinguishes the complete agreed payment arrangement from the amount
requested now. The partial-receipt rule says never request both figures as still owed, rather
than forbidding both figures from appearing. No runtime/schema/model change.

- Original A04/A01/U1/U2/U3: 15/15 live PASS after the change.
- A01 retention across RU/EN/ES: all nine contain amount, percentage, total, balance after
  final PDF/PPTX and future separate invoice. Eight are clear; one Spanish phrase ambiguously
  attaches 50% to 15,000 RUB and is marked REVIEW, requiring manual wording correction.
- All 21 outputs: one successful A06 and provider call, text-only result, UI/Copy equality.
- Full outputs, exact inputs and provider evidence are preserved in the adjacent
  `any-604-prepaid-request-live-acceptance.evidence.json`; historical failures remain unchanged.
- The original task criteria passed. The extra Spanish ambiguity remains an explicit owner
  acceptance decision; this is not a claim of error-free generation or autonomous ticket closure.

## Checks

Product tests passed, including the new prompt-contract regression. These assertions protect
the instruction wording, not stochastic model behavior. Doctor, config, architecture and generated
docs passed. Ruff adds no findings; nine pre-existing line-length findings are unchanged.
Live evidence self-check and documentation/whitespace checks passed. Local live services stopped;
volumes and diagnostic traces retained. Final quick-check outcome is appended below.

Final canonical quick-check: 3,326 passed, 12 skipped, 654 deselected, one failed in 674.06s.
The same pre-existing environment limitation remains: `test_activation_marker_is_readable_by_non_root_api_user`
requires `sudo -n -u nobody`, which returns “interactive authentication is required”. No skip,
assertion weakening or permission bypass was introduced. The product test module is outside this
DB-free baseline selection and passed separately with the new regression included.
