// The shared web product runtime, proven against the test-only product definition (ANY-453:
// "One test-only definition proves registration, form submission, scenario polling, canonical
// result rendering, next-action callback, retry, and quota/error behavior") -- no real product's
// meaning is in the loop here. ProposalAI's own meaning is covered in ProposalAIProduct.test.tsx.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProductRunPage, type ProductRunPageProps } from "../src/products/runtime/ProductRunPage";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import {
  RESULT_TEXT,
  errorResponse,
  guestIdentityResponse,
  idempotencyKeyOf,
  makeClient,
  makeClientCapturingRequests,
  makeClientWithDeferredRoute,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
  type RouteQueues,
} from "./fixtures/platformResponses";
import { TEST_PRODUCT_IDS, testProductDefinition, type TestProductValues } from "./fixtures/testProductDefinition";

const ROUTES = routesFor(TEST_PRODUCT_IDS);
const RUN_FAILED = testProductDefinition.copy.runFailed;

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

/** The three boot responses every ready-form test needs. */
function bootRoutes(): RouteQueues {
  return {
    [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(TEST_PRODUCT_IDS)],
    [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
    [ROUTES.QUOTA]: [quotaResponse(TEST_PRODUCT_IDS)],
  };
}

/** A complete successful run on top of bootRoutes(). */
function happyPathRoutes(): RouteQueues {
  return {
    ...bootRoutes(),
    [ROUTES.START]: [startResponse()],
    [ROUTES.SESSION]: [sessionResponse()],
    [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS)],
  };
}

type Props = Omit<ProductRunPageProps<TestProductValues, string>, "definition">;

function renderPage(props: Props) {
  return render(<ProductRunPage definition={testProductDefinition} {...props} />);
}

async function waitForForm() {
  await waitFor(() => expect(screen.getByLabelText("Text")).toBeTruthy());
}

function fillValidForm() {
  fireEvent.change(screen.getByLabelText("Text"), { target: { value: "Some input text." } });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
}

async function waitForResult() {
  await waitFor(() => expect(screen.getByText(RESULT_TEXT)).toBeTruthy());
}

describe("ProductRunPage", () => {
  it("loads runtime config, guest identity, and advisory quota, then shows the product's form", async () => {
    const { client } = makeClient(bootRoutes());

    renderPage({ client });

    expect(screen.getByRole("status").textContent).toMatch(/loading test product/i);
    await waitForForm();
    await waitFor(() => expect(screen.getByText("3 of 3 runs remaining.")).toBeTruthy());
    expect(screen.getByRole("heading", { name: "Test Product" })).toBeTruthy();
  });

  it("includes scenario_id in the advisory quota request, so a scenario-dimension quota policy is also supported", async () => {
    const { client, calls } = makeClientCapturingRequests(bootRoutes());

    renderPage({ client });
    await waitForForm();

    const quotaCall = calls.find((call) => call.key === ROUTES.QUOTA);
    expect(quotaCall).toBeTruthy();
    expect(new URL(quotaCall!.url).searchParams.get("scenario_id")).toBe(TEST_PRODUCT_IDS.scenarioId);
  });

  it("treats a runtime config with no enabled web frontend as unavailable, never falling back to an arbitrary frontend", async () => {
    const { client } = makeClient({
      [ROUTES.RUNTIME_CONFIG]: [
        runtimeConfigResponse(TEST_PRODUCT_IDS, {
          frontend_ids: ["web_mirror", "kernel_demo_ce"],
          frontends: [
            { frontend_id: "web_mirror", type: "web", enabled: false },
            { frontend_id: "kernel_demo_ce", type: "chrome_extension", enabled: true },
          ],
        }),
      ],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
    });

    renderPage({ client });

    await waitFor(() =>
      expect(screen.getByText("Test Product is unavailable right now. Please reload the page.")).toBeTruthy(),
    );
    expect(screen.queryByLabelText("Text")).toBeNull();
  });

  it("fires product_viewed exactly once even under React StrictMode's dev-only double-invoke of effects", async () => {
    const events: ProductRunEvent[] = [];
    // StrictMode's mount -> cleanup -> remount genuinely re-runs the boot effect's body (the
    // abort only stops the first invocation's own continuation from acting on its response, it
    // doesn't stop the fake fetch mock from "completing" the request) -- two responses queued per
    // route, matching how HandoffConsent.test.tsx's own remount test does this.
    const { client } = makeClient({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(TEST_PRODUCT_IDS), runtimeConfigResponse(TEST_PRODUCT_IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse(), guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(TEST_PRODUCT_IDS), quotaResponse(TEST_PRODUCT_IDS)],
    });

    render(
      <StrictMode>
        <ProductRunPage definition={testProductDefinition} client={client} onEvent={(event) => events.push(event)} />
      </StrictMode>,
    );

    await waitForForm();
    expect(events.filter((event) => event.type === "product_viewed")).toHaveLength(1);
  });

  it("blocks submission on the product's own validation errors, without starting a scenario", async () => {
    const { client, calls } = makeClient(bootRoutes());

    renderPage({ client });
    await waitForForm();

    submit();

    expect(await screen.findAllByText("Text is required.")).toHaveLength(1);
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("runs the full happy path: submit the product's input, poll to completion, render its result, and copy triggers its next action", async () => {
    const { client, calls } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.NEXT_ACTION]: [sessionResponse({ status: "completed" })],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();

    submit();

    await waitForResult();
    const startCall = calls.find((call) => call.key === ROUTES.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      frontend_id: "web_mirror",
      guest_id: "guest_1",
      input: { text: "Some input text." },
    });

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    await waitFor(() => expect(calls.some((call) => call.key === ROUTES.NEXT_ACTION)).toBe(true));
    const nextActionCall = calls.find((call) => call.key === ROUTES.NEXT_ACTION);
    expect(JSON.parse(nextActionCall?.init.body as string)).toEqual({ checkpoint_id: "checkpoint_1" });
  });

  it("enters a quota-exhausted state from the advisory quota check, with no form and no scenario started", async () => {
    const { client, calls } = makeClient({
      ...bootRoutes(),
      [ROUTES.QUOTA]: [quotaResponse(TEST_PRODUCT_IDS, { used_count: 3, remaining_count: 0, exhausted: true })],
    });

    renderPage({ client });

    await waitFor(() => expect(screen.getByText("You've used all your Test Product runs for now.")).toBeTruthy());
    expect(screen.queryByLabelText("Text")).toBeNull();
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("enters a quota-exhausted state when the authoritative start rejects with 429, showing no fake progress", async () => {
    const { client } = makeClient({
      ...bootRoutes(),
      [ROUTES.START]: [errorResponse(429, "quota_exhausted")],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();

    submit();

    await waitFor(() => expect(screen.getByText("You've used all your Test Product runs for now.")).toBeTruthy());
    expect(screen.queryByRole("status", { name: /running/i })).toBeNull();
  });

  it("does not let a late advisory quota response clobber an in-progress or completed run", async () => {
    const { client, resolveDeferred } = makeClientWithDeferredRoute(
      {
        [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(TEST_PRODUCT_IDS)],
        [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
        [ROUTES.START]: [startResponse()],
        [ROUTES.SESSION]: [sessionResponse()],
        [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS)],
      },
      ROUTES.QUOTA,
    );

    renderPage({ client });
    await waitForForm();
    fillValidForm();
    submit();
    await waitForResult();

    // The advisory quota GET only settles now, well after the run already completed -- exhausted,
    // as it would genuinely be after consuming the run this session just made.
    resolveDeferred(quotaResponse(TEST_PRODUCT_IDS, { used_count: 3, remaining_count: 0, exhausted: true }));

    // Confirms the response was actually processed (the advisory banner updates)...
    await waitFor(() => expect(screen.getByText("0 of 3 runs remaining.")).toBeTruthy());
    // ...without clobbering the already-completed run underneath it.
    expect(screen.getByText(RESULT_TEXT)).toBeTruthy();
    expect(screen.queryByText("You've used all your Test Product runs for now.")).toBeNull();
  });

  it("preserves entered form values and retries with the same Idempotency-Key after a retryable start failure", async () => {
    const { client, calls } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.START]: [errorResponse(500, "internal_error"), startResponse()],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();

    submit();
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not start test product/i));

    // Values must still be in the form -- a recoverable failure must not reset them.
    expect((screen.getByLabelText("Text") as HTMLTextAreaElement).value).toBe("Some input text.");

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitForResult();
    const startCalls = calls.filter((call) => call.key === ROUTES.START);
    expect(startCalls).toHaveLength(2);
    expect(idempotencyKeyOf(startCalls[0]!)).toBeTruthy();
    expect(idempotencyKeyOf(startCalls[0]!)).toBe(idempotencyKeyOf(startCalls[1]!));
  });

  it("starts a genuinely new logical submission (new Idempotency-Key) after a terminal execution failure, instead of replaying the dead session", async () => {
    const SECOND_SESSION_ROUTE = "GET /v1/scenario-sessions/session_2";
    const { client, calls } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.START]: [startResponse(), startResponse({ scenario_session_id: "session_2" })],
      [ROUTES.SESSION]: [sessionResponse({ status: "failed" })],
      [SECOND_SESSION_ROUTE]: [
        sessionResponse({ scenario_session_id: "session_2", status: "completed", result_artifact_id: "result_1" }),
      ],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();
    submit();

    await waitFor(() => expect(screen.getByText(RUN_FAILED)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    // Same, unchanged form values -- the natural case a user retries without editing anything.
    submit();

    await waitForResult();
    const startCalls = calls.filter((call) => call.key === ROUTES.START);
    expect(startCalls).toHaveLength(2);
    expect(idempotencyKeyOf(startCalls[0]!)).toBeTruthy();
    expect(idempotencyKeyOf(startCalls[1]!)).toBeTruthy();
    expect(idempotencyKeyOf(startCalls[0]!)).not.toBe(idempotencyKeyOf(startCalls[1]!));
  });

  it("also uses a new Idempotency-Key when the user bypasses \"Try again\" and clicks the form's own Submit button directly after a terminal execution failure", async () => {
    // unknown-error is grouped with the form-showing phases, so the ordinary submit button stays
    // enabled and reachable -- the fix must not rely on the user going through the dedicated
    // "Try again" control.
    const SECOND_SESSION_ROUTE = "GET /v1/scenario-sessions/session_2";
    const { client, calls } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.START]: [startResponse(), startResponse({ scenario_session_id: "session_2" })],
      [ROUTES.SESSION]: [sessionResponse({ status: "failed" })],
      [SECOND_SESSION_ROUTE]: [
        sessionResponse({ scenario_session_id: "session_2", status: "completed", result_artifact_id: "result_1" }),
      ],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();
    submit();
    await waitFor(() => expect(screen.getByText(RUN_FAILED)).toBeTruthy());

    // Same, unchanged form values -- directly hitting the form's own submit button, not "Try
    // again".
    submit();

    await waitForResult();
    const startCalls = calls.filter((call) => call.key === ROUTES.START);
    expect(startCalls).toHaveLength(2);
    expect(idempotencyKeyOf(startCalls[0]!)).toBeTruthy();
    expect(idempotencyKeyOf(startCalls[1]!)).toBeTruthy();
    expect(idempotencyKeyOf(startCalls[0]!)).not.toBe(idempotencyKeyOf(startCalls[1]!));
  });

  it("retries just the result fetch, without starting a new (quota-consuming) run, after a transient failure to fetch an already-completed session's result", async () => {
    const { client, calls } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.RESULT]: [errorResponse(500, "internal_error"), resultResponse(TEST_PRODUCT_IDS)],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();
    submit();

    await waitFor(() =>
      expect(screen.getByText("Your result is ready, but we couldn't load it. Please try again.")).toBeTruthy(),
    );
    // The run already succeeded -- no form to resubmit, so no risk of a second, wasteful run.
    expect(screen.queryByLabelText("Text")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitForResult();
    expect(calls.filter((call) => call.key === ROUTES.START)).toHaveLength(1);
    expect(calls.filter((call) => call.key === ROUTES.RESULT)).toHaveLength(2);
  });

  it("lands on the safe error state when the completed result is unusable by the product", async () => {
    const { client } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.RESULT]: [resultResponse(TEST_PRODUCT_IDS, { output: { unexpected: 42 } })],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();
    submit();

    await waitFor(() => expect(screen.getByText(RUN_FAILED)).toBeTruthy());
    expect(screen.queryByText(RESULT_TEXT)).toBeNull();
  });

  it("keeps the copied result readable when the next-action call fails", async () => {
    const { client } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.NEXT_ACTION]: [errorResponse(500, "internal_error")],
    });

    renderPage({ client });
    await waitForForm();
    fillValidForm();
    submit();
    await waitForResult();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(screen.getByText(RESULT_TEXT)).toBeTruthy();
  });

  it("reports the full funnel to an injected onEvent handler, with no form/result text in any payload", async () => {
    const events: ProductRunEvent[] = [];
    const { client } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.NEXT_ACTION]: [sessionResponse({ status: "completed" })],
    });

    renderPage({ client, onEvent: (event) => events.push(event) });
    await waitFor(() => expect(events).toEqual([{ type: "product_viewed" }]));

    fillValidForm();
    expect(events).toEqual([{ type: "product_viewed" }, { type: "form_started" }]);

    // A second field edit must not emit a second "form_started".
    fireEvent.change(screen.getByLabelText("Text"), { target: { value: "Edited input text." } });
    expect(events.filter((event) => event.type === "form_started")).toHaveLength(1);

    submit();
    await waitForResult();
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());

    expect(events).toEqual([
      { type: "product_viewed" },
      { type: "form_started" },
      { type: "form_submitted" },
      { type: "scenario_completed", scenarioSessionId: "session_1" },
      { type: "copy_activated", scenarioSessionId: "session_1" },
    ]);
    const serialized = JSON.stringify(events);
    expect(serialized).not.toContain("input text");
    expect(serialized).not.toContain(RESULT_TEXT);
  });

  it("emits copy_activated even when the completed session has no checkpoint id, only skipping the next-action call", async () => {
    const events: ProductRunEvent[] = [];
    const { client, calls } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.SESSION]: [sessionResponse({ current_checkpoint_id: null })],
    });

    renderPage({ client, onEvent: (event) => events.push(event) });
    await waitForForm();
    fillValidForm();
    submit();
    await waitForResult();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(events.some((event) => event.type === "copy_activated")).toBe(true));
    expect(calls.some((call) => call.key === ROUTES.NEXT_ACTION)).toBe(false);
  });

  it("retrying after a failed submission emits a second form_submitted", async () => {
    const events: ProductRunEvent[] = [];
    const { client } = makeClient({
      ...happyPathRoutes(),
      [ROUTES.START]: [errorResponse(500, "internal_error"), startResponse()],
    });

    renderPage({ client, onEvent: (event) => events.push(event) });
    await waitForForm();
    fillValidForm();
    submit();
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not start test product/i));

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitForResult();

    expect(events.filter((event) => event.type === "form_submitted")).toHaveLength(2);
  });

  it.each<{ label: string; onEvent: Props["onEvent"] }>([
    { label: "no handler at all", onEvent: undefined },
    {
      label: "a throwing handler",
      onEvent: () => {
        throw new Error("handler boom");
      },
    },
    {
      label: "an async handler that rejects",
      // Deliberately a Promise-returning handler -- exactly the shape emitEvent() must survive
      // (TS's `() => void` accepts an `async` handler structurally; see emitEvent()'s docstring).
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      onEvent: () => Promise.reject(new Error("async handler boom")),
    },
  ])("keeps working through the full flow with $label", async ({ onEvent }) => {
    const { client } = makeClient(happyPathRoutes());

    renderPage({ client, onEvent });

    await waitForForm();
    fillValidForm();
    submit();
    await waitForResult();
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });
});
