# Acceptance Builder delivery findings (ANY-895)

## Status

- State: active
- Owner: agent
- Last updated: 2026-11-26
- Review date: 2026-11-26
- Next action: PR review and product acceptance.
- Blocker: none for ticket-specific verification; the repository full-check has a pre-existing Compose status test failure.

## Goal

Show the validated Check verdict and material findings before the detailed evidence. Keep the
stored result contract, Draft presentation, and Copy behavior for the full Check result.

## Implementation plan

1. Capture the pinned baseline and add five evaluator cases in Russian, English, and Spanish.
2. Update the comparison prompt to summarize distinct findings and ground dates in their events.
3. Use one parsed presentation for the visible Check result, recap and clipboard text.
4. Verify the fixture cases, saved results, keyboard disclosure and clipboard failure. Run the
   repository checks and capture desktop and 390 CSS px browser results.

## Progress

- Baseline `7a90428a` passed the Python evaluator and focused web tests. Fixed comparisons reproduced
  the baseline reading order in Chromium at desktop and mobile widths.
- The Check presenter and clipboard now lead with the same localized verdict and findings. The prompt
  distinguishes the launch deadline, delivery date and confirmed launch date. The evaluator includes
  all 15 Russian, English and Spanish cases and preserves the previous verdict matrix.
- All 1,167 web-mirror tests passed, along with the production build and focused lint and type checks.
  Chromium passed five fixed comparisons at 1280 and 390 CSS px, including the closed recap,
  keyboard toggle, page and result widths, and complete clipboard content.
- All 324 focused Python evaluator, API bundle and product tests passed.
- `full-check` passed config, architecture and docs checks. The fail-fast run stopped at the
  pre-existing `test_prod_stack_running_reflects_compose_ps_output` failure after 313 passing tests.

## Live verification

The tested implementation is `183ecbdabd7cc12334a379096570a402b2120ee0`, compared against
baseline `7a90428a1797ffc576246082b25a5f591e978f67`. The isolated deployment profile was
verified, and the provider ledger confirmed `gpt-6.1-sol` with medium reasoning configured
for the backend. The fixed comparison prompt SHA-256 is
`e14d185ed0cf132231fabe05d8728e66b3316bf91c0be8f7f2db74ae68de4b33`.

The three original Russian baseline inputs completed. Historical W4 incorrectly treated delivery
on December 23 as a violation of the December 10 launch deadline. The fixed evaluation covered
Russian, English and Spanish, with three runs of each language-specific case.

| Case | Expected and observed result | Live runs |
|---|---|---:|
| W2 | `does_not_meet`; separate missing reviews and Figma source findings | 9/9 |
| W3 | `does_not_meet`; one finding identifying the wrong project | 9/9 |
| W4 delivery | `partially_meets`; December 10 launch deadline, December 23 delivery, launch unconfirmed | 9/9 |
| W4 launch | `does_not_meet`; December 10 deadline, confirmed December 23 launch | 9/9 |
| FULL | `meets_expectations`; all four criteria match | 9/9 |

All 45 deviation runs and 63 prior ANY-893 verdict controls returned the expected verdicts and analysis
languages. The ticket-level semantic review confirmed distinct findings and correctly attributed dates
in both the rationales and W4 deadline evidence. The ledger confirmed 216 successful provider calls,
two per completed run, plus one recovered provider request failure in the Spanish W1 control.
The canonical per-authored-field human review templates remain available for separate acceptance.

The five first-round Russian live comparison artifacts were replayed through the pinned production UI
in Chromium, with local API interception. All ten desktop (1280 CSS px) and mobile (390 CSS px)
captures passed collapsed-recap layout, keyboard disclosure, complete clipboard content and page/result
overflow checks. The raw comparison payloads, ledgers and screenshots remain in local QA artifacts.
