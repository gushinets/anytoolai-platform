// Reuses ce-kit's own shared handoff preview fixture instead of a second hand-maintained copy of
// the same HandoffPreviewResponse shape -- see that fixture's docstring.
import { handoffPreviewPayload as previewPayload } from "@anytoolai/ce-kit/test/handoffs/fixtures";
// Reuses ce-kit's own routed-fetch-mock test util instead of a second hand-maintained
// implementation of the same "fake platform-api backend" purpose.
import { makeRoutedFetchClient } from "@anytoolai/ce-kit/test/testUtils/routedFetchClient";
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

function makeRoutedClient(routes: Record<string, Array<Response | (() => Response)>>) {
  return makeRoutedFetchClient("https://api.example.com", routes);
}

const GUEST_IDENTITY_ROUTE = "POST /v1/identity/guest";
const PREVIEW_ROUTE = "GET /v1/handoffs/token_abc";
const ACCEPT_ROUTE = "POST /v1/handoffs/token_abc/accept";
const DECLINE_ROUTE = "POST /v1/handoffs/token_abc/decline";

/** Makes `window.localStorage` itself throw synchronously (privacy-hardened browsers, storage-
 * denied sandboxed iframes) for the duration of `fn`, then restores it -- even if `fn` throws. */
async function withThrowingLocalStorage(fn: () => Promise<void>): Promise<void> {
  const originalDescriptor = Object.getOwnPropertyDescriptor(window, "localStorage");
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    get() {
      throw new DOMException("Storage access denied");
    },
  });
  try {
    await fn();
  } finally {
    if (originalDescriptor) {
      Object.defineProperty(window, "localStorage", originalDescriptor);
    }
  }
}

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

  it("renders a safe-error view instead of hanging on Loading forever if the mount fetch rejects", async () => {
    const { client } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
    });
    // getHandoff()/createGuestIdentity() always resolve today (see the .catch() this exercises),
    // so this forces the rejection a future change could introduce by overriding the method
    // directly, bypassing PlatformApiClient's own internal error handling entirely.
    client.createGuestIdentity = () => Promise.reject(new Error("boom"));

    render(<HandoffConsent client={client} handoffToken="token_abc" />);

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/went wrong/i));
  });

  it("recovers from a safe-error view via its Try again button instead of requiring a page reload", async () => {
    const { client, calls } = makeRoutedClient({
      [PREVIEW_ROUTE]: [errorResponse(500, "some_unexpected_backend_error"), jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse(), guestIdentityResponse()],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/went wrong/i));

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(screen.getByText("Kernel Demo")).toBeTruthy());
    expect(calls.filter((call) => call.key === PREVIEW_ROUTE)).toHaveLength(2);
  });

  it("renders the consent view but keeps Accept disabled when guest identity resolution fails, to avoid misattributing quota to the handoff creator", async () => {
    const { client, calls } = makeRoutedClient({
      [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
      [GUEST_IDENTITY_ROUTE]: [errorResponse(500, "internal_error")],
      [DECLINE_ROUTE]: [jsonResponse(200, previewPayload({ status: "declined" }))],
    });

    render(<HandoffConsent client={client} handoffToken="token_abc" />);
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/couldn't verify your identity/i));

    // No guestId means an accept would silently attribute quota to the handoff's creator
    // (HandoffService.accept() falls back to record.created_by_guest_id) instead of the person
    // accepting -- so Accept must stay unavailable rather than send guest_id-less request.
    const acceptButton = screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement;
    expect(acceptButton.disabled).toBe(true);
    fireEvent.click(acceptButton);
    expect(calls.some((call) => call.key === ACCEPT_ROUTE)).toBe(false);

    // Decline needs no guest attribution, so it stays available and works normally.
    const declineButton = screen.getByRole("button", { name: "Decline" }) as HTMLButtonElement;
    expect(declineButton.disabled).toBe(false);
    fireEvent.click(declineButton);
    await waitFor(() => expect(screen.getByText("declined")).toBeTruthy());
  });

  it("still resolves a guest identity and allows Accept when window.localStorage itself throws (storage-denied sandboxes)", async () => {
    await withThrowingLocalStorage(async () => {
      // resolveGuestIdentity() must catch the synchronous throw from window.localStorage and fall
      // back to an in-memory adapter -- still calling the backend to mint a real (if ephemeral)
      // guest id, rather than leaving Accept permanently disabled.
      const { client, calls } = makeRoutedClient({
        [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
        [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse("guest_ephemeral")],
        [ACCEPT_ROUTE]: [jsonResponse(200, previewPayload({ status: "accepted", target_scenario_session_id: "scenario_session_1" }))],
      });

      render(<HandoffConsent client={client} handoffToken="token_abc" />);
      await waitFor(() => expect(screen.getByRole("button", { name: "Accept" })).toBeTruthy());

      const acceptButton = screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement;
      expect(acceptButton.disabled).toBe(false);
      fireEvent.click(acceptButton);

      await waitFor(() => expect(screen.getByText("accepted")).toBeTruthy());
      const acceptCall = calls.find((call) => call.key === ACCEPT_ROUTE);
      expect(JSON.parse(acceptCall?.init.body as string)).toEqual({ guest_id: "guest_ephemeral" });
    });
  });

  it("resolves neither localStorage nor a guest identity, but still renders usably with Accept disabled", async () => {
    await withThrowingLocalStorage(async () => {
      // Both failures at once: the ephemeral fallback resolveGuestIdentity() reaches for after
      // catching the localStorage throw is itself a real backend call, and that call fails too.
      const { client } = makeRoutedClient({
        [PREVIEW_ROUTE]: [jsonResponse(200, previewPayload())],
        [GUEST_IDENTITY_ROUTE]: [errorResponse(500, "internal_error")],
      });

      render(<HandoffConsent client={client} handoffToken="token_abc" />);

      await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/couldn't verify your identity/i));
      expect(screen.getByText("Kernel Demo")).toBeTruthy();
      const acceptButton = screen.getByRole("button", { name: "Accept" }) as HTMLButtonElement;
      expect(acceptButton.disabled).toBe(true);
    });
  });

  it("self-heals a stale guest id via the ephemeral fallback even when clearing it from localStorage itself fails", async () => {
    const removeItemSpy = vi.spyOn(window.localStorage, "removeItem").mockImplementationOnce(() => {
      throw new DOMException("write restricted");
    });

    try {
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
      // If the failed removeItem() left "guest_stale" readable from localStorage,
      // createGuestIdentity() would short-circuit on that cached read and never reach the backend
      // a second time -- this assertion is what the ephemeral-fallback-on-failed-clear fix buys.
      expect(calls.filter((call) => call.key === GUEST_IDENTITY_ROUTE)).toHaveLength(2);

      fireEvent.click(screen.getByRole("button", { name: "Accept" }));

      await waitFor(() => expect(screen.getByText("accepted")).toBeTruthy());
      const acceptCalls = calls.filter((call) => call.key === ACCEPT_ROUTE);
      expect(JSON.parse(acceptCalls[1]?.init.body as string)).toEqual({ guest_id: "guest_fresh" });
    } finally {
      removeItemSpy.mockRestore();
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
