import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { getRuntimeConfig } from "../../src/runtime/getRuntimeConfig";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const RUNTIME_CONFIG_PAYLOAD = {
  product_id: "kernel_demo",
  frontend_ids: ["kernel_demo_ce"],
  frontends: [{ frontend_id: "kernel_demo_ce", type: "chrome_extension", enabled: true }],
  scenario_ids: ["kernel_demo.single_action_smoke_v1"],
  scenarios: [
    {
      scenario_id: "kernel_demo.single_action_smoke_v1",
      version: 1,
      allowed_next_actions: ["copy_result"],
      input_renderer_hint: {
        renderer: "json_schema",
        schema_ref: "kernel_demo.generic_text_input_v1",
        schema_version: 1,
      },
      output_renderer_hint: {
        renderer: "json_schema",
        schema_ref: "kernel_demo.extract_output_v1",
        schema_version: 1,
      },
    },
  ],
  quota_summary: {
    quota_policy_id: "kernel_demo.guest_quota_v1",
    unit: "scenario_run",
    limit_count: 3,
    period: "lifetime",
    dimension: "product",
  },
  allowed_ui_capabilities: ["copy_result"],
};

describe("getRuntimeConfig", () => {
  it("requests the product's runtime config and maps it to camelCase", async () => {
    const fetchImpl = vi.fn(
      async (_input: RequestInfo | URL) => jsonResponse(200, RUNTIME_CONFIG_PAYLOAD),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getRuntimeConfig(client, "kernel_demo");

    expect(result).toEqual({
      ok: true,
      value: {
        productId: "kernel_demo",
        frontendIds: ["kernel_demo_ce"],
        frontends: [{ frontendId: "kernel_demo_ce", type: "chrome_extension", enabled: true }],
        scenarioIds: ["kernel_demo.single_action_smoke_v1"],
        scenarios: [
          {
            scenarioId: "kernel_demo.single_action_smoke_v1",
            version: 1,
            allowedNextActions: ["copy_result"],
            inputRendererHint: {
              renderer: "json_schema",
              schemaRef: "kernel_demo.generic_text_input_v1",
              schemaVersion: 1,
            },
            outputRendererHint: {
              renderer: "json_schema",
              schemaRef: "kernel_demo.extract_output_v1",
              schemaVersion: 1,
            },
          },
        ],
        quotaSummary: {
          quotaPolicyId: "kernel_demo.guest_quota_v1",
          unit: "scenario_run",
          limitCount: 3,
          period: "lifetime",
          dimension: "product",
        },
        allowedUiCapabilities: ["copy_result"],
      },
      status: 200,
    });
    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/products/kernel_demo/runtime-config",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("passes a null quota summary through unchanged", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { ...RUNTIME_CONFIG_PAYLOAD, quota_summary: null }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getRuntimeConfig(client, "kernel_demo");

    expect(result.ok).toBe(true);
    expect(result.ok && result.value.quotaSummary).toBeNull();
  });

  it("returns a backend_error result for an unknown product", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: { code: "product_not_found", message: "Product not found", request_id: "req_1" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getRuntimeConfig(client, "unknown_product");

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

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { product_id: "kernel_demo" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getRuntimeConfig(client, "kernel_demo");

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Runtime config response was invalid.",
      },
    });
  });

  it("reports the response's real status in invalid_response, not a hardcoded 200", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(202, { product_id: "kernel_demo" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getRuntimeConfig(client, "kernel_demo");

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 202,
        message: "Runtime config response was invalid.",
      },
    });
  });

  it("rejects a payload whose frontend_ids/scenario_ids desync from frontends/scenarios", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, {
        ...RUNTIME_CONFIG_PAYLOAD,
        frontend_ids: ["kernel_demo_ce", "web_mirror"], // frontends only lists kernel_demo_ce
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await getRuntimeConfig(client, "kernel_demo");

    expect(result.ok).toBe(false);
  });
});
