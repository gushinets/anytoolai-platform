# @anytoolai/ce-kit

Shared Platform API client foundation for AnytoolAI Chrome Extensions and web frontends.

This package currently covers **A15a — CE Kit API Client Foundation** (ANY-170): the transport
layer, the stable error union, injectable storage, guest identity, and runtime config. It does
**not** yet cover quota, scenario start, or polling (A15b / ANY-171) — `getQuota()` and
`startScenario()` are still demo stubs, and several other exports (`pollJob`, `getScenarioSession`,
`getArtifact`, `createHandoff`, `openHandoffConsent`, `captureEmail`, `trackClientEvent`, the
`render*` helpers) are fake-success placeholders deferred to later tickets. Do not treat their
presence in `src/index.ts` as a working contract.

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

If the read fails, the fresh id from that fallback request is *not* persisted back to
`storage`/`storageKey`, unlike the ordinary cache-miss path. A failed read is indistinguishable
from "another concurrent call already has the real cached value and is about to return it without
persisting anything new" -- persisting anyway risks overwriting that already-in-use cached id with
a different one from the same backend response. The returned identity is still valid and usable by
the caller; only the write-back is skipped.

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
