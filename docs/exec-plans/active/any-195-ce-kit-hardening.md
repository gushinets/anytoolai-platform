# Execution Plan: ANY-195 CE-kit error, cancellation, storage, and drift hardening

## Status

- State: active
- Owner: agent
- Created: 2026-08-05
- Last updated: 2026-08-05
- Review date: 2026-08-05
- Next action: run `python scripts/agent/runner.py full-check`, open the PR, link this file from
  the PR description.
- Blocker: none

## Goal

Close four correctness/safety gaps left in the `PlatformApiClient` foundation (ANY-170, PR #49)
before A15b (ANY-171) builds scenario/quota/polling client methods on top of it: unsafe fetch
exception text leaking into public errors, retry backoff not observing caller cancellation,
`storage.get()` rejections escaping `createGuestIdentity()`, and OpenAPI drift checks that only
compare property names, not types/nullability.

## Scope

### In scope

- `networkError()` returns a fixed, safe message; the raw caught exception is dropped at the
  `performOnce()` catch site instead of being copied into `network_error.message`.
- `delay()` in `src/api/client/retry.ts` accepts an optional `AbortSignal` and resolves as soon as
  it fires; the retry loop in `PlatformApiClient.request()` passes `options.signal` through and
  returns `aborted` immediately (without another `performOnce()`/`fetchImpl` call) if the signal
  aborted during that wait.
- `createGuestIdentity()` wraps `options.storage.get()` in try/catch; a rejection is treated as a
  cache miss and falls through to the existing backend-request path, matching the `storage.set()`
  best-effort handling already in place.
- `driftAssertions.ts` gains `AssertExactSchemaShape<T, Shape>`, a field-for-field (name + type +
  optionality/nullability) check via strict type-equality (`IsEqual`), alongside the existing
  name-only `AssertExactSchemaKeys<T, Keys>`. Applied to `guestIdentity.ts`'s
  `GuestIdentityResponse` check and all four `parseRuntimeConfig.ts` schema checks
  (`RuntimeConfigResponse`, `RuntimeFrontendResponse`, `RuntimeScenarioResponse`,
  `RuntimeRendererHintResponse`, `RuntimeQuotaSummaryResponse`).
- Regression tests for each finding plus drift-assertion type-level tests
  (`test/api/driftAssertions.test.ts`, using `@ts-expect-error` to prove the assertion fails on
  same-key type/nullability changes and on missing/extra fields).
- README updates documenting the sanitized `network_error.message`, cancellation-aware retry
  backoff, storage-read-failure fallback, and the two-tier drift-assertion story.

### Out of scope

- A private diagnostics/telemetry sink for raw exception text (`src/events/trackClientEvent.ts` is
  still an empty stub) -- raw detail is simply dropped, not routed anywhere, per the ticket's "only
  in private diagnostics/telemetry where applicable."
- Scenario/quota/polling client methods (A15b / ANY-171).
- Any backend or OpenAPI schema changes.

## Design notes

- **Cancellation-aware backoff**: mirrors the existing `abortReason` timeout-vs-external-abort
  split in `performOnce()`, but applied to the *inter-attempt* wait rather than the fetch itself.
  `delay(ms, signal)` resolves on whichever comes first (timer or `abort` event) and always cleans
  up both the timer and the listener. The request loop checks `options.signal?.aborted` right after
  `delay()` returns and short-circuits to `abortedError()` before calling `performOnce()` again.
- **Type/nullability-aware drift check**: `AssertExactSchemaShape` compares `T[K]` against
  `Shape[K]` per key using a strict type-equality helper (distributes both types over a bare
  conditional rather than checking mutual assignability, so it also catches `unknown`/`any` and
  lost union members that assignability-based equality would miss). Optional keys are indexed with
  `-?` before comparison -- without that, TypeScript unions `undefined` into *any* indexed access on
  an optional property regardless of what it maps to, which would make every optional field
  (`allowed_next_actions`, `schema_version`) look mismatched even when correct. Verified against the
  real generated schema: `RuntimeScenarioResponse.allowed_next_actions` and
  `RuntimeRendererHintResponse.schema_version` are optional, `RuntimeConfigResponse.quota_summary`
  is a required-but-nullable union -- all three pass with the `-?` fix and would fail without it.

## Verification

- `python scripts/agent/runner.py doctor` -- passed.
- `python scripts/agent/runner.py frontend-check` -- passed (typecheck, `pnpm -r test`,
  `generate-api-types:check`, build all green).
- `python scripts/agent/runner.py full-check` -- to run before opening the PR.
- Manual check: temporarily reintroduced a `limit_count: number -> string` mismatch under
  `src/api/__drift_scratch.ts` and confirmed `tsc --noEmit` fails with `typeMismatch: "limit_count"`
  before removing the scratch file.

## Decision log

- Kept `AssertExactSchemaKeys` alongside the new `AssertExactSchemaShape` rather than replacing it
  -- the key-only check's error message (`missingFromParser`) is a strict subset of what the shape
  check reports, but removing it would be a larger diff than the ticket calls for and both types are
  cheap to keep in sync since `AssertExactSchemaShape`'s constraint already requires the same key
  set.

## Code review (2026-08-05)

`/code-review` on this branch found 2 CONFIRMED issues, both fixed:

1. **Dead `missingFromShape` branch.** The original `AssertExactSchemaShape<T extends object, Shape
   extends { [K in keyof T]: unknown }>` constrained `Shape` to already carry every key of `T` at
   the generic-instantiation site, so a genuinely missing key failed typecheck there -- before the
   conditional type's body (and its `missingFromShape` branch) ever ran. Fixed by relaxing the
   constraint to `Shape extends object` and doing the key-presence check inside the type itself
   (`MissingShapeKeys`/`ExtraShapeKeys`/`MismatchedShapeKeys` helpers). Regression test:
   `test/api/driftAssertions.test.ts` > "reports the missing key by name via the missingFromShape
   branch, proving it is reachable" (asserts `Check extends { missingFromShape: infer K } ? K :
   never` resolves to `"b"`, not `never`).
2. **`parseRuntimeConfig` rejected a schema-valid payload.** `_parseScenario()` required
   `allowed_next_actions` to be present via `_isStringArray()`, which returns `false` for
   `undefined` -- but the file's own new `AssertExactSchemaShape` check (correctly) declares
   `allowed_next_actions?: string[]` as optional per the generated `RuntimeScenarioResponse`. A
   backend response omitting the field (valid per schema) made the whole `parseRuntimeConfig()`
   call return `null` (`invalid_response`) instead of a working config. Fixed by accepting
   `undefined` and defaulting to `[]`. Regression tests:
   `test/runtime/parseRuntimeConfig.test.ts` > "accepts a scenario whose allowed_next_actions is
   absent, defaulting to an empty array" and "returns null when allowed_next_actions is present but
   not an array of strings" (kept to confirm the fix didn't loosen validation of a genuinely
   malformed value).

## Code review (2026-08-05, second pass)

A second `/code-review` pass, run after the first pass's two findings were fixed, surfaced 4 more
issues (3 CONFIRMED, 1 PLAUSIBLE). All fixed except the PLAUSIBLE one, which was a no-op reorder.

1. CONFIRMED `PlatformApiClient.ts` retry loop -- the `options.signal?.aborted` check after the
   backoff wait was nested inside `if (options.retry?.delayMs)`, so with `delayMs` unset or `0` the
   loop would call `performOnce()` (and thus `fetchImpl`) again immediately after cancellation,
   never observing the signal at all in that path. Fixed by moving the check out to run
   unconditionally every iteration, regardless of whether a delay happened. In this codebase's
   synchronous execution model a `delayMs: 0`/unset retry has no observable gap between one
   attempt's `network_error`/`timeout` result and the next attempt starting -- `performOnce()`'s own
   `controller.signal.aborted` check already absorbs any cancellation that happens during or
   through that gap into that attempt's own result as `aborted` (not retryable), so the loop stops
   via `isRetryable()` before ever reaching this new check. That makes the fix correct
   defense-in-depth matching the ticket's literal acceptance criteria ("do not invoke fetchImpl for
   another attempt after caller cancellation") and future-proofing against any refactor that
   introduces a real async gap here (e.g. non-JS-engine timing in a real browser's fetch stack),
   rather than something with a reproducible race in a unit test today -- confirmed by attempting
   several race-construction strategies, all of which collapsed into the already-tested
   pre-existing-abort-during-an-attempt case rather than exercising this specific line. Covered
   instead by a related regression test that does exercise the unconditional nature of the check:
   `test/api/client.test.ts` > "does not retry when the caller cancels mid-attempt and no retry
   delayMs is set".
2. CONFIRMED `PlatformApiClient.createGuestIdentity()` -- the try/catch around `storage.get()`
   only prevents a thrown exception; it doesn't prevent a genuine race where caller A's read on a
   given key succeeds (returns its cached id immediately, no persistence) while caller B's read on
   the *same* key fails around the same time (treated as miss, joins/triggers the shared backend
   request) and then persists a *different*, freshly-fetched id to that same key -- clobbering the
   value A already read and is using. Fixed by tracking whether this call's own read failed and
   skipping the `storage.set()` persistence step when it did (mirrors the existing best-effort
   `storage.set()` failure handling, now applied symmetrically on the read side). Regression test:
   `test/identity/guestIdentity.test.ts` > "does not clobber a concurrently cached guest id when
   this call's own storage read failed".
3. CONFIRMED `parseRuntimeConfig.ts` `_parseScenario()` -- the guard added in the first pass
   (`allowedNextActions !== undefined && ...`) only exempted an absent key. An explicit wire value
   of `null` for the same optional field still reached `_isStringArray(null) === false` and failed
   the whole `parseRuntimeConfig()` call, contradicting the guard's own comment ("absent means no
   next actions, not malformed payload"). Fixed by treating `null` the same as `undefined`.
   Regression test: `test/runtime/parseRuntimeConfig.test.ts` > "accepts a scenario whose
   allowed_next_actions is explicitly null, defaulting to an empty array".
4. PLAUSIBLE `retry.ts` `delay()` -- `onAbort`, referenced inside the `setTimeout` callback for
   `removeEventListener`, was declared *after* that callback in source order. Never an actual bug
   (the callback only runs once both consts are initialized, since `setTimeout`'s callback can't
   fire until the synchronous executor body -- including the `onAbort` declaration below it -- has
   finished), but reordered `onAbort` before the `setTimeout` call for readability/robustness
   against future refactors. No behavior change, no new test.
