import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import {
  COPY_RESULT_NEXT_ACTION_ID,
  copyResultAndRecordActivation,
} from "../../src/scenarios/copyResultAndRecordActivation";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const SESSION_PAYLOAD = {
  scenario_session_id: "scenario_session_123",
  job_id: "job_123",
  status: "completed",
  current_checkpoint_id: "result_ready",
  allowed_next_actions: [],
  result_artifact_id: "artifact_123",
};

const COPY_RESULT_URL =
  "https://api.example.com/v1/scenario-sessions/scenario_session_123/next-actions/copy_result";

function request(writeToClipboard: (text: string) => Promise<void>) {
  return {
    text: "Dear client, ...",
    scenarioSessionId: "scenario_session_123",
    checkpointId: "result_ready",
    writeToClipboard,
  };
}

describe("copyResultAndRecordActivation", () => {
  it("records exactly one copy_result next-action after a successful clipboard write", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    const writeToClipboard = vi.fn(async (_text: string) => undefined);

    const result = await copyResultAndRecordActivation(client, request(writeToClipboard));

    expect(writeToClipboard).toHaveBeenCalledWith("Dear client, ...");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).toHaveBeenCalledWith(COPY_RESULT_URL, expect.objectContaining({ method: "POST" }));
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ checkpoint_id: "result_ready" });
    expect(result.copied).toBe(true);
    expect(result.copied && result.activation.ok).toBe(true);
    expect(COPY_RESULT_NEXT_ACTION_ID).toBe("copy_result");
  });

  it("does not send the activation request until the clipboard write has actually completed", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    let resolveWrite: () => void = () => undefined;
    const pendingWrite = new Promise<void>((resolve) => {
      resolveWrite = resolve;
    });

    const inFlight = copyResultAndRecordActivation(client, request(() => pendingWrite));
    await Promise.resolve();
    await Promise.resolve();
    expect(fetchImpl).not.toHaveBeenCalled();

    resolveWrite();
    const result = await inFlight;

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(result.copied).toBe(true);
  });

  it("records nothing when the clipboard write fails", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, SESSION_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);
    const denied = new Error("NotAllowedError: clipboard permission denied");

    const result = await copyResultAndRecordActivation(
      client,
      request(async () => {
        throw denied;
      }),
    );

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(result).toEqual({ copied: false, reason: denied });
  });

  it("keeps a successful copy when the activation request is rejected by the backend", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: {
          code: "scenario_checkpoint_conflict",
          message: "Scenario checkpoint no longer matches the requested action.",
          request_id: "req_1",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await copyResultAndRecordActivation(client, request(async () => undefined));

    expect(result.copied).toBe(true);
    expect(result.copied && result.activation.ok).toBe(false);
    expect(
      result.copied && !result.activation.ok && result.activation.error.type === "backend_error"
        ? result.activation.error.code
        : undefined,
    ).toBe("scenario_checkpoint_conflict");
  });

  it("keeps a successful copy when the activation request never reaches the backend", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await copyResultAndRecordActivation(client, request(async () => undefined));

    expect(result.copied).toBe(true);
    expect(result.copied && result.activation.ok).toBe(false);
  });
});
