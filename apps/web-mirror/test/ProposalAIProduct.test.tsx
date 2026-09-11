// ProposalAI's own meaning only -- fields and their validation copy, the mapping to
// `proposal_ai.generate_input_v1`, the canonical `text` field, and the `copy_result`
// activation. The shared runtime behavior it rides on is proven in ProductRunPage.test.tsx.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    [ROUTES.QUOTA]: [quotaResponse(IDS)],
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
    expect(screen.getByText("3 of 3 proposals remaining.")).toBeTruthy();
  });

  it("validates its own fields client-side, mirroring generate_input.schema.json", async () => {
    const { calls } = renderReady();
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: " padded " } });
    fireEvent.change(screen.getByLabelText("Language (optional)"), { target: { value: "English" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    expect(await screen.findByText("Task description is required.")).toBeTruthy();
    expect(screen.getByText("Your positioning must not start or end with whitespace.")).toBeTruthy();
    expect(screen.getByText('Language must look like "en" or "en-US".')).toBeTruthy();
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("maps its fields to the snake_case input schema, omitting empty optional fields", async () => {
    const { calls } = renderReady();
    await waitFor(() => expect(screen.getByLabelText("Describe the task")).toBeTruthy());

    fireEvent.change(screen.getByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });
    fireEvent.change(screen.getByLabelText("Tone (optional)"), { target: { value: "warm" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    await waitFor(() => expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy());
    const startCall = calls.find((call) => call.key === ROUTES.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      input: { task_text: "Build a landing page.", freelancer_positioning: "Frontend freelancer.", tone: "warm" },
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

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(calls.some((call) => call.key === ROUTES.NEXT_ACTION)).toBe(true));
    expect(ROUTES.NEXT_ACTION.endsWith("/next-actions/copy_result")).toBe(true);
  });

  it("treats a result without a string `text` field as unusable rather than rendering something else", () => {
    expect(proposalAiDefinition.extractResult({ text: "ok" })).toBe("ok");
    expect(proposalAiDefinition.extractResult({ angle: "x", rationale: "y" })).toBeNull();
    expect(proposalAiDefinition.extractResult({ text: 42 })).toBeNull();
  });
});
