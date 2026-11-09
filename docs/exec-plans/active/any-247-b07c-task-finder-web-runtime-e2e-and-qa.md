# ANY-247: Task Finder web runtime and QA

## Status
- State: blocked
- Owner: agent
- Created: 2026-11-09
- Last updated: 2026-11-09
- Review date: 2026-11-16
- Next action: Rerun full-check on a host with passwordless sudo, then review the completed implementation.
- Blocker: full-check requires passwordless sudo for its existing activation-marker permission test.

## Goal
Deliver Task Finder through the shared web runtime with deterministic browser evidence.

## Scope
Shared smoke infrastructure (TD-014); product fields, parser, renderer, seven locales, registration,
unit and browser tests, runner command, optional CI workflow, documentation.
No execution-kernel, atom, Provider Gateway, mapping DSL or handoff changes.

## Implementation steps
- [x] Extract shared DB helpers, smoke configuration, runner preamble and CI workflow; verify four existing smokes.
- [x] Implement Task Finder using the shared runtime, canonical criterion ordering and independent score/verdict.
- [x] Add localization, directory card, copy/activation/error/quota tests and Task Finder browser smoke.
- [x] Run frontend/full checks and browser suites; record evidence and limitations.

## Decisions
The user authorized the mixed stack, number plus native meter, and optional ResultView.hideText.
Copy remains English per the renderer contract. On clipboard failure, reveal selectable text so the
existing fallback still works. Task Finder remains outside the committed release order; no handoff.
TD-014 extraction precedes the fifth smoke. Product-specific assertions stay in their suites.

## Validation
Use the repository-managed Python 3.12 environment. Run doctor, frontend-check, full-check, documentation and
architecture validation, then all five product smokes against dev-up.

## Progress log
- 2026-11-09: Confirmed Python 3.12 managed environment passes doctor; pnpm and Docker work with sandbox escalation.

## Risks
Shared smoke changes affect four existing suites. CI triggers require remote validation.
Translations require native-speaker review. Fake-provider checks do not assess live model quality.

- 2026-11-09: Extraction validated: ProposalAI 10/10, Client Update Writer 4/4, Brief Decoder 8/8, Acceptance Builder 11/11; smoke lint/typecheck and six focused runner tests pass. Existing runner permission test fails because passwordless sudo is unavailable.
- 2026-11-09: Task Finder's seven browser cases pass, including real API/worker/artifact correlation,
  independent score/verdict, once-per-result activation, copy, responsive layout/reset, validation,
  fixture-substituted weak result, terminal failure and quota exhaustion. Focused UI/copy tests:
  39 passed. Typecheck/lint, docs and architecture checks pass. Full repository/frontend gates running.
- 2026-11-09: Existing unrelated execution plans still contain a forbidden local skill-name literal;
  left untouched under the ticket-scoped documentation rule.
- 2026-11-09: Managed-environment doctor passes with Python 3.12.13, Node 24.22.1 and pnpm
  10.34.1. Product-suite tests pass (262); Task Finder API bundle tests pass (33), including the
  real weak-fixture workflow. Desktop and fresh mobile screenshots inspected. The existing CE-kit
  ESLint regression exceeds its 5-second timeout under parallel workers; limiting both workspace
  and Vitest worker concurrency makes it pass without changing test code or timeouts.

- 2026-11-09: Full-check baseline completed: 3,576 passed, 1 failed, 12 skipped, 655 deselected.
  Sole failure: `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`:
  sudo requires interactive authentication to run the marker read as nobody. The same failure was
  reproduced before the product implementation. No assertion, skip or privilege policy was changed.
  Full-check stops at that failure; frontend and product-suite stages are run separately.
- 2026-11-09: Frontend validation resumed from its failed stage: all 478 web tests pass after
  waiting for boot before the new description assertion. CE-kit 327, shared-ui 52 and Atom Lab
  browser 339 tests pass; generated OpenAPI types are current. Workspace lint and typecheck pass.
  Remaining frontend build and four final product browser regressions are running.
- 2026-11-09: Frontend stages completed successfully: frozen install, workspace lint/typecheck,
  CE-kit 327 tests, shared-ui 52 tests, Atom Lab 57 unit and 339 browser tests, web 478 tests,
  generated API-type drift check and workspace production builds. After the boot assertion fix,
  resumed with the web test command and remaining drift/build commands; the full frontend wrapper
  was not rerun through the already-passing 339 browser cases.

## Verification commands and environment

Use the managed Python 3.12 interpreter. The sandbox requires elevated access to the pnpm cache,
Docker and asynchronous API integration tests; no source or system privilege policy was changed.
For frontend resource limits use `VITEST_MAX_WORKERS=1 npm_config_workspace_concurrency=1`.
The checks executed were `doctor`, `full-check`, `frontend-check`, `validate-docs`,
`validate-architecture`, `generate-docs --check`, the five product smoke commands, and focused
runner, API-bundle and Freelancer Suite tests. The frontend continuation was:

```sh
VITEST_MAX_WORKERS=1 pnpm --filter @anytoolai/web-mirror test
pnpm -r --if-present generate-api-types:check
pnpm -r build
```

The development database's previous anonymous volume had incompatible credentials. Recreating
containers without deleting that volume gave the test stack a fresh database. The original data
volume was preserved. Sanitized failure context was collected for the sudo-dependent baseline test.

## Final outcome

Implementation complete on feature/ANY-247. The infrastructure extraction is commit 2f017cd1;
the product implementation is a separate follow-up commit. No kernel, atom, provider gateway,
mapping DSL or handoff-runtime code changed. No GitHub writes were made.

All five product browser suites pass: Task Finder 7, ProposalAI 10, Client Update Writer 4,
Brief Decoder 8, Acceptance Builder 11. The four existing suites were rerun after the shared copy
component change, including both accepted and declined handoff journeys. Frontend validation
completed in stages as documented above; production builds pass. Documentation, architecture,
generated-artifact checks and diff whitespace checks pass.

The sole remaining validation blocker is the pre-existing sudo-dependent baseline test;
3,576 other baseline tests pass. Remote workflow dispatch and live-provider tests were not run.
Translations are structurally tested but still need native-speaker review. The optional future
Task Finder to ProposalAI handoff and broad visual polish remain out of scope.
