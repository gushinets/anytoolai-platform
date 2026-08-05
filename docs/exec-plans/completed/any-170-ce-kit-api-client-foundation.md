# Execution Plan: ANY-170 CE Kit API Client Foundation

## Status

- State: completed
- Owner: agent
- Created: 2026-08-03
- Last updated: 2026-08-05
- Review date: 2026-08-04
- Next action: none outstanding. PR #49's description now links to
  `docs/exec-plans/completed/any-170-ce-kit-api-client-foundation.md`, verified via
  `gh pr view 49 --json body` on 2026-08-05.
- Blocker: none

## Goal

Replace CE-kit's ad-hoc `fetch` calls and synchronous storage assumptions with one tested,
central `PlatformApiClient` foundation: normalized base URL, injectable `fetch`, `AbortController`
timeout, caller cancellation, standard headers, a stable frontend-safe error union, real
`createGuestIdentity()`/`getRuntimeConfig()` calls against the Platform API, and an
OpenAPI-driven codegen + drift-check pipeline so CE-kit's types can't silently diverge from the
backend.

## Scope

### In scope

- `PlatformApiClient`: base URL normalization, injectable `fetch`, timeout, cancellation, standard
  headers, optional `X-Request-ID`, retry primitives restricted to explicitly safe (GET) calls.
- Stable `PlatformApiError` union (`backend_error` / `network_error` / `timeout` / `aborted` /
  `invalid_response`) and safe parsing of the backend's `{error:{code,message,request_id}}`
  envelope.
- Injectable `AsyncStorage` contract, a `chrome.storage.local` adapter, and an in-memory test
  implementation.
- `PlatformApiClient.createGuestIdentity()`: persists/reuses the opaque guest id, single-flight
  per client instance.
- Real `getRuntimeConfig()` as the first safe GET endpoint.
- OpenAPI-driven type codegen (`openapi-typescript`) for `src/api/generated/platformApi.ts`, with
  a committed-artifact drift check, plus type-level drift assertions tying the hand-maintained
  wire-format parsers to the generated schema.

### Out of scope

- `getQuota()`, `startScenario()`, `getScenarioSession()`, `pollScenarioSession()`,
  `nextAction()` (ANY-171 / A15b).
- Product-specific UX, direct provider calls, prompt/model selection.
- Email, artifact, client-event, and handoff integration.

## Relevant docs

- `docs/architecture/frontend-boundaries.md`
- `docs/product-specs/mvp-scope-source-of-truth.md`
- `packages/frontend/ce-kit/README.md`

## Contracts touched

- API: none added/changed. Consumes two existing endpoints: `GET
  /v1/products/{product_id}/runtime-config` (read-only), and `POST /v1/identity/guest`
  (`create_guest_identity_v1_identity_guest_post`; state-changing -- creates a new guest identity
  on the backend, not read-only).
- DB: none.
- Config: none.
- Events: none.
- Frontend: `packages/frontend/ce-kit/src/api`, `.../src/storage`, `.../src/identity`,
  `.../src/runtime`, `.../package.json`, `.../scripts/generate-api-types.mjs`.

## Implementation steps

- [x] Vitest test infrastructure in `ce-kit`, wired as a mandatory step in `frontend-check`
  (`scripts/agent/runner.py`), not a documentation-only aside.
- [x] Stable `PlatformApiError` union and backend error-envelope parsing without leaking
  unvalidated response content.
- [x] Core `PlatformApiClient`: base URL, DI `fetch`, timeout via `AbortController`, caller
  cancellation, headers, `X-Request-ID`, GET-only retry primitives.
- [x] Injectable `AsyncStorage` plus `createChromeStorageAdapter()` (wraps
  `chrome.storage.local`'s multi-key/untyped API without a `@types/chrome` dependency) and
  `createInMemoryAsyncStorage()`.
- [x] `createGuestIdentity()` moved onto `PlatformApiClient` (not a free function); single-flight
  in-flight guard is a private field on the client instance, keyed by the instance only (not by
  `storageKey`), so concurrent calls make at most one backend request per instance; returns a
  `GuestIdentityResult` through the stable `PlatformApiError` union instead of throwing.
- [x] Real `getRuntimeConfig()` against `GET /v1/products/{product_id}/runtime-config`, with
  cross-checked `frontend_ids`/`frontends` and `scenario_ids`/`scenarios` (rejects desync,
  including duplicate ids).
- [x] OpenAPI codegen: `apps/platform-api/.../openapi/generate.py` exports the real schema,
  `docs/generated/openapi.json` is a committed drift-checked artifact, `openapi-typescript`
  generates `src/api/generated/platformApi.ts`, `generate-api-types:check` fails CI on drift.
  `src/api/driftAssertions.ts`'s `AssertExactSchemaKeys<T, Keys>` additionally ties each
  hand-written wire-format parser (`parseGuestIdentityPayload`, `parseRuntimeConfig` and its
  nested parsers) to the exact key set of its corresponding generated schema, so a backend schema
  change that codegen picks up but a parser doesn't follow fails typecheck.
- [x] Unit tests: URL joining, headers, timeout, cancellation, malformed JSON, backend error
  envelope, guest-storage races, chrome storage adapter, timeout-vs-abort race classification.
- [x] `README.md`: base URL, DI, storage (including the Chrome adapter), timeout, errors,
  versioning, generated-contract drift-check workflow.
- [x] `frontend-check` and `full-check` green.
- [x] Replace PR #49's description placeholder with a link to this file. Confirmed via
  `gh pr view 49 --json body` (after `gh` auth was set up in this environment) that the body now
  reads `Link: \`docs/exec-plans/completed/any-170-ce-kit-api-client-foundation.md\``.
- [x] Every successful `createGuestIdentity()` caller persists the shared result to its own
  `storage`/`storageKey`, not just whichever call happened to trigger the backend request.
- [x] Documented the `AsyncStorage`-vs-`chrome.storage.local` adapter decision explicitly in the
  README, closing the ambiguity in the ticket's "compatible with `chrome.storage.local`" wording.
- [x] `createGuestIdentity()`'s single-flight coordination is scoped to the whole call (entry
  through persistence), not just around the shared backend request, so a caller with a slow
  `storage.get()` can't miss a request that started and finished while it was still pending.

## Validation

- [x] `pnpm --filter @anytoolai/ce-kit typecheck`
- [x] `pnpm --filter @anytoolai/ce-kit test` (86/86)
- [x] `python scripts/agent/runner.py frontend-check`
- [x] `python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-03 | Test runner is vitest, wired as a mandatory `frontend-check` step, not documented separately. | User decision; a broken-tests pipeline must fail CI, not just fail an unenforced convention. |
| 2026-08-03 | TS↔OpenAPI alignment uses generated types (`openapi-typescript`) plus a committed-artifact drift check, not hand-maintained DTOs. | Keeps CE-kit's view of the contract from silently drifting from the backend/prod; `PlatformApiClient` itself stays hand-written (out of codegen scope). |
| 2026-08-03 | `AsyncStorage` stays a narrow single-key `get`/`set`/`remove` contract; Chrome compatibility is achieved via a CE-kit-owned, tested `createChromeStorageAdapter()` rather than widening the contract itself to `chrome.storage.local`'s multi-key/untyped shape. | Team-lead review: the ticket requires a storage interface *compatible with* `chrome.storage.local`; an adapter satisfies that without forcing every non-Chrome caller (tests, web frontends) to deal with a multi-key/untyped API. |
| 2026-08-03 | `createGuestIdentity()` single-flight dedup is keyed by client instance only, not by `(client, storageKey)`. | Team-lead review: the acceptance criterion is "at most one backend request within one client instance," full stop -- a compound key (added in an earlier internal review pass to avoid collapsing different `storageKey`s) violated that literal AC. Reverted to instance-only keying. **Superseded 2026-08-04 (see that entry below): the persistence half of this decision -- "only the call that actually performs the request persists to its own `storageKey`" -- was itself a bug, since a racing caller with a different `storageKey` never got its own slot populated. The instance-only single-flight keying decision itself is unchanged and still current; only the persistence behavior described here is historical.** |
| 2026-08-03 | `createGuestIdentity()` returns a `GuestIdentityResult` (`{ok:true,value}` / `{ok:false,error}`) instead of throwing. | Team-lead review: throwing a plain `Error` for backend/malformed-response failures let them escape the stable `PlatformApiError` union that every other client failure goes through. |
| 2026-08-03 | Timeout-vs-caller-abort classification is decided by recording which trigger fires first (`abortReason`, set inside the abort callback itself), not by re-reading `externalSignal.aborted` after the fetch rejection settles. | Team-lead review: a timeout that fires first but is followed by a caller abort before the rejection lands was misclassified as `aborted` under the old re-check-in-catch approach. |
| 2026-08-04 | Declined to add a second `AssertExactSchemaKeys` layer for the hand-maintained *output* DTOs (`RuntimeConfig`, `GuestIdentity`). | Verified empirically (temporarily adding a bogus extra field to a parser's return literal) that TypeScript's own type checking on directly-returned, explicitly-typed object literals already rejects both directions with no gap: an added field is rejected by excess-property checking on the fresh literal, and a removed *required* field is separately rejected by ordinary structural assignability (the literal no longer satisfies the declared return type) -- two different TS mechanisms, but together a complete guard. A manual key-list would duplicate protection TypeScript already provides for free. The existing `AssertExactSchemaKeys` checks stay scoped to the wire format, where no such automatic protection exists because the payload starts as `unknown`. |
| 2026-08-04 | This plan was created under `docs/exec-plans/active/` after review pointed out ANY-170's working plan (`plans/ANY-170.md`) is untracked/gitignored, matching the same repo-policy gap already fixed for ANY-147. | `AGENTS.md` requires a tracked execution plan under `docs/exec-plans/active/` for non-trivial work; `plans/` is a personal, gitignored scratch directory, not the canonical location. |
| 2026-08-04 | `createGuestIdentity()`'s single-flight network request and per-caller storage persistence are decoupled: the shared in-flight promise (`shareGuestIdentityRequest()`/`requestGuestIdentity()`) now only performs the backend call, and every caller of `createGuestIdentity()` -- whether it triggered the request or just awaited the shared result -- persists to its own `storage`/`storageKey` afterward. | Second team-lead review round: the previous instance-scoped single-flight fix (2026-08-03 entry above) correctly stopped over-collapsing concurrent calls, but only the triggering call's `storage.set()` ran, so a racing caller with a different `storage`/`storageKey` got the right in-memory result but never got its own key populated -- its next lookup would miss and re-request. |
| 2026-08-04 | Documented the `AsyncStorage`-vs-`chrome.storage.local` design decision explicitly in the README (not just in this plan's decision log), stating in the "Storage" section itself that `AsyncStorage` is deliberately *not* structurally assignable to `chrome.storage.local` and that compatibility is provided via `createChromeStorageAdapter()`. | Second team-lead review round: asked for the narrow-contract-plus-adapter interpretation of the ticket's "compatible with `chrome.storage.local`" wording to be stated explicitly in requirements-facing documentation, not only implied by the adapter's existence, so the open question can be closed with a citable rationale. |
| 2026-08-04 | Declined to extend `AssertExactSchemaKeys` (or add a companion check) to validate field *types*, nullability, optionality, or enum values, not just key names. | Third team-lead review's additional observation is correct that key-name-only checks miss e.g. a field's type widening/narrowing or an enum growing a new literal. But every wire-format parser already re-validates each field's runtime shape (`typeof x === "string"`, `renderer !== "json_schema"`, etc.) and fails closed to `null`/`invalid_response` rather than trusting the generated type -- so an undetected type-level schema change degrades safely (a legitimate response starts being rejected, loudly, in production) rather than silently misbehaving. Building real type-level structural validation would mean hand-declaring an expected type shape per field as a second, parallel source of truth next to the runtime checks -- itself a drift risk of the same kind this mechanism exists to prevent -- for a category of backend change (field type/enum narrowing without a key rename) that's rare relative to key add/remove. Accepted as a documented limitation rather than implemented. |
| 2026-08-04 | Corrected a false "done" claim about the PR-description placeholder. | This file's "Implementation steps" checkbox for the placeholder was earlier marked `[x]` on the assumption that an externally-modified version of this file (attributed to "the user") reflected a real fix. The user then asked how to verify that claim, which prompted an actual check: `curl https://api.github.com/repos/gushinets/anytoolai-platform/pulls/49` (PR #49, head `9bd85e4` -- matches this branch's current HEAD) shows the body still contains the literal `Link: \`docs/exec-plans/active/...\``. The checkbox was wrong; corrected back to unchecked with the verification method recorded so it doesn't happen again. Lesson: a checked box or an externally-edited file is not evidence by itself -- verify state that lives outside the repo (like a PR description) against its actual source before reporting it as done. |
| 2026-08-04 | Re-confirmed the PR-description placeholder as actually fixed, this time via `gh pr view 49 --json body` after the user set up `gh` auth in this environment. | The user asked to re-check with `gh` now available. Body now reads `Link: \`docs/exec-plans/active/any-170-ce-kit-api-client-foundation.md\`` -- the user had fixed it on GitHub between the previous (unauthenticated-`curl`) check and this one. Checkbox restored to `[x]`, this time on direct tool-verified evidence rather than an inference from a locally-edited file. |
| 2026-08-04 | `createGuestIdentity()`'s single-flight coordination now spans the whole call (increment `activeGuestIdentityCalls` at entry, decrement in `finally` after persistence), and `inFlightGuestIdentity` is only cleared when that counter hits zero -- not immediately when the shared backend request itself settles. | Fourth team-lead review round (P1, head `cbe0ebe`): the previous fix (2026-08-04 entry above, "network request and per-caller persistence are decoupled") still cleared `inFlightGuestIdentity` in the shared request's own `.finally()`, and each caller only joined it *after* awaiting its own `storage.get()`. A caller with a slow storage lookup could therefore have another, fast caller's request start and fully finish -- clearing the in-flight state -- before the slow caller's lookup even resolved, so it wrongly started a second backend request. Reproduced with a new deferred-first-`get()` storage test double; confirmed the test fails (2 fetches) against the pre-fix code and passes (1 fetch, both callers' storage populated) with the fix. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-03 | Implemented vitest infra, error union, `PlatformApiClient`, `AsyncStorage`, `createGuestIdentity()`, `getRuntimeConfig()`, OpenAPI codegen + drift check, unit tests, README. Ran an internal self-review pass (10 findings) and fixed 8 of them (guest-storage-failure orphan risk, single-flight compound-keying, missing HTTP status on success, `frontend_ids`/`scenario_ids` desync validation, duplicate OpenAPI-schema builds, `_isRecord` duplication), accepted 2 as YAGNI/cross-language tradeoffs. | Await external review. |
| 2026-08-03 | Two further internal review rounds fixed: unbound `fetchImpl` ("Illegal invocation"), already-aborted external signal not propagating into a fresh internal controller, empty-2xx-body handling, `_sameIds` not rejecting duplicate entry ids, and missing `cause` on the guest-identity failure `Error`. | Await external review. |
| 2026-08-04 | Team-lead review (against PR head `bda5544c`) found 3 must-address AC gaps (Chrome storage compatibility, single-flight scoping, error union escape) and 2 recommended items (OpenAPI drift check not covering hand-maintained DTOs, timeout/abort race). Fixed all 5: added and tested `createChromeStorageAdapter()`; moved `createGuestIdentity()` onto `PlatformApiClient` with instance-only single-flight; switched it to return `GuestIdentityResult` instead of throwing; added `AssertExactSchemaKeys` type-level drift assertions for every hand-parsed wire schema; fixed the timeout-vs-abort race by recording `abortReason` at trigger time. Also moved this review's text out of `plans/ANY-147.md` (where it had been pasted by mistake) into `plans/ANY-170.md`. `frontend-check`/`full-check` green, 84/84 tests. | Address any follow-up review. |
| 2026-08-04 | Second-pass review re-verified the same 3 must-address items against current code and found them already fixed (review had run against the last-pushed commit, before the round above) -- confirmed via direct inspection, no further code change needed there. Confirmed the `docs/exec-plans/active/...` PR-description placeholder is real (no exec plan existed for ANY-170, same gap already fixed for ANY-147) and created this file. Evaluated the nitpick asking to extend `AssertExactSchemaKeys` to the parser *output* DTOs; verified empirically that TypeScript's own excess-property checking already fully covers that case, so declined as redundant. | Update the PR description's placeholder link once a PR exists to update. |
| 2026-08-04 | Third team-lead review round (against head `9bd85e4`, cross-referencing CodeRabbit feedback) found the guest-identity single-flight fix was incomplete (only the triggering caller persisted its result -- see decision log), asked for the Chrome-storage adapter decision to be stated explicitly rather than left implicit, and flagged that the PR description's placeholder was still unresolved as of that review. Fixed the persistence gap with a regression test covering both a different-`storageKey`-same-`storage` race and a different-`storage`-instance race; added the explicit design-decision paragraph to the README. The PR description placeholder was resolved directly by the user on GitHub (not a repo-file change). Also evaluated the review's additional observation that `AssertExactSchemaKeys` only checks key names, not field types/nullability/enum values -- see decision log entry below for the reasoning to accept this as a documented limitation rather than build a heavier type-level validator. | Await any further review. |
| 2026-08-04 | Fourth team-lead review round (P1, head `cbe0ebe`) found a remaining single-flight race: since `createGuestIdentity()` only joined `inFlightGuestIdentity` after awaiting its own `storage.get()`, a caller with a slow lookup could miss a request that another, faster caller started and fully finished (clearing the in-flight state) while the slow lookup was still pending -- yielding two backend requests for what was still one overlapping initialization window. Fixed by moving coordination to the whole call: an `activeGuestIdentityCalls` counter increments at method entry and decrements in `finally`, and `inFlightGuestIdentity` only clears at zero. Added the exact regression test requested (deferred/slow `storage.get()` for one caller, fast backend response for the other), and manually confirmed it fails against the pre-fix code (2 fetches) before confirming it passes with the fix (1 fetch, both callers' storage populated). Also fixed three doc-only findings in this same exec plan from an earlier inline-comment round (Contracts-touched section wrongly called `POST /v1/identity/guest` read-only; a decision-log entry imprecisely described TypeScript's excess-property-vs-assignability protection for output DTOs; a stale 2026-08-03 decision-log entry about per-caller persistence needed marking superseded). | Await any further review. |
| 2026-08-05 | Updated merged PR #49's external description to the archived `docs/exec-plans/completed/any-170-ce-kit-api-client-foundation.md` path and verified the result directly with `gh`. | None. |

## Open questions

None.

## Follow-up debt

- None beyond ANY-171 (A15b: `getQuota()`, `startScenario()`, polling), which is explicitly a
  separate ticket.
