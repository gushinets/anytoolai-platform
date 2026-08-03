import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

describe("PlatformApiClient", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("joins base URL and path without double slashes", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { ok: true }));
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com/", fetchImpl });

    await client.request({ path: "/v1/products/demo/runtime-config" });

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/products/demo/runtime-config",
      expect.anything(),
    );
  });

  it("sends standard headers plus an optional X-Request-ID", async () => {
    const fetchImpl = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse(200, {}),
    );
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    await client.request({ path: "/v1/x", requestId: "req_abc" });

    const [, init] = fetchImpl.mock.calls[0];
    const headers = init?.headers as Headers;
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("X-Request-ID")).toBe("req_abc");
  });

  it("parses a successful JSON response", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { product_id: "demo" }));
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    const result = await client.request<{ product_id: string }>({ path: "/v1/x" });

    expect(result).toEqual({ ok: true, value: { product_id: "demo" }, status: 200 });
  });

  it("returns a backend_error for a well-formed error envelope", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: { code: "product_not_found", message: "Product not found", request_id: "req_1" },
      }),
    );
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    const result = await client.request({ path: "/v1/x" });

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 404,
        code: "product_not_found",
        message: "Product not found",
        requestId: "req_1",
      },
    });
  });

  it("returns invalid_response for malformed JSON", async () => {
    const fetchImpl = vi.fn(
      async () =>
        new Response("not json{{", { status: 200, headers: { "Content-Type": "application/json" } }),
    );
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    const result = await client.request({ path: "/v1/x" });

    expect(result).toEqual({
      ok: false,
      error: { type: "invalid_response", status: 200, message: "Response body was not valid JSON." },
    });
  });

  it("returns invalid_response when a non-ok response has no parseable error envelope", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(500, { detail: "boom" }));
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    const result = await client.request({ path: "/v1/x" });

    expect(result).toEqual({
      ok: false,
      error: { type: "invalid_response", status: 500, message: "Response could not be parsed." },
    });
  });

  it("returns network_error when fetch rejects", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    const result = await client.request({ path: "/v1/x" });

    expect(result).toEqual({ ok: false, error: { type: "network_error", message: "Failed to fetch" } });
  });

  it("times out and reports a timeout error", async () => {
    const fetchImpl = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }),
    );
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl, timeoutMs: 50 });

    const pending = client.request({ path: "/v1/x" });
    await vi.advanceTimersByTimeAsync(50);

    await expect(pending).resolves.toEqual({ ok: false, error: { type: "timeout" } });
  });

  it("reports aborted when the caller cancels via its own signal", async () => {
    const fetchImpl = vi.fn(
      (_url: RequestInfo | URL, init?: RequestInit) =>
        new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
        }),
    );
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl, timeoutMs: 10_000 });
    const controller = new AbortController();

    const pending = client.request({ path: "/v1/x", signal: controller.signal });
    controller.abort();

    await expect(pending).resolves.toEqual({ ok: false, error: { type: "aborted" } });
  });

  it("retries a safe GET request on network_error up to the configured attempts", async () => {
    const fetchImpl = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    const result = await client.request({ path: "/v1/x", retry: { attempts: 2 } });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(result).toEqual({ ok: true, value: { ok: true }, status: 200 });
  });

  it("does not retry backend_error even when a retry policy is set", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, { error: { code: "not_found", message: "nope", request_id: "r" } }),
    );
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    await client.request({ path: "/v1/x", retry: { attempts: 3 } });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("throws synchronously if retry is requested for an unsafe (POST) request", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    await expect(
      client.request({ path: "/v1/x", method: "POST", retry: { attempts: 2 } }),
    ).rejects.toThrow(/retry is only supported for safe GET/);
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("never retries a plain POST request, even on a transient network error", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });

    await client.request({ path: "/v1/x", method: "POST", body: { a: 1 } });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
