import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { persistPaidStartRecovery, readPaidStartRecovery } from "@anytoolai/ce-kit";
import { createPlatformApiClient } from "../src/lib/apiClient";
import { getPaidPersistence, installPortalSession, requirePortalAuthorization } from "../src/lib/portalSession";
import { ProposalAIProduct, proposalAiDefinition, type ProposalAIValues } from "../src/products/proposalAi/ProposalAIProduct";
import { PROPOSAL_AI_MESSAGES } from "../src/products/proposalAi/messages";
import { productDraftKey, readProductDraft, saveDraftValues } from "../src/products/runtime/draftStorage";
import { errorResponse, resultResponse, runtimeConfigResponse, sessionResponse, startResponse } from "./fixtures/platformResponses";
import { makeRender } from "./support/renderWithI18n";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
const render = makeRender(PROPOSAL_AI_MESSAGES);
const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const ids = { productId: "proposal_ai", scenarioId: "proposal_ai.generate_v1" };
const draftKey = productDraftKey(ids.productId, proposalAiDefinition.messageScope, owner);
const original: ProposalAIValues = { taskText: "hello", freelancerPositioning: "hello", tone: "firm", language: "auto" };
const corrected: ProposalAIValues = { ...original, taskText: "Write a bakery landing page.", freelancerPositioning: "I write landing pages." };
const fetcher = vi.fn<typeof fetch>();
const starts: RequestInit[] = [];
const taskHint = PROPOSAL_AI_MESSAGES.en.validation.missing_task_description;
const profileHint = PROPOSAL_AI_MESSAGES.en.validation.missing_profile_information;

beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
  window.history.replaceState(null, "", "/products/proposal_ai?paid=1");
  requirePortalAuthorization(true);
  installPortalSession({ consumerId: "platform-kernel", consumerPolicyRevision: 1, owner,
    accessToken: "t".repeat(43), expiresAt: new Date(Date.now() + 3_600_000).toISOString() });
  starts.length = 0;
  fetcher.mockReset();
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function rejectedResult() {
  return resultResponse(ids, { schema_ref: proposalAiDefinition.outputSchema.schemaRef, output: {
    text: "Internal clarification.",
    gaps: ["missing_task_description", "missing_profile_information"].map(category => ({ category, description: "Missing input", severity: "high" })),
  } });
}

function setup(draft: unknown = original, submitted: ProposalAIValues = original) {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  const input = proposalAiDefinition.toInput(submitted);
  if (draft !== null) saveDraftValues(draftKey, draft);
  persistPaidStartRecovery(persistence, { version: 1, kind: "pending", owner, ...ids, idempotencyKey: "original_key",
    request: { ...ids, frontendId: "web_mirror", input } });
  const controls: { configAvailable: boolean; result: () => Response | Promise<Response> } = {
    configAvailable: true, result: rejectedResult,
  };
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (path.endsWith("runtime-config")) return controls.configAvailable ? runtimeConfigResponse(ids, { scenarios: [{
      scenario_id: ids.scenarioId, version: 1, allowed_next_actions: ["copy_result"],
      input_renderer_hint: { renderer: "json_schema", schema_ref: "proposal_ai.generate_input_v1", schema_version: 2 },
      output_renderer_hint: { renderer: "json_schema", schema_ref: proposalAiDefinition.outputSchema.schemaRef, schema_version: 1 },
    }] }) : errorResponse(503, "runtime_unavailable");
    if (path.endsWith("/start")) { starts.push(init!); return startResponse(); }
    if (path.endsWith("/historical_session")) return sessionResponse({ scenario_id: ids.scenarioId, scenario_session_id: "historical_session", result_artifact_id: "historical_result" });
    if (path.startsWith("/v1/scenario-sessions/")) return sessionResponse({ scenario_id: ids.scenarioId });
    if (path.endsWith("/historical_result")) return resultResponse(ids, { scenario_session_id: "historical_session", schema_ref: proposalAiDefinition.outputSchema.schemaRef, output: { text: "Historical proposal." } });
    if (path.startsWith("/v1/results/")) return controls.result();
    throw new Error("Unexpected guest/quota request: " + path);
  });
  return { client, persistence, input, controls };
}

async function settled(persistence: NonNullable<ReturnType<typeof getPaidPersistence>>) {
  await waitFor(() => expect(readPaidStartRecovery(persistence, ids.productId)).toBeNull());
  expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
}

function expectHints(task: boolean, profile: boolean) {
  expect(screen.queryByText(taskHint) !== null).toBe(task);
  expect(screen.queryByText(profileHint) !== null).toBe(profile);
}

function requestBody(index: number): unknown {
  const body = starts[index].body;
  if (typeof body !== "string") throw new Error("Expected JSON request body");
  return JSON.parse(body);
}

const cases: { name: string; draft: ProposalAIValues; hints: [boolean, boolean]; submitted?: ProposalAIValues }[] = [
  { name: "unchanged", draft: original, hints: [true, true] },
  { name: "tone only", draft: { ...original, tone: "warm" }, hints: [true, true] },
  { name: "auto to explicit language", draft: { ...original, language: "es" }, hints: [true, true] },
  { name: "explicit to auto language", submitted: { ...original, language: "es" }, draft: original, hints: [true, true] },
  { name: "profile corrected", draft: { ...original, freelancerPositioning: corrected.freelancerPositioning }, hints: [true, false] },
  { name: "task corrected", draft: { ...original, taskText: corrected.taskText }, hints: [false, true] },
  { name: "both corrected", draft: corrected, hints: [false, false] },
  { name: "backend whitespace and tone", draft: { ...original, taskText: "\u0085hello\u001f", freelancerPositioning: " hello ", tone: "warm" }, hints: [true, true] },
];

it.each(cases)("replays frozen input and binds only unchanged fields: $name", async ({ draft, hints, submitted }) => {
  const { client, persistence, input, controls } = setup(draft, submitted);
  render(<ProposalAIProduct client={client} />);
  await settled(persistence);
  expectHints(...hints);
  expect(readProductDraft(draftKey)?.values).toEqual(draft);
  expect((screen.getByLabelText(/^Describe the task/) as HTMLTextAreaElement).value).toBe(draft.taskText);
  expect((screen.getByLabelText(/^Your experience and strengths/) as HTMLTextAreaElement).value).toBe(draft.freelancerPositioning);
  expect(starts).toHaveLength(1);
  expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("original_key");
  expect(requestBody(0)).toMatchObject({ input, guest_id: null });
  if (hints.some(Boolean)) {
    fireEvent.submit(screen.getByRole("form"));
    expect(starts).toHaveLength(1);
    expectHints(...hints);
  }
  fireEvent.change(screen.getByLabelText(/^Describe the task/), { target: { value: corrected.taskText } });
  fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: corrected.freelancerPositioning } });
  controls.result = () => resultResponse(ids, { output: { text: "Corrected paid proposal." } });
  fireEvent.click(screen.getByRole("button", { name: "Generate proposal" }));
  await screen.findByText("Corrected paid proposal.");
  expect(starts).toHaveLength(2);
  expect(new Headers(starts[1].headers).get("Idempotency-Key")).not.toBe("original_key");
  expect(requestBody(1)).toMatchObject({ input: proposalAiDefinition.toInput({ ...draft, ...corrected, tone: draft.tone, language: draft.language }) });
});

it.each(["taskText", "freelancerPositioning"] as const)("remembers the frozen rejected %s after editing back", async (field) => {
  const { client, persistence } = setup(corrected);
  render(<ProposalAIProduct client={client} />);
  await settled(persistence);
  expectHints(false, false);
  fireEvent.change(screen.getByLabelText(field === "taskText" ? /^Describe the task/ : /^Your experience and strengths/), { target: { value: " hello " } });
  expectHints(field === "taskText", field === "freelancerPositioning");
  fireEvent.submit(screen.getByRole("form"));
  expect(starts).toHaveLength(1);
});

it.each([false, true])("retains original values across accepted reload (config unavailable: %s)", async (unavailable) => {
  const draft = { ...original, freelancerPositioning: corrected.freelancerPositioning };
  const { client, persistence, controls } = setup(draft);
  let finish!: (response: Response) => void;
  controls.result = () => new Promise(resolve => { finish = resolve; });
  const first = render(<ProposalAIProduct client={client} />);
  await waitFor(() => expect(finish).toBeDefined());
  expect(readProductDraft(draftKey)?.run?.input).toEqual(original);
  expect(readPaidStartRecovery(persistence, ids.productId)?.kind).toBe("accepted");
  first.unmount();
  controls.result = rejectedResult;
  controls.configAvailable = !unavailable;
  render(<ProposalAIProduct client={createPlatformApiClient()} />);
  await settled(persistence);
  expectHints(true, false);
  expect(readProductDraft(draftKey)?.values).toEqual(draft);
  expect(starts).toHaveLength(1);
  await act(async () => { finish(rejectedResult()); });
  expectHints(true, false);
  fireEvent.submit(screen.getByRole("form"));
  expect(starts).toHaveLength(1);
});

it("reaches a partially edited draft through an explicit historical result", async () => {
  const { client, persistence } = setup();
  const historical = render(<ProposalAIProduct client={client} attachFromUrl attachSessionId="historical_session" />);
  await screen.findByText("Historical proposal.");
  fireEvent.click(screen.getByRole("button", { name: "Restore saved draft" }));
  fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: corrected.freelancerPositioning } });
  expect(readPaidStartRecovery(persistence, ids.productId)?.kind).toBe("pending");
  historical.unmount();
  render(<ProposalAIProduct client={createPlatformApiClient()} />);
  await settled(persistence);
  expectHints(true, false);
  fireEvent.submit(screen.getByRole("form"));
  expect(starts).toHaveLength(1);
});

it.each([null, "malformed draft"])("retains the source even without a usable draft: %j", async (draft) => {
  const { client, persistence } = setup(draft);
  render(<ProposalAIProduct client={client} />);
  await settled(persistence);
  fireEvent.change(screen.getByLabelText(/^Describe the task/), { target: { value: original.taskText } });
  fireEvent.change(screen.getByLabelText(/^Your experience and strengths/), { target: { value: original.freelancerPositioning } });
  expectHints(true, true);
  fireEvent.submit(screen.getByRole("form"));
  expect(starts).toHaveLength(1);
});

it("recovers pending rejection without config while keeping fresh runs disabled", async () => {
  const { client, persistence, controls } = setup({ ...original, tone: "warm" });
  controls.configAvailable = false;
  render(<ProposalAIProduct client={client} />);
  await settled(persistence);
  expectHints(true, true);
  expect((screen.getByRole("button", { name: "Generate proposal" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.submit(screen.getByRole("form"));
  expect(starts).toHaveLength(1);
});

it("does not attribute a malformed frozen input to a matching-looking draft", async () => {
  const { client, persistence } = setup();
  // A damaged descriptor is read as opaque input by CE-kit; only the product can validate it.
  const recoveryKey = `anytoolai.paid_start.v1.${ids.productId}`;
  const saved = readPaidStartRecovery(persistence, ids.productId)!;
  if (saved.kind !== "pending") throw new Error("Expected pending recovery");
  window.sessionStorage.setItem(recoveryKey, JSON.stringify({ ...saved, request: { ...saved.request, input: { ...proposalAiDefinition.toInput(original), result_contract: null } } }));
  render(<ProposalAIProduct client={client} />);
  await settled(persistence);
  expectHints(false, false);
  expect(readProductDraft(draftKey)?.values).toEqual(original);
});

it.each(["logout", "new-owner"])("ignores a delayed recovered result after %s", async (change) => {
  const { client, controls } = setup({ ...original, tone: "warm" });
  let finish!: (response: Response) => void;
  controls.result = () => new Promise(resolve => { finish = resolve; });
  render(<ProposalAIProduct client={client} />);
  await waitFor(() => expect(finish).toBeDefined());
  requirePortalAuthorization(true);
  if (change === "new-owner") installPortalSession({ consumerId: "platform-kernel", consumerPolicyRevision: 1,
    owner: { ...owner, userId: "22222222-2222-2222-2222-222222222222" },
    accessToken: "n".repeat(43), expiresAt: new Date(Date.now() + 3_600_000).toISOString() });
  const savedStorage = JSON.stringify(window.sessionStorage);
  await act(async () => { finish(rejectedResult()); });
  expectHints(false, false);
  expect(JSON.stringify(window.sessionStorage)).toBe(savedStorage);
  fireEvent.submit(screen.getByRole("form"));
  expect(starts).toHaveLength(1);
});
