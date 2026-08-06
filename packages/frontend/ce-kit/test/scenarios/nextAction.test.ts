import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { isIdempotencyKeyConflict, isScenarioActionConflict } from "../../src/api/errors";
import { nextAction } from "../../src/scenarios/nextAction";
import type { NextActionRequest } from "../../src/scenarios/nextAction";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const REQUEST: NextActionRequest = {
  scenarioSessionId: "scenario_session_123",
  nextActionId: "copy_result",
  checkpointId: "result_ready",
};

const SESSION_PAYLOAD = {
  scenario_session_id: "scenario_session_123",
  job_id: "job_123",
  status: "completed",
  current_checkpoint_id: "result_ready",
  allowed_next_actions: ["copy_result"],
  result_artifact_id: "artifact_123",
};

describe("nextAction", () => {
  it("posts the checkpoint id to the next-action endpoint and maps the response", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await nextAction(client, REQUEST);

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/scenario-sessions/scenario_session_123/next-actions/copy_result",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ checkpoint_id: "result_ready" });
    expect(result).toEqual({
      ok: true,
      value: {
        scenarioSessionId: "scenario_session_123",
        jobId: "job_123",
        status: "completed",
        currentCheckpointId: "result_ready",
        allowedNextActions: ["copy_result"],
        resultArtifactId: "artifact_123",
      },
      status: 200,
    });
  });

  it("percent-encodes the session id and next action id in the URL", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await nextAction(client, {
      scenarioSessionId: "session with spaces",
      nextActionId: "action id",
      checkpointId: "checkpoint_1",
    });

    const [url] = fetchImpl.mock.calls[0] as unknown as [string];
    expect(url).toBe(
      "https://api.example.com/v1/scenario-sessions/session%20with%20spaces/next-actions/action%20id",
    );
  });

  it("returns a backend_error result for an unknown scenario session (404)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: {
          code: "scenario_session_not_found",
          message: "Scenario session not found.",
          request_id: "req_1",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await nextAction(client, REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 404,
        code: "scenario_session_not_found",
        message: "Scenario session not found.",
        requestId: "req_1",
      },
    });
  });

  it("surfaces a stale-checkpoint 409 distinctly from an idempotency conflict, by code", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: {
          code: "scenario_checkpoint_conflict",
          message: "Scenario checkpoint no longer matches the requested action.",
          request_id: "req_2",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await nextAction(client, REQUEST);

    expect(result.ok).toBe(false);
    expect(!result.ok && isScenarioActionConflict(result.error)).toBe(true);
    expect(!result.ok && isIdempotencyKeyConflict(result.error)).toBe(false);
  });

  it("surfaces a disallowed-action 409", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: {
          code: "scenario_next_action_not_allowed",
          message: "Next action is not allowed at this checkpoint.",
          request_id: "req_3",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await nextAction(client, REQUEST);

    expect(!result.ok && result.error.type === "backend_error" && result.error.code).toBe(
      "scenario_next_action_not_allowed",
    );
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { scenario_session_id: "scenario_session_123" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await nextAction(client, REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Scenario session response was invalid.",
      },
    });
  });
});
