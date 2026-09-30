// Shared runtime behavior added for cross-product handoff: attaching to an already-queued session
// (`attachSessionId`) and the handoff button (`ProductDefinition.handoff`). Proven against the
// test-only product, like the rest of the runtime.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import {
  RESULT_TEXT,
  errorResponse,
  guestIdentityResponse,
  jsonResponse,
  makeClientCapturingRequests,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
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
    expect(events.filter((event) => event.type === "scenario_completed")).toEqual([
      expect.objectContaining({ scenarioSessionId: "session_1", resultViewed: true }),
    ]);
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

  it("ends in the run-failed state when the attached session failed", async () => {
    const { client } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [sessionResponse({ status: "failed", result_artifact_id: null })] }),
    );
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
  });

  it("ends in the run-failed state, without a retry loop, for a session id that does not exist", async () => {
    const { client, calls } = makeClientCapturingRequests(
      attachRoutes({ [ROUTES.SESSION]: [errorResponse(404, "scenario_session_not_found")] }),
    );
    render(<ProductRunPage definition={testProductDefinition} client={client} attachSessionId="session_1" />);
    await waitFor(() => expect(screen.getByText(TEST_PRODUCT_MESSAGES_EN.run.runFailed)).toBeTruthy());
    expect(calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(1);
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
