# Execution Plan: ANY-243 B02c ProposalAI Web Runtime E2E And QA

## Status

- State: active
- Owner: agent
- Created: 2026-09-11
- Last updated: 2026-09-14
- Review date: 2026-09-14
- Next action: none — implementation landed, verified live against a real `dev-up` backend, code
  review rounds 1 (13 findings), 2 (3 findings), and 3 (14 findings) all addressed, and a
  self-review's 5 acceptance-criteria gaps (round 4) closed with real E2E coverage and a full
  `full-check` run.
- Blocker: none

## Goal

Prove the complete ProposalAI vertical through the shared multi-product web host:
web product page → shared client → Platform API → scenario session → job/worker → workflow →
canonical result → product renderer → activation, plus the required weak-input/quota/guest-identity
E2E coverage — without touching Platform Core, atoms, runners, Provider Gateway, or the mapping DSL.

## Starting state (already delivered by other tickets)

ANY-227 (bundle/workflow) and ANY-453 (shared web product runtime) had already landed almost the
entire vertical on this branch before this ticket's own work started:

- `apps/web-mirror/src/products/runtime/{ProductRunPage.tsx,productDefinition.ts}` — the shared,
  product-neutral runtime (identity/quota/start/poll/result/copy-activation, all required UI
  states, idempotency-preserving retries).
- `apps/web-mirror/src/products/proposalAi/ProposalAIProduct.tsx` — the ProposalAI product
  definition, fields, client-side validation, `text` output rendering via
  `@anytoolai/web-result-kit`'s `GeneratedTextRenderer`, and the `copy_result` activation.
- `apps/web-mirror/src/products/registry.ts` and `apps/web-mirror/src/app/products/[productId]/page.tsx`
  — route registration at `/products/proposal_ai`.
- `packages/backend/product-platforms/freelancer-suite/.../products/proposal_ai/` — the real
  backend product (A06 `text.compose_persuasive_text` workflow, deterministic fake-provider
  fixture, `proposal_ai.guest_quota_v1` lifetime-3 quota policy).
- `packages/frontend/ce-kit/src/events/{trackClientEvent.ts,webSession.ts}` — ANY-17's real
  `POST /v1/client-events` client and device-local `web_session_id` helper.

So this ticket's real remaining scope, verified against the actual current repo state rather than
assumed from the ticket text, was: (1) wire the shared runtime's already-existing injectable
`ProductRunEvent` callback to ANY-17's real event ingestion (nothing did this yet — the composition
layer built `<Component client={client} />` with no `onEvent` at all), and (2) the browser-level
Playwright E2E the ticket's acceptance criteria require, which did not exist for this product.

## What this ticket implemented

### 1. Real client-event wiring (composition layer)

`apps/web-mirror/src/products/runtime/productRunEventTracking.ts` — `createProductRunEventTracker()`
maps `ProductRunEvent` → ANY-17's `web.*` allowlist (`product_viewed`, `form_started`,
`form_submitted` → `web.result_viewed` for `scenario_completed`) and calls `trackClientEvent()`,
correlated with `product_id`/`frontend_id` (`web_mirror`)/`web_session_id`/`scenario_session_id`.
`copy_activated` deliberately has no `web.*` counterpart: the backend already records
`client.next_action_clicked` when `copy_result` fires (`ProductRunPage`'s own `nextAction()` call);
tracking it again would double-count the same activation.

Wired at the one place allowed to know both the shared runtime and a product
(`app/products/[productId]/page.tsx`), not inside `ProductRunPage` — the shared runtime stays
untied to any transport.

**Real bug found and fixed by testing this live, not just in Vitest**: the backend's
`POST /v1/client-events` requires at least one of `guest_id`/`user_id`/`scenario_session_id`
(`client_event_identity_required`), but the pre-session funnel events
(`product_viewed`/`form_started`/`form_submitted`) never carry a `scenarioSessionId`. The tracker
now resolves `guestId` itself via `client.createGuestIdentity({ storage })`, safe to call
independently of `ProductRunPage`'s own boot-time identity call because `PlatformApiClient`'s
single-flight guard for the actual backend POST is keyed by the client instance, not by which
`AsyncStorage` object asked, and `createGuestIdentity()` re-reads storage after that shared request
so both callers converge on the same id instead of minting two. Verified live: before the fix,
`POST /v1/client-events` for `product_viewed` returned `400 client_event_identity_required`; after,
it returns `200`.

Tests: `apps/web-mirror/test/productRunEventTracking.test.tsx` (mapping, guest-id resolution,
single-flight guest-identity coalescing, `scenario_session_id` passthrough, `copy_activated`
never sent, never throws / drops no analytics-forbidden fields on backend rejection).

### 2. Playwright E2E: `tests/e2e/proposal-ai-smoke/`

New pnpm workspace package (mirrors `tests/e2e/client-handoff-smoke`'s shape: `package.json`,
`tsconfig.json`, `eslint.config.mjs`, `playwright.config.ts`). Unlike client-handoff-smoke this
needs no browser extension and no visible display — headless Chromium is fine for an ordinary web
page — so there's no `xvfb`/persistent-context/extension-build step.

`tests/proposal-ai-smoke.spec.ts` covers, against a real running `platform-api` (deterministic
fake-provider composition, ANY-227) and a real served `web-mirror`:

- **Happy path**: product page loads, advisory quota shown, form submit → `running` status →
  canonical result rendered → copy writes the exact result text to the clipboard → exactly one
  `POST .../next-actions/copy_result` request from the one click.
- **Weak input**: empty required fields show the product's validation copy and never call
  `POST .../scenarios/.../start`.
- **Guest identity reuse**: `anytoolai.guest_id` in `localStorage` is unchanged across a reload.
- **Quota**: advisory display reflects `remaining_count` after each of 3 real runs (each run needs
  a fresh navigation — the current UI has no "run another" affordance from the result view, by
  design, so this is a real product page load per run, not a synthetic reset); the 4th navigation
  blocks the advisory quota GET via route interception (so the client can't short-circuit into
  quota-exhausted before submitting) and asserts the real submit hits the authoritative `429
  quota_exhausted` path, with no `running` status or `Copy` button ever appearing for the rejected
  attempt.

Runner integration: `proposal_ai_smoke()` in `scripts/agent/runner.py` (registered as
`proposal-ai-smoke`), mirroring `client_handoff_smoke()` — builds/serves `web-mirror` against
`dev-up`'s `platform-api` (`PLATFORM_API_BASE_URL`, since `next.config.ts`'s `rewrites()` bakes
that destination in at build time), runs the Playwright suite, writes JSON evidence under
`.agent/proposal-ai-smoke/` (gitignored), and tears the server down via its process group.

### Scope decision: how "exactly one backend-recorded `client.next_action_clicked`" is verified

The ticket's acceptance criterion — "exactly one backend-recorded `client.next_action_clicked` for
`copy_result`" — is already asserted at the DB-row level by ANY-17's own backend test suite
(`packages/backend/platform-core/tests/unit/test_scenario_runtime.py`,
`apps/platform-api/tests/test_scenario_runtime_api.py`, both querying `event_log_table` directly).
Reproducing that assertion in this new Playwright package would mean adding a direct Postgres
client dependency to a frontend-tooling package for one already-covered assertion. Instead, the
Playwright happy-path test asserts the *frontend's* responsibility: exactly one
`POST .../next-actions/copy_result` network request fires from one Copy click — proving the browser
drives the activation correctly, while backend-side recording/dedup stays proven where it already
is. Flagging this explicitly since it's a deliberate interpretation of the AC, not an oversight.

## Live verification performed (this session)

Rebuilt the `dev-up` Docker images (they were stale — missing `anytoolai_freelancer_suite`, an
environment-staleness issue unrelated to this ticket's code, fixed with a plain
`docker compose build`) and ran the real stack end to end via curl before writing the Playwright
spec, confirming: guest identity issuance, ProposalAI runtime-config/quota, a real scenario
start → poll → `completed` → canonical result fetch against the deterministic fake provider,
`copy_result` next-action, exactly-3-runs quota exhaustion with an authoritative `429
quota_exhausted` on the 4th, and idempotency-key replay consuming no additional quota unit. Then
ran the full Playwright suite (4/4 passing) and `python scripts/agent/runner.py proposal-ai-smoke`
end to end (also 4/4 passing, clean process teardown, evidence written).

## Validation run this session

- `pnpm --filter @anytoolai/web-mirror test` — 75/75 passing after code review round 1's fixes
  (includes the new `productRunEventTracking.test.tsx`). 76/76 after round 2's fixes added one
  further regression test to `ProductRunPage.test.tsx`. 74/74 after round 3 — see "Code review
  round 3" below for why the count went down (two tests were removed as obsolete, not skipped:
  they tested an independent-guest-identity-resolution code path that round 3's fix deleted
  entirely, not a coverage gap).
- `pnpm --filter @anytoolai/web-mirror lint` / `typecheck` / `build` — clean.
- `python scripts/agent/runner.py frontend-check` — clean across the whole pnpm workspace
  (includes the new `tests/e2e/proposal-ai-smoke` package's lint/typecheck/build).
- `python scripts/agent/runner.py quick-check` — 1241 passed (no backend behavior changed by this
  ticket; this only confirms the `runner.py` addition didn't break anything).
- `python scripts/agent/runner.py proposal-ai-smoke` — 4/4 Playwright tests passing against a real
  `dev-up` stack.
- `full-check`'s backend product-suite tail (freelancer-suite install + pytest) and the
  PostgreSQL-marked suite were not re-run in this session — no backend code changed here, and both
  are already covered by ANY-227/ANY-453's own validation.

## Non-goals (unchanged from the ticket)

Chrome Extension delivery, regional routing, payment/account journeys, load testing, broad visual
polish, and any product-to-product handoff (none required for the first ProposalAI vertical).

## Code review round 1 (2026-09-11) — disposition

All 13 findings re-verified by direct code reading before acting on any of them. 5 real bugs
fixed, 1 process gap closed, 2 test-quality gaps fixed, 2 defensive/cleanliness items applied, 3
noted and deliberately deferred.

**Fixed:**

- **Real bug: `proposal_ai_smoke()` never cleared `TMPDIR`/`TMP`/`TEMP`**, unlike
  `client_handoff_smoke()` (which needs it for its persistent-context profile path on a long CI
  checkout — see that function's own comment). Root-caused to the two functions being near-full
  duplicates (also flagged separately below): fixed by extracting a shared
  `_serve_web_mirror_and_run_smoke()` tail (serve, wait-ready, clear those three env vars, run the
  named Playwright package, write evidence, terminate) that both now call — so this class of fix
  only needs to land once going forward, not be re-applied to a second copy.
- **Real bug: the event tracker's independently-resolved `guestId` could diverge from
  `ProductRunPage`'s own**, in the private-browsing/storage-unavailable case where both fall back to
  separate in-memory storages with no shared cache for a second resolution to land on — for events
  fired well after mount, that second resolution mints a genuinely different guest id than the one
  actually running the scenario. Root-caused to duplicated identity resolution rather than patched
  per-instance: `ProductRunEvent` (`productDefinition.ts`) now carries the `guestId`
  `ProductRunPage` itself already resolved on every variant except `product_viewed` (which fires
  synchronously at mount, before that resolution has necessarily settled, and self-coalesces with
  `ProductRunPage`'s own concurrent mount-time call in practice); the tracker forwards it directly
  instead of re-deriving it, and only still resolves independently for `product_viewed`. This also
  resolves finding #12 (guestId re-resolved on every call) for 4 of 5 event types, and turns finding
  #3 (silent drop when identity resolution fails) into a single, already-accepted failure mode
  (`trackClientEvent`'s own documented "client analytics may legitimately undercount" contract)
  instead of two independent ones.
- **Significant: `registry.test.tsx`'s shared-runtime import-boundary check silently skipped
  `ProductRunPage.tsx`'s own multi-line `ce-kit` import.** Its regex was single-line-anchored
  (`^...$` with no `s` flag), so a multi-line `import {\n ...\n} from "...";` was never matched or
  checked at all. Fixed the regex to span lines, and added a self-check (matched-import count must
  equal the count of lines starting with `import`, not a raw `from "` substring count — a comment
  can coincidentally contain that text) proving no import statement is silently skipped going
  forward.
- **Significant: `ProposalAIProduct.test.tsx`'s next-action test asserted a tautology**
  (`ROUTES.NEXT_ACTION.endsWith(...)` against the test's own fixture-literal constant, always true
  regardless of app behavior). Replaced with a real assertion on the actual request body
  (`{ checkpoint_id: "checkpoint_1" }`).
- **Process gap: `proposal-ai-smoke` had no CI workflow**, unlike `client-handoff-smoke`. Per
  AGENTS.md ("Smoke checks become required only after a feature issue supplies a real vertical
  slice") this ticket is exactly that trigger for ProposalAI. Added
  `.github/workflows/proposal-ai-smoke.yml`, mirroring `client-handoff-smoke.yml`'s path-filtered
  PR / manual / weekly-schedule shape (simpler: no extension build, no `xvfb-run`, since this is an
  ordinary headless-Chromium web page).
- **Duplication: `proposal_ai_smoke()`/`_write_proposal_ai_smoke_evidence()` were near-full copies
  of `client_handoff_smoke()`/`_write_client_handoff_smoke_evidence()`** (the same TMPDIR finding
  is direct evidence: the fix had landed in the original, not the copy). Addressed by the
  `_serve_web_mirror_and_run_smoke()` extraction above; `client_handoff_smoke()` now also uses it.
- **Minor: the quota Playwright test (3 full run cycles + a 4th submit) had no timeout override**,
  running under the file's 60s default. Added `test.setTimeout(120_000)` for that one test.
- **Minor: `eventStorage` in `page.tsx` was a separate `useMemo` whose only consumer was the
  adjacent `onEvent` `useMemo`.** Inlined into one.

**Deliberately deferred (noted, not fixed):**

- **Hardcoded `FRONTEND_ID = "web_mirror"` in `productRunEventTracking.ts`** vs. `ProductRunPage`
  resolving `frontendId` dynamically from runtime config. Correct today (there is exactly one
  registered product/frontend id) and the private-browsing correctness risk that justified the
  `guestId` fix above doesn't apply here (a misconfigured `frontend_id` would fail loudly via
  `ClientEventFrontendInvalidError`, not silently misattribute analytics to a real different guest).
  Threading `frontendId` through events the same way as `guestId` is straightforward if a second
  product's `frontends.yaml` ever actually diverges from the literal `"web_mirror"` string; not
  worth the extra event-shape surface before that's a real case.
- **`TONE_OPTIONS`/`LANGUAGE_PATTERN` in `ProposalAIProduct.tsx` hardcoded from the backend schema
  with no sync test.** Pre-existing (ANY-453), not touched by this ticket's own diff; out of scope
  for this pass.
- **`tests/e2e/proposal-ai-smoke`'s config files (`playwright.config.ts`/`eslint.config.mjs`/
  `tsconfig.json`/`package.json`) are near-byte-copies of `client-handoff-smoke`'s.** Accepted
  per-package boilerplate, matching the existing `client-handoff-smoke`/`stakeholder-demo-browser`
  precedent — not extracted into a shared config package for two instances of intentionally
  minimal, rarely-changing tooling config.

Re-verified after fixes: `pnpm --filter @anytoolai/web-mirror {lint,typecheck,test}` (75/75
passing), `python scripts/agent/runner.py frontend-check` (clean across the whole workspace), and
`python scripts/agent/runner.py proposal-ai-smoke` (4/4 passing) against a freshly rebuilt `dev-up`
stack, plus a direct `POST /v1/client-events` curl check confirming the redesigned event shapes
are still accepted.

## Code review round 2 (2026-09-12) — disposition

A second review pass over the cumulative diff (the same files as round 1, plus round 1's own
fixes) found 3 more real findings, all confirmed by direct code reading and all fixed:

- **Real bug: `productRunEventTracking.ts`'s `WEB_EVENT_TYPE_BY_RUN_EVENT` lookup had no
  exhaustiveness guard.** It was a plain `Partial<Record<ProductRunEvent["type"],
  WebClientEventType>>` object literal; `createProductRunEventTracker()`'s handler silently
  `return`ed when a lookup missed, so a future new `ProductRunEvent` variant would compile cleanly
  and its events would be silently dropped forever with no test or typecheck signal — the same
  "event silently never reaches the backend" bug class this ticket's own live-testing session had
  to hunt down for the `client_event_identity_required` case, and a violation of
  `docs/agent/coding-conventions.md`'s "Exhaustiveness" convention that this diff's own sibling
  `ProductRunPage.tsx`'s `mainContent` switch already follows. Fixed by replacing the object
  literal with `webEventTypeForRunEvent()`, an exhaustive `switch (eventType) { ... default: return
  assertNever(eventType); }` (new local `assertNever` helper, matching `ProductRunPage.tsx`'s
  pattern). `copy_activated` still explicitly returns `undefined` with its existing explanatory
  comment; a new variant now fails typecheck instead of silently vanishing.
- **Real bug: `ProductRunPage.tsx`'s `updateField()` emitted `form_started` with `guestId:
  undefined` when boot-time `createGuestIdentity()` fails**, not only after a self-heal retry.
  `guestId` and `boot` are set together, synchronously, in the same `Promise.all(...).then()`
  callback, so a boot-time identity failure alone leaves `identityUnavailable === true` while the
  form is still fully interactive (`<Fields>` is gated only on `busy`, not on
  `identityUnavailable`, unlike the Submit button one line below it). A user typing into that
  still-enabled form then fired `form_started` with no `guestId` and no `scenarioSessionId` — the
  exact shape the backend's `client_event_identity_required` guard rejects — permanently, since
  the emit is guarded by a once-per-page-lifetime ref and can never be re-emitted even if identity
  later self-heals. Fixed by gating the `form_started` emit itself in `updateField()` on `guestId
  !== undefined`, rather than disabling `<Fields>`: `fireEvent.change` in `@testing-library/react`
  still invokes `onChange` on a `disabled` input under jsdom, so only gating the emit is provably
  testable, and it also means a later successful self-heal can still emit the event on a
  subsequent keystroke instead of losing it forever. Added a regression test to
  `apps/web-mirror/test/ProductRunPage.test.tsx` ("does not emit form_started with no guest id
  when identity fails at boot, not just after a self-heal retry") that boots with a failing
  `GUEST_IDENTITY` route (no self-heal involved) and asserts no `form_started` event fires after
  typing; verified this test fails on the pre-fix code (`expected true to be false`) and passes
  after the fix.
- **Duplication: `scripts/agent/runner.py`'s `_write_client_handoff_smoke_evidence()` and
  `_write_proposal_ai_smoke_evidence()` remained fully duplicated** even after round 1's
  `_serve_web_mirror_and_run_smoke()` extraction — that extraction only unified the serve/wait/
  run/teardown tail and takes an already-built `write_evidence: Callable[[int], Path]` as an
  injected parameter; it never touched the two evidence-writer functions themselves, which stayed
  identical aside from which `*_REPORT_PATH`/`*_EVIDENCE_ROOT` constants each closed over. Fixed by
  extracting a single `_write_smoke_evidence(exit_code, *, report_path, evidence_root)` used by
  both `client_handoff_smoke()` and `proposal_ai_smoke()` via `functools.partial(...)`, removing
  both original functions entirely.

**Verification commands run:** `cd apps/web-mirror && pnpm run typecheck` (clean), `pnpm run lint
--max-warnings=0` (clean), `pnpm test` (`Test Files 6 passed (6)`, `Tests 76 passed (76)` — up from
75/75 because of the new `ProductRunPage.test.tsx` regression test above), a stash-based
regression proof (reverting only `ProductRunPage.tsx` and re-running the new test alone fails as
expected, `git stash pop` restores it, full suite still 76/76 after), `python3 -m py_compile
scripts/agent/runner.py` (clean), and `python3 scripts/agent/runner.py quick-check` (passed,
including the DB-free pytest subset: 1241 passed, 451 deselected).

**Files changed:** `apps/web-mirror/src/products/runtime/productRunEventTracking.ts`,
`apps/web-mirror/src/products/runtime/ProductRunPage.tsx`,
`apps/web-mirror/test/ProductRunPage.test.tsx`, `scripts/agent/runner.py`.

## Code review round 3 (2026-09-14) — disposition

14 findings re-verified by direct code reading. 4 real issues fixed with one root-cause change
(closing 2 findings at once), 3 significant findings fixed, 2 minor duplication findings fixed, 1
finding explicitly deferred as out of this ticket's own defined funnel scope, and 3 minor findings
deferred with reasoning.

**Fixed, root-cause:**

- **`product_viewed` could still hit the backend's identity-required rejection, and remained the
  one event with its own independent guest-identity resolution (a private-browsing/storage-
  unavailable divergence risk round 2 narrowed to this one event but didn't close).** Round 2 made
  every event but `product_viewed` carry the exact `guestId` `ProductRunPage` itself resolved;
  `product_viewed` was left resolving its own via `client.createGuestIdentity()` because it fires
  synchronously at mount, before that resolution necessarily completes. Root-caused instead of
  patched: moved the `product_viewed` emission from its own mount-time `useEffect(() => {...}, [])`
  into the boot-resolution effect's own `.then()` callback (right after `setGuestId(resolvedGuestId)`,
  covering both the `runtimeResult.ok`/`!runtimeResult.ok` paths, plus the effectively-unreachable-
  in-practice outer rejection handler for completeness), so it now carries the identical resolved
  `guestId` every other event does. `ProductRunEvent`'s `product_viewed` variant now requires
  `guestId: string | undefined` like the rest. This removes the tracker's `client.createGuestIdentity()`
  call and the `"guestId" in event ? ... : ...` branching in `productRunEventTracking.ts` entirely —
  there is now exactly one guest-identity resolution anywhere in this event path, closing the
  divergence risk completely rather than narrowing it further, and reducing `product_viewed`'s
  identity-loss failure mode to the same single, already-accepted "client analytics may
  legitimately undercount" contract every other event already has. Traded off: `product_viewed`'s
  timestamp now reflects "boot resolved" rather than "component mounted" (typically tens to a few
  hundred ms later) — judged an acceptable, arguably more meaningful shift (the event now reflects
  whether the product was actually determined viewable, not just mounted) for what it buys in
  correctness and simplicity. `productViewedFiredRef`'s StrictMode double-invoke guard moved with
  it into a small `emitProductViewed()` helper; the existing "fires product_viewed exactly once
  even under React StrictMode's dev-only double-invoke of effects" test in `ProductRunPage.test.tsx`
  still passes unchanged, confirming the guard still holds from its new call site.

**Fixed:**

- **`<Fields disabled={busy}>` was still gated only on `busy`, not `identityUnavailable`, unlike
  the Submit button one line below it.** No longer causes analytics loss (round 2 already gated the
  `form_started` emit itself on a resolved `guestId`), but the inconsistency was real and cheap to
  close: changed to `disabled={busy || identityUnavailable}`, matching the Submit button.
- **The tracker's `void Promise.all([...]).then(...)` chain had no `.catch()`, and `emitEvent()`'s
  own defensive wrapper doesn't cover it** (the `onEvent` handler itself returns `void`, not the
  promise chain, so a synchronous-throw/rejection guard on the handler's return value never sees
  this detached chain). Harmless today since every promise in the chain is documented as never
  rejecting, but a silent regression of any of those three guarantees would surface as an unhandled
  promise rejection instead of being absorbed like everywhere else in this event path. Added a
  trailing `.catch(() => {})` as a backstop.
- **`.github/workflows/proposal-ai-smoke.yml`'s path filter omitted `apps/platform-api/**`,
  `apps/platform-worker/**`, `packages/backend/platform-actions/**`, and `infra/compose|docker/**`**
  — all of which `dev-up` actually builds and runs for this smoke. Added all four (the sibling
  `client-handoff-smoke.yml` has the same gap; not fixed here since it's pre-existing and outside
  this ticket's own new file).
- **`timeout-minutes: 15` vs. the sibling workflow's `20`, for a job that does a cold Next.js build,
  a cold Docker Compose stack boot, and 4 real Playwright E2E runs including one with 3 full
  submit-and-wait cycles.** No confirmed timeout, but the margin was thin for no real cost to
  widening it; bumped to `20` to match.

**Fixed, minor duplication:**

- **`_serve_web_mirror_and_run_smoke()` took both `report_path` directly and an injected
  `write_evidence: Callable[[int], Path]` that separately closed over the same `report_path` (plus
  `evidence_root`) via `functools.partial(...)` — the same path constant threaded through twice for
  one path.** The callable injection was also never actually polymorphic: both callers always
  passed the same `_write_smoke_evidence` function, only the bound constants differed. Simplified
  by having `_serve_web_mirror_and_run_smoke()` take `evidence_root` directly and call
  `_write_smoke_evidence()` itself, removing the `write_evidence` parameter, both
  `functools.partial(...)` call sites, the now-unused `functools` import, and the now-unused
  `Callable` import.
- **`proposal_ai_smoke()` printed its build command twice** — its own explicit `print_command(build_command)`
  plus `run_with_env()`'s own internal `print_command(command)` call. Removed the redundant explicit
  call (matches how every other `run_with_env()` call site in this file already relies on its own
  printing).
- **`webEventTypeForRunEvent()`'s local `assertNever()` in `productRunEventTracking.ts` duplicated
  `ProductRunPage.tsx`'s own, structurally identical, helper.** Extracted one `assertNever()` into
  `productDefinition.ts` (the module both already import from for shared contracts) and removed
  both local copies.

**Deferred, out of this ticket's defined scope:**

- **`handleRetry()`/`handleRetryResult()` don't emit a `web.retry_clicked` event, even though that
  event type already exists end-to-end** (ce-kit's `WebClientEventType`, the backend allowlist,
  `docs/architecture/event-taxonomy.md`). Real and correctly identified, but this ticket's own
  "Funnel and release tests" section defines the required funnel exhaustively as "product viewed →
  form started → form submitted → scenario completed/result viewed → copy activation" — five
  stages, matching the five `ProductRunEvent` variants that already exist. Retry-click tracking is
  a real, separate future addition (it would need a new `ProductRunEvent` variant, an emit call
  site, and its own test coverage) that no product currently requires; adding it here would be
  scope creep beyond what this ticket specifies, not a gap in what it specifies.

**Deferred, low value:**

- **`client_handoff_smoke()`/`proposal_ai_smoke()` still duplicate their preambles** (identity
  resolution, port-availability check, env setup, build invocation) after two rounds of tail
  extraction — only the port env-var names/build filters/etc. differ. Real, but the two preambles
  also genuinely differ (client-handoff-smoke's concurrent extension build has no proposal-ai-smoke
  equivalent); unifying further would need a config-object parameter list approaching the size of
  the functions it replaces, for two call sites. Left as is.
- **`playwright.config.ts`/`tsconfig.json` under `tests/e2e/proposal-ai-smoke` are still byte-copies
  of `client-handoff-smoke`'s, with no shared base config.** Same disposition as round 1: matches
  this repo's existing per-package-boilerplate precedent (`stakeholder-demo-browser` too); not
  extracted for two instances of intentionally minimal, rarely-changing tooling config.
- **`registry.test.tsx`'s import-boundary check uses a double-regex pass as its own self-check
  (round 1's own fix) rather than a real AST parser**, which would make the self-check unnecessary
  in principle. True, but a full AST parser is disproportionate machinery for one boundary
  assertion in one test file; the self-check already closes the specific blind spot round 1 found.
- **A few inline numeric timeouts in `proposal-ai-smoke.spec.ts` (`30_000`, `10_000`, `5_000`)
  aren't named constants.** Flagged by the reviewer itself as low-confidence; the values already
  read as self-explanatory in context (a full scenario run, a UI-state settle, a network-call
  settle) and there are only four occurrences of two distinct values. Not changed.

**Verification commands run:** `cd apps/web-mirror && pnpm run typecheck` (clean), `pnpm run lint
--max-warnings=0` (clean), `pnpm test` (`Test Files 6 passed (6)`, `Tests 74 passed (74)` — down
from 76/76 because two `productRunEventTracking.test.tsx` tests exercising the now-deleted
independent-guest-identity-resolution path were removed as obsolete, not because coverage
shrank), `pnpm run build` (clean), `python3 -m py_compile scripts/agent/runner.py` (clean),
`python3 scripts/agent/runner.py frontend-check` (clean across the whole workspace), and
`python3 scripts/agent/runner.py quick-check` (1241 passed, 451 deselected). Also re-verified live
against a freshly rebuilt `dev-up` stack: `python3 scripts/agent/runner.py proposal-ai-smoke`
(4/4 Playwright tests passing) and a direct `POST /v1/client-events` curl check confirming a
`web.product_viewed` event with a real `guest_id` still returns `200`.

**Files changed:** `apps/web-mirror/src/products/runtime/productDefinition.ts`,
`apps/web-mirror/src/products/runtime/ProductRunPage.tsx`,
`apps/web-mirror/src/products/runtime/productRunEventTracking.ts`,
`apps/web-mirror/test/ProductRunPage.test.tsx`, `apps/web-mirror/test/productRunEventTracking.test.tsx`,
`scripts/agent/runner.py`, `.github/workflows/proposal-ai-smoke.yml`.

## Code review round 4 (2026-09-14) — self-review acceptance-criteria gaps, disposition

A self-review pass (author's own account; GitHub rejects `REQUEST_CHANGES` from a PR's own author,
so this landed as blocking notes rather than a formal review) found 5 real gaps against ANY-243's
own literal acceptance criteria, distinct from rounds 1-3's code-quality findings: the E2E suite's
earlier "weak input" test was actually the validation path, not a genuine weak-input path; the
quota test never exercised idempotent-retry-consumes-no-extra-quota; there was no backend-recorded
(not just browser-sent) verification of `client.next_action_clicked`; there was no safe-error/
terminal-failure path at all; and `full-check` had never actually been run for this ticket (only
`quick-check`/`frontend-check` separately). All 5 confirmed real and closed.

**Architectural finding, verified by direct code reading before designing any fix:** the real
`FakeProviderAdapter` (`packages/backend/platform-core/.../providers/adapters/fake.py`,
`_fixture_key_for()`) resolves its fixture strictly from the action config id (or an explicit
`fixture_key` no real HTTP-triggered request ever sets) -- never from request content -- and
`proposal_ai.generate_v1` has exactly one action config. The real running `dev-up` stack therefore
has **no way to select the `weak_input` fixture via genuine input text**; only Python-level tests
that construct a fixed-fixture adapter subclass can reach it (confirmed against ANY-227's own exec
plan, which documents this same constraint). Making input content select a fixture would require a
Provider Gateway/mapping-DSL change, which ANY-243's own constraints explicitly forbid introducing.
This bounded how the weak-input and safe-error fixes below could honestly be built: real backend
calls wherever the real stack can produce the needed behavior, Playwright network interception only
at the one point each genuinely can't (documented inline in the spec, not left implicit).

**Fixed:**

- **Backend-recorded `client.next_action_clicked` verification.** The happy-path test previously
  only asserted the browser sent one `copy_result` HTTP request; ANY-17's own backend tests prove
  the endpoint works in isolation, not that this specific vertical's E2E run persisted it. Added
  `pg`/`@types/pg` as devDependencies of `tests/e2e/proposal-ai-smoke` (a test-tooling boundary, not
  product/runtime code) and a `countBackendEvents()` helper that queries the real `event_log` table
  directly (`platform.event_log` -- confirmed its actual schema via `information_schema.tables`,
  not assumed) for the specific `scenario_session_id` this run produced (extracted from the
  `copy_result` request's own URL), asserting exactly 1. `scripts/agent/runner.py`'s
  `proposal_ai_smoke()` now passes `DATABASE_URL` (`identity.database_url`, already computed and
  host-reachable since the compose Postgres port is published) into the Playwright process env.
- **Genuine weak-input path.** Renamed the old "weak input" test to "validation" (it always tested
  only client-side field-required validation). Added a real "weak input" test: a vague-but-schema-
  valid task (passes both client and backend validation) starts and polls against the real backend/
  worker for real, and only the final canonical-result fetch is intercepted to substitute the real,
  documented `weak_input` fixture's exact `text` (read from the repo's own fixture file at test
  time, never hand-copied, so the test can't silently drift from the actual documented output) --
  proving the frontend correctly renders the documented safe weak-input result, which is the
  furthest this can honestly be pushed given the architectural constraint above.
- **Idempotent-retry-consumes-no-extra-quota.** New dedicated test: intercepts the first `start`
  call with a transient `500` (not `quota_exhausted`/`guest_identity_not_found`, so the frontend
  takes its generic retryable-error path, which reuses the same prepared start/Idempotency-Key on
  retry per `submitCurrentValues()`'s own ANY-150 contract), asserts both attempts carried the
  identical `Idempotency-Key` header, retries via "Try again" through to a real completion, and
  confirms quota dropped by exactly one unit (`3 of 3` -> `2 of 3`) despite two HTTP `start` calls.
- **Safe-error/terminal-failure path.** New dedicated test: since the real fake provider has no
  failure mode to trigger on demand, intercepts the scenario-session poll response and forces
  `status: "failed"` on the first poll (deterministic, no need to wait out a real failure this
  stack can't produce) -- asserts the safe `unknown-error` message appears, the originally-typed
  form values are still present (`values` state is never cleared on this transition; confirmed by
  reading `ProductRunPage.tsx` before writing the assertion, not assumed), and no fake
  progress/result (`status` role, `Copy` button) remains for the failed attempt.
- **`full-check` never actually run.** Ran `python scripts/agent/runner.py full-check` for real on
  the current head: exit code 0 -- `quick-check` (1241 passed, 451 deselected), `frontend-check`
  (`ce-kit` 315 passed, `web-mirror` 74 passed, all builds/lints/typechecks clean), and the
  freelancer-suite backend pytest tail (17 passed). Evidence is this log; not re-pasted verbatim
  here.

**Verification commands run:** `cd tests/e2e/proposal-ai-smoke && pnpm run typecheck` (clean),
`pnpm run lint --max-warnings=0` (clean), `python3 -m py_compile scripts/agent/runner.py` (clean),
`python scripts/agent/runner.py dev-up` + `python scripts/agent/runner.py proposal-ai-smoke` (7/7
Playwright tests passing, including all 4 new ones, against a freshly rebuilt live stack -- one
genuine bug caught live in the process: the first `countBackendEvents()` attempt failed with
`relation "event_log" does not exist` because the table lives in the `platform` schema, not
`public`; fixed by schema-qualifying the query after confirming the actual schema via
`information_schema.tables`, not guessing), and `python scripts/agent/runner.py full-check` (exit
0, see above).

**Files changed:** `scripts/agent/runner.py`, `tests/e2e/proposal-ai-smoke/package.json`,
`tests/e2e/proposal-ai-smoke/tests/proposal-ai-smoke.spec.ts`, `pnpm-lock.yaml`.
