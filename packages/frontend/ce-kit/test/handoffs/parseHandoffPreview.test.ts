import { describe, expect, it } from "vitest";
import { parseHandoffPreview } from "../../src/handoffs/parseHandoffPreview";
import { handoffPreviewPayload } from "./fixtures";

const VALID_PAYLOAD = handoffPreviewPayload({ preview: { some_key: "some_value" } });

describe("parseHandoffPreview", () => {
  it("maps a full snake_case payload to camelCase", () => {
    expect(parseHandoffPreview(VALID_PAYLOAD)).toEqual({
      handoffId: "handoff_123",
      status: "created",
      sourceProductId: "kernel_demo",
      sourceProductDisplayName: "Kernel Demo",
      targetProductId: "freelancer_demo",
      targetProductDisplayName: "Freelancer Demo",
      targetScenarioId: "scenario_1",
      preview: { some_key: "some_value" },
      expiresAt: "2026-01-01T00:10:00Z",
      targetScenarioSessionId: null,
      targetJobId: null,
    });
  });

  it("treats absent target_scenario_session_id/target_job_id keys as null", () => {
    const { target_scenario_session_id, target_job_id, ...withoutTargets } = VALID_PAYLOAD;
    void target_scenario_session_id;
    void target_job_id;

    const result = parseHandoffPreview(withoutTargets);

    expect(result?.targetScenarioSessionId).toBeNull();
    expect(result?.targetJobId).toBeNull();
  });

  it("maps populated target_scenario_session_id/target_job_id (post-acceptance)", () => {
    const result = parseHandoffPreview({
      ...VALID_PAYLOAD,
      status: "accepted",
      target_scenario_session_id: "scenario_session_1",
      target_job_id: "job_1",
    });

    expect(result?.targetScenarioSessionId).toBe("scenario_session_1");
    expect(result?.targetJobId).toBe("job_1");
  });

  it("renders preview as opaque key/value pairs regardless of shape", () => {
    const result = parseHandoffPreview({ ...VALID_PAYLOAD, preview: { nested: { a: 1 }, list: [1, 2] } });

    expect(result?.preview).toEqual({ nested: { a: 1 }, list: [1, 2] });
  });

  it("returns null for a non-record payload", () => {
    expect(parseHandoffPreview(null)).toBeNull();
    expect(parseHandoffPreview("string")).toBeNull();
  });

  it("returns null when a required string field is missing or mistyped", () => {
    const { status, ...withoutStatus } = VALID_PAYLOAD;
    void status;
    expect(parseHandoffPreview(withoutStatus)).toBeNull();
    expect(parseHandoffPreview({ ...VALID_PAYLOAD, status: 123 })).toBeNull();
  });

  it("returns null when preview is not a record", () => {
    expect(parseHandoffPreview({ ...VALID_PAYLOAD, preview: "not-a-record" })).toBeNull();
    expect(parseHandoffPreview({ ...VALID_PAYLOAD, preview: null })).toBeNull();
    expect(parseHandoffPreview({ ...VALID_PAYLOAD, preview: [1, 2, 3] })).toBeNull();
  });

  it("returns null when target_scenario_session_id/target_job_id are mistyped", () => {
    expect(parseHandoffPreview({ ...VALID_PAYLOAD, target_scenario_session_id: 123 })).toBeNull();
    expect(parseHandoffPreview({ ...VALID_PAYLOAD, target_job_id: 123 })).toBeNull();
  });

  it("returns null when status is not a known HandoffStatus member", () => {
    expect(parseHandoffPreview({ ...VALID_PAYLOAD, status: "pending" })).toBeNull();
  });
});
