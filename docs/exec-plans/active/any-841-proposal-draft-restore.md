# Execution Plan: ProposalAI draft and accepted run recovery (ANY-841)

## Status

- State: active
- Owner: agent
- Created: 2026-11-11
- Last updated: 2026-11-11
- Review date: 2026-11-18
- Next action: commit and push feature/ANY-841 under the approved validation exception; live navigation verification remains pending.
- Blocker: none for commit/push; the sudo-dependent baseline limitation is documented below and explicitly accepted by the user.

## Goal

Restore ProposalAI form fields and its last accepted run on reload or return in the same tab,
without another scenario start or quota reservation.

## Scope

Opt-in shared frontend storage and recovery, ProposalAI parsing, tests and frontend architecture docs.
No API, database, event or backend changes. Other products remain unchanged.

## Implementation steps

1. Add defensive versioned sessionStorage helpers and product-owned parsing.
2. Restore values at boot; poll the accepted session, with existing result/error handling.
3. Persist edits and accepted starts; clear all on New task, only run on terminal failure.
4. Test reload states, storage failures, retry, stale schema and handoff precedence.
5. Run web tests, typecheck, lint, frontend-check, quick-check and validate-docs.

## Validation

- Passed: doctor with managed Python 3.12.13, Node 24.22.1 and cached pinned pnpm 10.34.1.
- Passed: web-mirror tests (24 files, 515 tests), typecheck, lint and validate-docs.
- Passed: frontend-check, including workspace lint/typecheck/tests, 339 Chromium browser cases,
  generated API contract checks and production builds.
- quick-check: 3,576 passed, 12 skipped, 657 deselected; one failure in
  `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`.
  It requires passwordless `sudo -n -u nobody`; outside the sandbox sudo reports
  "interactive authentication is required". Isolated rerun reproduces it. Its runner, marker
  implementation and test are unchanged from the base commit. No test was weakened or excluded.
- Pending manual verification: no local API responds at 127.0.0.1:8000. F5 and catalog/Back
  checks against a live API were not performed. Automated remount tests cover the three states;
  recovered running/completed sessions send no start request.
- Environment: Linux; base SHA 8364cbdbeb840eeda6afd0c079f50ccbdeac7e33 plus this change.
- Global pnpm launcher fails in the sandbox; checks use the cached pinned 10.34.1 via a temporary
  PATH entry. Full frontend checks need browser launch/local server permissions.

## Decision log

- Use existing React/TypeScript runtime: the task requires a frontend fix and explicitly excludes backend changes.
- Keep shared design tokens and UI unchanged. ProposalAI alone opts in.
- Stay on existing feature/ANY-841 branch per repository rules.
- User approved commit and push with the documented sudo-dependent quick-check failure; no
  test expectations or results were changed to obtain approval.

## Progress log

- 2026-11-11: Implemented opt-in storage, boot restoration, accepted-run polling, ProposalAI parsing
  and documentation. Regression tests cover all fields, in-flight and completed runs, edited inputs,
  clearing, missing/terminal sessions, incompatible schemas, polling/result retries, StrictMode,
  handoff priority, opt-out products and storage/parser failures. All frontend checks pass. The backend baseline has an environment-dependent sudo failure;
  sanitized failure context was collected through the repository runner.
- 2026-11-11: User explicitly authorized committing with the sudo limitation documented and
  pushing to feature/ANY-841. This overrides the all-validations-must-pass commit gate for this
  change; quick-check remains failed and manual live navigation checks remain pending.

## Follow-up debt

- Reload before start acceptance does not retain the Idempotency-Key; only the draft recovers.
- Other products require separate opt-in work.
