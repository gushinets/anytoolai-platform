import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { isIdempotencyKeyConflict, isQuotaExhausted } from "../../src/api/errors";
import { prepareScenarioStart } from "../../src/scenarios/prepareScenarioStart";
import type { ScenarioStartRequest } from "../../src/scenarios/types";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const START_REQUEST: ScenarioStartRequest = {
  productId: "kernel_demo",
  scenarioId: "kernel_demo.single_action_smoke_v1",
  frontendId: "kernel_demo_ce",
  input: { text: "hello" },
  guestId: "guest_123",
};

const START_PAYLOAD = {
  scenario_session_id: "scenario_session_123",
  job_id: "job_123",
  status: "started",
  allowed_next_actions: [],
  result_artifact_id: null,
};

function idempotencyHeader(call: unknown[]): string | null {
  const init = call[1] as RequestInit;
  return new Headers(init.headers).get("Idempotency-Key");
}

function parsedBody(call: unknown[]): unknown {
  const init = call[1] as RequestInit;
  return JSON.parse(init.body as string) as unknown;
}

describe("prepareScenarioStart", () => {
  it("sends the same Idempotency-Key on every execute() of one prepared operation", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, START_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    const prepared = prepareScenarioStart(START_REQUEST);

    await prepared.execute(client);
    await prepared.execute(client);

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    const [firstKey, secondKey] = fetchImpl.mock.calls.map((call) => idempotencyHeader(call));
    expect(firstKey).toBeTruthy();
    expect(firstKey).toBe(secondKey);
  });

  it("keeps every execute() call on the same identical payload even if the caller mutates the request afterward", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, START_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    const mutableRequest: ScenarioStartRequest = {
      productId: "kernel_demo",
      scenarioId: "kernel_demo.single_action_smoke_v1",
      frontendId: "kernel_demo_ce",
      input: { text: "hello" },
      guestId: "guest_123",
    };
    const prepared = prepareScenarioStart(mutableRequest);

    await prepared.execute(client);
    // Simulates a caller reusing a form-bound request object across a retry: this must not
    // change what the retry sends, since it reuses the same Idempotency-Key as the original.
    mutableRequest.guestId = "guest_456";
    (mutableRequest.input as { text: string }).text = "mutated";
    await prepared.execute(client);

    const [firstBody, secondBody] = fetchImpl.mock.calls.map((call) => parsedBody(call));
    expect(secondBody).toEqual(firstBody);
    expect(firstBody).toMatchObject({ guest_id: "guest_123", input: { text: "hello" } });
  });

  it("gives a separate prepared operation a different Idempotency-Key", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, START_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await prepareScenarioStart(START_REQUEST).execute(client);
    await prepareScenarioStart(START_REQUEST).execute(client);

    const [firstKey, secondKey] = fetchImpl.mock.calls.map((call) => idempotencyHeader(call));
    expect(firstKey).not.toBe(secondKey);
  });

  it("posts to the scenario start endpoint with the mapped snake_case body", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, START_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await prepareScenarioStart(START_REQUEST).execute(client);

    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(
      "https://api.example.com/v1/products/kernel_demo/scenarios/kernel_demo.single_action_smoke_v1/start",
    );
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      frontend_id: "kernel_demo_ce",
      input: { text: "hello" },
      guest_id: "guest_123",
      user_id: null,
      source_frontend_instance_id: null,
    });
  });

  it("maps a successful start response to camelCase", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, START_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await prepareScenarioStart(START_REQUEST).execute(client);

    expect(result).toEqual({
      ok: true,
      value: {
        scenarioSessionId: "scenario_session_123",
        jobId: "job_123",
        status: "started",
        allowedNextActions: [],
        resultArtifactId: null,
      },
      status: 200,
    });
  });

  it("distinguishes idempotency_key_conflict from a checkpoint conflict via the error code", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: {
          code: "idempotency_key_conflict",
          message: "Idempotency-Key was already used with a different request.",
          request_id: "req_1",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await prepareScenarioStart(START_REQUEST).execute(client);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 409,
        code: "idempotency_key_conflict",
        message: "Idempotency-Key was already used with a different request.",
        requestId: "req_1",
      },
    });
    expect(!result.ok && isIdempotencyKeyConflict(result.error)).toBe(true);
  });

  it("surfaces 429 quota_exhausted without producing a session/job", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(429, {
        error: { code: "quota_exhausted", message: "Guest quota exhausted.", request_id: "req_2" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await prepareScenarioStart(START_REQUEST).execute(client);

    expect(result.ok).toBe(false);
    expect(!result.ok && isQuotaExhausted(result.error)).toBe(true);
  });

  it("surfaces 422 validation errors", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(422, {
        error: {
          code: "scenario_input_invalid",
          message: "Scenario input must be a JSON object.",
          request_id: "req_3",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await prepareScenarioStart(START_REQUEST).execute(client);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 422,
        code: "scenario_input_invalid",
        message: "Scenario input must be a JSON object.",
        requestId: "req_3",
      },
    });
  });

  it("returns invalid_response for a malformed 200 payload", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { scenario_session_id: "s1" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await prepareScenarioStart(START_REQUEST).execute(client);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Scenario start response was invalid.",
      },
    });
  });

  it("passes an execute-scoped AbortSignal through to the request", async () => {
    const controller = new AbortController();
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.signal?.aborted).toBe(false);
      return jsonResponse(200, START_PAYLOAD);
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await prepareScenarioStart(START_REQUEST).execute(client, { signal: controller.signal });

    expect(fetchImpl).toHaveBeenCalled();
  });
});
