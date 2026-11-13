# Execution Plan: First-run input and result examples

## Status

- State: active
- Owner: agent
- Linear: ANY-847
- Created: 2026-11-13
- Last updated: 2026-11-13
- Review date: 2026-11-13
- Next action: review implementation, rerun the permission test on a host with passwordless sudo, and perform the new-user comprehension check
- Blocker: the local baseline permission test requires passwordless sudo as nobody; this machine requires interactive authentication

## Goal

Show compact input/result examples on ProposalAI, Brief Decoder and Client Update Writer without changing typed input or drafts.

## Scope

### In scope

Shared disclosure, three product integrations (all Client Update Writer modes), seven locales, Amount help, unit/browser tests and documentation.

### Out of scope

Acceptance Builder and Task Finder examples, home/onboarding routes, backend changes and prefilling forms.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/agent/coding-conventions.md`

## Contracts touched

- API, DB, Config, Events: none.
- Frontend: host `example.*`, product `<scope>.example.*`, shared `ExampleDisclosure`.

## Baseline

Analysis and implementation started at HEAD `2d237817` on `feature/ANY-847` (Linux, Node 24.22.1). No input/result example exists in ProposalAIProduct, BriefDecoderProduct, ClientUpdateWriterProduct or the shared ProductRunPage. System Python 3.14 lacks pytest/pydantic; doctor passes with the existing managed Python 3.12.13 environment. pnpm initially reports an environment database error.

## Implementation steps

- [x] Add shared native disclosure and localized host headings.
- [x] Add product-owned examples in seven locales and Amount help.
- [x] Test preservation, mode changes, valid samples, localization and browser interaction.
- [x] Document ownership and run frontend, baseline, docs and browser checks (baseline environment limitation recorded below).

## Validation

Environment: Linux, Node 24.22.1, pnpm 10.34.1 (existing cached pinned version), managed Python 3.12.13; starting HEAD `2d237817`.

- Doctor: passed with the managed Python and pinned pnpm.
- Web-mirror lint and typecheck: passed.
- Web-mirror unit tests: 30 files, 765 tests passed. Includes all seven locales’ sample validators, draft/event/request preservation, per-mode content and accessible help.
- Full `frontend-check`: passed (locked install, workspace lint/typechecks/tests, generated API-contract drift check and production builds). Includes 349 existing Atom Lab browser tests, 336 CE-kit tests, 55 shared-ui tests and 765 web-mirror tests.
- `proposal-ai-smoke`: 10/10 passed against the local fake-provider development stack; the happy path now opens the disclosure after typing and checks both input values before generation.
- Additional Chromium mobile check: 35/35 passed (seven locales × ProposalAI, Brief Decoder and all three Client Update Writer modes). At 390px, verified collapsed defaults, Space/Enter toggles, preserved typed input, no horizontal overflow and no page errors. Visually inspected ProposalAI and Prepaid Request screenshots.
- `quick-check`: config, architecture, docs and generated-doc checks passed; pytest finished with **3700 passed, 12 skipped, 657 deselected, 1 failed**. The failure is the unchanged `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`: `sudo -n -u nobody` requires interactive authentication on this host. An independent permission probe confirmed the same error. No tests were removed, excluded beyond the canonical runner selection, or marked to skip by this change. The baseline is not fully green; rerun this test and the canonical gate on a host supporting its required user switch.
- Dedicated `validate-docs` and `generate-docs --check`: passed. Collected sanitized diagnostic context for the baseline environment failure.

The initial unit run exposed whole-page assertions that now also matched example labels/headings. Updated those assertions to target the tone radiogroup and actual result region; no assertions or tests removed. The first full frontend attempt stopped in CE-kit without diagnostics; a direct rerun passed all 336 CE-kit tests. The canonical frontend check then passed with browser-capable permissions. Quick-check initially needed network access to reinstall editable build dependencies and required Review date/Next action/Blocker plan metadata; both were resolved before the backend run.

Repository scan found pre-existing local-command-name references in execution plans for ANY-17, ANY-339, ANY-391, ANY-221 and ANY-227. None are introduced or edited by this ticket.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-13 | Static disclosure inside each product’s Fields; no prefill. | Studying samples must preserve typed text and tab drafts. |
| 2026-11-13 | Use existing React/TypeScript stack. | User explicitly confirmed the ticket’s frontend scope over the generic Python requirement. |
| 2026-11-13 | Keep native summary marker, focus outline and 44px target. | Visible open/closed affordance and keyboard access within fixed shared tokens. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-13 | Implemented disclosure, three product integrations, seven locales, Amount help and tests. | Run broader checks and browser verification. |
| 2026-11-13 | Frontend check, product smoke, 35 mobile cases and documentation checks passed. Recorded the baseline sudo limitation; stopped temporary verification services. | Review, validate on a compatible host and perform manual acceptance. |

## Open questions

None for implementation. New-user comprehension requires a manual check on the deployed build. GitHub push and ticket updates remain subject to explicit user approval.

## Follow-up debt

None introduced.
