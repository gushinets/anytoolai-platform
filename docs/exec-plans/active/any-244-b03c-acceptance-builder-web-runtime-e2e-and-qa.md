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
- Lock rules (`ProductRunPage` `locked`, reported through `onLockedChange` to the mode switch): a run in
  flight, a handoff being created or navigated to ("navigating", visible status, no timer, reset on a
  bfcache return), and an attached session still booting; a failed boot releases it and keeps the
  persisted session (`useAttachSession` forgets it only for an `onAttachEnd` that follows an `onAttachBegin`).

## Repo tooling

`scripts/agent/runner.py` (the repo's command interface) gains only the `acceptance-builder-smoke` command,
as ANY-243/ANY-248/ANY-414 did for their smokes; it changes no platform runner semantics.

## Out of scope

Chrome Extension (ANY-236), any Platform Core, atom, workflow/action runner (`platform-core`
`workflows/runner.py`, `actions/runner.py`), Provider Gateway, handoff runtime or mapping DSL change
(the acceptance criterion's "runner" is that platform runner, not the repo command interface), localizing `HandoffConsent` beyond its existing messages, pre-filling the form from an
attached session, and making the route a release gate.

## Open items

- None open. The smoke found one product bug, fixed here: a reload of a restored handoff result reported `web.result_viewed` a second time (now once per session per tab in `productRunEventTracking.ts`).
- `client-handoff-smoke` (Chrome extension) passes locally (2/2) and in CI.

## Notes

- `confidence` fields are not shown (like Brief Decoder's): a model self-estimate beside a rule-derived verdict invites false precision.
- The session id in `?session=` is an opaque public runtime handle after consent (the platform GETs take no guest id and the session has no expiry), distinct from the short-lived handoff bearer token; the route strips it from the address bar and keeps it per tab for reload.
