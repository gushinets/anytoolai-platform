import { describe, expect, it } from "vitest";
import { parseResultArtifact } from "../../src/results/parseResultArtifact";

const VALID_PAYLOAD = {
  result_artifact_id: "artifact_123",
  scenario_session_id: "scenario_session_123",
  job_id: "job_123",
  workflow_id: "kernel_demo.single_action_extract_v1",
  workflow_version: 1,
  schema_ref: "kernel_demo.extract_output_v1",
  schema_version: 1,
  created_at: "2026-01-01T00:00:00Z",
  output: { title: "Example", fields: ["one", "two"] },
};

describe("parseResultArtifact", () => {
  it("returns null for a non-object payload", () => {
    expect(parseResultArtifact(null)).toBeNull();
    expect(parseResultArtifact("artifact_123")).toBeNull();
  });

  it("returns null when a required field is missing", () => {
    const { result_artifact_id: _resultArtifactId, ...rest } = VALID_PAYLOAD;
    expect(parseResultArtifact(rest)).toBeNull();
  });

  it("returns null when a field has the wrong type", () => {
    expect(parseResultArtifact({ ...VALID_PAYLOAD, workflow_version: "1" })).toBeNull();
    expect(parseResultArtifact({ ...VALID_PAYLOAD, schema_version: "1" })).toBeNull();
    expect(parseResultArtifact({ ...VALID_PAYLOAD, created_at: 123 })).toBeNull();
  });

  it("returns null when output is not an object", () => {
    expect(parseResultArtifact({ ...VALID_PAYLOAD, output: "not an object" })).toBeNull();
    expect(parseResultArtifact({ ...VALID_PAYLOAD, output: null })).toBeNull();
  });

  it("returns null when output is an array, even though typeof [] === \"object\"", () => {
    expect(parseResultArtifact({ ...VALID_PAYLOAD, output: [] })).toBeNull();
    expect(parseResultArtifact({ ...VALID_PAYLOAD, output: ["one", "two"] })).toBeNull();
  });

  it("maps a valid payload to camelCase", () => {
    expect(parseResultArtifact(VALID_PAYLOAD)).toEqual({
      resultArtifactId: "artifact_123",
      scenarioSessionId: "scenario_session_123",
      jobId: "job_123",
      workflowId: "kernel_demo.single_action_extract_v1",
      workflowVersion: 1,
      schemaRef: "kernel_demo.extract_output_v1",
      schemaVersion: 1,
      createdAt: "2026-01-01T00:00:00Z",
      output: { title: "Example", fields: ["one", "two"] },
    });
  });

  it("passes the output object through structurally unchanged", () => {
    const nestedOutput = { title: "Example", nested: { a: 1, b: [1, 2, 3] } };
    const parsed = parseResultArtifact({ ...VALID_PAYLOAD, output: nestedOutput });
    expect(parsed?.output).toEqual(nestedOutput);
  });

  it("does not carry any provider/model/provider-call fields through, even if present on the payload", () => {
    const parsed = parseResultArtifact({
      ...VALID_PAYLOAD,
      provider: "anthropic",
      model: "claude-x",
      prompt: "system prompt text",
    });
    expect(parsed).toEqual({
      resultArtifactId: "artifact_123",
      scenarioSessionId: "scenario_session_123",
      jobId: "job_123",
      workflowId: "kernel_demo.single_action_extract_v1",
      workflowVersion: 1,
      schemaRef: "kernel_demo.extract_output_v1",
      schemaVersion: 1,
      createdAt: "2026-01-01T00:00:00Z",
      output: { title: "Example", fields: ["one", "two"] },
    });
  });
});
