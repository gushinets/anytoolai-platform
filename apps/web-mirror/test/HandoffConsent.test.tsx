import { PlatformApiClient } from "@anytoolai/ce-kit";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { HandoffConsent } from "../src/components/HandoffConsent";

afterEach(() => {
  cleanup();
  // HandoffConsent persists guest identity to real window.localStorage (jsdom provides it) so it
  // survives remounts within a browser session -- clear it between tests so one test's minted
  // guest id can't leak into the next.
  window.localStorage.clear();
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function errorResponse(status: number, code: string, message = "x"): Response {
  return jsonResponse(status, { error: { code, message, request_id: "req_1" } });
}

function previewPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    handoff_id: "handoff_123",
    status: "created",
    source_product_id: "kernel_demo",
    source_product_display_name: "Kernel Demo",
    target_product_id: "freelancer_demo",
    target_product_display_name: "Freelancer Demo",
    target_scenario_id: "scenario_1",
    preview: { summary: "Two-step summary" },
    expires_at: "2026-01-01T00:10:00Z",
    target_scenario_session_id: null,
    target_job_id: null,
    ...overrides,
  };
}

function routeKey(url: string, method: string): string {
  return `${method} ${new URL(url).pathname}`;
}

/**
 * Dispatches by (method, path) instead of call order -- HandoffConsent fires the preview GET and
 * the guest-identity POST concurrently (`Promise.all`), so a purely positional mock would be
 * fragile to their actual interleaving. Each route is a FIFO queue so the same endpoint (e.g. the
 * preview GET, hit again on refetch) can return a different response on each call.
 */
function makeRoutedClient(routes: Record<string, Array<Response | (() => Response)>>): {
  client: PlatformApiClient;
  calls: Array<{ key: string; init: RequestInit }>;
} {
  const queues = new Map(Object.entries(routes).map(([key, responses]) => [key, [...responses]]));
  const calls: Array<{ key: string; init: RequestInit }> = [];
  const fetchImpl = vi.fn(async (url: string, init: RequestInit) => {
    const key = routeKey(url, init.method ?? "GET");
    calls.push({ key, init });
    const queue = queues.get(key);
    if (!queue || queue.length === 0) {
      throw new Error(`No mock response queued for ${key}`);
    }
    const next = queue.shift();
    return typeof next === "function" ? next() : (next as Response);
  });
  return {
    client: new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl: fetchImpl as unknown as typeof fetch }),
    calls,
  };
}

const GUEST_IDENTITY_ROUTE = "POST /v1/identity/guest";
const PREVIEW_ROUTE = "GET /v1/handoffs/token_abc";
const ACCEPT_ROUTE = "POST /v1/handoffs/token_abc/accept";
const DECLINE_ROUTE = "POST /v1/handoffs/token_abc/decline";

function guestIdentityResponse(guestId = "guest_1"): Response {
  return jsonResponse(200, { guest_id: guestId });
}

describe("HandoffConsent", () => {
  it("shows a loading state, then the consent view with source/target identity", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);

    expect(screen.getByRole("status").textContent).toMatch(/loading/i);
    await waitFor(() => expect(screen.getByText("Kernel Demo")).toBeTruthy());
    expect(screen.getByText("Freelancer Demo")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Decline" })).toBeTruthy();
  });

  it("renders preview fields as opaque key/value pairs", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload({ preview: { summary: "A brief" } }))],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);

    await waitFor(() => expect(screen.getByText("summary")).toBeTruthy());
    expect(screen.getByText("A brief")).toBeTruthy();
  });

  it("renders a not-found view for an unknown token", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [errorResponse(404, "handoff_not_found")],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/not valid/i));
  });

  it("renders a safe-error view for an unclassified error", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [errorResponse(500, "some_unexpected_backend_error")],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/went wrong/i));
  });

  it("renders the consent view without blocking when guest identity resolution fails, falling back to no guestId on accept", async () => {
    const { client, calls } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [errorResponse(500, "internal_error")],
      [ACCEPT_ROUTE]: [jsonResponse(200, previewPayload({ status: "accepted", target_scenario_session_id: "scenario_session_1" }))],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(calls.some((call) => call.key === ACCEPT_ROUTE)).toBe(true));
    const acceptCall = calls.find((call) => call.key === ACCEPT_ROUTE);
    expect(JSON.parse(acceptCall?.init.body as string)).toEqual({});
  });

  it("keeps the page usable when accessing window.localStorage itself throws (storage-denied sandboxes)", async () => {
    const originalDescriptor = Object.getOwnPropertyDescriptor(window, "localStorage");
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new DOMException("Storage access denied");
      },
    });

    try {
      // No GUEST_IDENTITY_ROUTE queued -- resolveGuestIdentity() must catch the synchronous throw
      // from constructing the adapter and never reach the network call.
      const { client } = makeRoutedClient({
        [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      });

      render(<HandoffConsent client={client} handoffToken="token_abc" />);

      await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());
    } finally {
      if (originalDescriptor) {
        Object.defineProperty(window, "localStorage", originalDescriptor);
      }
    }
  });

  it("reuses the persisted guest identity across remounts instead of minting a new one each time", async () => {
    const { client, calls } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload()), jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse("guest_persisted")],
    });

    const { unmount } = render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());
    unmount();

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    expect(calls.filter((call) => call.key === GUEST_IDENTITY_ROUTE)).toHaveLength(1);
  });

  it.each(["accepted", "declined", "consumed", "expired", "failed"])(
    "renders the %s terminal state directly from the initial GET, with no action buttons",
    async (status) => {
      const { client } = makeRoutedClient({
        [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload({ status }))],
        [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      });

      render(<HandoffConsent client={client} handoffToken="token_abc" />);

      await waitFor(() => expect(screen.getByText(status)).toBeTruthy());
      expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
      expect(screen.queryByRole("button", { name: "Decline" })).toBeNull();
    },
  );

  it("transitions to the accepted terminal view on a successful accept (non-immediate target), attributing quota to the acceptor's own guest id", async () => {
    const { client, calls } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse("guest_acceptor")],
      // A non-immediate target start policy attaches the session but queues no job yet, so the
      // record stays "accepted" rather than transitioning straight to "consumed" -- see
      // HandoffService.accept() (only `consume()`s when `linked.job is not None`).
      [ACCEPT_ROUTE]: [
        jsonResponse(
          200,
          previewPayload({
            status: "accepted",
            target_scenario_session_id: "scenario_session_1",
            target_job_id: null,
          }),
        ),
      ],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByText("accepted")).toBeTruthy());
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    const acceptCall = calls.find((call) => call.key === ACCEPT_ROUTE);
    expect(acceptCall).toBeTruthy();
    expect(JSON.parse(acceptCall?.init.body as string)).toEqual({ guest_id: "guest_acceptor" });
  });

  it("transitions directly to the consumed terminal view when an immediate target queues a job as part of accept", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      // An immediate target start policy queues a job as part of the same accept call, which the
      // backend transitions straight to "consumed" -- see HandoffService.accept()'s consume() call
      // when `linked.job is not None`.
      [ACCEPT_ROUTE]: [
        jsonResponse(
          200,
          previewPayload({
            status: "consumed",
            target_scenario_session_id: "scenario_session_1",
            target_job_id: "job_1",
          }),
        ),
      ],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByText("consumed")).toBeTruthy());
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  });

  it("transitions to the declined terminal view on a successful decline", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [DECLINE_ROUTE]: [jsonResponse(200, previewPayload({ status: "declined" }))],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Decline" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Decline" }));

    await waitFor(() => expect(screen.getByText("declined")).toBeTruthy());
  });

  it("on a stale accept that races an already-consumed token, refetches and renders the authoritative terminal state instead of retrying", async () => {
    const { client, calls } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload()), jsonResponse(200, previewPayload({ status: "consumed" }))],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [ACCEPT_ROUTE]: [errorResponse(409, "handoff_already_accepted")],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByText("consumed")).toBeTruthy());
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
    expect(calls.filter((call) => call.key === PREVIEW_ROUTE)).toHaveLength(2);
  });

  it("on an expired accept, refetches and renders the expired terminal state", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload()), jsonResponse(200, previewPayload({ status: "expired" }))],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [ACCEPT_ROUTE]: [errorResponse(410, "handoff_expired")],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByText("expired")).toBeTruthy());
  });

  it("on an accept that fails because the source session vanished, refetches and renders the resulting failed terminal state", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload()), jsonResponse(200, previewPayload({ status: "failed" }))],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [ACCEPT_ROUTE]: [errorResponse(500, "handoff_source_invalid")],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByText("failed")).toBeTruthy());
    expect(screen.queryByRole("button", { name: "Accept" })).toBeNull();
  });

  it("on an accept rejected because the accepting guest id itself doesn't resolve (404, pre-claim), shows an inline error instead of a pointless refetch", async () => {
    const { client, calls } = makeRoutedClient({
      // Two identical, still non-terminal preview responses queued: a refetch here (if the fix
      // regressed) would just return the same actionable preview, not a terminal status.
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload()), jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse("guest_stale"), guestIdentityResponse("guest_fresh")],
      [ACCEPT_ROUTE]: [errorResponse(404, "handoff_source_invalid")],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not be completed/i));
    expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy();
    expect(calls.filter((call) => call.key === PREVIEW_ROUTE)).toHaveLength(1);
  });

  it("on an accept rejected because the persisted guest id no longer resolves, clears it, mints a fresh one, and lets a retry succeed", async () => {
    const { client, calls } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse("guest_stale"), guestIdentityResponse("guest_fresh")],
      [ACCEPT_ROUTE]: [
        errorResponse(404, "handoff_source_invalid"),
        jsonResponse(200, previewPayload({ status: "accepted", target_scenario_session_id: "scenario_session_1" })),
      ],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not be completed/i));
    // Clearing the stale persisted id makes createGuestIdentity() miss its localStorage read on
    // retry and hit the backend again for a fresh one.
    expect(calls.filter((call) => call.key === GUEST_IDENTITY_ROUTE)).toHaveLength(2);

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByText("accepted")).toBeTruthy());
    const acceptCalls = calls.filter((call) => call.key === ACCEPT_ROUTE);
    expect(acceptCalls).toHaveLength(2);
    expect(JSON.parse(acceptCalls[1]?.init.body as string)).toEqual({ guest_id: "guest_fresh" });
  });

  it("on an accept against an unknown token, refetches and renders the not-found view", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload()), errorResponse(404, "handoff_not_found")],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [ACCEPT_ROUTE]: [errorResponse(404, "handoff_not_found")],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/not valid/i));
  });

  it("keeps the consent view and shows an inline error for an unclassified accept failure", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [ACCEPT_ROUTE]: [errorResponse(500, "internal_error")],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not be completed/i));
    expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy();
  });
});
