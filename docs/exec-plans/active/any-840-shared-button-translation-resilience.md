# Execution Plan: ANY-840 Shared Button Translation Resilience

## Status

- State: active
- Owner: agent
- Created: 2026-11-11
- Last updated: 2026-11-11
- Review date: 2026-11-11
- Next action: merge PR #268 after required GitHub checks; owner-approved QA acceptance is complete.
- Blocker: none from Android QA under the owner-approved acceptance decision below. Physical-device evidence remains unavailable; earlier local gate/smoke limitations are retained, and SonarCloud's duplication blocker is resolved.

## Goal

The shared Button survives browser translation replacing its label text nodes through
loading false → true → false, label changes, and repeated product submissions.

## Scope

In scope: shared Button markup, label CSS, Button/CopyButton regression tests, and
ProposalAI, Brief Decoder, Client Update Writer and Acceptance Builder submit/regenerate regression tests.
The shared component also reaches Acceptance Builder, Task Finder and handoff controls.

Out of scope: SSR locale detection, message changes, disabling browser translation,
global error boundaries and backend changes.

## Root cause

A translator replaces a bare button text node with nested font elements. React still
references the detached text node when inserting the conditional spinner before it,
causing NotFoundError during commit. A stable label span supplies the insertion anchor;
string label updates replace its translated content safely.

## Implementation steps

- [x] Reproduce the crash with the shared Button regression before changing production code.
- [x] Wrap the label, preserving spacing, accessible names, disabled and busy states.
- [x] Cover translation before/while loading, copy feedback and product regeneration.
- [x] Run repository gates and record manual QA limits and failures.
- [x] Verify Russian submit/regenerate with simulated translation on/off across the four atom products and prepare the Android QA record.

## Verification

- Baseline HEAD and origin/main: `527dc53d674703451eed7d5c705fab3cf1c70d09`.
- Working branch: `feature/ANY-840`.
- System-Python doctor failed: Python 3.14 lacks pytest and pydantic.
- Doctor with the existing managed Python 3.12.13 passed; pnpm launcher warns
  about an inaccessible database. Use the cached pinned pnpm 10.34.1 runtime.
- Before the fix, the shared-ui suite failed 3 tests: loading threw NotFoundError,
  the stable wrapper was absent, and successful clipboard writes left translated
  Copy feedback stale. After the fix, all 55 shared-ui tests passed.
- Targeted product suites: all 79 tests passed, including translated submit and
  regenerate in the three reported products. ProposalAI holds each start pending
  to verify the spinner, disabled and aria-busy state, then the updated result.
- `frontend-check`: frozen install, workspace lint and typecheck passed. The test
  phase stopped on an unrelated Atom Lab browser test: "malformed accepted response
  keeps the same submission available for safe replay" asserted two requests
  immediately after a click but observed one (338 other browser tests passed).
  That test passed unchanged on an isolated rerun. It serves the Python API's static
  Atom Lab assets, not the shared React Button; its source is outside this change.
  The whole frontend-check command is therefore not recorded as green.
- Completed the remaining workspace test phase separately: web-mirror 545 tests,
  shared-ui 55 tests and CE-kit 336 tests passed, as did the other workspace tests.
  `pnpm -r --if-present generate-api-types:check` and `pnpm -r build` passed.
- `validate-docs` passed after supplying the required Review date metadata.
- `quick-check`: config, architecture, docs and generated-doc checks passed. Backend
  tests finished with 3576 passed, 12 existing skips and 657 deselected. One unrelated
  host-dependent test failed: `tests/test_runner.py::test_activation_marker_is_readable_by_non_root_api_user`;
  its `sudo -n -u nobody` subprocess reports "interactive authentication is required".
  No tests were changed or skipped to bypass this requirement.
- Optional proposal-ai-smoke requires the dev API/worker/PostgreSQL stack.
  The sandbox cannot access Docker, but an approved status check outside the
  sandbox confirmed that the workspace stack is running. The smoke build succeeded,
  but the page displayed "ProposalAI is unavailable right now" before the form.
  A direct runtime-config GET confirmed `404 product_not_found`. Stopped the run
  after two failures (one interrupted, seven not run); this is not smoke success.
  No running deployment configuration was changed to enable a product.
- Physical Honor 50 is unavailable. DOM simulation is not evidence of physical-device
  verification. The owner subsequently accepted mobile emulation for this PR's AC;
  see the acceptance decision below.
- Sonar duplication follow-up: removed the web-mirror simulator copy and switched
  its three product tests to the shared-ui test helper. Lint and typecheck passed
  for both packages; all 11 Button/CopyButton tests and 79 product tests passed.
  Full gates were not repeated for this test-only import change. SonarCloud on
  `5f17c68f50a97ea6397d9c2d3de5f1aaed5e19a9` now reports a passing gate and 0.0%
  new-code duplication. The original review's duplication blocker is resolved.
- Review round 1: existing locale tests already cover Russian ProposalAI and all
  Client Update Writer modes. The missing combination is Russian labels with the
  translation mutation and regeneration. Extend the existing regression cases with
  Russian translated/untranslated runs, preserving the English translated case;
  include Acceptance Builder's draft mode because it shares this button path.
  Pin the reported Russian field/mode labels with literal expectations rather than
  deriving every expected string from the message files under test.
- Review follow-up validation: all 156 tests in the four product suites and
  ProductPageShell passed, including eight added Russian translation on/off cases.
  Web-mirror lint/typecheck, documentation validation and diff checks passed.
  Full backend/frontend gates and physical-device checks were not repeated for this
  test/documentation-only change. The first test run exposed ambiguous result-text
  selectors (hidden recap versus copy text, and mode radio versus labelled section);
  queries now target the intended paragraph/radio and the full affected suites pass.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-11 | Implement in existing TypeScript, confirmed by user. | The crash occurs in React DOM reconciliation; no Python change is needed. |
| 2026-11-11 | Use a stable label span, preserving shared design tokens. | Fix the common insertion anchor and keep translation enabled. |
| 2026-11-11 | Defer a global error boundary. | Separate fallback behavior is outside this targeted fix. |
| 2026-11-11 | Reuse the shared-ui test simulator from web-mirror, replacing the initially duplicated helper. | SonarCloud reported 26 duplicated lines (13.4%, limit 3%). Existing CE-kit test-helper imports establish this pattern; no production export, new package or Sonar exclusion is needed. |
| 2026-11-11 | Recommend a separate issue: SSR html lang and first render do not match the user's locale. | Locale detection and translated label distortion have a different cause from the button insertion crash. |
| 2026-11-11 | Leave unrelated gate failures and the running development stack unchanged. | Host sudo access, an Atom Lab test's asynchronous assertion and disabled product availability are outside the shared-button fix. |
| 2026-11-11 | Owner explicitly accepts the recorded Pixel 7 mobile emulation as sufficient for PR #268's QA AC, retaining all test limitations. | This changes the required acceptance evidence for this PR; it does not claim physical Android or real Chrome Translate was tested. |

## Follow-up debt

Physical Honor 50 submit/regenerate with real browser translation remains unverified
and is deferred as an accepted limitation for this PR, not an AC blocker.
Investigate SSR locale separately: `apps/web-mirror/src/app/layout.tsx` serves
`lang="en"` before the client locale changes, potentially triggering unwanted translation.
The supplied attachment analysis attributes distorted Russian labels to translation;
attachments and browser settings have not been independently verified in this run.

The supplied report compared these labels; repository Russian messages match the
source column, so no message-file correction is indicated:

| Reported on Honor 50 | Russian source |
|---|---|
| данные о месторождении | Ваши данные |
| Как вачасе | Как в задаче |
| Оставьте задачу | Опишите задачу |
| Ваш опыт и сильная сторона | Ваш опыт и сильные стороны |
| Нет языка интерфейса… | Не язык интерфейса… |
| Заметки по убийствам | Заметки по оплате |
| (мок) | Сумма |
| надежный ответ | Цель ответа |
| Черновик ответ | Черновик ответа |

The simulator covers replacement of text nodes, not arbitrary replacement of the
label element or all translation mutations elsewhere on the page. Task Finder
and handoffs share this fix; their translated journeys were not individually tested.

## Physical Android QA record — not executed; deferred by owner

This is the physical-device procedure and empty evidence record requested in review
round 1. No physical Android result is claimed. The owner explicitly accepted the
mobile emulation below as sufficient for PR #268's AC; this physical-device record
remains unexecuted and is retained for future QA.

### Run metadata

| Field | Recorded value |
|---|---|
| Operator and UTC date | Not recorded; awaiting manual QA |
| Tested URL/environment | Not recorded |
| Exact deployed build SHA | Not recorded; fill from the deployment, not merely local HEAD |
| Device/model and Android version | Not recorded; Honor 50 preferred, otherwise identify comparable Android |
| Browser name and full version | Not recorded |
| OS/browser language and app UI locale | Not recorded; app UI must be Russian |
| Translation engine, source/target languages, automatic-translation rule | Not recorded |
| Console collection method and evidence links | Not recorded; use remote debugging or equivalent device console capture |

### Procedure

1. Confirm the recorded build contains the fix and the product form is available.
   Use synthetic input, sufficient quota and a fresh tab for each case; clear any
   attached run between cases. Select Russian UI and reload.
2. With browser translation disabled for the site, record the actual field and
   button labels. Compare the reported phrases with the canonical table above.
   For Client Update Writer also inspect Reply Draft and Prepaid Request labels.
3. Submit a valid task, observe disabled/busy feedback, wait for the result, then
   regenerate from the same form. Capture console output and screenshots or video
   showing both completed runs; record any exception, white screen or clipped label.
4. Repeat in a fresh tab with the browser's real translation enabled. Record the
   detected source, target language and translation indicator; reload with that
   setting active before submission. A toggle with no actual translation applied
   does not count as an exercised translation-on case. Repeat step 3.
5. Record the exact observed text with translation off and on. If only translated
   labels are distorted, keep that observation separate from the DOM-crash result.
   Attach an existing or newly authorized follow-up issue for locale/SSR behavior;
   do not mark distorted text as corrected by the stable button wrapper.

### Results

| Product | Browser translation | Labels / submit / pending / result / regenerate / console | Evidence |
|---|---|---|---|
| ProposalAI | Off | Not executed | None |
| ProposalAI | On | Not executed | None |
| Brief Decoder | Off | Not executed | None |
| Brief Decoder | On | Not executed | None |
| Client Update Writer | Off | Not executed | None |
| Client Update Writer | On | Not executed | None |
| Acceptance Builder (shared-pattern check) | Off | Not executed | None |
| Acceptance Builder (shared-pattern check) | On | Not executed | None |

Physical-device verification remains **unexecuted**. PR #268's QA AC is **accepted
by the owner using mobile emulation**, as recorded below.
The suspected SSR/locale follow-up is **not filed or linked by this change**; suggested
title: "SSR html lang and first render do not match the user's locale". Confirm its
role using the device evidence before claiming that it caused the reported distortion.

### Desktop Chrome mobile emulation — 2026-11-11

The requested DevTools browser could not start because its graphical display was
unavailable. The fallback used installed Google Chrome 156.0.8078.73 in headless
mode, controlled by Playwright with its Pixel 7 device profile: 412 × 839 CSS pixels,
DPR 2.625, touch enabled, Android 14 / Chrome 151 mobile user agent. This is desktop
Chrome emulation, not an Android device or a manual DevTools device-menu run.

Tested local Next.js development server at `http://127.0.0.1:3100`, source revision
`804ce917265c080a80c564552cc81e5b923f9210`, with Russian UI. Local platform-api returned
`404 product_not_found`, so browser requests used the existing response builders
and result fixtures. Translation was the shared test helper's text-node replacement
inside the submit button, applied before each submission; real Chrome Translate
was not exercised.

All eight cases passed: ProposalAI, Brief Decoder, Client Update Writer (Update),
and Acceptance Builder (Draft), each with original and synthetically mutated button
text. Each case checked Russian field labels, touch submission, disabled/busy button
with spinner while the start response was held, result display, and regeneration.
There were 16 completed submissions, no uncaught page errors, no console errors,
and no unexpected API routes. Captured 32 local screenshots covering pending and
completed states. These results support the button regression check; real backend
execution, actual browser translation and physical Android remain unverified.
The owner accepted these limitations for this PR's QA AC, as recorded below.

### Owner-approved QA acceptance — 2026-11-11

The owner explicitly stated: "Да, принимаю эмуляцию для AC этого PR."
This decision supersedes the earlier requirement to obtain physical-device evidence
before accepting PR #268. It applies only to this PR and does not change what ran.

**QA verdict: ready to merge.** By the owner's explicit decision, mobile emulation
with the Android / Pixel 7 profile is sufficient for this PR's QA AC. All eight
cases and 16 submissions passed without page or console errors. Required GitHub
checks and branch protections still apply; this decision does not bypass CI.

Accepted limitations: desktop headless Chrome rather than physical Android or an
Android OS emulator; API responses from test builders/fixtures; synthetic button
text-node replacement rather than real Chrome Translate. The 32 screenshots were
captured locally and are not attached to the PR. Physical-device behavior, real
translation and backend execution were not verified by this browser run. No
follow-up issue is claimed to have been filed.

Repository hygiene check found pre-existing local-skill references in execution
plans for ANY-17, ANY-339, ANY-391, ANY-221 and ANY-227; unrelated files remain untouched.
