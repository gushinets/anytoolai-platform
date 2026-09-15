# Execution Plan: ANY-414 Client Update Writer Web Runtime E2E And QA

## Status

- State: active
- Owner: agent
- Created: 2026-09-15
- Last updated: 2026-09-15
- Review date: 2026-09-15
- Next action: none — implementation, tests, and verification below are complete.
- Blocker: none

## Goal

Prove the complete Client Update Writer vertical (Update / PrepaidRequest / ReplyDraft) through
the shared multi-product web host (`apps/web-mirror`), reusing the ANY-453 shared runtime, and
close the two shared-runtime gaps this ticket's own acceptance criteria expose (client event
correlation, copy-activation via ce-kit's ready-made helper).

## Scope

### In scope

- `apps/web-mirror/src/products/clientUpdateWriter/ClientUpdateWriterProduct.tsx` — the concrete
  product: one `ProductDefinition` per mode (Update/ReplyDraft/PrepaidRequest), each mapping its
  own fields to its own input schema, sharing one canonical-result extractor/renderer
  (`text` + optional `call_to_action`, composed per `renderer_contract.yaml`'s
  `append_after_blank_line`), plus a small mode-selector wrapper around `ProductRunPage`.
- `apps/web-mirror/src/products/registry.ts` — registers `client_update_writer`; widens
  `RegisteredProduct.Component` to accept the shared `onEvent` prop.
- `apps/web-mirror/src/products/runtime/clientEventTracker.ts` (new) — translates
  `ProductRunPage`'s product-neutral funnel events into `POST /v1/client-events` (ANY-17), wired
  into `apps/web-mirror/src/app/products/[productId]/page.tsx` for every product on this route,
  not just this one.
- `apps/web-mirror/src/products/runtime/productDefinition.ts` /
  `apps/web-mirror/src/products/runtime/ProductRunPage.tsx` /
  `apps/web-mirror/src/components/ResultView.tsx` — `ProductResultProps.onCopied: () => void`
  replaced with `onCopy: (text: string) => Promise<boolean>`; `ProductRunPage.handleCopy` now
  calls ce-kit's `copyResultAndRecordActivation` (write-then-record, exactly once) instead of a
  hand-rolled fire-and-forget `nextAction` call. Also updates `ProposalAIProduct.tsx` (the only
  other caller) and its/the shared runtime's tests.
- Tests: `apps/web-mirror/test/ClientUpdateWriterProduct.test.tsx` (per-mode validation/mapping,
  happy path per mode, one weak-input safe-result path, quota-exhausted, terminal-error, event
  correlation, mode switching), `apps/web-mirror/test/clientEventTracker.test.tsx` (new), plus
  additions to `ProductRunPage.test.tsx` (write-then-record ordering), `ResultView.test.tsx`,
  `registry.test.tsx`.

### Out of scope

Chrome Extension delivery, automated sending, payment/account journeys, load testing, broad visual
polish, any Platform Core/atom/runner/Provider Gateway/handoff-runtime/mapping-DSL change, a new
automated browser-level Playwright spec (component tests only, matching ANY-243/ANY-453
precedent), resolving the `mvp-scope-source-of-truth.md` MVP-B release-order discrepancy flagged
below (see Risks).

## Design decisions

1. **Mode switching stays entirely product-owned, not a shared-runtime concept.** Each mode
   (Update/ReplyDraft/PrepaidRequest) is its own complete, independently-typed `ProductDefinition`
   object (own `Values` type, `validate`/`toInput`/`Fields`); `ClientUpdateWriterProduct` holds
   local `mode` state and renders one `<ProductRunPage key={modeId} definition={...}>` per mode via
   a switch, so switching modes remounts the shared runtime with a clean form/run state (the same
   as navigating to a different product). `ProductDefinition`/`ProductRunPage` needed no change for
   this: the existing "one definition, one scenario" contract already covers a single mount, and a
   mode switch is just which definition this component currently renders. This avoids widening a
   generic type over a union of differently-shaped `ProductDefinition<V,R>` instances (a real
   TypeScript variance problem with no product-level payoff) and keeps ProposalAI's single-scenario
   path completely untouched.
2. **Client event wiring lives in a new `clientEventTracker.ts` under `products/runtime/`, composed
   into the route, not into one product.** `createClientEventTracker(client, productId)` maps
   `ProductRunEvent` to the backend's `web.*` allowlist (`product_viewed` → `web.product_viewed`,
   `form_started`/`form_submitted` → matching `web.*`, `scenario_completed` → `web.result_viewed`)
   and posts via ce-kit's `trackClientEvent`, with one persisted `web_session_id` per tracker
   lifetime (`getOrCreateWebSessionId`). `copy_activated` is deliberately **not** forwarded: a
   successful copy already records `client.result_copied`/`client.next_action_clicked`
   server-side via the `copy_result` next-action call itself, so re-sending it as a `web.*` event
   would double-count, not add signal. `frontend_id` is a hardcoded `"web_mirror"` constant, not
   threaded from `ProductRunPage`'s internal boot state: every product's own `frontends.yaml`
   registers exactly one `web_mirror` web frontend, and `apps/web-mirror` *is* that frontend.
   `guest_id` is deliberately omitted from these events (the field is optional on
   `TrackClientEventRequest`) rather than threading guest identity out of `ProductRunPage`'s
   internal state through `ProductRunEvent`/the tracker — correlation is scenario-session-id-based
   for the events that carry one, and the added plumbing/StrictMode-timing risk on the delicate
   existing boot effect wasn't justified by this ticket's acceptance criteria.
3. **Copy-activation switches to ce-kit's `copyResultAndRecordActivation`, changing the shared
   `ProductResultProps`/`ResultView` contract.** `onCopied: () => void` (fired *after* `ResultView`
   already wrote to the clipboard itself) becomes `onCopy: (text: string) => Promise<boolean>` (the
   full write-then-record operation, owned by `ProductRunPage.handleCopy`); `ResultView` no longer
   touches `navigator.clipboard` directly, it just awaits `onCopy` and reflects the boolean.
   Preserves the existing "copied state never depends on the next-action HTTP outcome" contract
   (ANY-243) because `copyResultAndRecordActivation`'s own `copied` flag already means exactly
   that. The now-unused `ProductDefinition.copyNextActionId` field (every product set it to the
   same `"copy_result"` ce-kit already hardcodes as `COPY_RESULT_NEXT_ACTION_ID`) was deleted rather
   than left dead. This is a shared-runtime change reused by ProposalAI too (not a
   Client-Update-Writer-only patch), verified by ProposalAI's own existing tests still passing
   unmodified plus a new ordering assertion in `ProductRunPage.test.tsx`.
4. **No UI for the `constraints` (`language`/`max_length`/`output_format`) input field.** All three
   modes' schemas make it optional; the ticket's acceptance criteria don't require it, and
   ProposalAI's own `language` field is the only existing precedent for exposing an
   advanced/optional knob — adding one here without a concrete need would be speculative. Add if a
   real user need surfaces.

## Verification

- `pnpm --filter @anytoolai/web-mirror typecheck` — passed.
- `pnpm --filter @anytoolai/web-mirror lint` — passed.
- `pnpm --filter @anytoolai/web-mirror test` — 86/86 passed.
- `pnpm --filter @anytoolai/ce-kit test` — 315/315 passed (unaffected).
- `python scripts/agent/runner.py frontend-check` — passed (lint, typecheck, test, API-types-drift
  check, and `next build`/extension build across every frontend workspace).
- `python scripts/agent/runner.py quick-check` — passed (1254 passed, 451 deselected), confirming
  no backend/config/architecture regression.

## Risks / open items

- `docs/product-specs/mvp-scope-source-of-truth.md` does not list Client Update Writer in the
  committed MVP-B validation order and separately calls it "capability backlog without a committed
  release order," even though its backend (ANY-413) is merged and this ticket delivers its web
  runtime. Flagged for a human/reviewer decision, not resolved unilaterally here.
- No automated browser-level (Playwright) E2E exists for `apps/web-mirror` product pages; "prove
  the complete vertical" is satisfied at the component-test level (fake routed `PlatformApiClient`,
  per ANY-243/ANY-453 precedent), not via a new browser spec.
