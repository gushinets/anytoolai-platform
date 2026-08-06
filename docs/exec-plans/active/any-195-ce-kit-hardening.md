# Execution Plan: ANY-195 CE-kit error, cancellation, storage, and drift hardening

## Status

- State: active
- Owner: agent
- Created: 2026-08-05
- Last updated: 2026-08-06
- Review date: 2026-08-06
- Next action: fifth- and sixth-pass fixes are pushed (PR #56, head `c2b0adb`) and CI is green
  (frontend, docs, Windows/Ubuntu baseline, PostgreSQL, smoke, full-check, CodeRabbit); awaiting
  review sign-off/merge.
- Blocker: none

## Goal

Close four correctness/safety gaps left in the `PlatformApiClient` foundation (ANY-170, PR #49)
before A15b (ANY-171) builds scenario/quota/polling client methods on top of it: unsafe fetch
exception text leaking into public errors, retry backoff not observing caller cancellation,
`storage.get()` rejections escaping `createGuestIdentity()`, and OpenAPI drift checks that only
compare property names, not types/nullability. Two subsequent `/code-review` passes (see "Code
review" sections below) surfaced and fixed follow-on issues in the same four areas that weren't
caught by the original scope: an unreachable branch and a missing optionality check in the new
drift assertion, a `parseRuntimeConfig` false-rejection the drift assertion itself exposed, a
retry-loop abort check that only ran after a configured delay, and two variants of a
`createGuestIdentity()` storage-write race that could clobber a concurrently cached guest id.

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
- `python scripts/agent/runner.py full-check` -- passed locally; PR #56 is open and CI (frontend,
  docs, Windows/Ubuntu baseline, PostgreSQL, smoke, full-check, CodeRabbit) is green on the current
  head (`c2b0adb`), which includes the fifth- and sixth-pass fixes below.
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

## Code review (2026-08-05, third pass -- inline review comments)

Verified each inline finding against current code before changing anything; two nitpicks on the
exec plan itself are addressed by this section and the updated Goal above.

1. VALID `README.md` drift-assertion section -- described `AssertExactSchemaKeys` as still used by
   parsers (`_guestIdentityResponseKeys`, per-schema key lists) and read as bidirectional. Both were
   stale: `AssertExactSchemaShape` replaced every use in the first-pass fix, and
   `AssertExactSchemaKeys` is now unused (`grep -rn "AssertExactSchemaKeys" src test` -> only its
   own declaration). Fixed by rewriting the section to describe `AssertExactSchemaShape` as the
   active check and `AssertExactSchemaKeys` as an unused, one-way-only legacy type kept for
   reference.
2. VALID `driftAssertions.ts` `MismatchedShapeKeys` -- compared only `IsEqual<T[K], Shape[K]>`.
   Indexing an optional property already produces `... | undefined` independent of the mapped
   type's own `-?` modifier, so `backend?: string` and `backend: string | undefined` index to the
   *same* type and were wrongly treated as equal. Fixed by adding `IsOptionalKey<T, K>` (`{} extends
   Pick<T, K>`) and requiring it to match between `T` and `Shape` too. Regression tests:
   `test/api/driftAssertions.test.ts` > "rejects an optionality mismatch even when the indexed value
   type is identical..." and its reverse-direction counterpart.
3. VALID `PlatformApiClient.createGuestIdentity()` -- the second-pass fix (skip persisting when
   *this call's own* `storage.get()` threw) doesn't cover a second variant of the same class of
   race: this call's own read genuinely misses (no throw), and *before* this call persists its
   freshly-fetched id, some other context (another tab, another client instance, a concurrent
   caller with a successful cache-hit read) writes a valid id to the same key -- blindly persisting
   would still clobber it. `AsyncStorage` has no atomic set-if-absent/compare-and-set primitive to
   fully close this (adding one is a breaking interface change touching
   `createChromeStorageAdapter()` and `createInMemoryAsyncStorage()` too, out of proportion for a
   minimal fix), so this is narrowed rather than eliminated: re-read the key immediately before
   persisting and skip the write if a value is already there, preferring whatever's already cached
   over this call's own fetched id. Regression test: `test/identity/guestIdentity.test.ts` > "does
   not overwrite a guest id cached concurrently between this call's own miss-read and its persist
   step".
4. Nitpick -- exec plan's Goal only listed the four original scope items, not the second-pass
   fixes. Fixed by extending the Goal paragraph above to reference the follow-on issues fixed by
   later review passes.

## Code review (2026-08-05, fourth pass -- pre-merge CI review)

1. VALID `parseRuntimeConfig.ts` `_parseScenario()` -- the second-pass fix normalized an explicit
   `allowed_next_actions: null` to `[]`, treating it the same as an absent key. But the generated
   schema types it `allowed_next_actions?: string[]` -- optional, not nullable -- and the
   `_RuntimeScenarioShapeCheck` drift assertion right below the parser asserts exactly that
   optional-not-nullable shape. Accepting `null` anyway was inconsistent with the very drift check
   this ticket added, and silently masked either a payload bug or genuine backend/schema drift
   that should surface as `invalid_response` instead. Since backend/OpenAPI schema changes are
   out of scope for ANY-195 (see Out of scope above), the fix is on the parser side: `null` is now
   rejected like any other malformed field; only an absent key defaults to `[]`. Regression test
   updated: `test/runtime/parseRuntimeConfig.test.ts` > "returns null when allowed_next_actions is
   explicitly null" (previously asserted acceptance; now asserts rejection).
2. Acknowledged, no code change -- the `createGuestIdentity()` re-read-before-write guard (third
   pass, finding 3 above) narrows but does not eliminate the storage-write race; a genuinely
   atomic fix needs a `setIfAbsent`/compare-and-set primitive on `AsyncStorage`, which is a
   breaking interface change out of proportion for this ticket (see finding 3's reasoning above).
   This was already stated as "narrowed rather than eliminated" rather than "fixed" in both the
   code comments and finding 3 above; recorded here explicitly as follow-up debt for a future
   ticket, not something this pass silently closes.
3. VALID (docs) -- Status/Verification still said `full-check` and PR-opening were pending,
   stale now that the PR is open and CI is green on this head. Fixed by updating both to reflect
   current state (see Status and Verification above).

## Code review (2026-08-06, fifth pass -- P2 persistence-after-transient-failure)

1. VALID `PlatformApiClient.createGuestIdentity()` -- `storageReadFailed` (set when this call's
   *initial* `storage.get()` threw) gated the entire persist-time re-read-and-write block, not
   just the decision of what to prefer once re-read. If the initial read failure was transient
   (a momentarily locked storage backend, not a permanent one), the backend-created guest id was
   still returned to the caller but never cached -- permanently, since nothing re-attempts
   persistence later. The next `createGuestIdentity()` call would find nothing cached and create
   a second, different identity, splitting guest-based quota across two ids for what should be
   one guest and violating the "reuses a persisted guest id if present" contract documented on
   the method itself. Fixed by removing the `storageReadFailed` gate: the persist-time re-read
   (added in the third pass to narrow the concurrent-write race) now always runs after a
   successful backend response, regardless of whether the initial read failed. It still prefers
   an existing value found on that re-read (unchanged), and still skips the write if the re-read
   or the write itself fails -- only *that* second failure is now treated as non-recoverable,
   not the first one. The now-unused `storageReadFailed` flag was removed. Regression test:
   `test/identity/guestIdentity.test.ts` > "persists the fetched guest id when the initial
   storage read failed but a later read succeeds (transient failure recovery)" -- first read
   throws, backend succeeds, second read succeeds and is empty (persists), and a subsequent
   `createGuestIdentity()` call reuses the persisted id without calling the backend again.
   README's guest-identity section updated to match (previously said a failed initial read
   always skips the write-back, which is no longer true).

## Code review (2026-08-06, sixth pass -- P2 return recovered cached identity)

1. VALID `PlatformApiClient.createGuestIdentity()` -- when the persist-time re-read found an
   existing guest id (another caller already won the race and cached its own), the write was
   correctly skipped but the method still `return`ed the outer `result`, i.e. *this* call's own
   backend-fetched id, not the cached one it just found and deferred to. The caller therefore used
   one id while storage (and every later call) used a different one, splitting guest-based quota
   across two ids -- the same failure mode the fifth pass fixed for the *initial*-read-failure
   path, just reachable from the concurrent-write path instead. Fixed by returning
   `{ ok: true, value: { guestId: existingGuestId } }` immediately once that second read finds a
   value, instead of falling through to the outer `result`. Regression test:
   `test/identity/guestIdentity.test.ts` > "returns the concurrently cached guest id, not its own
   fetched id, when the persist-step re-read finds one" (renamed/updated from "does not overwrite
   a guest id cached concurrently between this call's own miss-read and its persist step", which
   asserted the old, buggy return value as if it were correct). The sibling race test ("does not
   clobber a concurrently cached guest id when this call's own storage read failed") is unaffected
   -- there the persist-time re-read itself throws rather than finding a value, so it still falls
   through to the outer `result` by design; nothing to prefer was ever observed. README's
   guest-identity section updated to state that the recovered cached id, not this call's own
   fetched id, is what gets returned when the second read finds a value, and to explicitly note
   the still-open two-concurrent-empty-reads race (separate, non-atomic `get`/`set` on
   `AsyncStorage` means two callers can still both miss the re-read and both write different ids).
