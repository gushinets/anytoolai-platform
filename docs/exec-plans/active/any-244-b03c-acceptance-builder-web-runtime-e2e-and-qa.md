# Execution Plan: ANY-244 Acceptance Builder Web Runtime E2E And QA

## Status

- State: active
- Owner: agent
- Created: 2026-09-30
- Last updated: 2026-09-30
- Review date: 2026-10-07
- Next action: merge decision; `acceptance-builder-smoke` (11 tests) passes against a fresh `dev-up`, as do the brief-decoder, client-update-writer and proposal-ai smokes.
- Blocker: none (the ANY-26 handoff route is already in this branch's history).

## Goal

Host Acceptance Builder in the shared multi-product web host and prove its journey, including the
immediate same-tab handoff from Brief Decoder into a queued `acceptance_builder.draft_v1` run.

## Decisions

- Two `ProductDefinition`s (`draft`, `check`) behind a mode switch, like Client Update Writer.
- The result view shows the copy text composed from `extracted`/`comparison` only
  (`renderer_contract.yaml` `copy_text`), so what is read is what is copied. The model-written
  `document` is a collapsed, display-only recap. The verdict is labelled as judged on four general
  criteria, never as a check of the extracted list.
- Activation: `check_v1` always counts a shown verdict; `draft_v1` counts only a non-empty criteria
  list (no verdict exists), like Brief Decoder's question list. A draft without criteria still
  renders and completes.
- Three shared-runtime additions, each with shared tests (`ProductRunPageHandoff.test.tsx`,
  `HandoffConsent.test.tsx`): `attachSessionId` on `ProductRunPage` (poll an already-queued
  session, no start, no quota), a same-tab redirect after Accept to
  `/products/{target}?session={id}`, and `ProductDefinition.handoff` (a button that creates the
  backend handoff and opens its consent page; hidden when the target product is not enabled).
- An attached session always opens `draft` mode: the ANY-26 route targets `draft_v1`.

## Out of scope

Chrome Extension (ANY-236), Platform Core/atoms/runner/Provider Gateway/handoff runtime/mapping
DSL changes, localizing `HandoffConsent` beyond its existing messages, pre-filling the form from an
attached session, and making the route a release gate.

## Open items

- None open. The smoke found one product bug, fixed here: a reload of a restored handoff result reported `web.result_viewed` a second time (now once per session per tab in `productRunEventTracking.ts`).
- `client-handoff-smoke` (Chrome extension) was not run.

## Notes

- `confidence` fields are not shown (like Brief Decoder's): a model self-estimate beside a rule-derived verdict invites false precision.
- The session id in `?session=` is a short-lived capability (the platform GETs take no guest id); the route strips it from the address bar.
