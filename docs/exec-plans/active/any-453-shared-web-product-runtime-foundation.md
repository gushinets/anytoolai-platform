# Execution Plan: ANY-453 Shared Web Product Runtime Foundation

## Status

- State: active
- Owner: agent
- Created: 2026-09-10
- Last updated: 2026-09-11
- Review date: 2026-09-11
- Next action: none — happy-path vertical, the generic event integration point, the fixes from
  every review round (including round 3's result-fetch-vs-terminal-failure and scenario-dimension
  quota bugs), and the Phase 2 extraction of the shared `ProductRunPage` + product-definition
  contract (with the test-only definition ANY-453's acceptance criteria require) are all
  implemented and verified.
- Blocker: none

## Goal

Prove the `apps/web-mirror` runtime against a real product end to end — guest identity, advisory
quota, idempotent scenario start, bounded polling, canonical result rendering, and copy
activation — using ProposalAI (the only product with an implemented backend bundle, from ANY-227)
as the first real product, rather than building a generic shared abstraction with no product yet
proving its shape.

## Team lead guidance (2026-09-10) — supersedes ANY-453's original front-loaded scope

> По ANY-453 не нужно делать вообще весь фреймворк. Делаешь первый продукт и понимаешь, что из
> этого продукта точно не является специфичным для этого продукта, а может быть переиспользовано —
> и выносишь это в shared kit. Второй продукт — видишь общую часть хотя бы для двух продуктов —
> выносишь в web-kit.

How this was applied, in two phases: Phase 1 built ProposalAI's page as one concrete,
product-owned component (no contract designed up front), filling in only the already-named
shared integration points (ce-kit's data-layer primitives, web-mirror's
`apiClient`/`ErrorState`/`ResultView` placeholders, web-result-kit's `GeneratedTextRenderer`
placeholder). Phase 2 (see "Phase 2" below) then extracted the shared `ProductRunPage` and the
product-definition contract *from* that proven code -- the "understand what is definitely not
product-specific, and extract it" step of the guidance -- rather than waiting for a second product.
What stays deliberately unbuilt is the "whole framework" the guidance warned against: no
schema-driven form builder (fields remain a product-owned React component) and no renderer
registry.

This also means this plan's scope overlaps what ANY-243 owns as ProposalAI's own ticket (product
definition, fields, renderer, activation). That overlap is intentional per the
team-lead guidance above, not scope creep: ANY-453 cannot be usefully "proven against a real
product" without that product's page actually existing. ANY-243 remains the ticket that owns
ProposalAI's full E2E/QA evidence (Playwright, funnel/event assertions, weak-input path); this
plan covers the shared-runtime-proving happy path only.

## Scope

### In scope (implemented)

1. **`apps/web-mirror/src/lib/apiClient.ts`** — `createPlatformApiClient()`, replacing the dead
   `{ baseUrl: "/v1" }` stub. Same-origin `PlatformApiClient`, matching the pattern
   `HandoffPage` already used inline; `HandoffPage` refactored to call this helper too (the second
   real usage that justifies the extraction, not a speculative one).
2. **`apps/web-mirror/src/products/registry.ts`** + **`src/app/products/[productId]/page.tsx`** —
   a static array (`productId` → component), safe `notFound()` for an unknown/disabled product id.
   Minimal, not a generic product-definition contract.
3. **`apps/web-mirror/src/products/proposalAi/ProposalAIProduct.tsx`** — the concrete ProposalAI
   page: runtime-config + guest identity + advisory quota on mount; a form for
   `task_text`/`freelancer_positioning`/`tone`/`language` with client-side validation mirroring
   `generate_input.schema.json`; idempotent scenario start (reuses the same
   `PreparedScenarioStart`/Idempotency-Key handle across a same-input retry); bounded polling;
   canonical result fetch/render; copy-to-clipboard activation firing the `copy_result` next action
   (non-blocking on failure). States: loading, form (idle/submitting/running), result,
   quota-exhausted (both advisory-upfront and reactive-429), retryable-error, unknown-error.
4. **`apps/web-mirror/src/components/ErrorState.tsx`** / **`ResultView.tsx`** — filled in for
   real (were dead `return null`/no-op stubs nothing imported). `ResultView` owns the
   clipboard-write mechanic and an `onCopied` callback; which next action (if any) to fire after a
   copy stays product-owned, not baked into this shared component.
5. **`packages/frontend/web-result-kit`** — `GeneratedTextRenderer` implemented (verbatim
   `white-space: pre-wrap` text), exported from `src/index.tsx` (was `export {}`). Package.json
   gained `main`/`types` (missing entirely before — nothing had ever imported this package) and a
   `react` runtime dependency (needed once the file contains real JSX). `ArtifactRenderer`,
   `StructuredJsonRenderer`, `ErrorBoundary`, `HandoffPreview`, `EmailCapture` left as stubs —
   ProposalAI needs none of them (single plain-text canonical field, no handoff, no email capture).
6. **`packages/frontend/ce-kit/src/ui/*`** — left untouched. Not exported from ce-kit's own
   `index.ts`, nothing imports them; building them out now would be speculative ahead of a second
   product's actual need.
7. **`onEvent` prop on `ProposalAIProduct`** — the "generic event ... integration points" half of
   ANY-453's scope doc that isn't the next-action call: an injectable
   `(event: ProposalAIProductEvent) => void` covering the funnel ANY-243 names (`product_viewed` →
   `form_started` → `form_submitted` → `scenario_completed` → `copy_activated`), payloads carrying
   only ids/status, never form or result text. No real dispatch is wired anywhere yet (ANY-17 owns
   that); the prop exists and is tested with an injected fake handler, matching ANY-453's own
   "exposes callbacks/integration points and tests them with injected handlers" wording. A thrown
   handler is caught and otherwise ignored so a broken caller-supplied handler can't break the page.
8. **Tests** — `apps/web-mirror/test/ProposalAIProduct.test.tsx` (13 cases: mount/load, client
   validation blocking submit, full happy path including the copy→next-action call, advisory and
   reactive quota-exhausted, preserved form values + same-Idempotency-Key retry, non-blocking
   next-action failure, the full `onEvent` funnel sequence with a text-leak check,
   `copy_activated`-without-checkpoint, a retry emitting a second `form_submitted`, no-handler
   safety, and throwing/async-rejecting-handler safety, each through the full happy path) and
   `test/registry.test.tsx`. Both use ce-kit's existing `makeRoutedFetchClient` test util, matching
   `HandoffConsent.test.tsx`'s conventions.

### Out of scope (left for other tickets)

- A schema-driven form builder or a renderer registry — explicit ANY-453 non-goals. The shared
  `ProductRunPage` and product-definition contract themselves are implemented (Phase 2 below);
  products supply fields as their own React component, not as a field schema.
- ProposalAI's Playwright E2E, funnel/event correlation assertions, and full weak-input coverage —
  ANY-243's own scope. This plan's `onEvent` tests prove the callback contract with an injected
  handler, not a real analytics backend.
- Real client-event ingestion (`ANY-17`) — nothing calls `onEvent` in production composition yet
  (the `/products/[productId]` route doesn't pass one); wiring a real implementation in is ANY-17's
  job plus whichever ticket composes it into the route.
- `apps/web-mirror/src/lib/runtimeConfig.ts` (a different, unrelated build/deploy-environment stub)
  — not touched, not used by this vertical.
- Any other product (Client Message Decoder, Scope Creep Guard, Send-Ready, Brief Decoder) — none
  has a backend bundle yet; building one is separate ticket scope.

## Design decisions

1. **ProposalAI, not a mock, as the first product.** ANY-453's scope doc explicitly says "no
   dependency on a real product bundle." The team-lead guidance directly supersedes that: build
   against something real. ProposalAI is the only product with an implemented backend bundle
   (ANY-227) in this working tree, so it is the only candidate that doesn't itself require
   unplanned backend work.
2. **Scenario/frontend id sourced from `getRuntimeConfig()`, not hardcoded.** Only `productId`
   (`"proposal_ai"`) is a literal in the component; `scenarioId`/`frontendId` come from the
   backend's own runtime-config response (`scenarios[0]`, the first enabled `type: "web"`
   frontend). Avoids a second, driftable copy of `scenarios.yaml`/`frontends.yaml` string content
   in the frontend.
3. **One retry path, not two.** A failed *poll* and a failed *start* both retry through the same
   `PreparedScenarioStart.execute()` call, not a separate "just re-poll this session id" branch.
   Per ce-kit's own ANY-150 contract, re-executing the same Idempotency-Key-bound handle after the
   scenario session already started is safe (the backend collapses it into the original
   session/job) — so a second, parallel "resume polling only" code path would have been redundant
   complexity, not a correctness requirement.
4. **Advisory quota can preempt the form.** Scope text says quota display is "advisory" (doesn't
   block initial render while loading), but once known, an already-exhausted quota puts the page
   straight into the `quota-exhausted` state rather than showing a form whose submit button is
   merely disabled — matches ANY-243's "no fake progress ... for the rejected attempt" language in
   spirit even before any submit is attempted.
5. **`react` as a plain `dependency` of `web-result-kit`, not a `peerDependency`.** First tried as
   a peer dependency (matching the usual library convention of not pinning a consumer's React).
   That resolved fine under a plain `pnpm install` but the symlink pnpm creates for it into
   `web-result-kit/node_modules` did not survive a subsequent `pnpm install --frozen-lockfile` (the
   install `frontend-check` itself runs first), breaking `react/jsx-dev-runtime` resolution for
   Vitest. Moved to a regular `dependency` — resolves identically (pinned to the same `19.2.7` in
   `pnpm-lock.yaml` either way) but the symlink is then guaranteed by ordinary dependency
   installation, not peer-resolution heuristics. `web-result-kit` isn't a published, externally
   consumed package with a real "don't double-install React" concern to protect against here.
6. **`onEvent` behind a ref uniformly, at every `emitEvent()` call site.** `handleSubmit`,
   `handleRetry`, and `updateField` are genuinely synchronous DOM-event-handler closures, where
   using the `onEvent` prop directly would already be safe. `runPoll` (a multi-second async
   continuation) and `handleCopied` (invoked from `ResultView`'s own clipboard-write promise,
   itself async) are not: either can still be running after a re-render has handed the parent a
   new `onEvent` identity, and a closure captured before that await would fire the stale one. A
   prior version tried classifying each call site as "safe" or not and routed only the mount
   effect through the ref — that classification was wrong for `runPoll` (a second code review pass
   caught it as a real, reintroduced bug). Using the ref uniformly for every site removes the need
   to keep re-deriving that classification correctly as the component changes.
7. **`AbortController` created inside its mount effect, not held in `useState`.** A `useState`
   singleton is the same instance across React StrictMode's double-invoke of effects (mount →
   cleanup → remount); that cleanup's `abort()` would permanently kill the one shared controller
   before the remount's own effects — or any later user action — ever got to use it, leaving every
   later request short-circuited by `signal.aborted` forever. Recreating the controller inside the
   effect (stored in a ref, read by `runStart`/`runPoll`/`handleCopied`) gives each invocation,
   including a StrictMode replay, its own independent controller. Verified live that neither this
   app's default `next dev` config nor an explicit `reactStrictMode: true` currently reproduces
   the double-invoke for this route (no duplicate network calls observed either way) — so this
   isn't a presently user-facing bug in this app today, but the fix is correct hardening against a
   real class of fragility regardless (this app opting into strict mode later, or a future Next.js
   default change).

## Code review pass #1 (2026-09-11) — disposition

All 8 findings re-verified by direct code reading before fixing; none refuted. Fixed:

- **Finding #1 (real bug): `handleCopied()` dropped `copy_activated` for a completed session with
  no checkpoint id.** `currentCheckpointId` is legitimately `string | null` on a completed session;
  the old guard (`if (phase.kind !== "result" || !phase.checkpointId) return;`) skipped both the
  event *and* the next-action call together, even though the clipboard write had already succeeded
  (`ResultView` only calls `onCopied` after a successful write). Split into two checks: emit
  `copy_activated` whenever `phase.kind === "result"`, regardless of checkpoint; only skip the
  `nextAction()` HTTP call (which requires a checkpoint id) when there isn't one. Regression test:
  "emits copy_activated even when the completed session has no checkpoint id ...".
- **Finding #2 (real bug): `handleRetry()` emitted no `form_submitted`.** Added the same
  `emitEvent(onEvent, { type: "form_submitted" })` call `handleSubmit()` already had. Regression
  test: "retrying after a failed submission emits a second form_submitted".
- **Finding #3 (real bug): `emitEvent()`'s `try/catch` didn't cover an async handler's rejection.**
  `onEvent?: (event) => void` structurally accepts an `async` handler (TS's `void` return type
  is satisfied by any return value, including a `Promise`); a later rejection wouldn't be seen by
  a synchronous `catch`. `emitEvent()` now also checks the call's return value for a `.then` and
  attaches a swallowing `.catch()`. Regression test: "does not let an async onEvent handler's
  rejection break the page" (needs one inline `eslint-disable-next-line
  @typescript-eslint/no-misused-promises` — deliberately passing a Promise-returning handler is
  exactly the shape being tested).
- **Finding #4 (moderate): the `product_viewed` mount effect had no StrictMode guard.** Dev-only
  `next dev` StrictMode double-invokes effects (mount → cleanup → remount); with no cleanup here,
  that double-fired `product_viewed`. Added a `productViewedFiredRef` guard that survives the
  synthetic cycle (same component instance throughout).
- **Finding #6 (minor): stale test count.** "11 cases" corrected to the current, `grep -c`-verified
  count (13, after this pass's own regression tests).
- **Finding #7 (minor, not a bug): unnecessary `onEventRef` indirection.** Simplified per design
  decision #6 above — only the mount effect still needs a ref.
- **Finding #8 (minor): the no-handler/throwing-handler tests didn't exercise the real `emitEvent()`
  call sites.** Both now run the full happy path (submit → poll → result → copy) instead of just
  `fillValidForm()`, and a third test covers the async-rejecting-handler case finding #3 fixed.

Reviewed and left as documented, not a code change:

- **Finding #5: `web-result-kit`'s `react` dependency-type change loses the "single React
  instance" tooling guarantee a `peerDependency` gives a published library.** Already captured as
  design decision #5 above with the concrete reason (the peer symlink didn't survive
  `pnpm install --frozen-lockfile`) and the accepted risk (single current consumer,
  `apps/web-mirror`, so the risk this protects against is currently inactive).

## Code review pass #2 (2026-09-11) — disposition

All 9 findings re-verified by direct code reading before fixing; none refuted. Fixed:

- **Finding #1 (critical, reintroduced by pass #1's own fix): `runPoll`'s `emitEvent` closed over
  a stale `onEvent`.** Pass #1's finding #7 fix classified `runPoll` as a "safe" direct-`onEvent`
  call site; it isn't, since it's an async continuation spanning at least two `await`s — see design
  decision #6 above. Restored the uniform ref for every `emitEvent()` call site, including
  `runPoll`.
- **Finding #2: the exec plan itself asserted the wrong reasoning.** Design decision #6 above
  rewritten to state the actual rule (why `runPoll`/`handleCopied` need the ref and the other
  three don't) instead of the "all five call sites are safe" claim finding #1 disproved.
- **Finding #3: `handleSubmit`/`handleRetry` duplicated the same 3-line "begin a start" sequence**
  (`setPhase(submitting)` + `emitEvent(form_submitted)` + `runStart(...)`) — the exact sequence
  whose missing `emitEvent` in one of the two copies was pass #1's own finding #2. Extracted a
  shared `beginStart(prepared)`.
- **Finding #4: no test proved the `productViewedFiredRef` StrictMode guard actually works.**
  Added "fires product_viewed exactly once even under React StrictMode's dev-only double-invoke of
  effects", wrapping `render()` in `<StrictMode>`. This test is also what surfaced the unrelated,
  more severe `AbortController` bug below — it initially failed by getting the whole component
  stuck on "Loading ProposalAI...", not just on a `product_viewed` double-count.
- **Findings #5 and #6: `emitEvent()`'s discard logic didn't reuse the file's own `_noop`, and its
  manual `.then`-sniffing could collapse to an unconditional wrap.** Simplified to
  `Promise.resolve(handler?.(event)).catch(_noop)` inside the same `try/catch` — behaviorally
  identical (a plain sync return value just wraps into an already-resolved, harmless promise) but
  removes the manual thenable check and reuses `_noop`, which also resolves finding #8 (duck-typing
  on `.then` could theoretically misfire on a non-Promise value with its own `.then` property;
  `Promise.resolve()` handles a genuine thenable correctly per spec and needs no manual check).
- **Finding #7: the three near-identical safety tests differed only in the `onEvent` prop.**
  Consolidated into one `it.each` over `{label, onEvent}` cases (no handler, a throwing handler, an
  async-rejecting handler), each still exercising the full submit → poll → result → copy flow.

Found while re-verifying finding #1, not one of the review's own 9 numbered findings, but real and
more severe — fixed the same way (see design decision #7 above):

- **The shared `AbortController` was a `useState` singleton, fragile to the exact same StrictMode
  double-invoke class of bug `runPoll`'s `onEvent` had, but worse.** Once finding #4's StrictMode
  test made the double-invoke actually happen in a test, the pre-fix component got permanently
  stuck on "Loading ProposalAI..." (the mount fetch's own controller, shared for the whole
  component's lifetime via `useState`, got aborted by the first invocation's cleanup before the
  second invocation — or any later user action — could ever use it). Fixed by creating the
  controller inside its own mount effect (ref-held) instead of `useState`, so each invocation gets
  an independent, un-aborted controller. Verified live via both this app's default `next dev` and
  an explicit `reactStrictMode: true` that neither currently reproduces the double-invoke for this
  route (no duplicate network calls either way) — not a presently user-facing bug in this app, but
  a real fragility now closed regardless.

Reviewed and left as is, not a code change:

- **Finding #9: `productViewedFiredRef` defends against a StrictMode double-invoke no real
  consumer currently reaches.** Correct as stated, but it's a pass #1 fix already made and now has
  direct test coverage (finding #4 above) proving it does what it claims; not worth reverting.

## Coding-conventions compliance pass (2026-09-11)

Checked the render's `Phase` handling against `docs/agent/coding-conventions.md`'s
"Exhaustiveness" rule ("For discriminated unions and UI state machines, handle every variant. Use
a `never` helper so a new union member fails typecheck") ahead of marking that PR checklist item
compliant. The main-content ternary (`result` / `quota-exhausted` / implicit-else-form) didn't
satisfy it: a future `Phase` variant would have silently rendered the form by default instead of
failing typecheck. Replaced with a `switch (phase.kind)` over every variant (grouping the five that
render the form under one case-fallthrough) ending in `default: return assertNever(phase);`.
`BootState` didn't need the same treatment: its two early returns (`loading`/`boot-error`) already
force TypeScript to narrow `boot` to `{ kind: "ready" }` for every later `boot.scenarioId`/
`boot.frontendId` access, so a new `BootState` variant lacking those fields already fails
typecheck without an explicit helper.

## Code review (blocking, PR author's own account) — disposition

Posted as blocking inline PR comments (GitHub does not allow the PR author to submit
`REQUEST_CHANGES` on their own PR). Two real bugs, fixed:

- **`registry.ts`'s frontend-selection fallback in `ProposalAIProduct.tsx` could pick a disabled or
  wrong-type frontend.** `frontends.find(web && enabled) ?? frontends[0]` — if no frontend was both
  `type: "web"` and `enabled`, this silently fell back to whatever `frontends[0]` happened to be
  (a disabled web frontend, or even a `chrome_extension` entry), still exposing the form/start flow
  under that id. Removed the `?? frontends[0]` fallback entirely: no enabled web frontend now
  correctly lands on the `boot-error` safe state. Regression test: "treats a runtime config with no
  enabled web frontend as unavailable, never falling back to an arbitrary frontend".
- **The advisory quota GET could resolve after the phase had already moved on and clobber it.** The
  quota fetch is fire-and-forget alongside the rest of boot; if it resolved `exhausted: true` after
  the user had already submitted (or even completed) a run, the unconditional
  `setPhase({ kind: "quota-exhausted" })` would overwrite `submitting`/`running`/`result` and hide
  an active or already-successful run behind a quota-exhausted screen. Changed to a functional
  update gated on the phase still being `"idle"`. Regression test: "does not let a late advisory
  quota response clobber an in-progress or completed run" (uses a custom deferred-response
  `PlatformApiClient` fetch mock, not the routed-queue test util, since the queue's response shape
  can't model "resolves after other requests/UI interactions have already happened"). Both new
  tests confirmed to fail against the pre-fix code before being left in place.

One finding raised a scope/process question rather than a code bug, not resolved in this pass —
see the open question below:

- **`registry.ts` registers `ProposalAIProduct` as ANY-453's production implementation, while the
  Linear issue's own literal acceptance criteria describe a shared `ProductRunPage`/typed
  product-definition contract plus a *test-only* minimal definition, with product-specific modules
  excluded from the common runtime.** This is exactly the team-lead guidance already recorded at
  the top of this doc and in the PR description (superseding the original scope) — but the actual
  Linear issue ANY-453 itself is not updated to reflect it. A reviewer (or future reader) who
  checks the Linear ticket directly, rather than this exec plan or the PR description, has no way
  to see the guidance that justifies the deviation from its literal acceptance criteria.

### Open question: should the Linear issue ANY-453 itself be updated to reflect the team-lead's guidance?

Not resolved in this pass — needs the user's call, not a unilateral edit to a shared team-visible
Linear issue. Options: (a) update ANY-453's Linear description with the approved scope change, (b)
leave Linear as-is and rely on this exec plan / PR description as the record, (c) something else.
Still open as of the round-2 re-review below — the reviewer left that thread unresolved for the
same reason.

## Code review round 2 (PR author's own account, and CodeRabbit) — disposition

A second review pass (both the PR author's own re-review and CodeRabbit, an automated reviewer)
found one real bug in common, plus re-confirmed the three items already fixed above (frontend
fallback, quota race, and CodeRabbit's own clipboard-availability finding, which matches the fix
already landed in the coding-conventions/self-review pass before this round — all three replied to
on the PR pointing at the commits that already fixed them, no further changes needed).

- **Real bug, confirmed: retry after a terminal execution failure replayed the dead session
  instead of starting a fresh one.** `unknown-error` (a `failed`/`expired` polling result, or an
  unexpected completed-but-unusable result) is a *definitive* terminal outcome for that specific
  backend session — different from `retryable-error` (an *ambiguous* transport-level failure
  during start/poll, where reusing the same `PreparedScenarioStart`/Idempotency-Key is correct;
  see `beginStart()`). The `unknown-error` retry button only reset `phase` to `"idle"`, leaving
  `pendingStart` untouched. Retrying without editing the form (the common case) reused the same
  key; per the scenario-session idempotency contract, a repeated key is replayed as the *existing*
  session's snapshot rather than starting a new run — so a failed/expired session came back as the
  same dead session indefinitely, not a fresh attempt. Fixed by clearing `pendingStart` on that
  retry, forcing the next submit to mint a genuinely new key. Regression test: "starts a genuinely
  new logical submission (new Idempotency-Key) after a terminal execution failure, instead of
  replaying the dead session" — confirmed to fail against the pre-fix code (asserted the same key
  twice) before being left in place with the correct assertion.

## Phase 2: shared `ProductRunPage` extracted from the proven ProposalAI code (2026-09-11)

Resolves the round-2 review's open finding #1 (the PR contradicting ANY-453's literal acceptance
criteria) in code rather than by editing Linear. Re-reading the team-lead guidance against the
Linear AC and `docs/architecture/frontend-boundaries.md`: they agree on the *destination*
(product-neutral common runtime; product modules own only definition/fields/renderer/meaning;
"Product surfaces consume shared clients rather than copy transport, storage, identity, quota,
polling, result, next-action, event, or handoff code") and differ only on the *order* — derive
the contract from a real product instead of designing it up front. The earlier phase over-weighted
the "at least two products" heuristic and under-weighted "extract what is definitely not
product-specific"; with the first product built, that extraction is now mechanical and
evidence-based, not speculative: of `ProposalAIProduct.tsx`'s ~550 lines, the product-specific
surface was six things (product id, the four fields + validation, the input mapping, the canonical
field name `text`, the `copy_result` next-action id, and the UI copy). Everything else referenced
no ProposalAI concept. Leaving it fused would also mean the five product tickets this issue blocks
each copying ~500 lines — exactly what the architecture doc forbids.

Design, derived from the real code (not a schema-driven builder — fields stay a product-owned
React component; no renderer registry):

- `src/products/runtime/productDefinition.ts` — the published contract: `ProductDefinition<V, R>`
  (`productId`, `title`, `emptyValues`, `validate`, `toInput`, `extractResult`,
  `copyNextActionId`, `Fields`, `Result`, `copy`), `ProductFieldsProps<V>`,
  `ProductResultProps<R>`, `ProductRunEvent`.
- `src/products/runtime/ProductRunPage.tsx` — the shared runtime: everything that was
  product-neutral in the old component, unchanged in behavior (all round-1/round-2 fixes carried
  over verbatim). Imports no product module.
- `src/products/proposalAi/ProposalAIProduct.tsx` — now `proposalAiDefinition` plus a thin
  `ProposalAIProduct` wrapper. The registry keeps its `Component` shape (composition layer, allowed
  to import products per `frontend-boundaries.md`); its entry type is renamed `RegisteredProduct`
  to avoid clashing with the runtime's `ProductDefinition`.
- `test/fixtures/testProductDefinition.tsx` — the test-only definition (`test_product`), not in
  the registry; `test/fixtures/platformResponses.ts` — response/route builders parameterized by
  product/scenario id, shared by both suites.
- `test/ProductRunPage.test.tsx` — the shared suite, moved from the ProposalAI suite and pointed
  at the fixture; `test/ProposalAIProduct.test.tsx` — reduced to ProposalAI meaning only (fields
  and validation copy, input mapping, canonical `text` rendering + `copy_result`);
  `test/registry.test.tsx` — additionally proves the fixture is not registered and that the shared
  runtime source imports no product module.

## Code review round 3 (PR author's own account) — disposition

A third review pass on the Phase 2 extraction (`018d049`) found the previous two blockers fixed
and raised 3 new findings. All verified by direct code reading; 2 real bugs fixed, 1 reviewed and
declined as premature/speculative for the current single product:

- **Real bug: a transient `getResult()` failure was indistinguishable from a genuinely terminal
  unusable result, and its retry started a whole new (quota-consuming) scenario run for a session
  that had already completed successfully.** `runPoll` landed both cases in `unknown-error`, whose
  retry clears `pendingStart` to mint a fresh Idempotency-Key — correct for a session that never
  produced a usable result, wrong for one that already has a `resultArtifactId` sitting on the
  backend and just failed to fetch (a network blip, a transient 5xx on `GET /v1/results/{id}`).
  Added a `"result-fetch-error"` `Phase` variant (`scenarioSessionId`, `resultArtifactId`,
  `checkpointId` retained) and a `fetchResult()` helper shared by `runPoll` and its own
  `handleRetryResult`, which only re-calls `getResult()` — no scenario start, no new key, no form
  shown (resubmitting would just create a second, wasteful run on top of the one that already
  succeeded). `extractResult()` returning `null` (a genuinely unusable/malformed canonical result)
  still lands on `unknown-error`, since that *is* a terminal, unexpected outcome. Regression test:
  "retries just the result fetch, without starting a new (quota-consuming) run, after a transient
  failure to fetch an already-completed session's result" — confirmed to fail against the pre-fix
  code (landed on the generic form-showing `unknown-error` instead) before being left in place.
- **Real bug: the advisory quota request never passed `scenario_id`.** `docs/architecture/
  frontend-boundaries.md`: "When a product's quota policy uses `dimension: scenario`, quota state
  checks also provide `scenario_id`; product-wide policies do not require it" (optional, not
  rejected, for a product-wide policy). `ProductRunPage` always omitted it, which is correct for
  ProposalAI's `dimension: product` policy but would silently lose advisory quota state entirely
  for a future `dimension: scenario` product (the failed quota GET is swallowed as advisory-only).
  The resolved `scenario.scenarioId` is already in scope at the call site, so passing it
  unconditionally is free and correct for either quota-dimension shape. Regression test: "includes
  scenario_id in the advisory quota request, so a scenario-dimension quota policy is also
  supported" — confirmed to fail (missing query param) against the pre-fix code.
- **Reviewed and declined (for now): the shared runtime's next-action/checkpoint contract is
  copy-only, not a general typed multi-checkpoint/next-action system, and `waiting_for_user`
  always lands on the safe-error state.** Confirmed as accurately described — `ProductDefinition`
  only has `copyNextActionId`/`ProductResultProps.onCopied`, sized to exactly the single-checkpoint
  "run to completion, then one post-completion activation" shape ProposalAI proved. Building a
  general typed next-action/checkpoint system now, with no real multi-checkpoint product (e.g.
  Send-Ready's user-selected-angle flow) built yet to prove its actual shape, is exactly the
  "speculative abstraction" ANY-453's own non-goals forbid, and the same premature-genericity
  mistake round 2's finding #1 disposition already reasoned through once for the runtime
  extraction as a whole (team-lead guidance: derive the contract from a real product, don't design
  it ahead of one). Left as a documented, deliberately deferred extension point instead of a code
  change: `ProductDefinition`'s docstring and `ProductRunPage`'s `waiting_for_user` handling both
  now say explicitly that generalizing this waits for whichever product first needs a
  non-single-checkpoint flow, rather than silently under-scoping "generic" as before.

## Required evidence

- `pnpm --filter @anytoolai/web-mirror typecheck` / `lint` / `test` (57 passed: 20 shared-runtime
  cases against the test-only definition, 5 ProposalAI-meaning cases, 4 registry/boundary cases,
  2 `ResultView` cases, plus the 26 pre-existing `HandoffConsent` cases) / `build` — all
  passed.
- `pnpm --filter @anytoolai/web-result-kit typecheck` / `lint` — passed.
- `pnpm --filter @anytoolai/ce-kit test` (289 passed, unaffected by this change) — passed, confirms
  the `HandoffPage` → `createPlatformApiClient()` refactor didn't regress `HandoffConsent`'s suite.
- `pnpm -r typecheck` / `pnpm -r lint` (all 7 non-extension workspaces) — passed.
- Manual Playwright smoke (headless Chromium, no backend running): `/products/proposal_ai` renders
  the `boot-error` safe state with no uncaught `pageerror` when identity/runtime-config calls fail;
  `/products/does_not_exist` renders Next's default not-found page (HTTP 404). Screenshots taken,
  reviewed.
- `python3 scripts/agent/runner.py frontend-check` — passed (exit 0): `pnpm -r lint`, `typecheck`,
  `test`, `generate-api-types:check`, `build` across all 7 frontend workspaces, including the
  `next build` of `apps/web-mirror`.
- `python3 scripts/agent/runner.py quick-check` — passed: config/architecture/docs validation,
  1232 passed / 399 deselected (backend baseline unaffected by this frontend-only change).

## Resolved follow-up

None outstanding. The shared `ProductRunPage` and product-definition contract are implemented
(Phase 2) and proven against the test-only definition; the five product tickets this issue blocks
consume `src/products/runtime/productDefinition.ts` and register a definition in `registry.ts`.
The round-2 open question about editing the Linear issue is moot: the PR now satisfies ANY-453's
acceptance criteria as written.
