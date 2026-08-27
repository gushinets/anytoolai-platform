import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { isHandoffNotFound } from "../../src/api/errors";
import { getHandoff } from "../../src/handoffs/getHandoff";
import { handoffPreviewPayload } from "./fixtures";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const PREVIEW_PAYLOAD = handoffPreviewPayload({ status: "viewed" });

describe("getHandoff", () => {
  it("fetches /v1/handoffs/{token} and maps the response to camelCase", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PREVIEW_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getHandoff(client, "token_abc");

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/handoffs/token_abc",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result).toEqual({
      ok: true,
      value: {
        handoffId: "handoff_123",
        status: "viewed",
        sourceProductId: "kernel_demo",
        sourceProductDisplayName: "Kernel Demo",
        targetProductId: "freelancer_demo",
        targetProductDisplayName: "Freelancer Demo",
        targetScenarioId: "scenario_1",
        preview: { key: "value" },
        expiresAt: "2026-01-01T00:10:00Z",
        targetScenarioSessionId: null,
        targetJobId: null,
      },
      status: 200,
    });
  });

  it("percent-encodes the token as an opaque path segment", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PREVIEW_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await getHandoff(client, "token/with special chars");

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/handoffs/token%2Fwith%20special%20chars",
      expect.anything(),
    );
  });

  it("returns the terminal status as-is instead of rejecting (e.g. consumed)", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { ...PREVIEW_PAYLOAD, status: "consumed" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getHandoff(client, "token_abc");

    expect(result.ok && result.value.status).toBe("consumed");
  });

  it("returns a backend_error result with handoff_not_found for an unknown token", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: { code: "handoff_not_found", message: "Handoff not found.", request_id: "req_1" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getHandoff(client, "token_abc");

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffNotFound(result.error)).toBe(true);
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { handoff_id: "handoff_123" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getHandoff(client, "token_abc");

    expect(result).toEqual({
      ok: false,
      error: { type: "invalid_response", status: 200, message: "Handoff preview response was invalid." },
    });
  });
});
