# Execution Plan: ANY-850 Brief Decoder question copy

## Status

- State: active
- Owner: agent
- Created: 2026-11-26
- Last updated: 2026-11-26
- Review date: 2026-11-27
- Next action: Verify paste in an actual unsent email draft and rerun full-check in a clean validation environment before sign-off.
- Blocker: Full-check has three unrelated local runner failures; no accessible email client is available.

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

- [ ] `python scripts/agent/runner.py full-check`
- [x] `python scripts/agent/runner.py brief-decoder-smoke`
- [x] `python scripts/agent/runner.py acceptance-builder-smoke`
- [x] `python scripts/agent/runner.py frontend-check` (independent of full-check's baseline failure)
- [x] Brief Decoder product tests (including renderer contract and deadline rule).
- [ ] Paste into a real, unsent email draft.

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

## Open questions

- Real email-client verification requires an accessible draft surface; manual acceptance remains pending.
- Full-check needs a clean local validation environment for the three unrelated runner tests.
- The user authorized committing and pushing the implementation despite the outstanding acceptance checks; issue closure remains pending.

## Follow-up debt

None planned.
