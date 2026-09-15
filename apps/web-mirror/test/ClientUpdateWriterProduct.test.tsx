// Client Update Writer's own meaning: its three modes (Update, ReplyDraft, PrepaidRequest), their
// field mappings to ANY-413's own input schemas, the shared compose_reply canonical result
// (`text` + optional `call_to_action`, composed per `renderer_contract.yaml`'s
// `append_after_blank_line`), and the mode switcher. The shared runtime behavior every mode rides
// on (polling, retry, quota, copy-activation ordering, event callbacks) is proven once in
// ProductRunPage.test.tsx -- not re-proven per mode here.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import {
  ClientUpdateWriterProduct,
  prepaidRequestDefinition,
  replyDraftDefinition,
  updateDefinition,
} from "../src/products/clientUpdateWriter/ClientUpdateWriterProduct";
import {
  errorResponse,
  guestIdentityResponse,
  makeClient,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
} from "./fixtures/platformResponses";

/** `getByText`'s default matcher collapses whitespace (including the composed result's blank-line
 * separator) to a single space -- this matches against each element's raw `textContent` instead,
 * so the `text`/`call_to_action` blank-line composition is actually asserted, not normalized away. */
function byExactText(expected: string) {
  return (_: string, element: Element | null) => element?.textContent === expected;
}

const MODE_IDS = {
  update: { productId: "client_update_writer", scenarioId: "client_update_writer.update_v1" },
  reply_draft: { productId: "client_update_writer", scenarioId: "client_update_writer.reply_draft_v1" },
  prepaid_request: { productId: "client_update_writer", scenarioId: "client_update_writer.prepaid_request_v1" },
} as const;

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(() => Promise.resolve()) },
  });
});

function bootAndHappyPathRoutes(ids: (typeof MODE_IDS)[keyof typeof MODE_IDS], resultOutput: Record<string, unknown>) {
  const routes = routesFor(ids);
  return {
    routes,
    queues: {
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids)],
      [routes.START]: [startResponse()],
      [routes.SESSION]: [sessionResponse()],
      [routes.RESULT]: [resultResponse(ids, { output: resultOutput })],
      [routes.NEXT_ACTION]: [sessionResponse({ status: "completed" })],
    },
  };
}

describe("Client Update Writer product definitions", () => {
  it("is registered under the client_update_writer product id, one scenario per mode", () => {
    expect(updateDefinition.productId).toBe("client_update_writer");
    expect(updateDefinition.scenarioId).toBe("client_update_writer.update_v1");
    expect(replyDraftDefinition.productId).toBe("client_update_writer");
    expect(replyDraftDefinition.scenarioId).toBe("client_update_writer.reply_draft_v1");
    expect(prepaidRequestDefinition.productId).toBe("client_update_writer");
    expect(prepaidRequestDefinition.scenarioId).toBe("client_update_writer.prepaid_request_v1");
  });

  it("treats a result with call_to_action as usable, appended after a blank line when copied/rendered", () => {
    expect(updateDefinition.extractResult({ text: "Thanks." })).toEqual({ text: "Thanks.", callToAction: undefined });
    expect(updateDefinition.extractResult({ text: "Thanks.", call_to_action: "Reply by Friday." })).toEqual({
      text: "Thanks.",
      callToAction: "Reply by Friday.",
    });
  });

  it("treats a result without a string `text` field as unusable rather than rendering something else", () => {
    expect(updateDefinition.extractResult({ call_to_action: "Reply by Friday." })).toBeNull();
    expect(updateDefinition.extractResult({ text: 42 })).toBeNull();
  });

  it("Update mode validates progress_notes/tone and maps them to update_input_v1", async () => {
    const ids = MODE_IDS.update;
    const { routes, queues } = bootAndHappyPathRoutes(ids, {
      text: "Quick update: the homepage redesign is done and ready for review by Friday. Checkout flow work is in progress, no blockers so far.",
      call_to_action: "Let me know if you'd like any changes to the homepage.",
    });
    const { client, calls } = makeClient(queues);

    render(<ProductRunPage definition={updateDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    expect(await screen.findByText("Progress notes is required.")).toBeTruthy();
    expect(screen.getByText("Tone is required.")).toBeTruthy();
    expect(calls.some((call) => call.key === routes.START)).toBe(false);

    fireEvent.change(screen.getByLabelText("Progress notes"), {
      target: { value: "Homepage redesign is done and ready for review by Friday." },
    });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "warm" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          byExactText(
            "Quick update: the homepage redesign is done and ready for review by Friday. Checkout flow work is in progress, no blockers so far.\n\nLet me know if you'd like any changes to the homepage.",
          ),
        ),
      ).toBeTruthy(),
    );
    const startCall = calls.find((call) => call.key === routes.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      input: { progress_notes: "Homepage redesign is done and ready for review by Friday.", tone: "warm" },
    });
  });

  it("Update mode's weak-input path still renders a safe, copy-ready result (text alone, no call_to_action)", async () => {
    const ids = MODE_IDS.update;
    const { queues } = bootAndHappyPathRoutes(ids, { text: "Quick update: work is still underway." });
    const { client } = makeClient(queues);

    render(<ProductRunPage definition={updateDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Still working on it." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));

    await waitFor(() => expect(screen.getByText("Quick update: work is still underway.")).toBeTruthy());
    expect(screen.queryByRole("alert")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });

  it("Reply Draft mode validates client_message/reply_goal/tone and maps them to reply_draft_input_v1", async () => {
    const ids = MODE_IDS.reply_draft;
    const { routes, queues } = bootAndHappyPathRoutes(ids, {
      text: "Thanks for the question about the timeline. The revised delivery date is next Wednesday, which covers both the copy edits and the final review pass.",
    });
    const { client, calls } = makeClient(queues);

    render(<ProductRunPage definition={replyDraftDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Client message")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Client message"), { target: { value: "When will this ship?" } });
    fireEvent.change(screen.getByLabelText("Reply goal"), { target: { value: "Give a concrete date." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write reply" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          "Thanks for the question about the timeline. The revised delivery date is next Wednesday, which covers both the copy edits and the final review pass.",
        ),
      ).toBeTruthy(),
    );
    const startCall = calls.find((call) => call.key === routes.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      input: { client_message: "When will this ship?", reply_goal: "Give a concrete date.", tone: "neutral" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(calls.some((call) => call.key === routes.NEXT_ACTION)).toBe(true));
    expect(routes.NEXT_ACTION.endsWith("/next-actions/copy_result")).toBe(true);
  });

  it("Prepaid Request mode validates billing_context/tone (due_date optional) and maps them to prepaid_request_input_v1", async () => {
    const ids = MODE_IDS.prepaid_request;
    const { routes, queues } = bootAndHappyPathRoutes(ids, {
      text: "The design phase you approved wraps up this week, with phase 2 (development) starting next. Could you send the $500 prepayment for phase 2 by Friday?",
      call_to_action: "Please send the $500 prepayment and reply once it's on its way.",
    });
    const { client, calls } = makeClient(queues);

    render(<ProductRunPage definition={prepaidRequestDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Billing notes")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Billing notes"), {
      target: { value: "The approved design phase wraps up this week; phase 2 starts next." },
    });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "$500" } });
    fireEvent.change(screen.getByLabelText("Due date (optional)"), { target: { value: "Friday" } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "firm" } });
    fireEvent.click(screen.getByRole("button", { name: "Write request" }));

    await waitFor(() =>
      expect(
        screen.getByText(
          byExactText(
            "The design phase you approved wraps up this week, with phase 2 (development) starting next. Could you send the $500 prepayment for phase 2 by Friday?\n\nPlease send the $500 prepayment and reply once it's on its way.",
          ),
        ),
      ).toBeTruthy(),
    );
    const startCall = calls.find((call) => call.key === routes.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      input: {
        billing_context: {
          notes: "The approved design phase wraps up this week; phase 2 starts next.",
          amount: "$500",
          due_date: "Friday",
        },
        tone: "firm",
      },
    });
  });

  it("Prepaid Request mode omits due_date from the input payload when left blank", async () => {
    const ids = MODE_IDS.prepaid_request;
    const { routes, queues } = bootAndHappyPathRoutes(ids, { text: "Ok." });
    const { client, calls } = makeClient(queues);

    render(<ProductRunPage definition={prepaidRequestDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Billing notes")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Billing notes"), { target: { value: "Work is ongoing." } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "the agreed amount" } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write request" }));

    await waitFor(() => expect(screen.getByText("Ok.")).toBeTruthy());
    const startCall = calls.find((call) => call.key === routes.START);
    const body = JSON.parse(startCall?.init.body as string) as { input: { billing_context: unknown } };
    expect(body.input.billing_context).toEqual({ notes: "Work is ongoing.", amount: "the agreed amount" });
  });

  it("enters a quota-exhausted state from the advisory quota check, with no form and no scenario started", async () => {
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client, calls } = makeClient({
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids, { used_count: 3, remaining_count: 0, exhausted: true })],
    });

    render(<ProductRunPage definition={updateDefinition} client={client} />);

    await waitFor(() => expect(screen.getByText("You've used all your Client Update Writer runs for now.")).toBeTruthy());
    expect(screen.queryByLabelText("Progress notes")).toBeNull();
    expect(calls.some((call) => call.key === routes.START)).toBe(false);
  });

  it("lands on the safe terminal-error state when the scenario session itself fails", async () => {
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client } = makeClient({
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids)],
      [routes.START]: [startResponse()],
      [routes.SESSION]: [sessionResponse({ status: "failed" })],
    });

    render(<ProductRunPage definition={updateDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Still working on it." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));

    await waitFor(() =>
      expect(
        screen.getByText("Something went wrong writing your update. Please try again."),
      ).toBeTruthy(),
    );
  });

  it("also rejects an authoritative-start 429 even when the advisory quota check missed it", async () => {
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client } = makeClient({
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids)],
      [routes.START]: [errorResponse(429, "quota_exhausted")],
    });

    render(<ProductRunPage definition={updateDefinition} client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Still working on it." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));

    await waitFor(() => expect(screen.getByText("You've used all your Client Update Writer runs for now.")).toBeTruthy());
  });

  it("reports scenario_completed/copy_activated events with the started session's own id", async () => {
    const ids = MODE_IDS.update;
    const { queues } = bootAndHappyPathRoutes(ids, { text: "Quick update: work is still underway." });
    const { client } = makeClient(queues);
    const events: ProductRunEvent[] = [];

    render(<ProductRunPage definition={updateDefinition} client={client} onEvent={(event) => events.push(event)} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Still working on it." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() => expect(screen.getByText("Quick update: work is still underway.")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());

    expect(events).toEqual([
      { type: "product_viewed" },
      { type: "form_started" },
      { type: "form_submitted" },
      { type: "scenario_completed", scenarioSessionId: "session_1" },
      { type: "copy_activated", scenarioSessionId: "session_1" },
    ]);
  });
});

describe("ClientUpdateWriterProduct (mode switcher)", () => {
  it("defaults to Update mode and switches its own form fields when another mode is selected", async () => {
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client } = makeClient({
      // RUNTIME_CONFIG/GUEST_IDENTITY/QUOTA are keyed by product id only, shared across all three
      // modes -- boot fires once per mode mount (`key={modeId}` remounts ProductRunPage on switch),
      // so two entries cover the initial Update mount and the switch to Reply Draft.
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids), runtimeConfigResponse(MODE_IDS.reply_draft)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids), quotaResponse(MODE_IDS.reply_draft)],
    });

    render(<ClientUpdateWriterProduct client={client} />);

    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());
    expect((screen.getByRole("radio", { name: "Update" }) as HTMLInputElement).checked).toBe(true);

    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));

    await waitFor(() => expect(screen.getByLabelText("Client message")).toBeTruthy());
    expect(screen.queryByLabelText("Progress notes")).toBeNull();
  });
});
