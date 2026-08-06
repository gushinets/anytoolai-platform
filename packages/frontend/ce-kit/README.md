# @anytoolai/ce-kit

Shared Platform API client foundation for AnytoolAI Chrome Extensions and web frontends.

This package covers **A15 — CE Kit MVP API Client** (ANY-8): both **A15a — Foundation** (ANY-170)
and **A15b — Scenario, Quota, and Polling Client** (ANY-171). The transport layer, the stable error
union, injectable storage, guest identity, runtime config, quota, idempotent scenario start,
session polling, and next-action are all real. Several other exports (`pollJob`, `getArtifact`,
`createHandoff`, `openHandoffConsent`, `captureEmail`, `trackClientEvent`, the `render*` helpers)
remain fake-success placeholders deferred to later tickets (public job polling, artifact fetching,
handoff, email capture, client-event ingestion). Do not treat their presence in `src/index.ts` as a
working contract.

## PlatformApiClient

`PlatformApiClient` is the only thing in this package that talks to the network. Helpers built on
top of it (`createGuestIdentity`, `getRuntimeConfig`, ...) never construct URLs, parse errors,
implement their own timeouts, or retry on their own -- all of that lives here, once.

```ts
import { PlatformApiClient } from "@anytoolai/ce-kit";

const client = new PlatformApiClient({
  baseUrl: "https://api.anytoolai.example.com",
  timeoutMs: 10_000, // default; overridable per-request
});

const result = await client.request<{ product_id: string }>({
  method: "GET",
  path: "/v1/products/kernel_demo/runtime-config",
});

if (result.ok) {
  console.log(result.value.product_id);
} else {
  // result.error.type: "backend_error" | "network_error" | "timeout" | "aborted" | "invalid_response"
}
```

### Base URL

`baseUrl` is normalized once at construction (trimmed, trailing slash stripped) and combined with
each request's `path` via a single `/`. Pass an empty or whitespace-only `baseUrl` and the
constructor throws immediately rather than producing a malformed URL later.

### Dependency injection

`fetchImpl` (defaults to `globalThis.fetch`) lets tests and non-browser hosts (e.g. a service
worker or a Node-based test harness) supply their own `fetch`. `AsyncStorage` (see below) is
injected the same way into anything that needs to persist state, so nothing in this package reaches
for a global directly.

```ts
const client = new PlatformApiClient({
  baseUrl: "https://api.anytoolai.example.com",
  fetchImpl: myFetchImpl, // e.g. a vitest mock, or a fetch bound to a specific origin
});
```

### Timeout and cancellation

Every request has a timeout (`timeoutMs` on the client, overridable per-request) enforced via an
internal `AbortController`. Callers can additionally pass their own `signal` for cooperative
cancellation (e.g. tied to a popup closing); the two are independent and distinguishable in the
result:

```ts
const controller = new AbortController();
const pending = client.request({ path: "/v1/x", signal: controller.signal, timeoutMs: 5_000 });
controller.abort(); // -> { ok: false, error: { type: "aborted" } }
// vs. no external abort and the timeout elapsing -> { ok: false, error: { type: "timeout" } }
```

### Headers

`Accept: application/json` is always set. `Content-Type: application/json` is set only when the
request has a body, and `X-Request-ID` only when a `requestId` is passed -- both are skippable via
an explicit header override, which always wins over the client's defaults.

```ts
await client.request({
  path: "/v1/x",
  method: "POST",
  body: { foo: "bar" },
  requestId: crypto.randomUUID(), // correlation-only; not an idempotency key
});
```

### Retries

Retries are opt-in per request via `retry: { attempts, delayMs? }`, and are **only accepted for
safe (`GET`) requests** -- passing `retry` on any other method throws synchronously, before any
network call is made. Even with a retry policy set, only `network_error` and `timeout` are
retried; `backend_error`, `invalid_response`, and `aborted` never are.

```ts
await client.request({ path: "/v1/x", retry: { attempts: 3, delayMs: 200 } }); // GET only
```

The wait between retry attempts observes the caller's `signal`: if it aborts during that delay,
the request settles promptly with `aborted` and no further attempt is made -- cancellation is not
delayed until the next `fetchImpl` call would otherwise have started.

## Errors

Every failure from `PlatformApiClient.request()` is one of five variants, safe to log or display
as-is (no raw response bodies or headers ever leak through):

| `type` | When | Extra fields |
|---|---|---|
| `backend_error` | Non-2xx with a parseable `{ error: { code, message, request_id } }` envelope | `status`, `code`, `message`, `requestId` |
| `invalid_response` | Response body isn't valid JSON, or (for non-2xx) doesn't match the error envelope | `status`, `message` |
| `network_error` | `fetch` itself rejected (offline, DNS, CORS, ...) | `message` |
| `timeout` | The client's own timeout elapsed | -- |
| `aborted` | The caller's own `signal` was aborted | -- |

`network_error.message` is always the fixed string `"Network request failed."` -- the raw caught
exception (which can contain URLs, internal hostnames, or other environment detail) is never
copied into it. There is currently no private diagnostics/telemetry sink in CE-kit to preserve
that raw detail elsewhere; it is simply dropped.

```ts
if (!result.ok) {
  switch (result.error.type) {
    case "backend_error":
      return showError(result.error.code); // safe to display
    case "timeout":
    case "network_error":
      return showRetryPrompt();
    default:
      return showGenericError();
  }
}
```

## Storage

`AsyncStorage` is a minimal, single-key `get`/`set`/`remove` contract -- narrower than
`chrome.storage.local`'s own multi-key, untyped-value API. CE-kit ships and tests
`createChromeStorageAdapter()`, which wraps `chrome.storage.local` (or any object matching its
promise-based `get`/`set`/`remove` shape) into this contract, so extensions can pass
`chrome.storage.local` straight in without writing their own adapter. The adapter only depends on
the `ChromeStorageArea` structural type CE-kit declares itself, not `@types/chrome`, so the
dependency stays optional. Everything else (including tests) can use the bundled in-memory
implementation.

This is a deliberate reading of "compatible with `chrome.storage.local`": `AsyncStorage` itself is
*not* structurally assignable to `chrome.storage.local` (it's single-key/typed-value where Chrome's
API is multi-key/untyped-value) -- compatibility is provided via the adapter, not by widening the
contract to match Chrome's own shape. Widening `AsyncStorage` itself would force every non-Chrome
caller (tests, web frontends, the in-memory implementation) to deal with a multi-key, untyped-value
API for no benefit to them. If a future ticket needs direct structural assignability instead, that's
a breaking change to `AsyncStorage`, not an extension of this adapter.

```ts
import { createChromeStorageAdapter, createInMemoryAsyncStorage } from "@anytoolai/ce-kit";

const storage = createInMemoryAsyncStorage(); // for tests / non-extension hosts
const chromeStorage = createChromeStorageAdapter(chrome.storage.local); // inside an extension
```

## Guest identity

`client.createGuestIdentity({ storage, storageKey? })` reuses a persisted guest id if one exists,
and otherwise requests a new one and persists it. It's owned by `PlatformApiClient` (not a free
function) so single-flight dedup can be scoped to the client instance itself: concurrent calls on
one client make at most one backend request, regardless of which `storageKey` each call passes.
Every successful caller persists the (shared) result to its own `storage`/`storageKey`, not just
whichever call happened to trigger the backend request.

```ts
const result = await client.createGuestIdentity({ storage });
if (result.ok) {
  const { guestId } = result.value;
}
```

Like `getRuntimeConfig()` below, this returns a result object (`{ ok: true, value }` or
`{ ok: false, error }`) rather than throwing, so callers can distinguish backend, network, timeout,
cancellation, and malformed-response failures through the same stable `PlatformApiError` union
everywhere else in CE-kit.

A rejected `storage.get()` (e.g. a Chrome storage read failure) is treated as a cache miss, not
surfaced as a thrown exception -- `createGuestIdentity()` falls through to requesting a new guest
id from the backend exactly as it would if nothing were cached. As with the persist-side
`storage.set()` failure already documented above, guest creation still returns its documented
`GuestIdentityResult`.

Persisting the fresh id from that fallback request re-reads `storage`/`storageKey` immediately
before writing, regardless of whether the *initial* read above failed or genuinely missed --
skipping persistence just because the first read errored would risk losing the id forever on a
transient failure, forcing every later call to create (and pay quota for) a new one. If that second
read already finds a value there, the write is skipped and *that* cached value is returned instead
of this call's own freshly-fetched id -- another concurrent call already has the real cached value,
so persisting or returning this call's different id would split guest-based quota across two ids.
The write is otherwise skipped only if the second read/write itself fails, in which case this call's
own fetched id is returned unpersisted (still valid and usable, just not cached).

This second read narrows the race but does not eliminate it: `AsyncStorage`'s `get` and `set` are
separate, non-atomic calls, so two concurrent callers can both perform their re-read, both observe
nothing cached, and both then `set()` a different guest id -- the last write wins and silently
orphans the other caller's id on the backend. Closing this fully would need an atomic
set-if-absent/compare-and-set primitive on `AsyncStorage`, which none of the current adapters
provide.

## Runtime config

`getRuntimeConfig(client, productId)` is the first real safe `GET` on the client. Unlike guest
identity, it returns a `PlatformApiResult<RuntimeConfig>` directly, since callers plausibly want to
distinguish an unknown product (`backend_error` with `code: "product_not_found"`) from a network or
timeout failure:

```ts
import { getRuntimeConfig } from "@anytoolai/ce-kit";

const result = await getRuntimeConfig(client, "kernel_demo");
if (result.ok) {
  const { scenarios, quotaSummary, allowedUiCapabilities } = result.value;
}
```

## Quota

`getQuota(client, { productId, guestId, scenarioId? })` reads backend-owned guest quota state.
`scenarioId` is only needed for scenario-dimension quota policies; product-dimension queries omit
it. Quota is never enforced client-side -- this is read-only visibility into state the backend
already checks on scenario start.

```ts
import { getQuota } from "@anytoolai/ce-kit";

const result = await getQuota(client, { productId: "kernel_demo", guestId });
if (result.ok) {
  const { usedCount, remainingCount, exhausted } = result.value;
}
```

## Scenario start and idempotent retry (ANY-150)

`prepareScenarioStart(request)` returns an opaque, retryable handle: it generates one
`Idempotency-Key` when prepared, and every `.execute(client)` call on that same handle -- including
an explicit retry of an ambiguous failure -- reuses that key, so the backend collapses duplicate
submits into the original session/job instead of double-charging quota. A genuinely new submission
means calling `prepareScenarioStart()` again for a fresh key. Callers never see or manage the key or
its header directly.

```ts
import { prepareScenarioStart } from "@anytoolai/ce-kit";

const prepared = prepareScenarioStart({
  productId: "kernel_demo",
  scenarioId: "kernel_demo.single_action_smoke_v1",
  frontendId: "kernel_demo_ce",
  input: { text: "hello" },
  guestId,
});

let result = await prepared.execute(client);
if (
  !result.ok &&
  (result.error.type === "network_error" ||
    result.error.type === "timeout" ||
    (result.error.type === "invalid_response" && result.error.status >= 200 && result.error.status < 300))
) {
  // Genuinely ambiguous outcomes only -- explicit retry, same Idempotency-Key. A 2xx
  // invalid_response means the backend already created the session and consumed quota but
  // returned an unparseable body, so the caller still lacks the session/job IDs -- that is
  // ambiguous too, and retrying with the same key is the recovery path (the backend returns the
  // existing session/job instead of creating a new one). `aborted` means the caller's own signal
  // fired, so retrying would defeat that cancellation; `backend_error` and a non-2xx
  // `invalid_response` are not retried here either, since the backend already answered with an
  // error it isn't expected to reconsider on a same-key resubmit.
  result = await prepared.execute(client);
}
```

`startScenario(client, request)` is a one-shot convenience wrapper -- `prepareScenarioStart(request).execute(client)`
-- for callers that don't need to retry:

```ts
import { startScenario } from "@anytoolai/ce-kit";

const result = await startScenario(client, {
  productId: "kernel_demo",
  scenarioId: "kernel_demo.single_action_smoke_v1",
  frontendId: "kernel_demo_ce",
  input: { text: "hello" },
  guestId,
});
```

Both surface `404` (unknown scenario/guest), `409 idempotency_key_conflict` (retry with a new key
or the original request), `422` (invalid input/guest requirement), and `429 quota_exhausted` (no
session/job/quota state is created in CE-kit on this path) through the standard `PlatformApiResult`.

## Scenario session and polling

`getScenarioSession(client, scenarioSessionId, { signal?, timeoutMs? })` is a single typed
`GET /v1/scenario-sessions/{id}` read.

`pollScenarioSession(client, scenarioSessionId, { intervalMs?, maxDurationMs?, signal? })` polls it
on a bounded interval and stops on `completed`, `failed`, `expired`, or `waiting_for_user` (the last
one stops polling too, since only `nextAction()` can move it forward -- continuing to poll would
just idle until `maxDurationMs`), on a backend error, on cancellation, or once `maxDurationMs`
elapses. It never starts, replays, or configures workflow/LLM execution -- it only reads
backend-owned session state.

Any individual request's own timeout also stops the whole poll immediately (reported as
`reason: "timeout"`), even if it fires well before `maxDurationMs` would have elapsed -- e.g. with
the defaults, a slow `GET` can time out at the client's 10s `timeoutMs` while `maxDurationMs` still
has ~50s left. `maxDurationMs` is an upper bound on total poll duration, not a per-request retry
budget; this is intentional fail-fast behavior, not a bug.

```ts
import { pollScenarioSession } from "@anytoolai/ce-kit";

const controller = new AbortController();
const outcome = await pollScenarioSession(client, scenarioSessionId, {
  intervalMs: 2_000,
  maxDurationMs: 60_000,
  signal: controller.signal, // e.g. tied to a popup closing
});

switch (outcome.reason) {
  case "session_status": // outcome.result.value.status is a stop status
  case "error": // outcome.result is the backend_error/invalid_response that stopped polling
  case "timeout": // maxDurationMs elapsed, or a single poll ran into the deadline and had to be
                  // cut short; outcome.result is the last successful read if one happened before
                  // the deadline, otherwise a failed (timeout-type) result
  case "aborted": // signal fired mid-poll
}
```

## Next action

`nextAction(client, { scenarioSessionId, nextActionId, checkpointId })` sends the checkpoint the
frontend is currently acting on; the backend is authoritative on whether it's stale, returning
`409` if the session moved on. That `409` is a **different** conflict than scenario-start's
`409 idempotency_key_conflict` even though both are HTTP 409 -- see `isScenarioActionConflict()` /
`isIdempotencyKeyConflict()` below.

```ts
import { nextAction } from "@anytoolai/ce-kit";

const result = await nextAction(client, {
  scenarioSessionId,
  nextActionId: "copy_result",
  checkpointId: currentCheckpointId,
});
```

## Classifying backend errors

`isIdempotencyKeyConflict()`, `isScenarioActionConflict()`, and `isQuotaExhausted()` are typed
guards over `PlatformApiError` for the ambiguous cases above -- prefer them over comparing
`error.code` strings directly, since they're the tested, reusable source of truth for which codes
mean what:

```ts
import { isIdempotencyKeyConflict, isQuotaExhausted } from "@anytoolai/ce-kit";

if (!result.ok && isQuotaExhausted(result.error)) {
  // no session/job was created; show the paywall/upsell path
}
```

## API versioning

Paths are not implicitly prefixed by the client -- callers always pass the full path including the
version segment (e.g. `/v1/products/{product_id}/runtime-config`), matching the backend's
path-based versioning (`APIRouter(prefix="/v1/...")`). A future `/v2` endpoint is just a different
path string; it does not require a `PlatformApiClient` change.

## Generated API contracts

`src/api/generated/platformApi.ts` holds TypeScript types generated from the backend's live
OpenAPI schema via [`openapi-typescript`](https://openapi-ts.dev/) -- not hand-maintained DTOs, so
the frontend's view of the contract can't silently drift from the backend or from prod.

`PlatformApiClient` and the hand-written response parsers (`parseGuestIdentityPayload()`,
`parseRuntimeConfig()`) don't consume the generated types directly at runtime -- the backend's
snake_case wire format still needs runtime validation and mapping to CE-kit's camelCase DTOs, which
`openapi-typescript`'s static types alone can't provide. Instead, `src/api/driftAssertions.ts` ties
each parser to the generated schema at the type level via `AssertExactSchemaShape<T, Shape>`: a
hand-maintained `Shape` object type mirroring each backend schema field-for-field (e.g.
`guestIdentity.ts`'s `{ guest_id: string }`, `parseRuntimeConfig.ts`'s per-schema shapes) is
compared against `components["schemas"][...]` by key set *and* by type -- including
optionality/nullability -- in both directions (a key missing from `Shape`, an extra key not on the
backend schema, or a same-key type/nullability/optionality mismatch all fail). A backend change
such as `limit_count: number -> string`, or a field losing its `| null`, fails this assertion even
though the key set is unchanged.

`driftAssertions.ts` also exports `AssertExactSchemaKeys<T, Keys>`, an older, narrower check kept
for reference: it only verifies that a flat list of key names covers every property of `T`, one-way
(it does not fail if `Keys` lists a name `T` doesn't have, since `Keys extends readonly (keyof
T)[]` already rejects that at the type-parameter level, but it also does not catch a same-key type
or nullability change). No parser in this package uses it anymore -- `AssertExactSchemaShape` above
is strictly more precise and is what every parser is actually checked against.

If the backend schema drifts, regenerating `platformApi.ts` makes the relevant assertion fail
typecheck instead of silently leaving the parser's runtime type guards stale. Beyond these drift
assertions, nothing in this package consumes the generated types directly yet --
`PlatformApiClient` and the hand-written response shapes stay as they are; this is the codegen +
drift-check plumbing for future callers to build on.

The pipeline:

1. `python scripts/agent/runner.py generate-docs` renders `docs/generated/openapi.json`, the raw
   schema, from `anytoolai_platform_api.openapi.generate.build_openapi_schema()`
   (`create_app().openapi()`). This file is committed, and `generate-docs --check` (part of
   `quick_check()`, itself part of `full-check`) fails the build if it's stale relative to the
   backend's actual routes/schemas.
2. `pnpm --filter @anytoolai/ce-kit generate-api-types` regenerates
   `src/api/generated/platformApi.ts` from that JSON via `openapi-typescript`.
3. `pnpm --filter @anytoolai/ce-kit generate-api-types:check` regenerates into a temp file and
   byte-compares it against the committed one, instead of overwriting it -- this is what
   `frontend-check` actually runs, so a stale generated file fails CI.

To pick up a backend contract change:

```sh
python scripts/agent/runner.py generate-docs
pnpm --filter @anytoolai/ce-kit generate-api-types
git add docs/generated/openapi.json packages/frontend/ce-kit/src/api/generated/platformApi.ts
```

## Commands

```sh
pnpm --filter @anytoolai/ce-kit test        # vitest
pnpm --filter @anytoolai/ce-kit typecheck   # tsc --noEmit
python scripts/agent/runner.py frontend-check
python scripts/agent/runner.py full-check
```
