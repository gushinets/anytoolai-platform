// Platform API response builders and route keys shared by the web product runtime suites.
// Reuses ce-kit's routed-fetch test util for the common case; `makeClientWithDeferredRoute` is
// the one addition (see its docstring).
import { PlatformApiClient } from "@anytoolai/ce-kit";
import { makeRoutedFetchClient } from "@anytoolai/ce-kit/test/testUtils/routedFetchClient";
import { vi } from "vitest";

export type ProductIds = { productId: string; scenarioId: string };

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function errorResponse(status: number, code: string, message = "x"): Response {
  return jsonResponse(status, { error: { code, message, request_id: "req_1" } });
}

export function guestIdentityResponse(guestId = "guest_1"): Response {
  return jsonResponse(200, { guest_id: guestId });
}

export function runtimeConfigResponse(ids: ProductIds, overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    product_id: ids.productId,
    frontend_ids: ["web_mirror"],
    frontends: [{ frontend_id: "web_mirror", type: "web", enabled: true }],
    scenario_ids: [ids.scenarioId],
    scenarios: [
      {
        scenario_id: ids.scenarioId,
        version: 1,
        allowed_next_actions: ["copy_result"],
        input_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.input_v1`, schema_version: 1 },
        output_renderer_hint: { renderer: "json_schema", schema_ref: `${ids.productId}.output_v1`, schema_version: 1 },
      },
    ],
    quota_summary: null,
    allowed_ui_capabilities: [],
    ...overrides,
  });
}

export function quotaResponse(ids: ProductIds, overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    guest_id: "guest_1",
    product_id: ids.productId,
    quota_policy_id: `${ids.productId}.guest_quota_v1`,
    quota_dimension: "product",
    dimension_key: ids.productId,
    scenario_id: null,
    unit: "scenario_run",
    period: "lifetime",
    limit_count: 3,
    used_count: 0,
    remaining_count: 3,
    exhausted: false,
    ...overrides,
  });
}

export function startResponse(overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    scenario_session_id: "session_1",
    job_id: "job_1",
    status: "started",
    allowed_next_actions: [],
    result_artifact_id: null,
    ...overrides,
  });
}

export function sessionResponse(overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    scenario_session_id: "session_1",
    job_id: "job_1",
    status: "completed",
    allowed_next_actions: ["copy_result"],
    result_artifact_id: "result_1",
    current_checkpoint_id: "checkpoint_1",
    ...overrides,
  });
}

export const RESULT_TEXT = "Generated result text.";

export function resultResponse(ids: ProductIds, overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    result_artifact_id: "result_1",
    scenario_session_id: "session_1",
    job_id: "job_1",
    workflow_id: ids.scenarioId,
    workflow_version: 1,
    schema_ref: `${ids.productId}.output_v1`,
    schema_version: 1,
    created_at: "2026-09-10T00:00:00Z",
    output: { text: RESULT_TEXT },
    ...overrides,
  });
}

export function routesFor(ids: ProductIds) {
  return {
    GUEST_IDENTITY: "POST /v1/identity/guest",
    RUNTIME_CONFIG: `GET /v1/products/${ids.productId}/runtime-config`,
    QUOTA: `GET /v1/products/${ids.productId}/quota`,
    START: `POST /v1/products/${ids.productId}/scenarios/${ids.scenarioId}/start`,
    SESSION: "GET /v1/scenario-sessions/session_1",
    RESULT: "GET /v1/results/result_1",
    NEXT_ACTION: "POST /v1/scenario-sessions/session_1/next-actions/copy_result",
  } as const;
}

export type RouteQueues = Record<string, Array<Response | (() => Response)>>;

export function makeClient(routes: RouteQueues) {
  return makeRoutedFetchClient("https://api.example.com", routes);
}

export type CapturedCall = { key: string; url: string; init: RequestInit };

/** Shared by makeClientWithDeferredRoute()/makeClientCapturingRequests(): dispatches by (method,
 * path) from `routes`' FIFO queues, recording every call (including its full URL, e.g. for
 * asserting on query-string parameters) as it goes. */
function fetchImplFor(
  routes: RouteQueues,
  calls: CapturedCall[],
  onCall?: (key: string) => Response | Promise<Response> | undefined,
) {
  const queues = new Map(Object.entries(routes).map(([key, responses]) => [key, [...responses]]));
  return vi.fn(async (url: string, init: RequestInit) => {
    const key = `${init.method ?? "GET"} ${new URL(url).pathname}`;
    calls.push({ key, url, init });
    const overridden = onCall?.(key);
    if (overridden !== undefined) {
      return overridden;
    }
    const queue = queues.get(key);
    if (!queue || queue.length === 0) {
      throw new Error(`No mock response queued for ${key}`);
    }
    const next = queue.shift();
    return typeof next === "function" ? next() : (next as Response);
  });
}

/**
 * Like makeClient(), but `deferredRouteKey`'s response is a promise this function returns control
 * of via `resolveDeferred`, instead of being queued up front -- for tests that need one specific
 * request to settle *after* other, later requests/UI interactions have already happened.
 */
export function makeClientWithDeferredRoute(routes: RouteQueues, deferredRouteKey: string) {
  const calls: CapturedCall[] = [];
  let resolveDeferred!: (response: Response) => void;
  const deferredResponse = new Promise<Response>((resolve) => {
    resolveDeferred = resolve;
  });
  const fetchImpl = fetchImplFor(routes, calls, (key) => (key === deferredRouteKey ? deferredResponse : undefined));
  const client = new PlatformApiClient({
    baseUrl: "https://api.example.com",
    fetchImpl: fetchImpl as unknown as typeof fetch,
  });
  return { client, calls, resolveDeferred };
}

/**
 * Like makeClientWithDeferredRoute(), but `deferredRouteKey` gets its own independent, separately
 * resolvable promise for each of its first `callCount` calls -- for tests proving an out-of-order
 * response race (e.g. a second, slower call's later failure must not clobber a first call's
 * already-applied earlier success). `resolveCall(0, ...)` resolves the first call to that route,
 * `resolveCall(1, ...)` the second, and so on.
 */
export function makeClientWithDeferredCalls(routes: RouteQueues, deferredRouteKey: string, callCount: number) {
  const calls: CapturedCall[] = [];
  const resolvers: Array<(response: Response) => void> = [];
  const deferredResponses: Promise<Response>[] = [];
  for (let index = 0; index < callCount; index += 1) {
    let resolve!: (response: Response) => void;
    deferredResponses.push(new Promise<Response>((res) => (resolve = res)));
    resolvers.push(resolve);
  }
  let callIndex = 0;
  const fetchImpl = fetchImplFor(routes, calls, (key) => {
    if (key !== deferredRouteKey) {
      return undefined;
    }
    const promise = deferredResponses[callIndex];
    callIndex += 1;
    return promise;
  });
  const client = new PlatformApiClient({
    baseUrl: "https://api.example.com",
    fetchImpl: fetchImpl as unknown as typeof fetch,
  });
  return {
    client,
    calls,
    resolveCall: (index: number, response: Response) => {
      resolvers[index]!(response);
    },
  };
}

/** Like makeClient(), but each call is recorded with its full URL -- for asserting on
 * query-string parameters (e.g. that a request includes `scenario_id`). */
export function makeClientCapturingRequests(routes: RouteQueues) {
  const calls: CapturedCall[] = [];
  const fetchImpl = fetchImplFor(routes, calls);
  const client = new PlatformApiClient({
    baseUrl: "https://api.example.com",
    fetchImpl: fetchImpl as unknown as typeof fetch,
  });
  return { client, calls };
}

export function idempotencyKeyOf(call: { init: RequestInit }): string | null {
  return (call.init.headers as Headers).get("Idempotency-Key");
}
