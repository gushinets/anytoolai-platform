import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import {
  isHandoffNotFound,
  isHandoffSourceInvalid,
  isHandoffTargetSchemaInvalid,
} from "../../src/api/errors";
import { createHandoff } from "../../src/handoffs/createHandoff";
import type { CreateHandoffRequest } from "../../src/handoffs/types";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

const REQUEST: CreateHandoffRequest = {
  handoffDefinitionId: "kernel_demo.to_freelancer_demo",
  sourceScenarioSessionId: "scenario_session_123",
  sourceArtifactId: "artifact_123",
};

const CREATED_PAYLOAD = {
  handoff_id: "handoff_123",
  handoff_token: "token_abc",
  status: "pending",
  expires_at: "2026-01-01T00:10:00Z",
};

describe("createHandoff", () => {
  it("posts the mapped request body to /v1/handoffs and maps the response to camelCase", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, CREATED_PAYLOAD));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await createHandoff(client, REQUEST);

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/handoffs",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      handoff_definition_id: "kernel_demo.to_freelancer_demo",
      source_scenario_session_id: "scenario_session_123",
      source_artifact_id: "artifact_123",
    });
    expect(result).toEqual({
      ok: true,
      value: {
        handoffId: "handoff_123",
        handoffToken: "token_abc",
        status: "pending",
        expiresAt: "2026-01-01T00:10:00Z",
      },
      status: 200,
    });
  });

  it("returns a backend_error result with handoff_not_found for an unknown handoff definition", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: { code: "handoff_not_found", message: "Handoff not found.", request_id: "req_1" },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await createHandoff(client, REQUEST);

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffNotFound(result.error)).toBe(true);
  });

  it("returns a backend_error result with handoff_source_invalid for an invalid source session/artifact", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(404, {
        error: {
          code: "handoff_source_invalid",
          message: "Handoff source is not available.",
          request_id: "req_2",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await createHandoff(client, REQUEST);

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffSourceInvalid(result.error)).toBe(true);
    expect(!result.ok && isHandoffNotFound(result.error)).toBe(false);
  });

  it("returns a backend_error result with handoff_target_schema_invalid on conflict (409)", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(409, {
        error: {
          code: "handoff_target_schema_invalid",
          message: "Handoff target schema is invalid.",
          request_id: "req_3",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await createHandoff(client, REQUEST);

    expect(result.ok).toBe(false);
    expect(!result.ok && isHandoffTargetSchemaInvalid(result.error)).toBe(true);
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { handoff_id: "handoff_123" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await createHandoff(client, REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Handoff creation response was invalid.",
      },
    });
  });

  it("propagates a caller-supplied AbortSignal", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchImpl = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal?.aborted) {
        throw new DOMException("Aborted", "AbortError");
      }
      return jsonResponse(200, CREATED_PAYLOAD);
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await createHandoff(client, REQUEST, { signal: controller.signal });

    expect(result).toEqual({ ok: false, error: { type: "aborted" } });
  });
});
