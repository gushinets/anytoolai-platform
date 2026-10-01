// Shared runtime behavior added for cross-product handoff: attaching to an already-queued session
// (`attachSessionId`) and the handoff button (`ProductDefinition.handoff`). Proven against the
// test-only product, like the rest of the runtime.
import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import { ProductShellContext } from "../src/products/runtime/ProductShellContext";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import {
  RESULT_TEXT,
  errorResponse,
  guestIdentityResponse,
  jsonResponse,
  makeClientCapturingRequests,
  makeClientWithDeferredCalls,
  makeClientWithDeferredRoute,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
  type RouteQueues,
} from "./fixtures/platformResponses";
import {
  TEST_PRODUCT_IDS,
  TEST_PRODUCT_MESSAGES_EN,
  testProductDefinition,
} from "./fixtures/testProductDefinition";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const render = makeRender(englishForAllLocales(TEST_PRODUCT_MESSAGES_EN));
const ROUTES = routesFor(TEST_PRODUCT_IDS);
const HANDOFFS_ROUTE = "POST /v1/handoffs";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(() => Promise.resolve()) },
  });
});

function attachRoutes(extra: RouteQueues = {}): RouteQueues {
  return {
    [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(TEST_PRODUCT_IDS)],
    [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
    [ROUTES.QUOTA]: [quotaResponse(TEST_PRODUCT_IDS)],
    [ROUTES.SESSION]: [sessionResponse()],
    [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS)],
    ...extra,
  };
}

describe("ProductRunPage attachSessionId", () => {
  it("renders the queued session's result without a start request, and reports completion once", async () => {
    const { client, calls } = makeClientCapturingRequests(attachRoutes());
    const events: ProductRunEvent[] = [];
    render(
      <StrictMode>
        <ProductRunPage
          definition={testProductDefinition}
          client={client}
          attachSessionId="session_1"
          onEvent={(event) => events.push(event)}
        />
      </StrictMode>,
    );

    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
    expect(calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(1);
    // Emitted from an effect after the result commits, so wait for it rather than racing the text.
    await waitFor(() =>
      expect(events.filter((event) => event.type === "scenario_completed")).toEqual([
        expect.objectContaining({ scenarioSessionId: "session_1", resultViewed: true }),
      ]),
    );
    // No local input, so nothing to compare against: no "previous details" notice; form stays empty.
    expect(screen.queryByText("Created from previous details")).toBeNull();
    expect((screen.getByLabelText("Text") as HTMLTextAreaElement).value).toBe("");
  });

  it("lets the user copy the attached result and start a new task", async () => {
    const { client, calls } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.NEXT_ACTION]: [sessionResponse({ status: "completed" })] }),
    );
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(calls.some((call) => call.key === ROUTES.NEXT_ACTION)).toBe(true));

    fireEvent.click(screen.getByRole("button", { name: "New task" }));
    expect(screen.queryByText(RESULT_TEXT)).toBeNull();
  });

  it("keeps polling the attached session when the onAttachBegin callback throws", async () => {
    const { client } = makeClientCapturingRequests(attachRoutes());
    render(
      <ProductRunPage
        definition={testProductDefinition}
        client={client}
        attachSessionId="session_1"
        onAttachBegin={() => {
          throw new Error("callback broke");
        }}
      />,
    );
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
  });

  it.each([
    ["throws synchronously", () => { throw new Error("callback broke"); }],
    ["rejects asynchronously", () => Promise.reject(new Error("callback broke")) as unknown as void],
  ])("still shows the run-failed state when the onAttachEnd callback %s", async (_name, onAttachEnd) => {
    const { client } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [sessionResponse({ status: "failed", result_artifact_id: null })] }),
    );
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onAttachEnd={onAttachEnd} />);
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
  });

  it("locks the mode switch while the attached session boots, but only tells the shell a run is in progress once it polls", async () => {
    const locked: boolean[] = [];
    const reportBusy = vi.fn();
    const { client, resolveCall } = makeClientWithDeferredCalls(attachRoutes(), { [ROUTES.RUNTIME_CONFIG]: 1, [ROUTES.SESSION]: 1 });
    render(
      <ProductShellContext.Provider value={{ reportBusy }}>
        <ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onLockedChange={(l) => locked.push(l)} />
      </ProductShellContext.Provider>,
    );
    await waitFor(() => expect(locked.at(-1)).toBe(true)); // booting: the mode switch is locked ...
    expect(reportBusy).not.toHaveBeenCalledWith(true); // ... but no run is on screen yet

    resolveCall(ROUTES.RUNTIME_CONFIG, 0, runtimeConfigResponse(TEST_PRODUCT_IDS));
    await waitFor(() => expect(reportBusy).toHaveBeenCalledWith(true)); // polling (session still pending): a run now

    resolveCall(ROUTES.SESSION, 0, sessionResponse());
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    expect(locked.at(-1)).toBe(false);
  });

  it("tells the route the attached result was left when the user clicks New task", async () => {
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests(attachRoutes());
    render(
      <ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onAttachEnd={ended} />,
    );
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    expect(ended).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "New task" }));
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it("ends in the run-failed state when the attached session failed", async () => {
    const { client } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [sessionResponse({ status: "failed", result_artifact_id: null })] }),
    );
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
  });

  it("tells the route to stop restoring an attached session that ended in a terminal failure", async () => {
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [sessionResponse({ status: "failed", result_artifact_id: null })] }),
    );
    render(
      <ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onAttachEnd={ended} />,
    );
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it("does not end an attach for an ordinary run that fails", async () => {
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests({
      ...attachRoutes(),
      [ROUTES.START]: [jsonResponse(200, { scenario_session_id: "session_1", job_id: "job_1", status: "started", allowed_next_actions: [], result_artifact_id: null })],
      [ROUTES.SESSION]: [sessionResponse({ status: "failed", result_artifact_id: null })],
    });
    render(<ProductRunPage definition={testProductDefinition} client={client} onAttachEnd={ended} />);
    await waitFor(() => expect(screen.getByLabelText("Text")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "hello" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
    expect(ended).not.toHaveBeenCalled();
  });

  it("ends in the run-failed state, without a retry loop, for a session id that does not exist", async () => {
    const { client, calls } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [errorResponse(404, "scenario_session_not_found")] }),
    );
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
    expect(calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(1);
  });

  it("stays busy through an ambiguous poll failure of the attached session, and Try again polls the same session", async () => {
    // Same rule as a started run's pendingStart: the queued session may still be running server-side, so
    // a mode switch (which remounts and drops the attach) must stay blocked until it has a result.
    const busy: boolean[] = [];
    const { client, calls } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [errorResponse(500, "internal_error"), sessionResponse()] }),
    );
    render(
      <ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onLockedChange={(b) => busy.push(b)} />,
    );
    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy());
    expect(busy.at(-1)).toBe(true);
    expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    expect(busy.at(-1)).toBe(false);
    expect(calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(2);
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("fails closed on a shape-compatible result from another scenario (its schema ref is not this scenario's)", async () => {
    const events: ProductRunEvent[] = [];
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests(
      attachRoutes({
        // Same output shape the product parser accepts, but produced by a different scenario.
        [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS, { schema_ref: "other_product.output_v1" })],
      }),
    );
    render(
      <ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onEvent={(e) => events.push(e)} onAttachEnd={ended} />,
    );
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
    expect(screen.queryByText(RESULT_TEXT)).toBeNull();
    expect(events.filter((e) => e.type === "scenario_completed")).toHaveLength(0);
    // A foreign session is dropped from the persisted attach state too.
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it("fails closed on the right schema ref at another schema version (an older session after a version bump)", async () => {
    const events: ProductRunEvent[] = [];
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests(
      attachRoutes({
        // runtimeConfigResponse declares `schema_version: 1` for the output; this artifact is version 0.
        [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS, { schema_version: 0 })],
      }),
    );
    render(
      <ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onEvent={(e) => events.push(e)} onAttachEnd={ended} />,
    );
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
    expect(screen.queryByText(RESULT_TEXT)).toBeNull();
    expect(events.filter((e) => e.type === "scenario_completed")).toHaveLength(0);
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it("lets the user leave an attached result with New task even when guest identity resolution failed", async () => {
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.GUEST_IDENTITY]: [errorResponse(500, "internal_error")] }),
    );
    render(
      <ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onAttachEnd={ended} />,
    );
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "New task" }));
    expect(screen.queryByText(RESULT_TEXT)).toBeNull();
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it("retries by re-polling the attached session, without validating the form or starting a run", async () => {
    const { client, calls } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [errorResponse(500, "internal_error"), sessionResponse()] }),
    );
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "typed meanwhile" } });
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    expect(calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(2);
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });
});

describe("ProductRunPage handoff button", () => {
  const withHandoff = {
    ...testProductDefinition,
    handoff: { handoffDefinitionId: "test_to_next_v1", targetProductId: "next_product" },
  };

  function renderWithResult(extra: RouteQueues = {}) {
    const made = makeClientCapturingRequests(attachRoutes(extra));
    render(<ProductRunPage definition={withHandoff} client={made.client} attachSessionId="session_1" />);
    return made;
  }

  it("creates the handoff for the shown result and opens its consent page in the same tab", async () => {
    const assign = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      origin: "https://web.example.com",
      pathname: "/base/products/test_product",
      assign,
    } as unknown as Location);
    const { calls } = renderWithResult({
      [HANDOFFS_ROUTE]: [
        jsonResponse(200, {
          handoff_id: "handoff_1",
          handoff_token: "tok en",
          status: "created",
          expires_at: "2026-09-30T00:00:00Z",
        }),
      ],
    });
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Continue to next tool" }));

    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://web.example.com/base/handoff/tok%20en"));
    const call = calls.find((c) => c.key === HANDOFFS_ROUTE);
    expect(JSON.parse(call?.init.body as string)).toEqual({
      handoff_definition_id: "test_to_next_v1",
      source_scenario_session_id: "session_1",
      source_artifact_id: "result_1",
    });
  });

  /** A normal (not attached) run that has completed, with a deferred `POST /v1/handoffs`. */
  async function completedRunWithPendingHandoff() {
    const assign = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      origin: "https://web.example.com",
      pathname: "/products/test_product",
      assign,
    } as unknown as Location);
    const busy: boolean[] = [];
    const made = makeClientWithDeferredRoute(
      {
        ...attachRoutes(),
        [ROUTES.START]: [startResponse(), startResponse()],
        [ROUTES.SESSION]: [sessionResponse(), sessionResponse()],
        [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS), resultResponse(TEST_PRODUCT_IDS)],
      },
      HANDOFFS_ROUTE,
    );
    render(<ProductRunPage definition={withHandoff} client={made.client} onLockedChange={(b) => busy.push(b)} />);
    await waitFor(() => expect(screen.getByLabelText("Text")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "first" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Continue to next tool" }));
    await waitFor(() => expect(busy.at(-1)).toBe(true));
    return { ...made, assign, busy };
  }

  it("refuses a new run while the handoff is being created (the handler, not only the disabled button), then navigates for the result it was made from", async () => {
    const { calls, resolveDeferred, assign } = await completedRunWithPendingHandoff();
    const starts = () => calls.filter((call) => call.key === ROUTES.START).length;
    expect(starts()).toBe(1);

    // The form is locked, and a submit that reaches the handler anyway (Enter, a stale handler) is refused.
    expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Run again" }) as HTMLButtonElement).disabled).toBe(true);
    // ... and the person is told why: a status line, and the Continue button is busy.
    expect(screen.getByRole("status").textContent).toBe("Opening the next step…");
    expect(screen.getByRole("button", { name: "Continue to next tool" }).getAttribute("aria-busy")).toBe("true");
    fireEvent.submit(screen.getByLabelText("Text").closest("form")!);
    expect(starts()).toBe(1);

    resolveDeferred(
      jsonResponse(200, { handoff_id: "handoff_1", handoff_token: "tok", status: "created", expires_at: "2026-09-30T00:00:00Z" }),
    );
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://web.example.com/handoff/tok"));
    expect(starts()).toBe(1);
  });

  it("stays locked, with a visible status, once the navigation started (no timer), and a bfcache return resets it", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      const { resolveDeferred, assign, busy } = await completedRunWithPendingHandoff();
      resolveDeferred(
        jsonResponse(200, { handoff_id: "handoff_1", handoff_token: "tok", status: "created", expires_at: "2026-09-30T00:00:00Z" }),
      );
      await waitFor(() => expect(assign).toHaveBeenCalled());
      expect(screen.getByRole("status").textContent).toBe("Opening the next step…");

      // However long the navigation takes the page is still the old one, and it must not unlock.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(60_000);
      });
      expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(true);
      expect((screen.getByRole("button", { name: "New task" }) as HTMLButtonElement).disabled).toBe(true);
      expect(busy.at(-1)).toBe(true);

      // Back/forward cache restores this very page: only then is it usable again.
      act(() => {
        window.dispatchEvent(Object.assign(new Event("pageshow"), { persisted: true }));
      });
      expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(false);
      expect(screen.queryByText("Opening the next step…")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("lets the person out of a navigation that never happened (Esc, Stop) with an explicit action", async () => {
    const { resolveDeferred, assign } = await completedRunWithPendingHandoff();
    resolveDeferred(
      jsonResponse(200, { handoff_id: "handoff_1", handoff_token: "tok", status: "created", expires_at: "2026-09-30T00:00:00Z" }),
    );
    await waitFor(() => expect(assign).toHaveBeenCalled());
    expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(true);

    const stop = vi.spyOn(window, "stop").mockImplementation(() => undefined);
    fireEvent.click(screen.getByRole("button", { name: "Stay on this page" }));
    // It does not abort the document's other requests (a copy activation POST must survive).
    expect(stop).not.toHaveBeenCalled();
    expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(false);
    expect(screen.queryByText("Opening the next step…")).toBeNull();
  });

  it("ends the attach when own work's result replaces the attached one on screen, not for typing, nor at submit", async () => {
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests({
      ...attachRoutes(),
      [ROUTES.START]: [startResponse()],
      [ROUTES.SESSION]: [sessionResponse(), sessionResponse()],
      [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS), resultResponse(TEST_PRODUCT_IDS)],
    });
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onAttachEnd={ended} />);
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "my own work" } });
    expect(ended).not.toHaveBeenCalled(); // typing alone says nothing
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(ended).toHaveBeenCalledTimes(1)); // the own result replaced it on screen

    // "New task" after the own run says nothing more about the attach.
    fireEvent.click(await screen.findByRole("button", { name: "New task" }));
    expect(ended).toHaveBeenCalledTimes(1);
  });

  it("keeps the attach when the person's own run fails to start (the attached result is still what is on screen)", async () => {
    const ended = vi.fn();
    const { client } = makeClientCapturingRequests({
      ...attachRoutes(),
      [ROUTES.START]: [errorResponse(500, "internal_error")],
    });
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" onAttachEnd={ended} />);
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "my own work" } });
    fireEvent.click(screen.getByRole("button", { name: "Run" }));
    await waitFor(() => expect(screen.getByRole("button", { name: /try again/i })).toBeTruthy());
    expect(ended).not.toHaveBeenCalled();
  });

  it("ends in the safe failure message, unlocked, when the navigation itself throws", async () => {
    const assign = vi.fn(() => {
      throw new Error("navigation blocked");
    });
    vi.spyOn(window, "location", "get").mockReturnValue({
      origin: "https://web.example.com",
      pathname: "/products/test_product",
      assign,
    } as unknown as Location);
    const { client } = makeClientCapturingRequests(
      attachRoutes({
        [HANDOFFS_ROUTE]: [
          jsonResponse(200, { handoff_id: "handoff_1", handoff_token: "tok", status: "created", expires_at: "2026-09-30T00:00:00Z" }),
        ],
      }),
    );
    render(<ProductRunPage definition={withHandoff} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Continue to next tool" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not open the next step/i));
    expect((screen.getByRole("button", { name: "New task" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("shows a safe message when the handoff cannot be created", async () => {
    renderWithResult({ [HANDOFFS_ROUTE]: [errorResponse(409, "handoff_not_eligible")] });
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Continue to next tool" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not open the next step/i));
  });

  it("does not carry a failure or an in-flight state over to the next result", async () => {
    renderWithResult({ [HANDOFFS_ROUTE]: [errorResponse(409, "handoff_not_eligible")] });
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Continue to next tool" }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "New task" }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("is hidden when the target product is not enabled in this deployment", async () => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_ENABLED_PRODUCT_IDS", "test_product");
    renderWithResult();
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    expect(screen.queryByRole("button", { name: "Continue to next tool" })).toBeNull();
  });

  it("is absent for a definition without a handoff", async () => {
    const { client } = makeClientCapturingRequests(attachRoutes());
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
    expect(screen.queryByRole("button", { name: "Continue to next tool" })).toBeNull();
  });
});
