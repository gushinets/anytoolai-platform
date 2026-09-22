// ProposalAI's own meaning only -- fields and their validation copy, the mapping to
// `proposal_ai.generate_input_v1`, the canonical `text` field, and the `copy_result`
// activation. The shared runtime behavior it rides on is proven in ProductRunPage.test.tsx.
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProposalAIProduct, proposalAiDefinition } from "../src/products/proposalAi/ProposalAIProduct";
import {
  guestIdentityResponse,
  makeClient,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
} from "./fixtures/platformResponses";
import { PROPOSAL_AI_MESSAGES } from "../src/products/proposalAi/messages";
import { makeRender } from "./support/renderWithI18n";

const render = makeRender(PROPOSAL_AI_MESSAGES);

const IDS = { productId: "proposal_ai", scenarioId: "proposal_ai.generate_v1" } as const;
const ROUTES = routesFor(IDS);
const PROPOSAL_TEXT = "Dear client, here is my proposal.";

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

function renderReady() {
  const routed = makeClient({
    [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
    [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
    [ROUTES.QUOTA]: [quotaResponse(IDS, { limit_count: 10, remaining_count: 10 })],
    [ROUTES.START]: [startResponse()],
    [ROUTES.SESSION]: [sessionResponse()],
    [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })],
    [ROUTES.NEXT_ACTION]: [sessionResponse()],
  });
  render(<ProposalAIProduct client={routed.client} />);
  return routed;
}

describe("ProposalAI product definition", () => {
  it("is registered under its backend product id with ProposalAI copy", async () => {
    expect(proposalAiDefinition.productId).toBe("proposal_ai");
    renderReady();

    await waitFor(() => expect(screen.getByRole("heading", { name: "ProposalAI" })).toBeTruthy());
    expect(screen.getByRole("button", { name: "Generate proposal" })).toBeTruthy();
    expect(screen.getByText("10 of 10 proposals remaining.")).toBeTruthy();
    expect(
      screen.getByText("Turn a client brief and your relevant strengths into a proposal ready to send."),
    ).toBeTruthy();
    expect(screen.getByPlaceholderText("Paste the client's task, brief, or job post.")).toBeTruthy();
    expect(
      screen.getByPlaceholderText("Describe the experience and strengths that make you a good fit."),
    ).toBeTruthy();
    expect(screen.getByRole("radiogroup", { name: "Proposal style" })).toBeTruthy();
    expect((screen.getByRole("radio", { name: "Warm & personable" }) as HTMLInputElement).checked).toBe(true);
    expect(screen.queryByLabelText(/Language/)).toBeNull();
  });

  it("validates its own fields client-side, mirroring generate_input.schema.json", async () => {
    const { calls } = renderReady();
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: " padded " } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    expect(await screen.findByText("Task description: required.")).toBeTruthy();
    expect(screen.getByText("Your positioning: no leading or trailing whitespace.")).toBeTruthy();
    const taskField = screen.getByLabelText("Describe the task");
    const positioningField = screen.getByLabelText("Your positioning");
    expect(taskField.getAttribute("aria-describedby")).toBe("proposal-ai-task-help proposal-ai-task-error");
    expect(positioningField.getAttribute("aria-describedby")).toBe(
      "proposal-ai-positioning-help proposal-ai-positioning-error",
    );
    for (const id of taskField.getAttribute("aria-describedby")!.split(" ")) {
      expect(document.getElementById(id)).toBeTruthy();
    }
    for (const id of positioningField.getAttribute("aria-describedby")!.split(" ")) {
      expect(document.getElementById(id)).toBeTruthy();
    }
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("maps the default warm style to the snake_case input schema and omits language", async () => {
    const { calls } = renderReady();
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    await waitFor(() => expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy());
    const startCall = calls.find((call) => call.key === ROUTES.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      input: { task_text: "Build a landing page.", freelancer_positioning: "Frontend freelancer.", tone: "warm" },
    });
    expect(JSON.parse(startCall?.init.body as string)).not.toHaveProperty("input.language");
  });

  it("maps the selected confident style to the firm backend value", async () => {
    const { calls } = renderReady();
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("radio", { name: "Confident & direct" }));
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    await waitFor(() => expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy());
    const startCall = calls.find((call) => call.key === ROUTES.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      input: { task_text: "Build a landing page.", freelancer_positioning: "Frontend freelancer.", tone: "firm" },
    });
    expect(JSON.parse(startCall?.init.body as string)).not.toHaveProperty("input.language");
  });

  it("renders the canonical `text` field and copies it through the copy_result next action", async () => {
    const { calls } = renderReady();
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());
    fireEvent.change(screen.getByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy());
    expect(screen.getByRole("button", { name: "Create another proposal" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(calls.some((call) => call.key === ROUTES.NEXT_ACTION)).toBe(true));
    const nextActionCall = calls.find((call) => call.key === ROUTES.NEXT_ACTION);
    expect(JSON.parse(nextActionCall?.init.body as string)).toEqual({ checkpoint_id: "checkpoint_1" });
  });

  it("treats a result without a string `text` field as unusable rather than rendering something else", () => {
    expect(proposalAiDefinition.extractResult({ text: "ok" })).toBe("ok");
    expect(proposalAiDefinition.extractResult({ angle: "x", rationale: "y" })).toBeNull();
    expect(proposalAiDefinition.extractResult({ text: 42 })).toBeNull();
  });
});
