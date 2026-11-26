# Acceptance Builder delivery findings (ANY-895)

## Status

- State: active
- Owner: agent
- Last updated: 2026-11-26
- Review date: 2026-11-26
- Next action: review live comparison output after provider approval.
- Blocker: approval to submit QA inputs for live comparison.

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
- Live verification requires approval to send the QA inputs to the configured external model.
