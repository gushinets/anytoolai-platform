// ProposalAI's own meaning only -- fields and their validation copy, the mapping to
// `proposal_ai.generate_input_v1`, the canonical `text` field, and the `copy_result`
// activation. The shared runtime behavior it rides on is proven in ProductRunPage.test.tsx.
import type { PlatformApiClient } from "@anytoolai/ce-kit";
import { useAttachSession, readAttachSessionId } from "../src/products/runtime/attachSession";
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ProposalAIProduct, proposalAiDefinition } from "../src/products/proposalAi/ProposalAIProduct";
import {
  errorResponse,
  guestIdentityResponse,
  idempotencyKeyOf,
  jsonResponse,
  makeClient,
  makeClientCapturingRequests,
  makeClientWithDeferredCalls,
  quotaResponse,
  resultResponse,
  routesFor,
  runtimeConfigResponse,
  sessionResponse,
  startResponse,
} from "./fixtures/platformResponses";
import { getClientStorage } from "../src/products/runtime/clientStorage";
import { createProductRunEventTracker } from "../src/products/runtime/productRunEventTracking";
import { PROPOSAL_AI_MESSAGES } from "../src/products/proposalAi/messages";
import { makeRender } from "./support/renderWithI18n";
import { expectDataProcessingNotice } from "./support/expectDataProcessingNotice";
import { simulateBrowserTranslation } from "@anytoolai/shared-ui/test/support/simulateBrowserTranslation";
import type { ProductRunEvent } from "../src/products/runtime/productDefinition";
import { LOCALES } from "../src/i18n";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";

const render = makeRender(PROPOSAL_AI_MESSAGES);

const IDS = { productId: "proposal_ai", scenarioId: "proposal_ai.generate_v1" } as const;
const ROUTES = routesFor(IDS);
const PROPOSAL_TEXT = "Dear client, here is my proposal.";

afterEach(() => {
  vi.unstubAllEnvs();
  cleanup();
  window.localStorage.clear();
  window.sessionStorage.clear();
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
  it.each(LOCALES)("example inputs pass the product validator in %s", (locale) => {
    const inputs = PROPOSAL_AI_MESSAGES[locale].generate.example.inputs;
    expect(proposalAiDefinition.validate({ ...inputs, tone: "warm", language: "auto" })).toEqual({});
  });

  it("opening an example preserves typed input, draft and events, and never submits sample text", async () => {
    const onEvent = vi.fn<(event: ProductRunEvent) => void>();
    const routed = makeClientCapturingRequests({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(IDS), quotaResponse(IDS)],
      [ROUTES.START]: [startResponse()],
      [ROUTES.SESSION]: [sessionResponse()],
      [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })],
    });
    render(<ProposalAIProduct client={routed.client} onEvent={onEvent} />);
    const task = await screen.findByLabelText<HTMLTextAreaElement>(/^Describe the task/);
    const profile = screen.getByLabelText<HTMLTextAreaElement>(/^Your experience and strengths/);
    const details = screen.getByTestId<HTMLDetailsElement>("first-run-example");
    fireEvent.change(task, { target: { value: "My own task" } });
    fireEvent.change(profile, { target: { value: "My own experience" } });
    const draft = { ...window.sessionStorage };
    const events = onEvent.mock.calls.slice();
    details.open = true;
    fireEvent(details, new Event("toggle"));
    expect(task.value).toBe("My own task");
    expect(profile.value).toBe("My own experience");
    expect({ ...window.sessionStorage }).toEqual(draft);
    expect(onEvent.mock.calls).toEqual(events);
    expect(onEvent.mock.calls.filter(([event]) => event.type === "form_started")).toHaveLength(1);
    expect(onEvent.mock.calls.filter(([event]) => event.type === "form_submitted")).toHaveLength(0);
    expect(screen.getByText(PROPOSAL_AI_MESSAGES.en.generate.example.inputs.taskText)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await screen.findByText(PROPOSAL_TEXT);
    const request = routed.calls.find((call) => call.key === ROUTES.START);
    expect((JSON.parse(request!.init.body as string) as { input: unknown }).input).toEqual({
      task_text: "My own task", freelancer_positioning: "My own experience", tone: "warm",
    });
    expect(request!.init.body).not.toContain(PROPOSAL_AI_MESSAGES.en.generate.example.inputs.taskText);
  });

  it("shows the shared processing notice and policy inside the form", async () => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", "https://example.com/privacy");
    renderReady();
    const form = await screen.findByRole("form");
    expectDataProcessingNotice(form, "https://example.com/privacy");
  });

  it.each([
    { locale: "en", translated: true },
    { locale: "ru", translated: false },
    { locale: "ru", translated: true },
  ] as const)("keeps submitting in $locale with translation=$translated (ANY-840)", async ({ locale, translated }) => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    const labels = locale === "ru"
      ? { task: /^Опишите задачу/, experience: /^Ваш опыт и сильные стороны/, submit: "Составить предложение", regenerate: "Пересоставить предложение" }
      : { task: /^Describe the task/, experience: /^Your experience and strengths/, submit: "Generate proposal", regenerate: "Regenerate proposal" };
    const errorSpy = vi.spyOn(console, "error");
    try {
      const routed = makeClientWithDeferredCalls({
        [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
        [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
        [ROUTES.QUOTA]: Array.from({ length: 5 }, () => quotaResponse(IDS)),
        [ROUTES.SESSION]: [sessionResponse(), sessionResponse()],
        [ROUTES.RESULT]: [
          resultResponse(IDS, { output: { text: PROPOSAL_TEXT } }),
          resultResponse(IDS, { output: { text: "Updated proposal." } }),
        ],
      }, { [ROUTES.START]: 2 });
      render(<ProposalAIProduct client={routed.client} />);
      fireEvent.change(await screen.findByLabelText(labels.task), { target: { value: "Build a landing page." } });
      fireEvent.change(screen.getByLabelText(labels.experience), { target: { value: "Frontend freelancer." } });
      if (locale === "ru") {
        expect(screen.getByRole("heading", { name: "Ваши данные" })).toBeTruthy();
        expect(screen.getByRole("option", { name: "Как в задаче" })).toBeTruthy();
        expect(screen.getByText("Не язык интерфейса. По умолчанию предложение пишется на языке задачи.")).toBeTruthy();
      }

      for (const [index, label, result] of [
        [0, labels.submit, PROPOSAL_TEXT],
        [1, labels.regenerate, "Updated proposal."],
      ] as const) {
        const button = screen.getByRole("button", { name: label }) as HTMLButtonElement;
        if (translated) simulateBrowserTranslation(button);
        fireEvent.click(button);
        await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.START)).toHaveLength(index + 1));
        expect(button.disabled).toBe(true);
        expect(button.getAttribute("aria-busy")).toBe("true");
        expect(button.querySelector('[aria-hidden="true"]')).not.toBeNull();
        if (locale === "ru") expect(button.textContent).toBe("Запускаем…");
        routed.resolveCall(ROUTES.START, index, startResponse());
        await screen.findByText(result);
        expect(screen.getByRole("button", { name: labels.regenerate })).toBe(button);
        expect(button.disabled).toBe(false);
        expect(button.hasAttribute("aria-busy")).toBe(false);
      }
      expect(errorSpy).not.toHaveBeenCalled();
    } finally {
      errorSpy.mockRestore();
    }
  });

  it("revalidates only the edited invalid field using its current product rules", async () => {
    const { calls } = renderReady();
    const task = await screen.findByLabelText(/^Describe the task/);
    const positioning = screen.getByLabelText(/^Your experience and strengths/);
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    expect(task.getAttribute("aria-invalid")).toBe("true");
    // Required, whitespace and maxLength are the actual product validator's rules.
    for (const [value, message] of [
      ["   ", "Task description: required."],
      ["x".repeat(4001), "Task description: 4,000 characters maximum."],
    ]) {
      fireEvent.change(task, { target: { value: "Build a landing page." } });
      expect(task.getAttribute("aria-invalid")).toBe("false");
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
    expect(screen.getByText("Your experience and strengths: required.")).toBeTruthy();
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
    await waitFor(() => expect(screen.getByLabelText(/^Describe the task/)).toBeTruthy());

    // Pasted text with outer whitespace is trimmed, not rejected (see the toInput test below).
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: " padded\n" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    expect(await screen.findByText("Task description: required.")).toBeTruthy();
    expect(screen.queryByText(/Your experience and strengths:/)).toBeNull();
    const taskField = screen.getByLabelText(/^Describe the task/);
    const positioningField = screen.getByLabelText(/^Your experience and strengths/);
    expect(taskField.getAttribute("aria-describedby")).toBe("proposal-ai-task-help proposal-ai-task-error");
    expect(positioningField.getAttribute("aria-describedby")).toBe("proposal-ai-positioning-help");
    for (const id of taskField.getAttribute("aria-describedby")!.split(" ")) {
      expect(document.getElementById(id)).toBeTruthy();
    }
    expect(calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("maps the default warm style to the snake_case input schema and omits language", async () => {
    const { calls } = renderReady();
    await waitFor(() => expect(screen.getByLabelText(/^Describe the task/)).toBeTruthy());

    fireEvent.change(screen.getByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
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
    await waitFor(() => expect(screen.getByLabelText(/^Describe the task/)).toBeTruthy());

    fireEvent.change(screen.getByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
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
    await waitFor(() => expect(screen.getByLabelText(/^Describe the task/)).toBeTruthy());
    fireEvent.change(screen.getByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
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
    const task = await screen.findByLabelText(/^Describe the task/) as HTMLTextAreaElement;
    const positioning = screen.getByLabelText(/^Your experience and strengths/) as HTMLTextAreaElement;
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
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
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
    expect(within(resultSection).getByRole("status").textContent).toContain("Generating your proposal…");
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
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
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
        quotaResponse(IDS, { used_count: 0, reserved_count: 1 }),
        quotaResponse(IDS, { used_count: 1, remaining_count: 2 }),
        quotaResponse(IDS, { used_count: 1, remaining_count: 2, reserved_count: 1 }),
        quotaResponse(IDS, { used_count: 2, remaining_count: 1 }),
        quotaResponse(IDS, { used_count: 2, remaining_count: 1, reserved_count: 1 }),
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
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });

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
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.QUOTA)).toHaveLength(8));
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
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
    await waitFor(() => expect(routed.calls.filter((call) => call.key === ROUTES.QUOTA)).toHaveLength(1));

    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await screen.findByText("2 of 3 proposals remaining.");
    await act(async () => routed.resolveCall(ROUTES.QUOTA, 0, quotaResponse(IDS)));
    expect(screen.getByText("2 of 3 proposals remaining.")).toBeTruthy();
  });

  it("treats a result without a string `text` field as unusable rather than rendering something else", () => {
    expect(proposalAiDefinition.extractResult({ text: "ok", gaps: [] })).toEqual({ text: "ok", gaps: [] });
    expect(proposalAiDefinition.extractResult({ angle: "x", rationale: "y" })).toBeNull();
    expect(proposalAiDefinition.extractResult({ text: 42, gaps: [] })).toBeNull();
  });

  it("keeps only gaps that carry a description and tolerates a missing gaps list", () => {
    expect(proposalAiDefinition.extractResult({ text: "ok" })).toEqual({ text: "ok", gaps: [] });
    expect(
      proposalAiDefinition.extractResult({
        text: "ok",
        gaps: [{ category: "experience_gap", description: "No HubSpot." }, { description: 3 }, "x", null],
      }),
    ).toEqual({ text: "ok", gaps: [{ description: "No HubSpot." }] });
  });

  it("sends the proposal language only when one is chosen, and trims pasted outer whitespace", async () => {
    const { calls } = renderReady();
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: "Build a landing page.\n" } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "  Frontend freelancer.\n\n" } });
    const language = screen.getByLabelText("Proposal language") as HTMLSelectElement;
    expect(language.value).toBe("auto");
    expect(within(language).getAllByRole("option")).toHaveLength(8);
    fireEvent.change(language, { target: { value: "de" } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    await waitFor(() => expect(calls.some((call) => call.key === ROUTES.START)).toBe(true));
    const startCall = calls.find((call) => call.key === ROUTES.START);
    expect(JSON.parse(startCall?.init.body as string)).toMatchObject({
      input: {
        task_text: "Build a landing page.",
        freelancer_positioning: "Frontend freelancer.",
        tone: "warm",
        language: "de",
      },
    });
  });

  it("marks both text fields required, caps them, and shows a counter only near the limit", async () => {
    renderReady();
    const task = (await screen.findByLabelText(/^Describe the task/)) as HTMLTextAreaElement;
    const positioning = screen.getByLabelText(/^Your experience and strengths/) as HTMLTextAreaElement;
    for (const field of [task, positioning]) {
      expect(field.getAttribute("aria-required")).toBe("true");
      // no hard cap: a paste over the limit must stay visible and get the counter and the error
      expect(field.maxLength).toBe(-1);
    }
    expect(screen.getAllByText("(required)")).toHaveLength(2);
    expect(screen.queryByText(/\/ 4000/)).toBeNull();

    fireEvent.change(task, { target: { value: "x".repeat(3501) } });
    expect(screen.getByText("3501 / 4000")).toBeTruthy();
    // the visible number is not a live region; a hidden status announces the state change only
    expect(screen.getByText("3501 / 4000").getAttribute("aria-hidden")).toBe("true");
    expect(screen.getByText("Approaching the limit of 4000 characters.").getAttribute("aria-live")).toBe("polite");

    fireEvent.change(task, { target: { value: "x".repeat(3999) } });
    expect(screen.getByText("Approaching the limit of 4000 characters.")).toBeTruthy();

    fireEvent.change(task, { target: { value: "x".repeat(4100) } });
    expect(task.value).toHaveLength(4100);
    expect(screen.getByText("4100 / 4000")).toBeTruthy();
    expect(screen.getByText("Over the limit of 4000 characters.")).toBeTruthy();

    // counted like the validation: code points of the trimmed text, not UTF-16 units or padding
    fireEvent.change(task, { target: { value: "\u{1F600}".repeat(3000) + "\n\n" } });
    expect(screen.queryByText(/\/ 4000/)).toBeNull();
    expect(screen.queryByText("Approaching the limit of 4000 characters.")).toBeNull();
  });

  it("shows the experience gaps under the proposal and copies only the proposal text", async () => {
    const routed = makeClient({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(IDS, { limit_count: 10, remaining_count: 10 }), quotaResponse(IDS, { limit_count: 10, remaining_count: 9 })],
      [ROUTES.START]: [startResponse()],
      [ROUTES.SESSION]: [sessionResponse()],
      [ROUTES.RESULT]: [
        resultResponse(IDS, {
          output: {
            text: PROPOSAL_TEXT,
            gaps: [{ category: "experience_gap", description: "The task needs HubSpot, which is not in your experience.", severity: "high" }],
          },
        }),
      ],
      [ROUTES.NEXT_ACTION]: [sessionResponse()],
    });
    render(<ProposalAIProduct client={routed.client} />);
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    const gaps = await screen.findByRole("region", { name: "Not covered by your experience" });
    expect(within(gaps).getByText("The task needs HubSpot, which is not in your experience.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Copy" }));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(PROPOSAL_TEXT));
  });

  it("hides the gaps block when the list is empty", async () => {
    renderReady();
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: "Build a landing page." } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: "Frontend freelancer." } });
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));

    await waitFor(() => expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy());
    expect(screen.queryByRole("region", { name: "Not covered by your experience" })).toBeNull();
  });
});

function AttachedProposalAIProduct({ client, sessionId }: { client: PlatformApiClient; sessionId?: string }) {
  const attach = useAttachSession("proposal_ai", sessionId);
  return <ProposalAIProduct client={client} {...attach} />;
}

it.each([false, true])("restores an accepted session and reloads without another start (poll recovery=%s)", async (recover) => {
  const { client, calls } = makeClient({
    [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
    [ROUTES.RESULT]: Array.from({ length: 2 }, () => resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })),
    [ROUTES.RUNTIME_CONFIG]: Array.from({ length: 2 }, () => runtimeConfigResponse(IDS)),
    [ROUTES.QUOTA]: Array.from({ length: 4 }, () => quotaResponse(IDS, { used_count: 1, remaining_count: 2 })),
    [ROUTES.SESSION]: [
      ...(recover ? [errorResponse(503, "internal_error")] : []),
      sessionResponse(), sessionResponse(),
    ],
  });
  const first = render(<AttachedProposalAIProduct client={client} sessionId="session_1" />);
  if (recover) {
    fireEvent.click(await screen.findByRole("button", { name: "Try again" }));
  }
  await screen.findByRole("button", { name: "New task" });
  expect(readAttachSessionId("proposal_ai")).toBe("session_1");
  first.unmount();
  render(<AttachedProposalAIProduct client={client} />);
  await screen.findByRole("button", { name: "New task" });
  expect(calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(recover ? 3 : 2);
  expect(calls.some((call) => call.key.endsWith("/start"))).toBe(false);
  expect(screen.getByText(/2 of 3/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  expect(readAttachSessionId("proposal_ai")).toBeUndefined();
});

describe("ProposalAI draft and run restore (ANY-841)", () => {
  const key = "anytoolai.product_draft.proposal_ai.generate";
  const values = { taskText: "Build a landing page.", freelancerPositioning: "Frontend freelancer.", tone: "firm", language: "de" };

  function seedRun(input: unknown = values) {
    window.sessionStorage.setItem(key, JSON.stringify({ v: 1, values, run: { scenarioSessionId: "session_1", input } }));
  }

  function recoveryClient(session = sessionResponse(), result = resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })) {
    return makeClient({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: Array.from({ length: 4 }, () => quotaResponse(IDS)),
      [ROUTES.SESSION]: [session],
      [ROUTES.RESULT]: [result],
    });
  }

  async function fillDraft() {
    fireEvent.change(await screen.findByLabelText(/^Describe the task/), { target: { value: values.taskText } });
    fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: values.freelancerPositioning } });
    fireEvent.click(document.getElementById("proposal-ai-tone-firm")!);
    fireEvent.change(screen.getByLabelText("Proposal language"), { target: { value: "de" } });
  }

  async function expectDraft() {
    expect((await screen.findByLabelText(/^Describe the task/) as HTMLTextAreaElement).value).toBe(values.taskText);
    expect((screen.getByLabelText(/^Your experience and strengths/) as HTMLTextAreaElement).value).toBe(values.freelancerPositioning);
    expect((document.getElementById("proposal-ai-tone-firm") as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText("Proposal language") as HTMLSelectElement).value).toBe("de");
  }

  it.each(["cleared", "unavailable"])("derives restored result-viewed identity from the session after localStorage is %s", async (storageState) => {
    const first = makeClientWithDeferredCalls({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse("guest_before_reload")],
      [ROUTES.QUOTA]: [quotaResponse(IDS), quotaResponse(IDS)],
      [ROUTES.START]: [startResponse()],
    }, { [ROUTES.SESSION]: 1 });
    render(<ProposalAIProduct client={first.client} />);
    await fillDraft();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(first.calls.some((call) => call.key === ROUTES.SESSION)).toBe(true));
    expect(JSON.parse(first.calls.find((call) => call.key === ROUTES.START)!.init.body as string)).toMatchObject({ guest_id: "guest_before_reload" });
    cleanup();
    const identityStorage = window.localStorage;
    identityStorage.clear();
    const storageSpy = storageState === "unavailable"
      ? vi.spyOn(window, "localStorage", "get").mockImplementation(() => { throw new DOMException("blocked", "SecurityError"); })
      : undefined;
    const viewedKey = "anytoolai.result_viewed.session_1";
    const eventRoute = "POST /v1/client-events";
    const makeReloadClient = (guestId: string) => makeClientCapturingRequests({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse(guestId)],
      [ROUTES.QUOTA]: [quotaResponse(IDS), quotaResponse(IDS)],
      [ROUTES.SESSION]: [sessionResponse()],
      [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })],
    }, (route, init) => {
      if (route !== eventRoute) return undefined;
      const body = JSON.parse(init.body as string) as { event_id: string; event_type: string; guest_id?: string };
      // Match the backend's session-owner check: the new page guest cannot claim the old run.
      if (body.event_type === "web.result_viewed" && body.guest_id !== undefined && body.guest_id !== "guest_before_reload") {
        return errorResponse(404, "scenario_session_not_found");
      }
      return jsonResponse(200, { event_id: body.event_id, event_type: body.event_type });
    });
    try {
      const second = makeReloadClient("guest_after_reload");
      render(<ProposalAIProduct client={second.client} onEvent={createProductRunEventTracker(second.client, IDS.productId, getClientStorage(second.client))} />);
      await screen.findByText(PROPOSAL_TEXT);
      await waitFor(() => expect(JSON.parse(window.sessionStorage.getItem(viewedKey) ?? "null")).toMatchObject({ accepted: true }));
      const viewed = second.calls.filter((call) => call.key === eventRoute).map((call) => JSON.parse(call.init.body as string) as { event_type: string; guest_id?: string; scenario_session_id?: string });
      expect(viewed.find((event) => event.event_type === "web.product_viewed")).toMatchObject({ guest_id: "guest_after_reload" });
      const resultEvents = viewed.filter((event) => event.event_type === "web.result_viewed");
      expect(resultEvents).toHaveLength(1);
      expect(resultEvents[0]).toMatchObject({ scenario_session_id: "session_1" });
      expect(resultEvents[0]).not.toHaveProperty("guest_id");
      expect(second.calls.some((call) => call.key === ROUTES.START)).toBe(false);
      cleanup();
      identityStorage.clear();
      const third = makeReloadClient("guest_third_load");
      render(<ProposalAIProduct client={third.client} onEvent={createProductRunEventTracker(third.client, IDS.productId, getClientStorage(third.client))} />);
      await screen.findByText(PROPOSAL_TEXT);
      await waitFor(() => expect(third.calls.some((call) => call.key === eventRoute)).toBe(true));
      const duplicateViews = third.calls.filter((call) => call.key === eventRoute).filter((call) => (JSON.parse(call.init.body as string) as { event_type: string }).event_type === "web.result_viewed");
      expect(duplicateViews).toHaveLength(0);
      expect(JSON.parse(window.sessionStorage.getItem(viewedKey)!)).toMatchObject({ accepted: true });
      expect(third.calls.some((call) => call.key === ROUTES.START)).toBe(false);
    } finally {
      cleanup();
      storageSpy?.mockRestore();
      first.resolveCall(ROUTES.SESSION, 0, sessionResponse());
    }
  });

  it("restores all four draft fields before submit", async () => {
    renderReady();
    await fillDraft();
    cleanup();
    const second = recoveryClient();
    render(<ProposalAIProduct client={second.client} />);
    await expectDraft();
    expect(second.calls.some((call) => call.key === ROUTES.START || call.key === ROUTES.SESSION)).toBe(false);
  });

  it("resumes an accepted running session after remount without another start", async () => {
    const first = makeClientWithDeferredCalls({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(IDS), quotaResponse(IDS)],
      [ROUTES.START]: [startResponse()],
    }, { [ROUTES.SESSION]: 1 });
    render(<ProposalAIProduct client={first.client} />);
    await fillDraft();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await waitFor(() => expect(first.calls.some((call) => call.key === ROUTES.SESSION)).toBe(true));
    cleanup();
    const second = recoveryClient();
    render(<ProposalAIProduct client={second.client} />);
    expect(await screen.findByText(PROPOSAL_TEXT)).toBeTruthy();
    await expectDraft();
    expect(second.calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(1);
    expect(second.calls.some((call) => call.key === ROUTES.START)).toBe(false);
    first.resolveCall(ROUTES.SESSION, 0, sessionResponse());
  });

  it.each([false, true])("restores a completed result and its original input (edited: %s)", async (edited) => {
    renderReady();
    await fillDraft();
    fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
    await screen.findByText(PROPOSAL_TEXT);
    if (edited) fireEvent.change(screen.getByLabelText(/^Describe the task/), { target: { value: "A different brief" } });
    cleanup();
    const second = recoveryClient();
    render(<ProposalAIProduct client={second.client} />);
    expect(await screen.findByText(PROPOSAL_TEXT)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Regenerate proposal" })).toBeTruthy();
    if (edited) {
      expect((screen.getByLabelText(/^Describe the task/) as HTMLTextAreaElement).value).toBe("A different brief");
      expect(screen.getByText(/previous details/i)).toBeTruthy();
    } else await expectDraft();
    expect(second.calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("New task clears draft and run across remount", async () => {
    seedRun();
    render(<ProposalAIProduct client={recoveryClient().client} />);
    await screen.findByText(PROPOSAL_TEXT);
    fireEvent.click(screen.getByRole("button", { name: "New task" }));
    expect(window.sessionStorage.getItem(key)).toBeNull();
    cleanup();
    const second = recoveryClient();
    render(<ProposalAIProduct client={second.client} />);
    expect((await screen.findByLabelText(/^Describe the task/) as HTMLTextAreaElement).value).toBe("");
    expect(screen.queryByText(PROPOSAL_TEXT)).toBeNull();
    expect(second.calls.some((call) => call.key === ROUTES.SESSION)).toBe(false);
  });

  it("forgets a missing session while retaining the draft without an alert", async () => {
    seedRun();
    const second = recoveryClient(errorResponse(404, "scenario_session_not_found"));
    render(<ProposalAIProduct client={second.client} />);
    await waitFor(() => expect((JSON.parse(window.sessionStorage.getItem(key)!) as { run?: unknown }).run).toBeUndefined());
    await expectDraft();
    expect(screen.queryByRole("alert")).toBeNull();
    expect((screen.getByRole("button", { name: "Generate proposal" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it.each([
    { schema_ref: "other.output_v1" },
    { schema_version: 2 },
    { output: { wrong: "payload" } },
  ])("drops a run with an incompatible result %j", async (overrides) => {
    seedRun();
    render(<ProposalAIProduct client={recoveryClient(sessionResponse(), resultResponse(IDS, overrides)).client} />);
    await waitFor(() => expect((JSON.parse(window.sessionStorage.getItem(key)!) as { run?: unknown }).run).toBeUndefined());
    expect(screen.queryByText(PROPOSAL_TEXT)).toBeNull();
  });

  it("keeps polling a restored healthy run beyond 60 seconds and shows its result", async () => {
    seedRun();
    const second = makeClient({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: Array.from({ length: 4 }, () => quotaResponse(IDS)),
      [ROUTES.SESSION]: [
        ...Array.from({ length: 32 }, () => () => sessionResponse({ status: "running" })),
        sessionResponse(),
      ],
      [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })],
    });
    vi.useFakeTimers();
    try {
      render(<ProposalAIProduct client={second.client} />);
      await act(async () => { await vi.advanceTimersByTimeAsync(100); });
      await act(async () => {
        for (let elapsed = 0; elapsed < 61_000; elapsed += 50) await vi.advanceTimersByTimeAsync(50);
      });
      expect((screen.getByLabelText(/^Describe the task/) as HTMLTextAreaElement).disabled).toBe(true);
      expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
      expect(second.calls.filter((call) => call.key === ROUTES.SESSION).length).toBeGreaterThan(30);
      expect((JSON.parse(window.sessionStorage.getItem(key)!) as { run?: unknown }).run).toBeTruthy();
      await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
      expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy();
      expect(second.calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(33);
      expect(second.calls.some((call) => call.key === ROUTES.START)).toBe(false);
    } finally {
      cleanup();
      vi.useRealTimers();
    }
  });

  const attachmentFailures: Array<{ name: string; session?: () => Response; result?: () => Response }> = [
    { name: "missing session", session: () => errorResponse(404, "scenario_session_not_found") },
    { name: "failed session", session: () => sessionResponse({ scenario_session_id: "attached_1", status: "failed" }) },
    { name: "expired session", session: () => sessionResponse({ scenario_session_id: "attached_1", status: "expired" }) },
    { name: "missing artifact id", session: () => sessionResponse({ scenario_session_id: "attached_1", result_artifact_id: null }) },
    { name: "missing result", result: () => errorResponse(404, "result_artifact_not_found") },
    { name: "unavailable result", result: () => errorResponse(404, "result_artifact_unavailable") },
    { name: "wrong schema ref", result: () => resultResponse(IDS, { scenario_session_id: "attached_1", schema_ref: "other.output_v1" }) },
    { name: "wrong schema version", result: () => resultResponse(IDS, { scenario_session_id: "attached_1", schema_version: 2 }) },
    { name: "unusable result", result: () => resultResponse(IDS, { scenario_session_id: "attached_1", output: {} }) },
  ];

  it.each(attachmentFailures)("preserves the saved own run after an unrelated attachment has $name", async ({ session = () => sessionResponse({ scenario_session_id: "attached_1" }), result }) => {
    seedRun();
    const stored = window.sessionStorage.getItem(key);
    const attachedSession = "GET /v1/scenario-sessions/attached_1";
    const first = makeClient({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(IDS), quotaResponse(IDS)],
      [attachedSession]: [session()],
      [ROUTES.RESULT]: result ? [result()] : [],
    });
    const onAttachEnd = vi.fn();
    render(<ProposalAIProduct client={first.client} attachSessionId="attached_1" onAttachEnd={onAttachEnd} />);
    await waitFor(() => expect(onAttachEnd).toHaveBeenCalledOnce());
    expect(window.sessionStorage.getItem(key)).toBe(stored);
    expect(first.calls.filter((call) => call.key === attachedSession)).toHaveLength(1);
    expect(first.calls.some((call) => call.key === ROUTES.START || call.key === ROUTES.SESSION)).toBe(false);
    cleanup();
    const second = recoveryClient();
    render(<ProposalAIProduct client={second.client} />);
    expect(await screen.findByText(PROPOSAL_TEXT)).toBeTruthy();
    await expectDraft();
    expect(second.calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(1);
    expect(second.calls.some((call) => call.key === ROUTES.START)).toBe(false);
  });

  it("forgets a failed attachment only when it matches the saved run", async () => {
    seedRun();
    const first = recoveryClient(errorResponse(404, "scenario_session_not_found"));
    const onAttachEnd = vi.fn();
    render(<ProposalAIProduct client={first.client} attachSessionId="session_1" onAttachEnd={onAttachEnd} />);
    await waitFor(() => expect(onAttachEnd).toHaveBeenCalledOnce());
    expect(JSON.parse(window.sessionStorage.getItem(key)!)).toEqual({ v: 1, values });
  });

  it("keeps a restored run locked after a request timeout and retries only that session", async () => {
    seedRun();
    let timedOut = false;
    const second = makeClientCapturingRequests({
      [ROUTES.RUNTIME_CONFIG]: [runtimeConfigResponse(IDS)],
      [ROUTES.GUEST_IDENTITY]: [guestIdentityResponse()],
      [ROUTES.QUOTA]: [quotaResponse(IDS), quotaResponse(IDS)],
      [ROUTES.SESSION]: [sessionResponse()],
      [ROUTES.RESULT]: [resultResponse(IDS, { output: { text: PROPOSAL_TEXT } })],
    }, (route, init) => {
      if (route !== ROUTES.SESSION || timedOut) return undefined;
      timedOut = true;
      return new Promise<Response>((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      });
    });
    vi.useFakeTimers();
    try {
      render(<ProposalAIProduct client={second.client} />);
      await act(async () => { await vi.advanceTimersByTimeAsync(100); });
      await act(async () => { await vi.advanceTimersByTimeAsync(10_000); });
      expect((screen.getByLabelText(/^Describe the task/) as HTMLTextAreaElement).disabled).toBe(true);
      expect((JSON.parse(window.sessionStorage.getItem(key)!) as { run?: unknown }).run).toBeTruthy();
      fireEvent.click(screen.getByRole("button", { name: "Try again" }));
      await act(async () => { await vi.advanceTimersByTimeAsync(100); });
      expect(screen.getByText(PROPOSAL_TEXT)).toBeTruthy();
      expect(second.calls.filter((call) => call.key === ROUTES.SESSION)).toHaveLength(2);
      expect(second.calls.some((call) => call.key === ROUTES.START)).toBe(false);
    } finally {
      cleanup();
      vi.useRealTimers();
    }
  });

  it("still generates when storage reads and writes throw", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("full"); });
    try {
      renderReady();
      await fillDraft();
      fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
      expect(await screen.findByText(PROPOSAL_TEXT)).toBeTruthy();
    } finally {
      vi.restoreAllMocks();
    }
  });

  it("defaults invalid stored fields and drops an unusable run input", async () => {
    seedRun(null);
    window.sessionStorage.setItem(key, JSON.stringify({ v: 1, values: { taskText: 5, tone: "loud", language: "xx" }, run: { scenarioSessionId: "session_1", input: null } }));
    const second = recoveryClient();
    render(<ProposalAIProduct client={second.client} />);
    expect((await screen.findByLabelText(/^Describe the task/) as HTMLTextAreaElement).value).toBe("");
    expect((screen.getByLabelText("Proposal language") as HTMLSelectElement).value).toBe("auto");
    expect((document.getElementById("proposal-ai-tone-warm") as HTMLInputElement).checked).toBe(true);
    expect(second.calls.some((call) => call.key === ROUTES.SESSION)).toBe(false);
    expect((JSON.parse(window.sessionStorage.getItem(key)!) as { run?: unknown }).run).toBeUndefined();
  });
});
