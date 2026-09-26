import { createInMemoryAsyncStorage } from "@anytoolai/ce-kit";
import { describe, expect, it, vi } from "vitest";
import { createProductRunEventTracker } from "../src/products/runtime/productRunEventTracking";
import { errorResponse, jsonResponse, makeClientCapturingRequests } from "./fixtures/platformResponses";

const CLIENT_EVENTS_ROUTE = "POST /v1/client-events";

function clientEventReceiptResponse() {
  return jsonResponse(200, { event_id: "event_1", accepted: true });
}

type ClientEventRequestBody = {
  event_type: string;
  product_id: string;
  frontend_id: string;
  web_session_id: string;
  guest_id?: string;
  scenario_session_id?: string;
  properties?: Record<string, unknown>;
};

function parseBody(call: { init: RequestInit }): ClientEventRequestBody {
  return JSON.parse(call.init.body as string) as ClientEventRequestBody;
}

function clientEventCalls<C extends { key: string }>(calls: C[]): C[] {
  return calls.filter((call) => call.key === CLIENT_EVENTS_ROUTE);
}

describe("createProductRunEventTracker", () => {
  it("tracks product_viewed/form_started/form_submitted as their web.* counterparts, forwarding the guest id ProductRunPage already resolved", async () => {
    const { client, calls } = makeClientCapturingRequests({
      [CLIENT_EVENTS_ROUTE]: [clientEventReceiptResponse(), clientEventReceiptResponse(), clientEventReceiptResponse()],
    });
    const onEvent = createProductRunEventTracker(client, "proposal_ai", createInMemoryAsyncStorage());

    onEvent({ type: "product_viewed", guestId: "guest_from_product_run_page" });
    onEvent({ type: "form_started", guestId: "guest_from_product_run_page" });
    onEvent({ type: "form_submitted", guestId: "guest_from_product_run_page" });
    await vi.waitFor(() => expect(clientEventCalls(calls)).toHaveLength(3));

    // No identity resolution of its own anywhere in this module -- only the client-events POSTs.
    expect(calls.some((call) => call.key !== CLIENT_EVENTS_ROUTE)).toBe(false);

    const bodies = clientEventCalls(calls).map(parseBody);
    expect(bodies.map((body) => body.event_type)).toEqual(["web.product_viewed", "web.form_started", "web.form_submitted"]);
    for (const body of bodies) {
      expect(body.product_id).toBe("proposal_ai");
      expect(body.frontend_id).toBe("web_mirror");
      expect(typeof body.web_session_id).toBe("string");
      expect(body.guest_id).toBe("guest_from_product_run_page");
    }
  });

  it("tracks scenario_completed as web.result_viewed, carrying the scenario session id and guest id", async () => {
    const { client, calls } = makeClientCapturingRequests({ [CLIENT_EVENTS_ROUTE]: [clientEventReceiptResponse()] });
    const onEvent = createProductRunEventTracker(client, "proposal_ai", createInMemoryAsyncStorage());

    onEvent({ type: "scenario_completed", scenarioSessionId: "session_1", guestId: "guest_1", resultViewed: true });
    await vi.waitFor(() => expect(clientEventCalls(calls)).toHaveLength(1));

    const body = parseBody(clientEventCalls(calls)[0]!);
    expect(body.event_type).toBe("web.result_viewed");
    expect(body.scenario_session_id).toBe("session_1");
    expect(body.guest_id).toBe("guest_1");
  });

  it("does not track web.result_viewed for a completed run the product does not count as viewed", async () => {
    const { client, calls } = makeClientCapturingRequests({ [CLIENT_EVENTS_ROUTE]: [clientEventReceiptResponse()] });
    const onEvent = createProductRunEventTracker(client, "brief_decoder", createInMemoryAsyncStorage());

    onEvent({ type: "scenario_completed", scenarioSessionId: "session_1", guestId: "guest_1", resultViewed: false });
    onEvent({ type: "form_started", guestId: "guest_1" });
    await vi.waitFor(() => expect(clientEventCalls(calls)).toHaveLength(1));

    expect(clientEventCalls(calls).map((call) => parseBody(call).event_type)).toEqual(["web.form_started"]);
  });

  it("reuses the same web_session_id across calls", async () => {
    const { client, calls } = makeClientCapturingRequests({
      [CLIENT_EVENTS_ROUTE]: [clientEventReceiptResponse(), clientEventReceiptResponse()],
    });
    const onEvent = createProductRunEventTracker(client, "proposal_ai", createInMemoryAsyncStorage());

    onEvent({ type: "product_viewed", guestId: "guest_1" });
    onEvent({ type: "form_started", guestId: "guest_1" });
    await vi.waitFor(() => expect(clientEventCalls(calls)).toHaveLength(2));

    const [first, second] = clientEventCalls(calls).map(parseBody);
    expect(first!.web_session_id).toBe(second!.web_session_id);
  });

  it("never sends copy_activated -- the backend already records next_action_clicked for it", async () => {
    const { client, calls } = makeClientCapturingRequests({});
    const onEvent = createProductRunEventTracker(client, "proposal_ai", createInMemoryAsyncStorage());

    onEvent({ type: "copy_activated", scenarioSessionId: "session_1", guestId: "guest_1" });
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(clientEventCalls(calls)).toHaveLength(0);
  });

  it("never throws or carries prompt/result text when the backend rejects the event", async () => {
    const { client, calls } = makeClientCapturingRequests({
      [CLIENT_EVENTS_ROUTE]: [errorResponse(400, "client_event_property_invalid")],
    });
    const onEvent = createProductRunEventTracker(client, "proposal_ai", createInMemoryAsyncStorage());

    expect(() => onEvent({ type: "form_started", guestId: "guest_1" })).not.toThrow();
    await vi.waitFor(() => expect(clientEventCalls(calls)).toHaveLength(1));

    const body = parseBody(clientEventCalls(calls)[0]!);
    expect(Object.keys(body)).not.toContain("properties");
  });

  it("passes through an undefined guest id exactly as ProductRunPage resolved it, for product_viewed included", async () => {
    const { client, calls } = makeClientCapturingRequests({ [CLIENT_EVENTS_ROUTE]: [clientEventReceiptResponse()] });
    const onEvent = createProductRunEventTracker(client, "proposal_ai", createInMemoryAsyncStorage());

    onEvent({ type: "product_viewed", guestId: undefined });
    await vi.waitFor(() => expect(clientEventCalls(calls)).toHaveLength(1));

    const body = parseBody(clientEventCalls(calls)[0]!);
    expect(body.guest_id).toBeUndefined();
  });
});
