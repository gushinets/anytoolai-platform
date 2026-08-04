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
if (!result.ok && result.error.type !== "backend_error") {
  // Ambiguous failure (network_error/timeout/aborted) -- explicit retry, same Idempotency-Key.
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
  case "timeout": // maxDurationMs elapsed; outcome.result is the last successful read
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
