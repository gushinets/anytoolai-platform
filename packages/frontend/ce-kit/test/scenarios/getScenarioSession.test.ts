import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { getScenarioSession } from "../../src/scenarios/getScenarioSession";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const SESSION_PAYLOAD = {
  scenario_session_id: "scenario_session_123",
  job_id: "job_123",
  status: "completed",
  current_checkpoint_id: "result_ready",
  allowed_next_actions: ["copy_result", "create_handoff"],
  result_artifact_id: "artifact_123",
};

describe("getScenarioSession", () => {
  it("requests the session by id and maps it to camelCase", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getScenarioSession(client, "scenario_session_123");

    expect(result).toEqual({
      ok: true,
      value: {
        scenarioSessionId: "scenario_session_123",
        jobId: "job_123",
        status: "completed",
        currentCheckpointId: "result_ready",
        allowedNextActions: ["copy_result", "create_handoff"],
        resultArtifactId: "artifact_123",
      },
      status: 200,
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/scenario-sessions/scenario_session_123",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("percent-encodes the scenario session id in the URL", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await getScenarioSession(client, "session with spaces");

    const [url] = fetchImpl.mock.calls[0] as unknown as [string];
    expect(url).toBe("https://api.example.com/v1/scenario-sessions/session%20with%20spaces");
  });

  it("passes a null current_checkpoint_id through unchanged", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { ...SESSION_PAYLOAD, current_checkpoint_id: null }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getScenarioSession(client, "scenario_session_123");

    expect(result.ok).toBe(true);
    expect(result.ok && result.value.currentCheckpointId).toBeNull();
  });

  it("returns a backend_error result for an unknown scenario session", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: {
          code: "scenario_session_not_found",
          message: "Scenario session not found.",
          request_id: "req_1",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getScenarioSession(client, "unknown_session");

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 404,
        code: "scenario_session_not_found",
        message: "Scenario session not found.",
        requestId: "req_1",
      },
    });
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { scenario_session_id: "scenario_session_123" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getScenarioSession(client, "scenario_session_123");

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Scenario session response was invalid.",
      },
    });
  });

  it("propagates a caller-supplied AbortSignal", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal?.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      return jsonResponse(200, SESSION_PAYLOAD);
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getScenarioSession(client, "scenario_session_123", {
      signal: controller.signal,
    });

    expect(result).toEqual({ ok: false, error: { type: "aborted" } });
  });
});
