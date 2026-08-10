import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { getResult } from "../../src/results/getResult";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const RESULT_PAYLOAD = {
  result_artifact_id: "artifact_123",
  scenario_session_id: "scenario_session_123",
  job_id: "job_123",
  workflow_id: "kernel_demo.single_action_extract_v1",
  workflow_version: 1,
  schema_ref: "kernel_demo.extract_output_v1",
  schema_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  output: { title: "Example", fields: ["one", "two"] },
};

describe("getResult", () => {
  it("requests the artifact by id and maps it to camelCase", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, RESULT_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getResult(client, "artifact_123");

    expect(result).toEqual({
      ok: true,
      value: {
        resultArtifactId: "artifact_123",
        scenarioSessionId: "scenario_session_123",
        jobId: "job_123",
        workflowId: "kernel_demo.single_action_extract_v1",
        workflowVersion: 1,
        schemaRef: "kernel_demo.extract_output_v1",
        schemaVersion: 1,
        createdAt: "2026-01-01T00:00:00Z",
        output: { title: "Example", fields: ["one", "two"] },
      },
      status: 200,
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/results/artifact_123",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("percent-encodes the result artifact id in the URL", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, RESULT_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await getResult(client, "artifact with spaces");

    const [url] = fetchImpl.mock.calls[0] as unknown as [string];
    expect(url).toBe("https://api.example.com/v1/results/artifact%20with%20spaces");
  });

  it("returns a backend_error result with result_artifact_not_found for an unknown id", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: {
          code: "result_artifact_not_found",
          message: "Result artifact not found.",
          request_id: "req_1",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getResult(client, "unknown_artifact");

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 404,
        code: "result_artifact_not_found",
        message: "Result artifact not found.",
        requestId: "req_1",
      },
    });
  });

  it("returns a backend_error result with result_artifact_unavailable for a non-canonical artifact", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: {
          code: "result_artifact_unavailable",
          message: "Result artifact is not available.",
          request_id: "req_2",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getResult(client, "artifact_123");

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 404,
        code: "result_artifact_unavailable",
        message: "Result artifact is not available.",
        requestId: "req_2",
      },
    });
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { result_artifact_id: "artifact_123" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getResult(client, "artifact_123");

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Result artifact response was invalid.",
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
      return jsonResponse(200, RESULT_PAYLOAD);
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getResult(client, "artifact_123", { signal: controller.signal });

    expect(result).toEqual({ ok: false, error: { type: "aborted" } });
  });
});
