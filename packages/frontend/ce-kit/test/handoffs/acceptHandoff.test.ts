import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import {
  isHandoffAcceptanceFailed,
  isHandoffExpired,
  isHandoffNotActionable,
  isQuotaExhausted,
} from "../../src/api/errors";
import { acceptHandoff } from "../../src/handoffs/acceptHandoff";
import { handoffPreviewPayload } from "./fixtures";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const PREVIEW_PAYLOAD = handoffPreviewPayload({
  status: "accepted",
  target_scenario_session_id: "scenario_session_1",
  target_job_id: "job_1",
});

describe("acceptHandoff", () => {
  it("posts to /v1/handoffs/{token}/accept with an empty body when no request is given", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PREVIEW_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await acceptHandoff(client, "token_abc");

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/handoffs/token_abc/accept",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({});
    expect(result.ok && result.value.targetScenarioSessionId).toBe("scenario_session_1");
    expect(result.ok && result.value.targetJobId).toBe("job_1");
  });

  it("maps guestId/sourceFrontendInstanceId to snake_case in the request body", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, PREVIEW_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await acceptHandoff(client, "token_abc", {
      guestId: "guest_1",
      sourceFrontendInstanceId: "frontend_1",
    });

    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      guest_id: "guest_1",
      source_frontend_instance_id: "frontend_1",
    });
  });

  it("returns a backend_error result with handoff_expired on 410", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(410, {
        error: { code: "handoff_expired", message: "Handoff has expired.", request_id: "req_1" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await acceptHandoff(client, "token_abc");

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffExpired(result.error)).toBe(true);
  });

  it("returns a backend_error result classified as not-actionable when already accepted (409)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: {
          code: "handoff_already_accepted",
          message: "Handoff has already been accepted.",
          request_id: "req_2",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await acceptHandoff(client, "token_abc");

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffNotActionable(result.error)).toBe(true);
  });

  it("returns a backend_error result with quota_exhausted on 429", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(429, {
        error: { code: "quota_exhausted", message: "Guest quota exhausted.", request_id: "req_3" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await acceptHandoff(client, "token_abc");

    expect(result.ok).toBe(false);
    expect(!result.ok && isQuotaExhausted(result.error)).toBe(true);
  });

  it("returns a backend_error result with handoff_acceptance_failed on 500", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(500, {
        error: {
          code: "handoff_acceptance_failed",
          message: "Handoff acceptance failed.",
          request_id: "req_4",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await acceptHandoff(client, "token_abc");

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffAcceptanceFailed(result.error)).toBe(true);
  });
});
