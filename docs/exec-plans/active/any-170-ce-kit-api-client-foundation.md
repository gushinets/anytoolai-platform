# Execution Plan: ANY-170 CE Kit API Client Foundation

## Status

- State: active
- Owner: agent
- Created: 2026-08-03
- Last updated: 2026-08-04
- Review date: 2026-08-04
- Next action: replace the PR description's `docs/exec-plans/active/...` placeholder with a link
  to this file (PR-description edit, not a repo file).
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

- API: none added/changed. Consumes two existing endpoints read-only:
  `POST /v1/identity/guest`, `GET /v1/products/{product_id}/runtime-config`.
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
- [x] Replace the PR description's `docs/exec-plans/active/...` placeholder with a link to this
  file (PR-description edit, not a repo file — done at PR-open/update time; no `gh` CLI available
  in this environment to do it directly).

## Validation

- [x] `pnpm --filter @anytoolai/ce-kit typecheck`
- [x] `pnpm --filter @anytoolai/ce-kit test` (84/84)
- [x] `python scripts/agent/runner.py frontend-check`
- [x] `python scripts/agent/runner.py full-check`

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-03 | Test runner is vitest, wired as a mandatory `frontend-check` step, not documented separately. | User decision; a broken-tests pipeline must fail CI, not just fail an unenforced convention. |
| 2026-08-03 | TS↔OpenAPI alignment uses generated types (`openapi-typescript`) plus a committed-artifact drift check, not hand-maintained DTOs. | Keeps CE-kit's view of the contract from silently drifting from the backend/prod; `PlatformApiClient` itself stays hand-written (out of codegen scope). |
| 2026-08-03 | `AsyncStorage` stays a narrow single-key `get`/`set`/`remove` contract; Chrome compatibility is achieved via a CE-kit-owned, tested `createChromeStorageAdapter()` rather than widening the contract itself to `chrome.storage.local`'s multi-key/untyped shape. | Team-lead review: the ticket requires a storage interface *compatible with* `chrome.storage.local`; an adapter satisfies that without forcing every non-Chrome caller (tests, web frontends) to deal with a multi-key/untyped API. |
| 2026-08-03 | `createGuestIdentity()` single-flight dedup is keyed by client instance only, not by `(client, storageKey)`. | Team-lead review: the acceptance criterion is "at most one backend request within one client instance," full stop -- a compound key (added in an earlier internal review pass to avoid collapsing different `storageKey`s) violated that literal AC. Reverted to instance-only keying; only the call that actually performs the request persists to its own `storageKey`. |
| 2026-08-03 | `createGuestIdentity()` returns a `GuestIdentityResult` (`{ok:true,value}` / `{ok:false,error}`) instead of throwing. | Team-lead review: throwing a plain `Error` for backend/malformed-response failures let them escape the stable `PlatformApiError` union that every other client failure goes through. |
| 2026-08-03 | Timeout-vs-caller-abort classification is decided by recording which trigger fires first (`abortReason`, set inside the abort callback itself), not by re-reading `externalSignal.aborted` after the fetch rejection settles. | Team-lead review: a timeout that fires first but is followed by a caller abort before the rejection lands was misclassified as `aborted` under the old re-check-in-catch approach. |
| 2026-08-04 | Declined to add a second `AssertExactSchemaKeys` layer for the hand-maintained *output* DTOs (`RuntimeConfig`, `GuestIdentity`). | Verified empirically (temporarily adding a bogus extra field to a parser's return literal) that TypeScript's own excess-property checking on directly-returned, explicitly-typed object literals already rejects both added and removed output fields with no gap -- a manual key-list would duplicate protection TypeScript already provides for free. The existing `AssertExactSchemaKeys` checks stay scoped to the wire format, where no such automatic protection exists because the payload starts as `unknown`. |
| 2026-08-04 | This plan was created under `docs/exec-plans/active/` after review pointed out ANY-170's working plan (`plans/ANY-170.md`) is untracked/gitignored, matching the same repo-policy gap already fixed for ANY-147. | `AGENTS.md` requires a tracked execution plan under `docs/exec-plans/active/` for non-trivial work; `plans/` is a personal, gitignored scratch directory, not the canonical location. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-03 | Implemented vitest infra, error union, `PlatformApiClient`, `AsyncStorage`, `createGuestIdentity()`, `getRuntimeConfig()`, OpenAPI codegen + drift check, unit tests, README. Ran an internal self-review pass (10 findings) and fixed 8 of them (guest-storage-failure orphan risk, single-flight compound-keying, missing HTTP status on success, `frontend_ids`/`scenario_ids` desync validation, duplicate OpenAPI-schema builds, `_isRecord` duplication), accepted 2 as YAGNI/cross-language tradeoffs. | Await external review. |
| 2026-08-03 | Two further internal review rounds fixed: unbound `fetchImpl` ("Illegal invocation"), already-aborted external signal not propagating into a fresh internal controller, empty-2xx-body handling, `_sameIds` not rejecting duplicate entry ids, and missing `cause` on the guest-identity failure `Error`. | Await external review. |
| 2026-08-04 | Team-lead review (against PR head `bda5544c`) found 3 must-address AC gaps (Chrome storage compatibility, single-flight scoping, error union escape) and 2 recommended items (OpenAPI drift check not covering hand-maintained DTOs, timeout/abort race). Fixed all 5: added and tested `createChromeStorageAdapter()`; moved `createGuestIdentity()` onto `PlatformApiClient` with instance-only single-flight; switched it to return `GuestIdentityResult` instead of throwing; added `AssertExactSchemaKeys` type-level drift assertions for every hand-parsed wire schema; fixed the timeout-vs-abort race by recording `abortReason` at trigger time. Also moved this review's text out of `plans/ANY-147.md` (where it had been pasted by mistake) into `plans/ANY-170.md`. `frontend-check`/`full-check` green, 84/84 tests. | Address any follow-up review. |
| 2026-08-04 | Second-pass review re-verified the same 3 must-address items against current code and found them already fixed (review had run against the last-pushed commit, before the round above) -- confirmed via direct inspection, no further code change needed there. Confirmed the `docs/exec-plans/active/...` PR-description placeholder is real (no exec plan existed for ANY-170, same gap already fixed for ANY-147) and created this file. Evaluated the nitpick asking to extend `AssertExactSchemaKeys` to the parser *output* DTOs; verified empirically that TypeScript's own excess-property checking already fully covers that case, so declined as redundant. | Update the PR description's placeholder link once a PR exists to update. |

## Open questions

None repo-side. The PR description placeholder is a non-repo follow-up tracked above.

## Follow-up debt

- None beyond ANY-171 (A15b: `getQuota()`, `startScenario()`, polling), which is explicitly a
  separate ticket.
