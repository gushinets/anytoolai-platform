import { describe, expect, it } from "vitest";
import { parseQuotaState } from "../../src/quota/parseQuotaState";

const VALID_PAYLOAD = {
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

describe("parseQuotaState", () => {
  it("returns null for a non-object payload", () => {
    expect(parseQuotaState(null)).toBeNull();
    expect(parseQuotaState("guest_123")).toBeNull();
  });

  it("returns null when a required field is missing", () => {
    const { guest_id: _guestId, ...rest } = VALID_PAYLOAD;
    expect(parseQuotaState(rest)).toBeNull();
  });

  it("returns null when a field has the wrong type", () => {
    expect(parseQuotaState({ ...VALID_PAYLOAD, limit_count: "3" })).toBeNull();
    expect(parseQuotaState({ ...VALID_PAYLOAD, exhausted: "false" })).toBeNull();
  });

  it("maps a valid product-dimension payload to camelCase with a null scenarioId", () => {
    expect(parseQuotaState(VALID_PAYLOAD)).toEqual({
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
    });
  });

  it("maps a valid scenario-dimension payload's scenarioId through", () => {
    const payload = {
      ...VALID_PAYLOAD,
      quota_dimension: "scenario",
      scenario_id: "kernel_demo.single_action_smoke_v1",
    };
    const parsed = parseQuotaState(payload);
    expect(parsed?.scenarioId).toBe("kernel_demo.single_action_smoke_v1");
  });

  it("returns null when scenario_id is present but not a string", () => {
    expect(parseQuotaState({ ...VALID_PAYLOAD, scenario_id: 123 })).toBeNull();
  });

  it("treats a missing scenario_id the same as null", () => {
    const { scenario_id: _scenarioId, ...rest } = VALID_PAYLOAD;
    expect(parseQuotaState(rest)?.scenarioId).toBeNull();
  });
});
