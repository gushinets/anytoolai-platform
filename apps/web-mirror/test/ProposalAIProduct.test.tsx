import { makeRoutedFetchClient } from "@anytoolai/ce-kit/test/testUtils/routedFetchClient";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProposalAIProduct, type ProposalAIProductEvent } from "../src/products/proposalAi/ProposalAIProduct";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function errorResponse(status: number, code: string, message = "x"): Response {
  return jsonResponse(status, { error: { code, message, request_id: "req_1" } });
}

function guestIdentityResponse(guestId = "guest_1"): Response {
  return jsonResponse(200, { guest_id: guestId });
}

function runtimeConfigResponse(overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    product_id: "proposal_ai",
    frontend_ids: ["web_mirror"],
    frontends: [{ frontend_id: "web_mirror", type: "web", enabled: true }],
    scenario_ids: ["proposal_ai.generate_v1"],
    scenarios: [
      {
        scenario_id: "proposal_ai.generate_v1",
        version: 1,
        allowed_next_actions: ["copy_result"],
        input_renderer_hint: {
          renderer: "json_schema",
          schema_ref: "proposal_ai.generate_input_v1",
          schema_version: 1,
        },
        output_renderer_hint: {
          renderer: "json_schema",
          schema_ref: "kernel.schemas.compose_persuasive_text_output_v1",
          schema_version: 1,
        },
      },
    ],
    quota_summary: null,
    allowed_ui_capabilities: [],
    ...overrides,
  });
}

function quotaResponse(overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    guest_id: "guest_1",
    product_id: "proposal_ai",
    quota_policy_id: "proposal_ai.guest_quota_v1",
    quota_dimension: "product",
    dimension_key: "proposal_ai",
    scenario_id: null,
    unit: "scenario_run",
    period: "lifetime",
    limit_count: 3,
    used_count: 0,
    remaining_count: 3,
    exhausted: false,
    ...overrides,
  });
}

function startResponse(overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    scenario_session_id: "session_1",
    job_id: "job_1",
    status: "started",
    allowed_next_actions: [],
    result_artifact_id: null,
    ...overrides,
  });
}

function sessionResponse(overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    scenario_session_id: "session_1",
    job_id: "job_1",
    status: "completed",
    allowed_next_actions: ["copy_result"],
    result_artifact_id: "result_1",
    current_checkpoint_id: "checkpoint_1",
    ...overrides,
  });
}

function resultResponse(overrides: Record<string, unknown> = {}): Response {
  return jsonResponse(200, {
    result_artifact_id: "result_1",
    scenario_session_id: "session_1",
    job_id: "job_1",
    workflow_id: "proposal_ai.generate_v1",
    workflow_version: 1,
    schema_ref: "kernel.schemas.compose_persuasive_text_output_v1",
    schema_version: 1,
    created_at: "2026-09-10T00:00:00Z",
    output: { text: "Dear client, here is my proposal." },
    ...overrides,
  });
}

const GUEST_IDENTITY_ROUTE = "POST /v1/identity/guest";
const RUNTIME_CONFIG_ROUTE = "GET /v1/products/proposal_ai/runtime-config";
const QUOTA_ROUTE = "GET /v1/products/proposal_ai/quota";
const START_ROUTE = "POST /v1/products/proposal_ai/scenarios/proposal_ai.generate_v1/start";
const SESSION_ROUTE = "GET /v1/scenario-sessions/session_1";
const RESULT_ROUTE = "GET /v1/results/result_1";
const NEXT_ACTION_ROUTE = "POST /v1/scenario-sessions/session_1/next-actions/copy_result";

function makeClient(routes: Record<string, Array<Response | (() => Response)>>) {
  return makeRoutedFetchClient("https://api.example.com", routes);
}

function fillValidForm() {
  fireEvent.change(screen.getByLabelText("Describe the task"), {
    target: { value: "Build a landing page for a bakery." },
  });
  fireEvent.change(screen.getByLabelText("Your positioning"), {
    target: { value: "Frontend freelancer with 5 years of experience." },
  });
}

beforeEach(() => {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(() => Promise.resolve()) },
  });
});

describe("ProposalAIProduct", () => {
  it("loads runtime config, guest identity, and advisory quota, then shows the form", async () => {
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
    });

    render(<ProposalAIProduct client={client} />);

    expect(screen.getByRole("status").textContent).toMatch(/loading/i);
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("3 of 3 proposals remaining.")).toBeTruthy());
  });

  it("blocks submission and shows field errors for empty required fields, without starting a scenario", async () => {
    const { client, calls } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
    });

    render(<ProposalAIProduct client={client} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Generate proposal" })).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    expect(await screen.findAllByText("Task description is required.")).toHaveLength(1);
    expect(calls.some((call) => call.key === START_ROUTE)).toBe(false);
  });

  it("runs the full happy path: submit, poll to completion, render the canonical text, and copy triggers the next action", async () => {
    const { client, calls } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
      [NEXT_ACTION_ROUTE]: [sessionResponse({ status: "completed" })],
    });

    render(<ProposalAIProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());
    expect(calls.some((call) => call.key === START_ROUTE)).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    await waitFor(() => expect(calls.some((call) => call.key === NEXT_ACTION_ROUTE)).toBe(true));
    const nextActionCall = calls.find((call) => call.key === NEXT_ACTION_ROUTE);
    expect(JSON.parse(nextActionCall?.init.body as string)).toEqual({ checkpoint_id: "checkpoint_1" });
  });

  it("enters a quota-exhausted state from the advisory quota check, with no form and no scenario started", async () => {
    const { client, calls } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse({ used_count: 3, remaining_count: 0, exhausted: true })],
    });

    render(<ProposalAIProduct client={client} />);

    await waitFor(() => expect(screen.getByText("You've used all your ProposalAI runs for now.")).toBeTruthy());
    expect(screen.queryByLabelText("Describe the task")).toBeNull();
    expect(calls.some((call) => call.key === START_ROUTE)).toBe(false);
  });

  it("enters a quota-exhausted state when the authoritative start rejects with 429, showing no fake progress", async () => {
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [errorResponse(429, "quota_exhausted")],
    });

    render(<ProposalAIProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    await waitFor(() => expect(screen.getByText("You've used all your ProposalAI runs for now.")).toBeTruthy());
    expect(screen.queryByRole("status", { name: /generating/i })).toBeNull();
  });

  it("preserves entered form values and retries with the same Idempotency-Key after a retryable start failure", async () => {
    const { client, calls } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [errorResponse(500, "internal_error"), startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
    });

    render(<ProposalAIProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();

    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not start proposalai/i));

    // Values must still be in the form -- a recoverable failure must not reset them.
    expect((screen.getByLabelText("Describe the task") as HTMLTextAreaElement).value).toBe(
      "Build a landing page for a bakery.",
    );

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());
    const startCalls = calls.filter((call) => call.key === START_ROUTE);
    expect(startCalls).toHaveLength(2);
    const firstKey = (startCalls[0]?.init.headers as Headers).get("Idempotency-Key");
    const secondKey = (startCalls[1]?.init.headers as Headers).get("Idempotency-Key");
    expect(firstKey).toBeTruthy();
    expect(firstKey).toBe(secondKey);
  });

  it("keeps the copied result readable when the copy_result next-action call fails", async () => {
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
      [NEXT_ACTION_ROUTE]: [errorResponse(500, "internal_error")],
    });

    render(<ProposalAIProduct client={client} />);
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy();
  });

  it("reports the full funnel to an injected onEvent handler, with no form/result text in any payload", async () => {
    const events: ProposalAIProductEvent[] = [];
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
      [NEXT_ACTION_ROUTE]: [sessionResponse({ status: "completed" })],
    });

    render(<ProposalAIProduct client={client} onEvent={(event) => events.push(event)} />);
    await waitFor(() => expect(events).toEqual([{ type: "product_viewed" }]));

    fillValidForm();
    expect(events).toEqual([{ type: "product_viewed" }, { type: "form_started" }]);

    // A second field edit must not emit a second "form_started".
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Updated positioning." } });
    expect(events.filter((event) => event.type === "form_started")).toHaveLength(1);

    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());
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
    expect(serialized).not.toContain("bakery");
    expect(serialized).not.toContain("Dear client");
  });

  it("emits copy_activated even when the completed session has no checkpoint id, only skipping the next-action call", async () => {
    const events: ProposalAIProductEvent[] = [];
    const { client, calls } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [startResponse()],
      [SESSION_ROUTE]: [sessionResponse({ current_checkpoint_id: null })],
      [RESULT_ROUTE]: [resultResponse()],
    });

    render(<ProposalAIProduct client={client} onEvent={(event) => events.push(event)} />);
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() =>
      expect(events.some((event) => event.type === "copy_activated")).toBe(true),
    );
    expect(calls.some((call) => call.key === NEXT_ACTION_ROUTE)).toBe(false);
  });

  it("retrying after a failed submission emits a second form_submitted", async () => {
    const events: ProposalAIProductEvent[] = [];
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [errorResponse(500, "internal_error"), startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
    });

    render(<ProposalAIProduct client={client} onEvent={(event) => events.push(event)} />);
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not start proposalai/i));

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());

    expect(events.filter((event) => event.type === "form_submitted")).toHaveLength(2);
  });

  it("keeps working with no onEvent handler at all", async () => {
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
    });

    render(<ProposalAIProduct client={client} />);

    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });

  it("does not let a throwing onEvent handler break the page through the full flow", async () => {
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
    });

    render(
      <ProposalAIProduct
        client={client}
        onEvent={() => {
          throw new Error("handler boom");
        }}
      />,
    );

    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });

  it("does not let an async onEvent handler's rejection break the page", async () => {
    const { client } = makeClient({
      [RUNTIME_CONFIG_ROUTE]: [runtimeConfigResponse()],
      [GUEST_IDENTITY_ROUTE]: [guestIdentityResponse()],
      [QUOTA_ROUTE]: [quotaResponse()],
      [START_ROUTE]: [startResponse()],
      [SESSION_ROUTE]: [sessionResponse()],
      [RESULT_ROUTE]: [resultResponse()],
    });

    render(
      <ProposalAIProduct
        client={client}
        // Deliberately a Promise-returning handler -- exactly the shape emitEvent() must survive
        // (TS's `() => void` accepts an `async` handler structurally; see emitEvent()'s docstring).
        // eslint-disable-next-line @typescript-eslint/no-misused-promises
        onEvent={() => Promise.reject(new Error("async handler boom"))}
      />,
    );

    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fillValidForm();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByText("Dear client, here is my proposal.")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });
});
