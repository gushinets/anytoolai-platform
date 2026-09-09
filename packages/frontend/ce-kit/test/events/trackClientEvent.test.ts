import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { trackClientEvent } from "../../src/events/trackClientEvent";
import type { TrackClientEventRequest } from "../../src/events/trackClientEvent";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

type ClientEventWireBody = {
  event_id: string;
  event_type: string;
  product_id: string;
  frontend_id: string;
  web_session_id: string;
  guest_id?: string;
  user_id?: string;
  scenario_session_id?: string;
  properties?: Record<string, string | number>;
};

function parseBody(init: RequestInit): ClientEventWireBody {
  return JSON.parse(init.body as string) as ClientEventWireBody;
}

const REQUEST: TrackClientEventRequest = {
  eventType: "web.product_viewed",
  productId: "kernel_demo",
  frontendId: "web_mirror",
  webSessionId: "web_session_123",
  guestId: "guest_123",
  scenarioSessionId: "scenario_session_123",
  properties: { mode: "one_run", fieldCount: 3, gapCategory: "budget" },
};

describe("trackClientEvent", () => {
  it("posts an allowlisted event with a generated idempotent event_id and maps the response", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { event_id: "web_evt_1", event_type: "web.product_viewed" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await trackClientEvent(client, REQUEST);

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://api.example.com/v1/client-events",
      expect.objectContaining({ method: "POST" }),
    );
    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const body = parseBody(init);
    expect(typeof body.event_id).toBe("string");
    expect(body.event_id.length).toBeGreaterThan(0);
    expect(body).toMatchObject({
      event_type: "web.product_viewed",
      product_id: "kernel_demo",
      frontend_id: "web_mirror",
      web_session_id: "web_session_123",
      guest_id: "guest_123",
      scenario_session_id: "scenario_session_123",
      properties: { mode: "one_run", field_count: 3, gap_category: "budget" },
    });
    expect(result).toEqual({
      ok: true,
      value: { eventId: "web_evt_1", eventType: "web.product_viewed" },
      status: 200,
    });
  });

  it("generates a different event_id on every call, so retries stay caller-controlled", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { event_id: "web_evt_1", event_type: "web.product_viewed" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await trackClientEvent(client, REQUEST);
    await trackClientEvent(client, REQUEST);

    const [firstCall, secondCall] = fetchImpl.mock.calls as unknown as [
      [string, RequestInit],
      [string, RequestInit],
    ];
    const firstBody = parseBody(firstCall[1]);
    const secondBody = parseBody(secondCall[1]);
    expect(firstBody.event_id).not.toBe(secondBody.event_id);
  });

  it("omits a non-finite fieldCount instead of letting it become null on the wire", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { event_id: "web_evt_1", event_type: "web.product_viewed" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await trackClientEvent(client, {
      eventType: "web.product_viewed",
      productId: "kernel_demo",
      frontendId: "web_mirror",
      webSessionId: "web_session_123",
      properties: { mode: "one_run", fieldCount: Number.NaN },
    });

    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const body = parseBody(init);
    expect(body.properties?.field_count).toBeUndefined();
    expect(body.properties?.mode).toBe("one_run");
  });

  it("omits a non-integer fieldCount instead of failing the whole event", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { event_id: "web_evt_1", event_type: "web.product_viewed" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await trackClientEvent(client, {
      eventType: "web.product_viewed",
      productId: "kernel_demo",
      frontendId: "web_mirror",
      webSessionId: "web_session_123",
      properties: { mode: "one_run", fieldCount: 2.5 },
    });

    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const body = parseBody(init);
    expect(body.properties?.field_count).toBeUndefined();
    expect(body.properties?.mode).toBe("one_run");
  });

  it("omits unset optional fields instead of sending them as undefined-turned-null", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(200, { event_id: "web_evt_1", event_type: "web.product_viewed" }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await trackClientEvent(client, {
      eventType: "web.product_viewed",
      productId: "kernel_demo",
      frontendId: "web_mirror",
      webSessionId: "web_session_123",
    });

    const [, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    const body = parseBody(init);
    expect(body.guest_id).toBeUndefined();
    expect(body.user_id).toBeUndefined();
    expect(body.scenario_session_id).toBeUndefined();
    expect(body.properties).toBeUndefined();
  });

  it("resolves ok:false without throwing when the request fails (non-blocking analytics)", async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error("network down");
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await expect(trackClientEvent(client, REQUEST)).resolves.toEqual({
      ok: false,
      error: { type: "network_error", message: "Network request failed." },
    });
  });

  it("surfaces a safe backend rejection (e.g. disallowed property) as a backend_error result", async () => {
    const fetchImpl = vi.fn(async () =>
      jsonResponse(422, {
        error: {
          code: "client_event_property_invalid",
          message: "Property 'prompt_text' is not an allowlisted scalar client-event property.",
          request_id: "req_1",
        },
      }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await trackClientEvent(client, REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 422,
        code: "client_event_property_invalid",
        message: "Property 'prompt_text' is not an allowlisted scalar client-event property.",
        requestId: "req_1",
      },
    });
  });

  it("returns an invalid_response result when the payload doesn't match the contract", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, { event_id: "web_evt_1" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await trackClientEvent(client, REQUEST);

    expect(result).toEqual({
      ok: false,
      error: {
        type: "invalid_response",
        status: 200,
        message: "Client event response was invalid.",
      },
    });
  });
});
