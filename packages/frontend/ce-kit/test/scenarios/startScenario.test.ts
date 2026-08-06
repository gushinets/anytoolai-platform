import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { isIdempotencyKeyConflict } from "../../src/api/errors";
import { startScenario } from "../../src/scenarios/startScenario";
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

describe("startScenario", () => {
  it("sends one Idempotency-Key-bound POST and maps a successful response", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, START_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await startScenario(client, START_REQUEST);

    expect(fetchImpl).toHaveBeenCalledTimes(1);
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

  it("generates a fresh Idempotency-Key for each separate startScenario() call", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, START_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await startScenario(client, START_REQUEST);
    await startScenario(client, START_REQUEST);

    const keys = (fetchImpl.mock.calls as unknown as [string, RequestInit][]).map(
      ([, init]) => new Headers(init.headers).get("Idempotency-Key"),
    );
    expect(keys[0]).toBeTruthy();
    expect(keys[0]).not.toBe(keys[1]);
  });

  it("surfaces 409 idempotency_key_conflict distinctly", async () => {
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

    const result = await startScenario(client, START_REQUEST);

    expect(result.ok).toBe(false);
    expect(!result.ok && isIdempotencyKeyConflict(result.error)).toBe(true);
  });

  it("surfaces 422 validation errors", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(422, {
        error: {
          code: "guest_identity_required",
          message: "Guest identity is required for this product.",
          request_id: "req_2",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await startScenario(client, START_REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 422,
        code: "guest_identity_required",
        message: "Guest identity is required for this product.",
        requestId: "req_2",
      },
    });
  });

  it("surfaces 429 quota_exhausted without a fake session/job", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(429, {
        error: { code: "quota_exhausted", message: "Guest quota exhausted.", request_id: "req_3" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await startScenario(client, START_REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 429,
        code: "quota_exhausted",
        message: "Guest quota exhausted.",
        requestId: "req_3",
      },
    });
  });

  it("surfaces 404 for an unknown scenario", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: { code: "scenario_not_found", message: "Scenario not found.", request_id: "req_4" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await startScenario(client, START_REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 404,
        code: "scenario_not_found",
        message: "Scenario not found.",
        requestId: "req_4",
      },
    });
  });
});
