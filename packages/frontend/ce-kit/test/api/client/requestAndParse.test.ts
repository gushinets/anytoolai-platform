import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../../src/api/client";
import { requestAndParse } from "../../../src/api/client/requestAndParse";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

describe("requestAndParse", () => {
  it("wraps a successfully parsed payload as an ok result", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { name: "kernel_demo" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await requestAndParse<{ name: string }>(
      client,
      { method: "GET", path: "/v1/x" },
      (payload) =>
        typeof payload === "object" && payload !== null && "name" in payload
          ? (payload as { name: string })
          : null,
      "invalid",
    );

    expect(result).toEqual({ ok: true, value: { name: "kernel_demo" }, status: 200 });
  });

  it("passes a non-ok request result through unchanged, without calling parse", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, { error: { code: "not_found", message: "x", request_id: "req_1" } }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    const parse = vi.fn(() => ({}));

    const result = await requestAndParse(client, { method: "GET", path: "/v1/x" }, parse, "invalid");

    expect(result).toEqual({
      ok: false,
      error: { type: "backend_error", status: 404, code: "not_found", message: "x", requestId: "req_1" },
    });
    expect(parse).not.toHaveBeenCalled();
  });

  it("falls back to invalid_response with the caller's message when parse returns null", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(202, { unexpected: true }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await requestAndParse(
      client,
      { method: "GET", path: "/v1/x" },
      () => null,
      "That payload was not the expected shape.",
    );

    expect(result).toEqual({
      ok: false,
      error: { type: "invalid_response", status: 202, message: "That payload was not the expected shape." },
    });
  });

  it("treats a valid falsy parsed value (false, 0, empty string) as ok, not invalid_response", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { exhausted: false }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await requestAndParse<boolean>(
      client,
      { method: "GET", path: "/v1/x" },
      (payload) =>
        typeof payload === "object" && payload !== null && "exhausted" in payload
          ? Boolean((payload as { exhausted: unknown }).exhausted)
          : null,
      "invalid",
    );

    expect(result).toEqual({ ok: true, value: false, status: 200 });
  });
});
