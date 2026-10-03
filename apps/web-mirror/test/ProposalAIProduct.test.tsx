// ProposalAI's own meaning only -- fields and their validation copy, the mapping to
// `proposal_ai.generate_input_v1`, the canonical `text` field, and the `copy_result`
// activation. The shared runtime behavior it rides on is proven in ProductRunPage.test.tsx.
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProposalAIProduct, proposalAiDefinition } from "../src/products/proposalAi/ProposalAIProduct";
import {
  errorResponse,
  guestIdentityResponse,
  idempotencyKeyOf,
  makeClient,
  makeClientWithDeferredCalls,
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
    [ROUTES.QUOTA]: [
      quotaResponse(IDS, { limit_count: 10, remaining_count: 10 }),
      quotaResponse(IDS, { limit_count: 10, used_count: 1, remaining_count: 9 }),
    ],
    [ROUTES.START]: [startResponse()],
    [ROUTES.SESSION]: [sessionResponse()],
    [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })],
    [ROUTES.NEXT_ACTION]: [sessionResponse()],
  });
  render(<ProposalAIProduct client={routed.client} />);
  return routed;
}

describe("ProposalAI product definition", () => {
  it("revalidates only the edited invalid field using its current product rules", async () => {
    const { calls } = renderReady();
    const task = await screen.findByLabelText("Describe the task");
    const positioning = screen.getByLabelText("Your positioning");
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    expect(task.getAttribute("aria-invalid")).toBe("true");
    // Required, whitespace and maxLength are the actual product validator's rules.
    for (const [value, message] of [
      ["   ", "Task description: required."],
      [" padded ", "Task description: no leading or trailing whitespace."],
      ["x".repeat(4001), "Task description: 4,000 characters maximum."],
    ]) {
      fireEvent.change(task, { target: { value } });
      fireEvent.blur(task);
      expect(task.getAttribute("aria-invalid")).toBe("true");
      expect(screen.getByText(message!)).toBeTruthy();
      expect(positioning.getAttribute("aria-invalid")).toBe("true");
    }
    fireEvent.change(task, { target: { value: "Build a landing page." } });
    fireEvent.blur(task);
    expect(task.getAttribute("aria-invalid")).toBe("false");
    expect(positioning.getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByText("Your positioning: required.")).toBeTruthy();
    expect(calls.filter((call) => call.key === ROUTES.START)).toHaveLength(0);
  });

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
    const language = screen.getByLabelText("Language");
    expect(screen.getByRole("heading", { name: "ProposalAI" }).parentElement?.contains(language)).toBe(true);
    expect(screen.getByRole("form", { name: "ProposalAI form" }).contains(language)).toBe(false);
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
    const copyButton = screen.getByRole("button", { name: "Copy" });
    const newTaskButton = screen.getByRole("button", { name: "New task" });
    expect(copyButton.parentElement).toBe(newTaskButton.parentElement);

    fireEvent.click(copyButton);

    await waitFor(() => expect(calls.some((call) => call.key === ROUTES.NEXT_ACTION)).toBe(true));
    const nextActionCall = calls.find((call) => call.key === ROUTES.NEXT_ACTION);
    expect(JSON.parse(nextActionCall?.init.body as string)).toEqual({ checkpoint_id: "checkpoint_1" });
  });

  it("keeps the task beside its result, shows when edits outdate it, and clears both for a new task", async () => {
    const routed = makeClientWithDeferredCalls({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [
        quotaResponse(IDS),
        quotaResponse(IDS, { used_count: 1, remaining_count: 2 }),
        quotaResponse(IDS, { used_count: 2, remaining_count: 1 }),
        quotaResponse(IDS, { used_count: 2, remaining_count: 1 }),
      ],
      [ROUTES.START]: [startResponse(), startResponse()],
      [ROUTES.SESSION]: [sessionResponse(), sessionResponse()],
      [ROUTES.NEXT_ACTION]: [],
    }, { [ROUTES.RESULT]: 2 });
    render(<ProposalAIProduct client={routed.client} />);
    const task = await screen.findByLabelText("Describe the task") as HTMLTextAreaElement;
    const positioning = screen.getByLabelText("Your positioning") as HTMLTextAreaElement;
    fireEvent.change(task, { target: { value: "Build a landing page." } });
    fireEvent.change(positioning, { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.RESULT)).toHaveLength(1));
    routed.resolveCall(ROUTES.RESULT, 0, resultResponse(IDS, { output: { text: PROPOSAL_TEXT } }));

    await screen.findByText(PROPOSAL_TEXT);
    expect(task.isConnected).toBe(true);
    expect(task.value).toBe("Build a landing page.");
    expect(positioning.value).toBe("Frontend freelancer.");
    fireEvent.change(task, { target: { value: "Build a mobile app." } });
    expect(screen.getByText("Created from previous details")).toBeTruthy();
    expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Regenerate proposal" }));
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.RESULT)).toHaveLength(2));
    expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy();
    expect(task.value).toBe("Build a mobile app.");
    routed.resolveCall(ROUTES.RESULT, 1, resultResponse(IDS, { output: { text: "Updated proposal." } }));
    await screen.findByText("Updated proposal.");
    expect(screen.queryByText("Created from previous details")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "New task" }));
    expect(task.value).toBe("");
    expect(positioning.value).toBe("");
    expect(screen.queryByText("Updated proposal.")).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(task));
  });

  it("regenerates unchanged details with a fresh start and one result-card progress notice", async () => {
    const routed = makeClientWithDeferredCalls({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [
        quotaResponse(IDS),
        quotaResponse(IDS, { used_count: 1, remaining_count: 2 }),
        quotaResponse(IDS, { used_count: 2, remaining_count: 1 }),
      ],
      [ROUTES.START]: [startResponse(), startResponse()],
      [ROUTES.SESSION]: [sessionResponse(), sessionResponse()],
    }, { [ROUTES.RESULT]: 2 });
    render(<ProposalAIProduct client={routed.client} />);
    fireEvent.change(await screen.findByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.RESULT)).toHaveLength(1));
    expect(screen.getAllByRole("status")).toHaveLength(1);
    routed.resolveCall(ROUTES.RESULT, 0, resultResponse(IDS, { output: { text: PROPOSAL_TEXT } }));
    await screen.findByText(PROPOSAL_TEXT);

    fireEvent.click(screen.getByRole("button", { name: "Regenerate proposal" }));
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.RESULT)).toHaveLength(2));
    const starts = routed.calls.filter((call) => call.key === ROUTES.START);
    expect(starts).toHaveLength(2);
    expect(idempotencyKeyOf(starts[0]!)).not.toBe(idempotencyKeyOf(starts[1]!));
    expect(screen.queryByText("Created from previous details")).toBeNull();
    const resultSection = screen.getByRole("heading", { name: "Proposal", level: 2 }).closest("section")!;
    expect(within(resultSection).getByRole("status").textContent).toBe("Generating your proposal…");
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy();

    routed.resolveCall(ROUTES.RESULT, 1, resultResponse(IDS, { output: { text: "Updated proposal." } }));
    await screen.findByText("Updated proposal.");
  });

  it("shows a regeneration error above a retained long proposal", async () => {
    const longProposal = "A detailed proposal. ".repeat(300);
    const routed = makeClient({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(IDS), quotaResponse(IDS, { used_count: 1, remaining_count: 2 })],
      [ROUTES.START]: [startResponse(), errorResponse(500, "internal_error")],
      [ROUTES.SESSION]: [sessionResponse()],
      [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: longProposal } })],
    });
    render(<ProposalAIProduct client={routed.client} />);
    fireEvent.change(await screen.findByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    const previousResult = await screen.findByText(/^A detailed proposal\./);

    fireEvent.click(screen.getByRole("button", { name: "Regenerate proposal" }));
    const error = await screen.findByText("Could not start ProposalAI. Please try again.");
    expect(error.compareDocumentPosition(previousResult) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(previousResult.isConnected).toBe(true);
  });

  it("refreshes advisory quota after consecutive regenerations and an authoritative rejection", async () => {
    const routed = makeClient({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [
        quotaResponse(IDS),
        quotaResponse(IDS, { used_count: 1, remaining_count: 2 }),
        quotaResponse(IDS, { used_count: 2, remaining_count: 1 }),
        quotaResponse(IDS, { used_count: 3, remaining_count: 0, exhausted: true }),
        quotaResponse(IDS, { used_count: 3, remaining_count: 0, exhausted: true }),
      ],
      [ROUTES.START]: [startResponse(), startResponse(), startResponse(), errorResponse(429, "quota_exhausted")],
      [ROUTES.SESSION]: [sessionResponse(), sessionResponse(), sessionResponse()],
      [ROUTES.RESULT]: [
        resultResponse(IDS, { output: { text: "Proposal 1" } }),
        resultResponse(IDS, { output: { text: "Proposal 2" } }),
        resultResponse(IDS, { output: { text: "Proposal 3" } }),
      ],
    });
    render(<ProposalAIProduct client={routed.client} />);
    fireEvent.change(await screen.findByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });

    for (const [submitLabel, resultText, remaining] of [
      ["Generate proposal", "Proposal 1", 2],
      ["Regenerate proposal", "Proposal 2", 1],
      ["Regenerate proposal", "Proposal 3", 0],
    ] as const) {
      fireEvent.click(screen.getByRole("button", { name: submitLabel }));
      await screen.findByText(resultText);
      await screen.findByText(`${remaining} of 3 proposals remaining.`);
    }

    fireEvent.click(screen.getByRole("button", { name: "Regenerate proposal" }));
    await screen.findByText("You've used all your ProposalAI runs for now.");
    expect(screen.getByText("0 of 3 proposals remaining.")).toBeTruthy();
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.QUOTA)).toHaveLength(5));
  });

  it("ignores an older quota response that arrives after the accepted run's refresh", async () => {
    const routed = makeClientWithDeferredCalls({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(IDS, { used_count: 1, remaining_count: 2 })],
      [ROUTES.START]: [startResponse()],
      [ROUTES.SESSION]: [sessionResponse()],
      [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })],
    }, { [ROUTES.QUOTA]: 1 });
    render(<ProposalAIProduct client={routed.client} />);
    fireEvent.change(await screen.findByLabelText("Describe the task"), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText("Your positioning"), { target: { value: "Frontend freelancer." } });
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.QUOTA)).toHaveLength(1));

    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await screen.findByText("2 of 3 proposals remaining.");
    await act(async () => routed.resolveCall(ROUTES.QUOTA, 0, quotaResponse(IDS)));
    expect(screen.getByText("2 of 3 proposals remaining.")).toBeTruthy();
  });

  it("treats a result without a string `text` field as unusable rather than rendering something else", () => {
    expect(proposalAiDefinition.extractResult({ text: "ok" })).toBe("ok");
    expect(proposalAiDefinition.extractResult({ angle: "x", rationale: "y" })).toBeNull();
    expect(proposalAiDefinition.extractResult({ text: 42 })).toBeNull();
  });
});
