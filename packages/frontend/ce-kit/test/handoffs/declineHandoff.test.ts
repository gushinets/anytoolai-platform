import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { isHandoffExpired, isHandoffNotActionable } from "../../src/api/errors";
import { declineHandoff } from "../../src/handoffs/declineHandoff";
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

const PREVIEW_PAYLOAD = handoffPreviewPayload({ status: "declined" });

describe("declineHandoff", () => {
  it("posts to /v1/handoffs/{token}/decline with no request body", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PREVIEW_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await declineHandoff(client, "token_abc");

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/handoffs/token_abc/decline",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBeUndefined();
    expect(result.ok && result.value.status).toBe("declined");
  });

  it("returns a backend_error result with handoff_expired on 410", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(410, {
        error: { code: "handoff_expired", message: "Handoff has expired.", request_id: "req_1" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await declineHandoff(client, "token_abc");

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffExpired(result.error)).toBe(true);
  });

  it("returns a backend_error result classified as not-actionable when already declined (409)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: { code: "handoff_declined", message: "Handoff has been declined.", request_id: "req_2" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await declineHandoff(client, "token_abc");

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffNotActionable(result.error)).toBe(true);
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { handoff_id: "handoff_123" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await declineHandoff(client, "token_abc");

    expect(result).toEqual({
      ok: false,
      error: { type: "invalid_response", status: 200, message: "Handoff decline response was invalid." },
    });
  });
});
