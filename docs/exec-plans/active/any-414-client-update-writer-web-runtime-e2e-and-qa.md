# Execution Plan: ANY-414 Client Update Writer Web Runtime E2E And QA

## Status

- State: active
- Owner: agent
- Created: 2026-09-15
- Last updated: 2026-09-21
- Review date: 2026-09-21
- Next action: wait for CI on the pushed head and for the merge decision; no open code findings.
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
6. **`busy`/`onBusyChange` broadened to cover *any* ambiguous `retryable-error`, keyed on
   `pendingStart` itself rather than a per-phase flag.** A second review round found two live bugs
   in the mode-switch guard: (a) it fired from a plain `useEffect`, so the parent's mirrored `busy`
   could still read `true` for one tick after the child had already rendered a settled result,
   silently dropping a click landing in that window — fixed by firing it from an isomorphic layout
   effect instead (`useLayoutEffect` in the browser/jsdom, `useEffect` under SSR, since
   `useLayoutEffect` warns with no DOM), which flushes the whole child-settles -> parent-unblocks
   cascade synchronously before anything else can observe the intermediate state; (b) `busy` only
   covered submitting/running, but `runPoll`'s own timeout/connection-loss failures land on
   `retryable-error` while the backend may still be genuinely running that *same* accepted,
   quota-consuming session — `pendingStart`/its Idempotency-Key are deliberately kept alive for
   exactly that reattachment case, so a mode switch there was exactly the "abandon an active run"
   bug design decision 1's guard exists to prevent, just reached via a different phase. The first
   fix for (b) added an optional `scenarioSessionId` to `Phase["retryable-error"]`, set only when
   `runPoll`'s own ambiguity applied — a **third** review round then found this only covered half
   the problem: the initial `POST /start` request itself can be just as ambiguous (a lost
   response/timeout/5xx never tells the client whether the backend already accepted it, created
   the session, and charged quota), and `runStart`'s own generic failure branch lands on
   `retryable-error` with no `scenarioSessionId` at all, incorrectly reading as safe. Fixed by
   dropping `scenarioSessionId` entirely and keying `busy` on `phase.kind === "retryable-error" &&
   pendingStart !== null` instead — `pendingStart` is already exactly true in every ambiguous case
   (both the start-itself and the poll-after-start ones) and already false in the one genuinely
   safe `retryable-error` (a deterministic guest-identity-not-found rejection, which explicitly
   clears it), so this single condition covers all of them correctly without needing to track which
   specific ambiguous case produced the phase. Also correctly gates the form's own Submit button
   and fields for the same underlying reason (editing/resubmitting there would equally strand the
   original Idempotency-Key). Three regression tests: a synchronous (no `waitFor`) assertion right
   after a settled result that the mode switch is already unblocked; `accepted start -> poll
   connection loss -> mode switch blocked -> Try again reattaches via the same Idempotency-Key ->
   mode switch unblocked again`; and the same shape for an ambiguous failure on the `/start`
   request itself, before any session id is ever learned client-side.
7. **`busy` also gated `result-fetch-error`, and `pendingStart` stopped being kept alive for
   deterministic `/start` rejections.** A fourth review round found the `pendingStart`-based `busy`
   from decision 6 was simultaneously under- and over-inclusive. Under: `result-fetch-error` (the
   scenario session already completed and consumed quota; only the follow-up `GET /results/{id}`
   failed) was never covered at all — a mode switch there would remount `ProductRunPage` and destroy
   the only handle (`resultArtifactId`) on an already-paid-for result, losing it exactly as
   permanently as the ambiguous-start bug decision 6 fixed. Fixed by adding
   `phase.kind === "result-fetch-error"` as its own disjunct in `busy`; it never renders the form
   itself, so this has no effect on the Submit button/fields, only the mode-switch guard. Over:
   `runStart`'s generic failure branch treated *every* non-quota, non-guest-identity `!result.ok` as
   ambiguous, including deterministic 4xx rejections the Platform API can return from `/start`
   (`scenario_not_found`, `idempotency_key_conflict`, `scenario_input_invalid`/
   `scenario_frontend_invalid`, `guest_identity_required`) that the backend validates and rejects
   *before* ever creating a session — there is nothing to reattach to, so keeping `pendingStart`
   alive there only over-blocked the form/mode-switch on a failure that's actually safe to abandon
   and resubmit (and, for `idempotency_key_conflict` specifically, kept replaying the same doomed
   key forever). Fixed by classifying `result.error.type === "backend_error" && result.error.status
   < 500` as deterministic — clearing `pendingStart` there the same way the existing
   guest-identity-not-found branch already does — while every other outcome (network error, timeout,
   aborted, malformed/`invalid_response`, or a 5xx `backend_error`) stays ambiguous. An existing
   shared-runtime test's own comment ("the form stays editable in this phase") had baked in the
   old, too-broad assumption; it now uses a deterministic 422 instead of an ambiguous 500 to justify
   that editability, and the file gained a second test proving a genuinely ambiguous 500 still keeps
   the form disabled. New regression tests: `ProductRunPage.test.tsx` gained "reports busy true
   through a result-fetch-error, and false again once the retry succeeds" and "stays busy through an
   ambiguous /start failure, but not through a deterministic one"; `ClientUpdateWriterProduct.test.tsx`
   gained the mode-switch-level equivalents of both.
8. **The `tone` vocabulary is shared across products but lives outside the runtime.** The tone
   list is product meaning mirrored from backend input schemas, and
   `docs/architecture/frontend-boundaries.md` forbids the shared runtime from containing product
   meaning, so it moved from `products/runtime/` to `products/shared/tone.tsx`. It stays one shared
   list rather than one per product (two earlier review rounds removed exactly that duplication).
   Per `coding-conventions.md`, a single map is the source: `Tone` and `TONE_OPTIONS` derive from
   it and `isTone` is an `Object.hasOwn` guard, so unknown values (including inherited keys like
   `toString`) never pass as a tone. `test/tone.test.tsx` holds the required drift check against
   the four input schemas that use `ToneSelect` (an explicit list, so a product with its own tone
   vocabulary is free to skip the shared control) and the unknown-member negative tests.
9. **Shared-ui controls, not bare HTML.** Review found the new code had swapped `ResultView`'s
   `CopyButton` (→ `Button variant="secondary"`) for a bare `<button>`, and `ToneSelect` (used by
   ProposalAI, which rendered shared `Select`) for a bare `<select>`; the new Client Update Writer
   fields likewise used bare `<textarea>`/`<input>`. Functional tests stayed green because vitest
   doesn't process CSS modules, so the visual regression was invisible to them. All now render
   `Button`/`Select`/`TextArea`/`Input` from `@anytoolai/shared-ui` (the async-copy logic is
   unchanged); `test/sharedUiUsage.test.ts` pins this structurally for those three files (radio
   inputs excepted — shared-ui has no radio).

10. **`copy_result` activation is not tied to the page's abort signal.** `handleCopy` passed the
    mount-level `AbortSignal` to `copyResultAndRecordActivation`, so unmounting right after clicking
    Copy -- a mode switch (`busy` is false once a result shows, so the radios are enabled) or just
    navigating away -- cancelled the activation: before it was sent if the clipboard write was still
    pending, or mid-flight otherwise. The text was on the clipboard but the journey's required
    `copy_result` was lost, and a comment claimed the record "proceeds to completion in the
    background either way". Once the clipboard write succeeds the copy is irreversible, so recording
    it is now independent of the page's lifetime; it is still bounded by the client's own request
    timeout (10s default) and touches no component state after unmount. Reads/polls keep the mount
    signal -- there, cancelling on unmount is the point. Regressions: two `ProductRunPage` tests
    (unmount while the write is pending / while the request is in flight) and one Client Update
    Writer test for the exact mode-switch scenario; all three fail without the change.
11. **The Client Update Writer guest quota is an explicit product decision, not a bug fix.**
    `client_update_writer.guest_quota_v1` (3 runs, `lifetime`, `dimension: product` -- one pool
    shared by all three modes) was added in the first review round after a finding that the product
    was unmetered. That finding was framed as a defect, but ANY-413 had *deliberately* shipped no
    quota (its design decision 6: the ticket names no quota policy), and neither ANY-414 nor its
    parent ANY-412 name a limit, period or dimension; the values were chosen by analogy with
    ProposalAI, whose own plan calls `3` a placeholder to revisit. A later review rightly flagged
    that this is new production policy (unlimited -> three runs forever) with no authoritative
    source. It stays, as a decision confirmed by the user on 2026-09-21: ANY-414's acceptance
    criteria require assertions covering quota, which is impossible for a product with no policy,
    and an unmetered real-provider LLM product is a cost exposure. Revisit the numbers if the
    product owner picks a different budget. ANY-413's decision 6 now points here.
    Also kept: the repo-wide `validate_configs.py` guard that every default-set product declares a
    `quota_policy_ref` (`add-product-recipe.md` now says so; a free product needs an explicit
    exemption in the validator). Earlier comments claiming the missing-quota bug "shipped twice
    (ProposalAI, then Client Update Writer)" were wrong -- ProposalAI has had its quota since it was
    created -- and were removed.

## Verification

Run twice: once before merging `main`, once after (to catch merge-resolution regressions —
see design decision 2 and the note below).

- `pnpm --filter @anytoolai/web-mirror typecheck` — passed.
- `pnpm --filter @anytoolai/web-mirror lint` — passed.
- `pnpm --filter @anytoolai/web-mirror test` — 136/136 passed as of design decision 10 (90/90 post-merge, 86/86 before).
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

- `docs/product-specs/mvp-scope-source-of-truth.md` keeps Client Update Writer in the capability
  backlog "without a committed release order" even though its backend (ANY-413) is merged and this
  ticket delivers its web runtime, enabled in the web registry. That paragraph now states this
  factually (implemented and enabled, still outside the committed validation order). Whether it
  should join the committed order is a product-owner decision and is deliberately not made here.
- `tests/e2e/client-update-writer-smoke` needs a running `dev-up` stack and Playwright's Chromium
  installed to run locally (`python scripts/agent/runner.py client-update-writer-smoke`); it is not
  part of `quick-check`/`full-check` and, like `proposal-ai-smoke`, is not yet a required CI check
  (path-filtered, runs on PR + weekly cron against `main`). It passes in this PR's CI, and was
  also run locally on the tree merged with `main` (3/3, alongside `proposal-ai-smoke` 7/7 and
  `client-handoff-smoke` 2/2 as shared-runtime regressions). `dev-up` reuses locally cached images
  without `--build`, so rebuild the compose images first if they predate the checkout.
