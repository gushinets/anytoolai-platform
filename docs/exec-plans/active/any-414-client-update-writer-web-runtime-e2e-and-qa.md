# Execution Plan: ANY-414 Client Update Writer Web Runtime E2E And QA

## Status

- State: active
- Owner: agent
- Created: 2026-09-15
- Last updated: 2026-09-15
- Review date: 2026-09-15
- Next action: none — implementation, tests, and verification below are complete, including
  reconciliation with `main` after merge (see design decision 2).
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
- Client event wiring: originally added as a new `clientEventTracker.ts`, translating
  `ProductRunPage`'s product-neutral funnel events into `POST /v1/client-events` (ANY-17) and wired
  into `apps/web-mirror/src/app/products/[productId]/page.tsx`. Superseded during the `main` merge
  by `productRunEventTracking.ts` (same purpose, landed independently via ANY-243/B02C) — see
  design decision 2.
- `apps/web-mirror/src/products/runtime/productDefinition.ts` /
  `apps/web-mirror/src/products/runtime/ProductRunPage.tsx` /
  `apps/web-mirror/src/components/ResultView.tsx` — `ProductResultProps.onCopied: () => void`
  replaced with `onCopy: (text: string) => Promise<boolean>`; `ProductRunPage.handleCopy` now
  calls ce-kit's `copyResultAndRecordActivation` (write-then-record, exactly once) instead of a
  hand-rolled fire-and-forget `nextAction` call. Also updates `ProposalAIProduct.tsx` (the only
  other caller) and its/the shared runtime's tests.
- Tests: `apps/web-mirror/test/ClientUpdateWriterProduct.test.tsx` (per-mode validation/mapping,
  happy path per mode, one weak-input safe-result path, quota-exhausted, terminal-error, event
  correlation, mode switching, mode-switch-disabled-while-busy), plus additions to
  `ProductRunPage.test.tsx` (write-then-record ordering, `onBusyChange` contract, `visitId`-scoped
  event dedupe), `ResultView.test.tsx`, `registry.test.tsx`.
- Mode-switch safety: `ProductRunPage` exposes `onBusyChange`; `ClientUpdateWriterProduct` disables
  its mode radios (both via `disabled` and a handler-level guard) while a run is submitting/running,
  so a mode switch can no longer abandon an already-accepted, quota-consuming scenario run
  (code review finding, round 4).
- Event-dedupe visit scoping: `ProductRunPage` accepts an optional `visitId`, scoping the
  once-per-visit `product_viewed`/`form_started` dedupe to one real landing on a product instead of
  the `(client, productId)` pair's whole lifetime; `page.tsx` mints a fresh `visitId` per `productId`
  change (code review finding, round 4 — a genuine A -> B -> A revisit previously undercounted).
- `tests/e2e/client-update-writer-smoke/` — a new Playwright browser-evidence suite (mirrors
  `tests/e2e/proposal-ai-smoke`) proving the real client -> Platform API -> workflow -> canonical
  result -> clipboard -> `copy_result` seam for Update mode, plus `scripts/agent/runner.py`'s
  `client_update_writer_smoke()` command and `.github/workflows/client-update-writer-smoke.yml`
  (path-filtered, not a required check yet — same precedent as `proposal-ai-smoke.yml`) (code
  review finding, round 4).
- `apps/platform-api/tests/test_client_update_writer_bundle.py`'s happy-path test extended with
  session/job/action/provider/artifact/event correlation assertions (step order, `scenario_session_id`
  correlation, one `provider_calls` row per `action_run`, artifact lineage, event coverage and
  per-step `action.started`/`action.succeeded` interleaving) — especially proving PrepaidRequest's
  two-step chain really ran in order, not just that the job succeeded (code review finding, round 4).

### Out of scope

Chrome Extension delivery, automated sending, payment/account journeys, load testing, broad visual
polish, any Platform Core/atom/runner/Provider Gateway/handoff-runtime/mapping-DSL change,
resolving the `mvp-scope-source-of-truth.md` MVP-B release-order discrepancy flagged below (see
Risks). A browser-level Playwright spec was *not* out of scope after all — round 4's review
correctly rejected that call (see design decision 5); `tests/e2e/client-update-writer-smoke`
covers Update mode only, the other two modes' meaning stays proven at the backend-pipeline level.

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
2. **Client event wiring, originally added here, was superseded by an independently-landed `main`
   implementation during the merge — kept that version, not both.** This ticket originally added
   its own `clientEventTracker.ts` (composed into the route, not into one product), mapping
   `ProductRunEvent` to the backend's `web.*` allowlist and posting via ce-kit's `trackClientEvent`,
   with `guestId` deliberately omitted from events (added plumbing/StrictMode-timing risk on the
   boot effect, judged not worth it against this ticket's acceptance criteria alone). Merging
   `main` brought in `productRunEventTracking.ts` — the same gap, closed independently by ANY-243
   (B02C, ProposalAI's own web-runtime E2E ticket), landed on `main` first. Its design threads
   `guestId` through every `ProductRunEvent` variant instead (resolved once in `ProductRunPage`'s
   own boot effect, carried on the event itself so no second, independently-resolved identity can
   diverge from it — see that type's own docstring in `productDefinition.ts`), which is more
   complete than this ticket's own omission. The merge left both files and a duplicate/broken
   `onEvent` declaration in `page.tsx` (two conflicting imports, an invalid double `const onEvent`)
   — reconciled by deleting `clientEventTracker.ts`/its test and keeping `productRunEventTracking.ts`
   as the single client-event integration point, matching the "generalize once, don't duplicate"
   rule this ticket's own description states. `copy_activated` still has no `web.*` counterpart in
   either version, for the same reason: it's already recorded server-side via the `copy_result`
   next-action call.
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
5. **Reversed course on "no browser-level E2E": a code reviewer correctly rejected that as out of
   scope.** The Linear ticket's own "Required journey" line names the seam end to end (web page ->
   shared client -> Platform API -> scenario/workflow/result -> clipboard -> `copy_result`); the
   component-level Vitest suite (routed-fake `PlatformApiClient`) and the backend pytest suite
   (starts at Platform API, never touches a browser or the shared client) each individually stop
   short of that seam, so nothing in this ticket's own test suite actually proved it end to end —
   only mirroring the ANY-243/ANY-453 precedent's test *level*, not the seam it also crossed via
   `tests/e2e/proposal-ai-smoke`. Added `tests/e2e/client-update-writer-smoke`, structurally
   identical to that suite (same package/config shape, same `runner.py`/CI wiring pattern), scoped
   to Update mode only — matching proposal-ai-smoke's own "prove the seam once" scope rather than
   re-proving all three modes' product meaning in a browser, which the backend-pipeline correlation
   tests (design point below) already do more cheaply.

## Verification

Run twice: once before merging `main`, once after (to catch merge-resolution regressions —
see design decision 2 and the note below).

- `pnpm --filter @anytoolai/web-mirror typecheck` — passed.
- `pnpm --filter @anytoolai/web-mirror lint` — passed.
- `pnpm --filter @anytoolai/web-mirror test` — 90/90 passed post-merge (86/86 before).
- `pnpm --filter @anytoolai/ce-kit test` — 315/315 passed (unaffected).
- `pnpm --filter @anytoolai/ce-kit typecheck` — passed.
- `python scripts/agent/runner.py frontend-check` — passed (lint, typecheck, test, API-types-drift
  check, and `next build`/extension build across every frontend workspace).
- `python scripts/agent/runner.py quick-check` — passed post-merge (1307 passed, 455 deselected),
  confirming no backend/config/architecture regression from `main`'s large concurrent Atom Lab
  landing.
- `python scripts/agent/runner.py full-check` — passed post-merge.

**Merge note**: `git merge main` correctly flagged `ProductRunPage.tsx` and `page.tsx` as conflicts
(both branches edited the same functions — `handleCopy` and the route's `onEvent` wiring,
respectively), but the manual conflict resolution left both broken: `handleCopy` referenced
undeclared identifiers (`scenarioSessionId`/`checkpointId`/`controller`/`writeToClipboard` never
destructured in the resolved version) plus a duplicate `emitEvent` call, and `page.tsx` kept two
conflicting `onEvent` implementations (`createProductRunEventTracker` from `main` and this ticket's
own `createClientEventTracker`) declared under one `const onEvent` name. Both were caught
immediately by `typecheck` (not a silent runtime-only bug); the still-lingering functional
duplication — two independently-built client-event trackers doing the same job — only surfaced by
reading both files and comparing designs (see design decision 2). `productDefinition.ts` (also
touched by both branches) merged cleanly with no conflict markers. Re-verify the full local
verification list, not just `git status` looking clean, after any merge that touches a file both
branches changed.

## Risks / open items

- `docs/product-specs/mvp-scope-source-of-truth.md` does not list Client Update Writer in the
  committed MVP-B validation order and separately calls it "capability backlog without a committed
  release order," even though its backend (ANY-413) is merged and this ticket delivers its web
  runtime. Flagged for a human/reviewer decision, not resolved unilaterally here.
- `tests/e2e/client-update-writer-smoke` needs a running `dev-up` stack and Playwright's Chromium
  installed to run locally (`python scripts/agent/runner.py client-update-writer-smoke`); it is not
  part of `quick-check`/`full-check` and, like `proposal-ai-smoke`, is not yet a required CI check
  (path-filtered, runs on PR + weekly cron against `main`) — this PR's own CI run has not exercised
  it, only local backend/frontend checks plus reading the spec against the existing
  proposal-ai-smoke precedent it mirrors.
