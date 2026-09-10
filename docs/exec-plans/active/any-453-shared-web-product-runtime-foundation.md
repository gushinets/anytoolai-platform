# Execution Plan: ANY-453 Shared Web Product Runtime Foundation

## Status

- State: active
- Owner: agent
- Created: 2026-09-10
- Last updated: 2026-09-10
- Review date: 2026-09-10
- Next action: none — happy-path vertical implemented and verified; awaiting code review.
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

Recorded verbatim in `plans/ANY-453.md`. Concretely: no generic `ProductRunPage(definition)`
abstraction, no product-definition contract, no schema-driven form builder yet — those are
explicit ANY-453 scope-doc asks this plan deliberately does not build. Instead: build ProposalAI's
page as a concrete, product-owned component; only the pieces that were already named,
already-scaffolded shared integration points (ce-kit's data-layer primitives, web-mirror's
`apiClient`/`ErrorState`/`ResultView` placeholders, web-result-kit's `GeneratedTextRenderer`
placeholder) get filled in for real. A second product's needs, not a guess, decide what else moves
to a shared kit.

This also means this plan's scope overlaps what `plans/ANY-243.md` describes as ProposalAI's own
ticket (product definition, fields, renderer, activation). That overlap is intentional per the
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
   `react` peer/dev dependency (needed once the file contains real JSX). `ArtifactRenderer`,
   `StructuredJsonRenderer`, `ErrorBoundary`, `HandoffPreview`, `EmailCapture` left as stubs —
   ProposalAI needs none of them (single plain-text canonical field, no handoff, no email capture).
6. **`packages/frontend/ce-kit/src/ui/*`** — left untouched. Not exported from ce-kit's own
   `index.ts`, nothing imports them; building them out now would be speculative ahead of a second
   product's actual need.
7. **Tests** — `apps/web-mirror/test/ProposalAIProduct.test.tsx` (8 cases: mount/load, client
   validation blocking submit, full happy path including the copy→next-action call, advisory and
   reactive quota-exhausted, preserved form values + same-Idempotency-Key retry, non-blocking
   next-action failure) and `test/registry.test.tsx`. Both use ce-kit's existing
   `makeRoutedFetchClient` test util, matching `HandoffConsent.test.tsx`'s conventions.

### Out of scope (left for other tickets)

- The generic `ProductRunPage`/product-definition contract, product-owned renderer *slot*
  abstraction, and shared event/next-action hook interface ANY-453's original scope doc describes
  — deferred until a second product exists to prove the actual shared shape (team-lead guidance).
- ProposalAI's Playwright E2E, funnel/event correlation assertions, and full weak-input coverage —
  `plans/ANY-243.md`.
- Real client-event ingestion (`ANY-17`) — `nextAction()`'s call today only fires the backend's
  next-action endpoint itself; no separate analytics/event dispatch exists yet to wire.
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

## Required evidence

- `pnpm --filter @anytoolai/web-mirror typecheck` / `lint` / `test` (35 passed) / `build` — all
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

None outstanding for the happy-path vertical implemented here. The generic shared contract
(product-definition type, `ProductRunPage`) stays deferred to whichever second product's
implementation first needs the same shape, per the team-lead guidance recorded above.
