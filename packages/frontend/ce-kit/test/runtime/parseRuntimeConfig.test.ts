import { describe, expect, it } from "vitest";
import { parseRuntimeConfig } from "../../src/runtime/parseRuntimeConfig";

const VALID_PAYLOAD = {
  product_id: "kernel_demo",
  frontend_ids: [],
  frontends: [],
  scenario_ids: [],
  scenarios: [],
  quota_summary: null,
  allowed_ui_capabilities: [],
};

describe("parseRuntimeConfig", () => {
  it("returns null for a non-object payload", () => {
    expect(parseRuntimeConfig(null)).toBeNull();
    expect(parseRuntimeConfig("kernel_demo")).toBeNull();
  });

  it("returns null when a required field is missing", () => {
    const { product_id: _productId, ...rest } = VALID_PAYLOAD;
    expect(parseRuntimeConfig(rest)).toBeNull();
  });

  it("returns null when a scenario's renderer hint is malformed", () => {
    const payload = {
      ...VALID_PAYLOAD,
      scenario_ids: ["s1"],
      scenarios: [
        {
          scenario_id: "s1",
          version: 1,
          allowed_next_actions: [],
          input_renderer_hint: { renderer: "not_json_schema", schema_ref: "x" },
          output_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
        },
      ],
    };
    expect(parseRuntimeConfig(payload)).toBeNull();
  });

  it("returns null when a frontend entry is malformed", () => {
    const payload = {
      ...VALID_PAYLOAD,
      frontend_ids: ["f1"],
      frontends: [{ frontend_id: "f1", type: "web" }],
    };
    expect(parseRuntimeConfig(payload)).toBeNull();
  });

  it("accepts a valid minimal payload with a null quota summary", () => {
    expect(parseRuntimeConfig(VALID_PAYLOAD)).toEqual({
      productId: "kernel_demo",
      frontendIds: [],
      frontends: [],
      scenarioIds: [],
      scenarios: [],
      quotaSummary: null,
      allowedUiCapabilities: [],
    });
  });
});
