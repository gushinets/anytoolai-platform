# Execution Plan: ANY-850 Brief Decoder question copy

## Status

- State: active
- Owner: agent
- Created: 2026-11-26
- Last updated: 2026-11-26
- Review date: 2026-11-27
- Next action: Owner review and merge after the recorded acceptance evidence is reviewed.
- Blocker: None. The actual email-draft check and required GitHub CI checks passed.

## Goal

Copy only the displayed clarifying questions as plain text, one question per logical line, in array order. Preserve the full-result copy and verify the new payload independently.

## Scope

### In scope

- Brief Decoder question formatter, renderer contract, localized section action (seven locales).
- Shared ResultView optional copy labels, preserving existing clipboard and accessibility behavior.
- Component and browser regression coverage including the Acceptance Builder handoff source.

### Out of scope

- Backend Python, API, workflow, schema, prompt, provider/model, design-token changes.
- Sending email or claiming email-client evidence from a simulated paste.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/product-specs/mvp-a2-client-surfaces.md`

## Contracts touched

- API/DB: unchanged.
- Config: Brief Decoder renderer contract documents the separate question payload.
- Events: existing copy_result and result_viewed behavior unchanged.
- Frontend: optional localized idle/success labels; plain text containing authored questions only.

## Implementation steps

- [x] Format questions independently from the full-result copy.
- [x] Add the embedded, localized action immediately below the questions heading.
- [x] Test formatter, product/runtime behavior, localization, and shared control.
- [x] Update browser smoke locators and verify clipboard MIME type, payload and activation.
- [x] Run repository checks and record actual email draft verification or its blocker.

## Validation

- [x] `python scripts/agent/runner.py full-check` (GitHub CI passed; prior local environment failures remain recorded below).
- [x] `python scripts/agent/runner.py brief-decoder-smoke`
- [x] `python scripts/agent/runner.py acceptance-builder-smoke`
- [x] `python scripts/agent/runner.py frontend-check` (independent of full-check's baseline failure)
- [x] Brief Decoder product tests (including renderer contract and deadline rule).
- [x] Paste into a real, unsent email draft.

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-11-26 | Reuse ResultView and ProductRunPage.handleCopy, extending only the labels and the product-specific formatter. | Keep clipboard text-only, feedback scoped, existing focus and event contracts intact. |
| 2026-11-26 | Use TypeScript/React, no Python source changes. | The ticket's current implementation is entirely client-side; backend already exposes ordered question strings. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-11-26 | Verified Linear acceptance criteria and checked branch. Doctor passed using the existing managed Python 3.12 environment; system Python lacks pytest/pydantic. | Implement, test, verify. |
| 2026-11-26 | Focused component suite 71/71; workspace lint and typecheck passed; renderer-contract test passed. | Run browser regressions and complete broad validation. |
| 2026-11-26 | Original local stack exposes Acceptance Builder only; Brief Decoder returned 404. Started an isolated fake-provider Compose project on API 18850 / PostgreSQL 16850; both product runtime-config endpoints returned HTTP 200. | Existing stack left untouched. |
| 2026-11-26 | Brief Decoder smoke 8/8 on isolated stack; keyboard activation yielded text/plain only, exact four-question payload, one copy_result POST for result_ready, one result_viewed. Full-result and zero-question tests passed. | Finish Acceptance Builder regression and record email-draft availability. |
| 2026-11-26 | Acceptance Builder smoke 11/11 on isolated stack, both Brief Decoder handoff paths passed. Removed only the isolated containers/network, preserving its test volume; original stack unchanged. | Record broader checks. |
| 2026-11-26 | Full-check failed in the Python baseline: 4379 passed, 3 failed, 12 skipped, 723 deselected. The two production-stack mock tests encounter the existing local production env file instead of the expected Compose ps call; the cross-user activation-marker test requires passwordless sudo, which is unavailable. No ticket source touches those tests or runner. | Run frontend-check independently; do not edit deployment setup or unrelated tests. |
| 2026-11-26 | Headed browser unavailable (no X server); no accessible authenticated email draft. No email opened or sent. Clipboard MIME and text were proven in Chromium, not in a mail client. | Keep email-draft acceptance criterion pending. |
| 2026-11-26 | Independent frontend-check passed: locked install, workspace lint and typecheck, all tests (including 1182 web-mirror and 349 Atom Lab browser tests), API types drift check and production builds. Both Brief Decoder backend product test modules passed. | Implementation and ticket-scoped automated checks complete; leave acceptance pending. |
| 2026-11-26 | Code review identified the open manual email-draft criterion, not a code defect. All required PR #292 CI checks, including full-check and Windows baseline, passed. Verified normal Ctrl+V in an actual offline Thunderbird HTML draft; all four questions are readable, in order, on separate lines. | Acceptance evidence recorded below; ready for owner review. |

## Email-draft acceptance evidence

- Date: 2026-11-26.
- Tested implementation revision: `5aeb93879635e042f53e6f6c5c33b48c5d69dfab` (production frontend build against isolated local fake-provider API).
- Source browser: headed Chromium 151.0.7922.34, English UI.
- Destination: Mozilla Thunderbird 161.0, actual HTML compose editor, light theme, isolated offline profile with a dummy local-only identity. No personal account used.
- Input: `Need a nice website.` with the existing weak-input canonical fixture substituted for the final result, matching the browser smoke's weak-input test.
- Keyboard activation: tabbed to **Copy questions**, pressed Enter, confirmed **Questions copied**, then pasted into the blank unaddressed draft using ordinary Ctrl+V. No recoloring or paste-without-formatting operation.
- Visible result: four immediately readable black-text questions on white, one per line in the original order; no headings, numbers, rationale, category, priority or other result text. [Screenshot of saved unsent email draft](any-850-brief-decoder-question-copy.email-draft.png).
- Saved draft inspection: one local HTML draft with no To, Cc, Bcc or subject; the HTML body contained a single unstyled paragraph with exactly three `<br>` elements separating these four exact question strings:

  1. What should the website do, and which pages or features do you need?
  2. When do you need the website to be ready?
  3. What budget do you have in mind for this project?
  4. What does "nice" mean to you -- can you share an example of a website you like?

- Sent and Outbox were both empty. No message was sent or queued.
- The original footer Copy was exercised separately after the draft was saved: it retained structured brief and issues headings, numbered questions and excluded the model summary.
- Result: **PASS**. This validates the destination-client behavior in Thunderbird; the original QA mail client's identity is unknown.

## Open questions

- None blocking acceptance. Issue closure remains owner-controlled.

## Follow-up debt

None planned.
