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

  it("returns null when frontend_ids lists an id frontends doesn't have", () => {
    const payload = {
      ...VALID_PAYLOAD,
      frontend_ids: ["f1", "f2"],
      frontends: [{ frontend_id: "f1", type: "web", enabled: true }],
    };
    expect(parseRuntimeConfig(payload)).toBeNull();
  });

  it("returns null when frontends has a duplicate frontend_id not covered by unique frontend_ids", () => {
    const payload = {
      ...VALID_PAYLOAD,
      frontend_ids: ["a", "b"],
      frontends: [
        { frontend_id: "a", type: "web", enabled: true },
        { frontend_id: "a", type: "web", enabled: true },
      ],
    };
    expect(parseRuntimeConfig(payload)).toBeNull();
  });

  it("returns null when scenario_ids and scenarios desync", () => {
    const payload = {
      ...VALID_PAYLOAD,
      scenario_ids: ["s1"],
      scenarios: [
        {
          scenario_id: "s2",
          version: 1,
          allowed_next_actions: [],
          input_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
          output_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
        },
      ],
    };
    expect(parseRuntimeConfig(payload)).toBeNull();
  });

  it("accepts a scenario whose allowed_next_actions is absent, defaulting to an empty array", () => {
    // allowed_next_actions is optional on the wire (RuntimeScenarioResponse) -- a scenario
    // omitting it entirely (not just sending []) is a valid payload per the backend schema and
    // must not be treated as malformed.
    const payload = {
      ...VALID_PAYLOAD,
      scenario_ids: ["s1"],
      scenarios: [
        {
          scenario_id: "s1",
          version: 1,
          input_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
          output_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
        },
      ],
    };
    expect(parseRuntimeConfig(payload)).toEqual({
      productId: "kernel_demo",
      frontendIds: [],
      frontends: [],
      scenarioIds: ["s1"],
      scenarios: [
        {
          scenarioId: "s1",
          version: 1,
          allowedNextActions: [],
          inputRendererHint: { renderer: "json_schema", schemaRef: "x", schemaVersion: null },
          outputRendererHint: { renderer: "json_schema", schemaRef: "x", schemaVersion: null },
        },
      ],
      quotaSummary: null,
      allowedUiCapabilities: [],
    });
  });

  it("accepts a scenario whose allowed_next_actions is explicitly null, defaulting to an empty array", () => {
    // `allowed_next_actions` is optional (not `| null`) on the generated backend schema, but an
    // explicit `null` on the wire must be treated the same as an absent key, not as malformed --
    // both mean "no next actions".
    const payload = {
      ...VALID_PAYLOAD,
      scenario_ids: ["s1"],
      scenarios: [
        {
          scenario_id: "s1",
          version: 1,
          allowed_next_actions: null,
          input_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
          output_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
        },
      ],
    };
    expect(parseRuntimeConfig(payload)).toEqual({
      productId: "kernel_demo",
      frontendIds: [],
      frontends: [],
      scenarioIds: ["s1"],
      scenarios: [
        {
          scenarioId: "s1",
          version: 1,
          allowedNextActions: [],
          inputRendererHint: { renderer: "json_schema", schemaRef: "x", schemaVersion: null },
          outputRendererHint: { renderer: "json_schema", schemaRef: "x", schemaVersion: null },
        },
      ],
      quotaSummary: null,
      allowedUiCapabilities: [],
    });
  });

  it("returns null when allowed_next_actions is present but not an array of strings", () => {
    const payload = {
      ...VALID_PAYLOAD,
      scenario_ids: ["s1"],
      scenarios: [
        {
          scenario_id: "s1",
          version: 1,
          allowed_next_actions: "not-an-array",
          input_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
          output_renderer_hint: { renderer: "json_schema", schema_ref: "x" },
        },
      ],
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
