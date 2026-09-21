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
  idempotencyKeyOf,
  makeClient,
  makeClientWithDeferredRoute,
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
    // `routes.NEXT_ACTION` (`POST /v1/scenario-sessions/session_1/next-actions/copy_result`) is
    // itself derived from the actual URL/method of whichever call matched it (see
    // makeRoutedFetchClient's `routeKey()`) -- this `calls.some(...)` match is already the real
    // assertion that the code called that exact endpoint. Code review finding: a second, now
    // removed line here compared `routes.NEXT_ACTION` against itself, asserting nothing new.
    await waitFor(() => expect(calls.some((call) => call.key === routes.NEXT_ACTION)).toBe(true));
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
      { type: "product_viewed", guestId: "guest_1" },
      { type: "form_started", guestId: "guest_1" },
      { type: "form_submitted", guestId: "guest_1" },
      { type: "scenario_completed", scenarioSessionId: "session_1", guestId: "guest_1" },
      { type: "copy_activated", scenarioSessionId: "session_1", guestId: "guest_1" },
    ]);
  });
});

// The real backend's runtime-config endpoint is product-scoped, not scenario-scoped -- it lists
// all three modes' scenarios in one response (proven at the bundle level by
// apps/platform-api/tests/test_client_update_writer_bundle.py). Building that full response
// (rather than runtimeConfigResponse()'s single-scenario default) matters for any mode-switcher
// test, since ProductRunPage caches it per (client, productId): a mode switch reuses this same
// response rather than fetching a fresh, mode-specific one.
function fullRuntimeConfigResponse(ids: (typeof MODE_IDS)[keyof typeof MODE_IDS]) {
  return runtimeConfigResponse(ids, {
    scenario_ids: Object.values(MODE_IDS).map((modeIds) => modeIds.scenarioId),
    scenarios: Object.values(MODE_IDS).map((modeIds) => ({
      scenario_id: modeIds.scenarioId,
      version: 1,
      allowed_next_actions: ["copy_result"],
      input_renderer_hint: { renderer: "json_schema", schema_ref: `${modeIds.productId}.input_v1`, schema_version: 1 },
      output_renderer_hint: { renderer: "json_schema", schema_ref: `${modeIds.productId}.output_v1`, schema_version: 1 },
    })),
  });
}

describe("ClientUpdateWriterProduct (mode switcher)", () => {
  it("defaults to Update mode and switches its own form fields when another mode is selected", async () => {
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client, calls } = makeClient({
      // RUNTIME_CONFIG is keyed by product id only, shared across all three modes. `key={modeId}`
      // still remounts ProductRunPage on switch (each mode's form values have an incompatible
      // shape), but ProductRunPage caches runtime config per (client, productId) -- code review
      // finding: it used to re-fetch identical runtime config on every mode switch -- so only one
      // RUNTIME_CONFIG response is needed. Identity and quota are deliberately NOT cached this way
      // (identity caches itself via guestStorage; an earlier attempt at caching quota the same way
      // went stale after a run actually consumed it -- code review finding), so those still queue
      // one response per mount.
      [routes.RUNTIME_CONFIG]: [fullRuntimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids), quotaResponse(MODE_IDS.reply_draft)],
    });

    render(<ClientUpdateWriterProduct client={client} />);

    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());
    expect((screen.getByRole("radio", { name: "Update" }) as HTMLInputElement).checked).toBe(true);

    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));

    await waitFor(() => expect(screen.getByLabelText("Client message")).toBeTruthy());
    expect(screen.queryByLabelText("Progress notes")).toBeNull();
    expect(calls.filter((call) => call.key === routes.RUNTIME_CONFIG)).toHaveLength(1);
  });

  it("reflects quota actually consumed by a run when switching modes, instead of a stale cached value", async () => {
    // Code review finding: an earlier attempt at caching quota across a mode switch never
    // invalidated after a run actually consumed it -- a guest who ran Update and then switched to
    // Reply Draft would still see the pre-run "3 of 3" forever. Quota is fetched fresh on every
    // mount here, so the second mount's own response (simulating what a backend with a quota
    // policy would report) must be what's shown. The mocked numbers are illustrative: this product
    // has no quota policy of its own today.
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    // QUOTA/GUEST_IDENTITY are keyed by product id only (both modes share the same
    // client_update_writer product id), so each is one FIFO queue covering both mounts, not two
    // separate per-mode keys.
    const { client } = makeClient({
      [routes.RUNTIME_CONFIG]: [fullRuntimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse()],
      [routes.QUOTA]: [
        quotaResponse(ids, { remaining_count: 3, used_count: 0 }),
        quotaResponse(MODE_IDS.reply_draft, { remaining_count: 2, used_count: 1 }),
      ],
      [routes.START]: [startResponse()],
      [routes.SESSION]: [sessionResponse()],
      [routes.RESULT]: [resultResponse(ids)],
    });

    render(<ClientUpdateWriterProduct client={client} />);
    await waitFor(() => expect(screen.getByText("3 of 3 Client Update Writer runs remaining.")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Still working on it." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copy" })).toBeTruthy());

    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    await waitFor(() => expect(screen.getByText("2 of 3 Client Update Writer runs remaining.")).toBeTruthy());
  });

  it("disables mode switching while a run is submitting or in progress, instead of abandoning it", async () => {
    // Code review finding [P1]: key={modeId} unmounts the active ProductRunPage the instant
    // another mode is picked -- its cleanup aborts the poll/result fetch, but the backend keeps
    // running an already-accepted scenario. A user could switch mode while "Writing…" and
    // permanently lose that run's result.
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client, resolveDeferred } = makeClientWithDeferredRoute(
      {
        // RUNTIME_CONFIG is cached per (client, productId) and must list all three modes'
        // scenarios (see fullRuntimeConfigResponse's own comment) -- only one is ever fetched.
        // GUEST_IDENTITY/QUOTA aren't cached, so the later switch to Reply Draft needs its own.
        [routes.RUNTIME_CONFIG]: [fullRuntimeConfigResponse(ids)],
        [routes.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse()],
        [routes.QUOTA]: [quotaResponse(ids), quotaResponse(MODE_IDS.reply_draft)],
        [routes.START]: [startResponse()],
        [routes.RESULT]: [resultResponse(ids, { output: { text: "Still going." } })],
      },
      routes.SESSION,
    );

    render(<ClientUpdateWriterProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Working on it still." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toMatch(/writing your update/i));

    // The run is still in flight (SESSION deferred) -- every mode radio, including the
    // already-checked Update one, must be disabled so the active run can't be abandoned.
    for (const label of ["Update", "Reply Draft", "Prepaid Request"]) {
      expect((screen.getByRole("radio", { name: label }) as HTMLInputElement).disabled).toBe(true);
    }

    // A click on a disabled radio is a no-op in the DOM -- this proves the guard actually prevents
    // the switch, not just that the input looks disabled.
    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    expect(screen.queryByLabelText("Client message")).toBeNull();
    expect(screen.getByLabelText("Progress notes")).toBeTruthy();

    resolveDeferred(sessionResponse());
    await waitFor(() => expect(screen.getByText("Still going.")).toBeTruthy());

    // The run settled -- mode switching is available again, and does switch mode now. Asserted
    // synchronously (no waitFor) right after the result text appears -- code review finding: an
    // earlier version notified the parent's busy state from a plain useEffect, which could still
    // be stale at this exact instant (result rendered, guard not yet lifted), silently dropping a
    // click landing in that window; onBusyChange now fires from a (isomorphic) layout effect, so
    // the whole child-settles -> parent-unblocks cascade is flushed before this line runs.
    expect((screen.getByRole("radio", { name: "Update" }) as HTMLInputElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    await waitFor(() => expect(screen.getByLabelText("Client message")).toBeTruthy());
  });

  it("keeps mode switching blocked through an ambiguous poll failure, and Try again continues the same logical run", async () => {
    // Code review finding [P1]: an accepted start whose poll then fails (timeout/connection loss)
    // lands on retryable-error, not running/submitting -- busy used to go back to false there,
    // so a mode switch could still remount and abandon a session the backend might still be
    // running, destroying pendingStart/the Idempotency-Key reattachment path. busy now also covers
    // any retryable-error reached with a live pendingStart, this ambiguous-poll case included.
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client, calls } = makeClient({
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids)],
      // Same Idempotency-Key handle retries START a second time -- both return the same session.
      [routes.START]: [startResponse(), startResponse()],
      // First poll GET fails outright (connection loss); the retry's poll GET then succeeds.
      [routes.SESSION]: [errorResponse(500, "internal_error"), sessionResponse()],
      [routes.RESULT]: [resultResponse(ids, { output: { text: "Reattached." } })],
    });

    render(<ClientUpdateWriterProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Working on it still." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() =>
      expect(screen.getByText("Lost connection while waiting for your result. Please try again.")).toBeTruthy(),
    );

    // The accepted start's own session may still be running server-side -- mode switching stays
    // blocked, and the form itself (not just the "Try again" control) is gated too.
    for (const label of ["Update", "Reply Draft", "Prepaid Request"]) {
      expect((screen.getByRole("radio", { name: label }) as HTMLInputElement).disabled).toBe(true);
    }
    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    expect(screen.queryByLabelText("Client message")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText("Reattached.")).toBeTruthy());

    // Reattached to the same logical run via the same Idempotency-Key, not a fresh one.
    const startCalls = calls.filter((call) => call.key === routes.START);
    expect(startCalls).toHaveLength(2);
    expect(idempotencyKeyOf(startCalls[0]!)).toBeTruthy();
    expect(idempotencyKeyOf(startCalls[1]!)).toBe(idempotencyKeyOf(startCalls[0]!));
    expect((screen.getByRole("radio", { name: "Update" }) as HTMLInputElement).disabled).toBe(false);
  });

  it("keeps mode switching blocked through an ambiguous /start failure itself, and Try again reuses the same Idempotency-Key", async () => {
    // Code review finding [P1]: the previous fix only covered the *poll* going ambiguous after an
    // already-accepted start. The start request itself can be just as ambiguous -- a network
    // failure/timeout/5xx on POST /start doesn't tell the client whether the backend already
    // created the session/job before the response was lost. runStart() lands on
    // retryable-error here too, without ever learning a scenarioSessionId, but pendingStart (with
    // its Idempotency-Key) is deliberately kept alive for exactly this case -- so `busy` must gate
    // on pendingStart itself, not on whether a session id happens to be known yet.
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client, calls } = makeClient({
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids)],
      // First START attempt is itself ambiguous (a lost/failed response, not a clean rejection);
      // the retry with the same Idempotency-Key is what the real backend would collapse onto
      // whatever it actually did with the first one.
      [routes.START]: [errorResponse(500, "internal_error"), startResponse()],
      [routes.SESSION]: [sessionResponse()],
      [routes.RESULT]: [resultResponse(ids, { output: { text: "Reattached from start." } })],
    });

    render(<ClientUpdateWriterProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Working on it still." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() =>
      expect(screen.getByText("Could not start Client Update Writer. Please try again.")).toBeTruthy(),
    );

    // The backend may have already accepted this start -- mode switching stays blocked even though
    // no scenarioSessionId was ever learned client-side.
    for (const label of ["Update", "Reply Draft", "Prepaid Request"]) {
      expect((screen.getByRole("radio", { name: label }) as HTMLInputElement).disabled).toBe(true);
    }
    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    expect(screen.queryByLabelText("Client message")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText("Reattached from start.")).toBeTruthy());

    const startCalls = calls.filter((call) => call.key === routes.START);
    expect(startCalls).toHaveLength(2);
    expect(idempotencyKeyOf(startCalls[0]!)).toBeTruthy();
    expect(idempotencyKeyOf(startCalls[1]!)).toBe(idempotencyKeyOf(startCalls[0]!));
    expect((screen.getByRole("radio", { name: "Update" }) as HTMLInputElement).disabled).toBe(false);
  });

  it("keeps mode switching blocked through a result-fetch-error, and Try again reveals the already-completed result", async () => {
    // Code review finding [P1]: result-fetch-error means the scenario session already completed
    // -- only the follow-up GET for the result failed. `busy` used to cover only
    // submitting/running/an ambiguous retryable-error, so a mode switch here could still remount
    // ProductRunPage and destroy the only handle (resultArtifactId) on an already-completed
    // result, permanently losing it.
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client } = makeClient({
      [routes.RUNTIME_CONFIG]: [runtimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids)],
      [routes.START]: [startResponse()],
      [routes.SESSION]: [sessionResponse()],
      [routes.RESULT]: [errorResponse(500, "internal_error"), resultResponse(ids, { output: { text: "Recovered." } })],
    });

    render(<ClientUpdateWriterProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Working on it still." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() =>
      expect(screen.getByText("Your result is ready, but we couldn't load it. Please try again.")).toBeTruthy(),
    );

    for (const label of ["Update", "Reply Draft", "Prepaid Request"]) {
      expect((screen.getByRole("radio", { name: label }) as HTMLInputElement).disabled).toBe(true);
    }
    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    expect(screen.queryByLabelText("Client message")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText("Recovered.")).toBeTruthy());
    expect((screen.getByRole("radio", { name: "Update" }) as HTMLInputElement).disabled).toBe(false);
  });

  it("unblocks mode switching right away on a deterministic /start rejection, unlike an ambiguous one", async () => {
    // Code review finding [P1]: `pendingStart !== null` over-blocked the UI on every non-quota,
    // non-guest-identity /start failure, including definite 4xx rejections (scenario_not_found,
    // idempotency_key_conflict, scenario_input_invalid, ...) that the backend validated and
    // rejected before ever creating a session -- there is nothing ambiguous left to protect there.
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client } = makeClient({
      // RUNTIME_CONFIG is cached per (client, productId) and must list all three modes' scenarios
      // (see fullRuntimeConfigResponse's own comment) -- the switch below mounts Reply Draft too.
      [routes.RUNTIME_CONFIG]: [fullRuntimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids), quotaResponse(MODE_IDS.reply_draft)],
      [routes.START]: [errorResponse(422, "scenario_input_invalid")],
    });

    render(<ClientUpdateWriterProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Working on it still." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() =>
      expect(screen.getByText("Could not start Client Update Writer. Please try again.")).toBeTruthy(),
    );

    for (const label of ["Update", "Reply Draft", "Prepaid Request"]) {
      expect((screen.getByRole("radio", { name: label }) as HTMLInputElement).disabled).toBe(false);
    }
    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    await waitFor(() => expect(screen.getByLabelText("Client message")).toBeTruthy());
  });

  it("still records copy_result when the mode is switched right after clicking Copy", async () => {
    // Code review finding [P2]: `busy` is false once a result is showing, so the mode radios are
    // enabled during a copy, and switching remounts (unmounts) ProductRunPage. Its copy_result
    // activation used to share the page's abort signal, so a switch while the clipboard write was
    // still pending cancelled it -- the text reached the clipboard but the journey's required
    // `copy_result` was silently lost. `init.signal` is the client's per-request signal.
    let resolveClipboard!: () => void;
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: vi.fn(() => new Promise<void>((resolve) => (resolveClipboard = resolve))) },
    });
    const ids = MODE_IDS.update;
    const routes = routesFor(ids);
    const { client, calls } = makeClient({
      [routes.RUNTIME_CONFIG]: [fullRuntimeConfigResponse(ids)],
      [routes.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse()],
      [routes.QUOTA]: [quotaResponse(ids), quotaResponse(MODE_IDS.reply_draft)],
      [routes.START]: [startResponse()],
      [routes.SESSION]: [sessionResponse()],
      [routes.RESULT]: [resultResponse(ids)],
      [routes.NEXT_ACTION]: [sessionResponse({ status: "completed" })],
    });

    render(<ClientUpdateWriterProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Progress notes")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "Still working on it." } });
    fireEvent.change(screen.getByLabelText("Tone"), { target: { value: "neutral" } });
    fireEvent.click(screen.getByRole("button", { name: "Write update" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copy" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
    await waitFor(() => expect(screen.getByLabelText("Client message")).toBeTruthy());
    resolveClipboard();
    await waitFor(() => expect(calls.some((call) => call.key === routes.NEXT_ACTION)).toBe(true));

    expect(calls.find((call) => call.key === routes.NEXT_ACTION)!.init.signal?.aborted).toBe(false);
  });
});
