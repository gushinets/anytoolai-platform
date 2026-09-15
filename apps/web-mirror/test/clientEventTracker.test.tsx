// ANY-414: wires ProductRunPage's product-neutral funnel events into POST /v1/client-events
// (ANY-17) for the real production route -- the gap ANY-453's own exec plan left deferred
// ("ANY-17's job plus whichever ticket composes it into the route").
import { PlatformApiClient } from "@anytoolai/ce-kit";
import { waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createClientEventTracker } from "../src/products/runtime/clientEventTracker";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";

afterEach(() => {
  window.localStorage.clear();
});

type CapturedCall = { url: string; body: Record<string, unknown> };

function makeClientCapturingClientEvents() {
  const calls: CapturedCall[] = [];
  const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, body: JSON.parse(init.body as string) as Record<string, unknown> });
    return new Response(JSON.stringify({ event_id: "event_1", accepted: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  const client = new PlatformApiClient({
    baseUrl: "https://api.example.com",
    fetchImpl: fetchImpl as unknown as typeof fetch,
  });
  return { client, calls };
}

describe("createClientEventTracker", () => {
  it("sends each mappable funnel event to /v1/client-events with product/frontend/session ids", async () => {
    const { client, calls } = makeClientCapturingClientEvents();
    const track = createClientEventTracker(client, "client_update_writer");

    track({ type: "product_viewed" });
    track({ type: "scenario_completed", scenarioSessionId: "session_1" });

    await waitFor(() => expect(calls).toHaveLength(2));

    expect(calls[0]!.url).toContain("/v1/client-events");
    expect(calls[0]!.body).toMatchObject({
      event_type: "web.product_viewed",
      product_id: "client_update_writer",
      frontend_id: "web_mirror",
    });
    expect(calls[0]!.body.web_session_id).toEqual(expect.any(String));
    expect(calls[0]!.body.scenario_session_id).toBeUndefined();

    expect(calls[1]!.body).toMatchObject({ event_type: "web.result_viewed", scenario_session_id: "session_1" });
  });

  it("reuses the same web_session_id across calls from one tracker", async () => {
    const { client, calls } = makeClientCapturingClientEvents();
    const track = createClientEventTracker(client, "client_update_writer");

    track({ type: "product_viewed" });
    track({ type: "form_started" });
    await waitFor(() => expect(calls).toHaveLength(2));

    expect(calls[0]!.body.web_session_id).toBe(calls[1]!.body.web_session_id);
  });

  it("does not send anything for events outside the web.* allowlist (copy_activated)", async () => {
    const { client, calls } = makeClientCapturingClientEvents();
    const track = createClientEventTracker(client, "client_update_writer");

    track({ type: "copy_activated", scenarioSessionId: "session_1" } satisfies ProductRunEvent);
    track({ type: "form_submitted" });
    await waitFor(() => expect(calls).toHaveLength(1));

    expect(calls[0]!.body.event_type).toBe("web.form_submitted");
  });
});
