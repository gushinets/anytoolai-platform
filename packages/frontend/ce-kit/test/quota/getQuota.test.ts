import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { getQuota } from "../../src/quota/getQuota";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const QUOTA_PAYLOAD = {
  guest_id: "guest_123",
  product_id: "kernel_demo",
  quota_policy_id: "kernel_demo.guest_quota_v1",
  quota_dimension: "product",
  dimension_key: "kernel_demo",
  scenario_id: null,
  unit: "scenario_run",
  period: "lifetime",
  limit_count: 3,
  used_count: 1,
  remaining_count: 2,
  exhausted: false,
};

describe("getQuota", () => {
  it("requests product-dimension quota and maps it to camelCase", async () => {
    const fetchImpl = vi.fn(
      async (_input: RequestInfo | URL) => jsonResponse(200, QUOTA_PAYLOAD),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getQuota(client, { productId: "kernel_demo", guestId: "guest_123" });

    expect(result).toEqual({
      ok: true,
      value: {
        guestId: "guest_123",
        productId: "kernel_demo",
        quotaPolicyId: "kernel_demo.guest_quota_v1",
        quotaDimension: "product",
        dimensionKey: "kernel_demo",
        scenarioId: null,
        unit: "scenario_run",
        period: "lifetime",
        limitCount: 3,
        usedCount: 1,
        remainingCount: 2,
        exhausted: false,
      },
      status: 200,
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/products/kernel_demo/quota?guest_id=guest_123",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("includes scenario_id for scenario-dimension quota requests", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, {
        ...QUOTA_PAYLOAD,
        quota_dimension: "scenario",
        scenario_id: "kernel_demo.single_action_smoke_v1",
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getQuota(client, {
      productId: "kernel_demo",
      guestId: "guest_123",
      scenarioId: "kernel_demo.single_action_smoke_v1",
    });

    expect(result.ok).toBe(true);
    expect(result.ok && result.value.scenarioId).toBe("kernel_demo.single_action_smoke_v1");
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/products/kernel_demo/quota?guest_id=guest_123&scenario_id=kernel_demo.single_action_smoke_v1",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("does not require scenario_id for product-dimension requests", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, QUOTA_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await getQuota(client, { productId: "kernel_demo", guestId: "guest_123" });

    const [url] = fetchImpl.mock.calls[0] as unknown as [string];
    expect(url).not.toContain("scenario_id");
  });

  it("includes an explicit empty-string scenario_id, rather than silently dropping it", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, QUOTA_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await getQuota(client, { productId: "kernel_demo", guestId: "guest_123", scenarioId: "" });

    const [url] = fetchImpl.mock.calls[0] as unknown as [string];
    expect(url).toContain("scenario_id=");
  });

  it("percent-encodes the product id and guest id in the URL", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, QUOTA_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await getQuota(client, { productId: "kernel demo", guestId: "guest 123" });

    const [url] = fetchImpl.mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "https://api.example.com/v1/products/kernel%20demo/quota?guest_id=guest+123",
    );
  });

  it("returns a backend_error result for an unknown guest identity", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: { code: "guest_identity_not_found", message: "Guest not found", request_id: "req_1" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getQuota(client, { productId: "kernel_demo", guestId: "unknown_guest" });

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 404,
        code: "guest_identity_not_found",
        message: "Guest not found",
        requestId: "req_1",
      },
    });
  });

  it("returns a backend_error result with quota_exhausted for 429", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(429, {
        error: { code: "quota_exhausted", message: "Quota exhausted", request_id: "req_2" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getQuota(client, { productId: "kernel_demo", guestId: "guest_123" });

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 429,
        code: "quota_exhausted",
        message: "Quota exhausted",
        requestId: "req_2",
      },
    });
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_123" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getQuota(client, { productId: "kernel_demo", guestId: "guest_123" });

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Quota response was invalid.",
      },
    });
  });

  it("reports the response's real status in invalid_response, not a hardcoded 200", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(202, { guest_id: "guest_123" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getQuota(client, { productId: "kernel_demo", guestId: "guest_123" });

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 202,
        message: "Quota response was invalid.",
      },
    });
  });
});
