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
`chrome.storage.local`'s own multi-key, untyped-value API, so extensions provide a thin per-key
adapter over `chrome.storage.local` rather than passing it in directly. That adapter is what
depends on `chrome.storage.local`, not this contract, so CE-kit itself needs no `@types/chrome`
dependency. Everything else (including tests) can use the bundled in-memory implementation.

```ts
import { createInMemoryAsyncStorage } from "@anytoolai/ce-kit";

const storage = createInMemoryAsyncStorage(); // or your own AsyncStorage-shaped adapter
```

## Guest identity

`createGuestIdentity({ client, storage, storageKey? })` reuses a persisted guest id if one exists,
and otherwise requests a new one and persists it. Concurrent calls sharing the same
`PlatformApiClient` instance are single-flight -- at most one backend request is made no matter how
many callers ask at once.

```ts
import { createGuestIdentity } from "@anytoolai/ce-kit";

const { guestId } = await createGuestIdentity({ client, storage });
```

Unlike `getRuntimeConfig()` below, this throws rather than returning a `PlatformApiResult` -- it's
bootstrap plumbing most callers can't meaningfully proceed without. The thrown `Error`'s message
still names the underlying failure type (e.g. `"Guest identity creation failed: backend_error"`).

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
the frontend's view of the contract can't silently drift from the backend or from prod. Nothing in
this package consumes those generated types yet (`PlatformApiClient` and the hand-written response
shapes above stay as they are); this is the codegen + drift-check plumbing for future callers to
build on.

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
