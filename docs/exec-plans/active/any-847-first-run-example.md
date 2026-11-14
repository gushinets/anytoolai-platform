# Execution Plan: First-run input and result examples

## Status

- State: active
- Owner: agent
- Linear: ANY-847
- Created: 2026-11-13
- Last updated: 2026-11-13
- Review date: 2026-11-13
- Next action: review the retrospective baseline evidence, rerun the permission test on a host with passwordless sudo, and perform the new-user comprehension check
- Blocker: the local baseline permission test requires passwordless sudo as nobody; this machine requires interactive authentication. New-user comprehension remains pending manual acceptance.

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

### Retrospective browser reproduction — 2026-11-13

This check was performed **after implementation**, at the user’s request following the first
code review. It reconstructs the pre-change commit; it is not a claim that a browser check was
performed before the changes or against the historical production deployment. The original
baseline above records source inspection only.

**Build and environment**

- Source: `2d237817606a00114b490ec96475d52aba69a842` (`ANY-842 - feat: show elapsed time during product generation (#274)`).
- Built a separate `git archive` of that commit with `pnpm --filter @anytoolai/web-mirror build`,
  then served it with `next start` on `http://localhost:3102`. Next.js build ID:
  `QzZ_FI_pjz4UjWFPaGNhw`. All 175 tracked web-mirror files matched the baseline Git blobs after building.
- Linux x86_64; Node 24.22.1; pnpm 10.34.1; Next.js 15.5.28; Playwright 1.62.1;
  Chromium 151.0.7922.34 (headless). Reused installed dependencies after confirming that
  the lockfile and shared frontend packages were identical between the base and implementation commits.
- Real local development API at `http://127.0.0.1:18782`, with PostgreSQL and fake-provider
  configuration; no browser API mocks. Backend source, migrations and Compose configuration were
  also unchanged between the two commits. This was a local reconstruction, not a production test.
- Successful run: `2026-11-13T18:31:49.692Z` to `2026-11-13T18:32:59.826Z` (UTC).
  UI locales: English and Russian. Viewports: 1440 × 1000 and 390 × 844.

**Procedure and inputs**

1. Open each product/mode in a fresh browser context with empty local/session storage except for
   the selected UI locale. For Client Update Writer, select each mode through its radio control.
2. Wait for the real runtime configuration and enabled, empty fields. Inspect the entire form and
   result card, including full-page screenshots, before generating anything.
3. Enter the representative inputs below; retain the default tone and ProposalAI’s default output
   language. Look for a way to study an input/output example while retaining those values. Confirm
   that the result card still shows its initial placeholder and that no scenario-start request occurs.
4. In Prepaid Request, replace Amount with the long value below and press the localized Write
   request button. Record the validation error, then restore the short value without resubmitting.

The following inputs were chosen for this reconstruction; they are not presented as the original
manual QA/S5 inputs. The same English field values were used under both UI locales, except for
those separate long-Amount probes.

| Product / mode | Exact entered values |
|---|---|
| ProposalAI (Task; profile) | `Redesign a yoga studio landing page in Figma: desktop, mobile and booking form. Deadline: 3 weeks. Budget: $600.` / `Web designer with 6 years of experience. Figma landing pages for a dental clinic and a fitness studio; two revision rounds.` |
| Brief Decoder (Client brief) | `We need a new website for our bakery. Something modern, like competitors. Launch before the holidays. Please send your price.` |
| Client Update Writer / Update (Progress notes) | `Homepage ready. Waiting for client feedback by Friday. Start inner pages Monday. No blockers.` |
| Client Update Writer / Reply Draft (Client message; reply goal) | `Can you add a blog and deliver everything one week earlier?` / `Offer the blog as a paid addition, keep the agreed deadline and suggest a short call.` |
| Client Update Writer / Prepaid Request (Billing notes; Amount; due date) | `Landing page budget: $1,800. A 50% deposit reserves team time. The remaining $900 is due after mockup delivery.` / `50% prepayment, $900` / `within 4 days` |

**Observed result**

| Product / mode | Observed before the first run |
|---|---|
| ProposalAI | Task/profile labels, generic placeholders and help text were present. No filled brief/profile example or sample proposal was available. The result card said “Your proposal will appear here after you generate it.” |
| Brief Decoder | One empty brief field and “Paste the brief as written. Longer briefs give more precise questions.” No example brief or decoded result. The result card said “Your decoded brief will appear here after you decode it.” |
| Client Update Writer / Update | Empty Progress notes field and tone choices; no sample notes/message. The result card said “Your update will appear here after you write it.” |
| Client Update Writer / Reply Draft | Empty Client message and Reply goal fields; no sample exchange/reply. The result card said “Your reply will appear here after you write it.” |
| Client Update Writer / Prepaid Request | Empty Billing notes, Amount and Due date fields; no sample payment request or Amount help explaining where to put the longer context. The result card said “Your request will appear here after you write it.” |

The same absence was reproduced in the Russian UI and at both viewport sizes. In **20/20 cases**,
there was no example disclosure/control or input-to-output reference; after typing, the entered
values remained and the result placeholder was unchanged. Thus studying such an example while
retaining input was unavailable on the base build. This confirms the missing reference content;
it does not establish how quickly a new user understands the form.

Prepaid Request’s separate length probes reproduced the reported field limit at both widths:

- EN: `50% prepayment of the $1,800 budget to reserve team time; remaining $900 after mockup delivery.` (95 characters) → `Amount: 40 characters maximum.`
- RU: `Предоплата 50% от бюджета 90 000 рублей для бронирования времени команды; остаток после сдачи макета.` (101 characters) → `Сумма: не более 40 символов.`

Replacing Amount with `50% prepayment, $900` cleared the field error and set `aria-invalid=false`.
The short value was not submitted. Across the successful matrix there were **zero scenario-start
POSTs and zero page JavaScript errors**; observed API responses were successful, with quota reads
checked where runtime configuration enabled quotas. Screenshots of all five forms and the Russian
Amount error were visually inspected.

**Disposition:** the missing browser-baseline evidence is now supplied by this explicitly
retrospective reconstruction. The implementation checks below describe the changes committed as
`0384047e` and provide the after-change evidence; those suites were not rerun during this
documentation-only pass. The short check with a new user on a deployed/preview build remains open
for manual acceptance; this reconstruction neither performs nor waives that criterion.

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
- Retrospective baseline browser check: 20/20 cases confirmed the missing examples on `2d237817`; detailed build, inputs and observations are recorded above.
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
| 2026-11-13 | Rebuilt `2d237817` in isolation and reproduced the missing first-run examples across five forms, two locales and two viewport sizes. Recorded the long-Amount validation and exact reconstruction environment above. | Baseline-evidence gap addressed; new-user comprehension remains a manual acceptance step. |

## Open questions

None for implementation. New-user comprehension requires a manual check on the deployed build. GitHub push and ticket updates remain subject to explicit user approval.

## Follow-up debt

None introduced.
