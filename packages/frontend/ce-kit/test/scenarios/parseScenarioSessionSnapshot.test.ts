import { describe, expect, it } from "vitest";
import {
  parseScenarioSession,
  parseScenarioSessionSnapshot,
  parseScenarioStartResponse,
} from "../../src/scenarios/parseScenarioSessionSnapshot";

const VALID_PAYLOAD = {
  scenario_session_id: "scenario_session_123",
  job_id: "job_123",
  status: "started",
  allowed_next_actions: [],
  result_artifact_id: null,
};

describe("parseScenarioSessionSnapshot", () => {
  it("returns null for a non-object payload", () => {
    expect(parseScenarioSessionSnapshot(null)).toBeNull();
    expect(parseScenarioSessionSnapshot("scenario_session_123")).toBeNull();
  });

  it("returns null when a required field is missing", () => {
    const { status: _status, ...rest } = VALID_PAYLOAD;
    expect(parseScenarioSessionSnapshot(rest)).toBeNull();
  });

  it("returns null when a field has the wrong type", () => {
    expect(parseScenarioSessionSnapshot({ ...VALID_PAYLOAD, allowed_next_actions: "x" })).toBeNull();
    expect(parseScenarioSessionSnapshot({ ...VALID_PAYLOAD, job_id: 123 })).toBeNull();
  });

  it("maps a valid payload to camelCase", () => {
    expect(parseScenarioSessionSnapshot(VALID_PAYLOAD)).toEqual({
      scenarioSessionId: "scenario_session_123",
      jobId: "job_123",
      status: "started",
      allowedNextActions: [],
      resultArtifactId: null,
    });
  });

  it("treats a null job_id as null, not invalid", () => {
    const parsed = parseScenarioSessionSnapshot({ ...VALID_PAYLOAD, job_id: null });
    expect(parsed?.jobId).toBeNull();
  });

  it("passes non-empty allowed_next_actions and result_artifact_id through", () => {
    const parsed = parseScenarioSessionSnapshot({
      ...VALID_PAYLOAD,
      allowed_next_actions: ["copy_result", "create_handoff"],
      result_artifact_id: "artifact_123",
    });
    expect(parsed?.allowedNextActions).toEqual(["copy_result", "create_handoff"]);
    expect(parsed?.resultArtifactId).toBe("artifact_123");
  });

  it("defaults a missing allowed_next_actions to [], since the field is optional on the wire", () => {
    const { allowed_next_actions: _allowedNextActions, ...rest } = VALID_PAYLOAD;
    expect(parseScenarioSessionSnapshot(rest)?.allowedNextActions).toEqual([]);
  });

  it("returns null for a missing job_id, since the field is required (though nullable) on the wire", () => {
    const { job_id: _jobId, ...rest } = VALID_PAYLOAD;
    expect(parseScenarioSessionSnapshot(rest)).toBeNull();
  });
});

describe("parseScenarioSession", () => {
  const SESSION_PAYLOAD = { ...VALID_PAYLOAD, current_checkpoint_id: "result_ready" };

  it("returns null for a non-object payload", () => {
    expect(parseScenarioSession(null)).toBeNull();
  });

  it("returns null when the shared snapshot fields are invalid", () => {
    expect(parseScenarioSession({ ...SESSION_PAYLOAD, allowed_next_actions: "x" })).toBeNull();
  });

  it("returns null when current_checkpoint_id has the wrong type", () => {
    expect(parseScenarioSession({ ...SESSION_PAYLOAD, current_checkpoint_id: 123 })).toBeNull();
  });

  it("maps a valid payload to camelCase including currentCheckpointId", () => {
    expect(parseScenarioSession(SESSION_PAYLOAD)).toEqual({
      scenarioSessionId: "scenario_session_123",
      jobId: "job_123",
      status: "started",
      allowedNextActions: [],
      resultArtifactId: null,
      currentCheckpointId: "result_ready",
    });
  });

  it("treats a null current_checkpoint_id as null, not invalid", () => {
    const parsed = parseScenarioSession({ ...SESSION_PAYLOAD, current_checkpoint_id: null });
    expect(parsed?.currentCheckpointId).toBeNull();
  });

  it("treats a missing current_checkpoint_id as null", () => {
    expect(parseScenarioSession(VALID_PAYLOAD)?.currentCheckpointId).toBeNull();
  });
});

describe("parseScenarioStartResponse", () => {
  it("maps a valid payload the same way parseScenarioSessionSnapshot does", () => {
    expect(parseScenarioStartResponse(VALID_PAYLOAD)).toEqual(
      parseScenarioSessionSnapshot(VALID_PAYLOAD),
    );
  });

  it("returns null for a null job_id, unlike parseScenarioSessionSnapshot", () => {
    const payload = { ...VALID_PAYLOAD, job_id: null };
    expect(parseScenarioSessionSnapshot(payload)?.jobId).toBeNull();
    expect(parseScenarioStartResponse(payload)).toBeNull();
  });

  it("returns null for a missing job_id", () => {
    const { job_id: _jobId, ...rest } = VALID_PAYLOAD;
    expect(parseScenarioStartResponse(rest)).toBeNull();
  });

  it("still returns null for anything parseScenarioSessionSnapshot itself already rejects", () => {
    expect(parseScenarioStartResponse({ ...VALID_PAYLOAD, allowed_next_actions: "x" })).toBeNull();
    expect(parseScenarioStartResponse(null)).toBeNull();
  });
});
