import { StrictMode } from "react";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { persistPaidStartRecovery, readPaidStartRecovery } from "@anytoolai/ce-kit";
import { handoffPreviewPayload } from "@anytoolai/ce-kit/test/handoffs/fixtures";
import ProductPage from "../src/app/products/[productId]/page";
import { HandoffConsent } from "../src/components/HandoffConsent";
import { HANDOFF_MESSAGES } from "../src/components/handoffMessages";
import { createPlatformApiClient } from "../src/lib/apiClient";
import { getPaidPersistence, installPortalSession, requirePortalAuthorization } from "../src/lib/portalSession";
import { productDraftKey, readProductDraft, saveDraftValues, saveProductDraftScenario } from "../src/products/runtime/draftStorage";
import { chooseAttachSession, readAttachSessionId } from "../src/products/runtime/attachSession";
import { proposalAiDefinition } from "../src/products/proposalAi/ProposalAIProduct";
import { updateDefinition, replyDraftDefinition, prepaidRequestDefinition } from "../src/products/clientUpdateWriter/ClientUpdateWriterProduct";
import { errorResponse, resultResponse, runtimeConfigResponse, sessionResponse, startResponse } from "./fixtures/platformResponses";
import { makeRender } from "./support/renderWithI18n";

const routerPush = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: routerPush }), notFound: () => { throw new Error("not found"); } }));
const renderHandoff = makeRender(HANDOFF_MESSAGES);
const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const productId = updateDefinition.productId;
const scenarioId = updateDefinition.scenarioId;
const definitions = [updateDefinition, replyDraftDefinition, prepaidRequestDefinition];
const ids = { productId, scenarioId };
let responseDefinitions = definitions.map(({ productId, scenarioId, outputSchema }) => ({ productId, scenarioId, outputSchema }));
const fetcher = vi.fn<typeof fetch>();
const starts: RequestInit[] = [];
const sessions: string[] = [];
let deferredSession: string | undefined;
let missingSession: string | undefined;
let runningA: boolean;
let resolveSession: (() => void)[];
let resolveAccept: (() => void) | undefined;
const draftKey = productDraftKey(productId, replyDraftDefinition.messageScope, owner);
const draft = { clientMessage: "Saved B client message", replyGoal: "Saved B reply goal", tone: "warm" };

function recovery() { return getPaidPersistence(createPlatformApiClient())!; }
function saveAccepted(id = "A") {
  persistPaidStartRecovery(recovery(), { version: 1, kind: "accepted", owner, ...ids, scenarioSessionId: id });
}
function fulfilled<T>(value: T): Promise<T> {
  return Object.assign(Promise.resolve(value), { status: "fulfilled", value });
}
function open(query?: string, selectedProductId = productId) {
  if (query !== undefined) window.history.replaceState(null, "", `/products/${selectedProductId}${query}`);
  const params = Object.fromEntries(new URL(window.location.href).searchParams);
  return render(<StrictMode><ProductPage params={fulfilled({ productId: selectedProductId })} searchParams={fulfilled(params)} /></StrictMode>);
}
function saveB() {
  saveDraftValues(draftKey, draft);
  saveProductDraftScenario(productId, replyDraftDefinition.scenarioId, owner);
}
async function expectB() {
  await screen.findByLabelText("Client message");
  expect((screen.getByRole("radio", { name: "Reply Draft" }) as HTMLInputElement).checked).toBe(true);
  expect((screen.getByLabelText("Client message") as HTMLTextAreaElement).value).toBe(draft.clientMessage);
  expect(screen.queryByText("Result A")).toBeNull();
  expect(screen.queryByText("Result C")).toBeNull();
}
const acceptedHandoff = () => handoffPreviewPayload({ status: "consumed", target_product_id: productId,
  target_scenario_id: scenarioId, target_scenario_session_id: "A" });

beforeEach(() => {
  window.sessionStorage.clear(); window.localStorage.clear();
  window.history.replaceState(null, "", `/products/${productId}`);
  requirePortalAuthorization(true);
  installPortalSession({ consumerId: "platform-kernel", consumerPolicyRevision: 1, owner,
    accessToken: "t".repeat(43), expiresAt: "2099-01-01T00:00:00Z" });
  starts.length = 0; sessions.length = 0; responseDefinitions = definitions;
  deferredSession = undefined; missingSession = undefined; runningA = false; resolveSession = []; resolveAccept = undefined;
  fetcher.mockReset().mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    const responseIds = { productId: responseDefinitions[0].productId, scenarioId: responseDefinitions[0].scenarioId };
    if (path.endsWith("runtime-config")) return runtimeConfigResponse(responseIds, {
      scenario_ids: responseDefinitions.map((d) => d.scenarioId), scenarios: responseDefinitions.map((d) => ({
        scenario_id: d.scenarioId, version: 1, allowed_next_actions: ["copy_result"],
        input_renderer_hint: { renderer: "json_schema", schema_ref: "test.input", schema_version: 1 },
        output_renderer_hint: { renderer: "json_schema", schema_ref: d.outputSchema.schemaRef, schema_version: 1 },
      })),
    });
    if (path.endsWith("/start")) { starts.push(init!); return startResponse({ scenario_session_id: "A" }); }
    if (path.startsWith("/v1/scenario-sessions/")) {
      const id = path.split("/").at(-1)!; sessions.push(id);
      if (id === deferredSession) await new Promise<void>((resolve) => resolveSession.push(resolve));
      if (id === missingSession) return errorResponse(404, "scenario_session_not_found");
      if (id === "A" && runningA) return sessionResponse({ scenario_session_id: id, scenario_id: scenarioId, status: "running", result_artifact_id: null });
      return sessionResponse({ scenario_session_id: id, scenario_id: responseIds.scenarioId, result_artifact_id: id });
    }
    if (path.startsWith("/v1/results/")) {
      const id = path.split("/").at(-1)!;
      return resultResponse(responseIds, { result_artifact_id: id, scenario_session_id: id,
        schema_ref: responseDefinitions[0].outputSchema.schemaRef, output: { text: `Result ${id}` } });
    }
    if (path.endsWith("/accept")) {
      await new Promise<void>((resolve) => { resolveAccept = resolve; });
      return Response.json(acceptedHandoff());
    }
    if (path.startsWith("/v1/handoffs/")) return Response.json(handoffPreviewPayload({
      target_product_id: productId, target_scenario_id: scenarioId,
    }));
    if (path === "/v1/client-events") return Response.json({ event_id: "e", event_type: "web.product_viewed" });
    throw new Error(`Unexpected request ${path}`);
  });
  vi.stubGlobal("fetch", fetcher);
});
afterEach(async () => {
  cleanup();
  await act(async () => { resolveSession.forEach((resolve) => resolve()); });
  vi.unstubAllGlobals(); vi.restoreAllMocks();
});

it("a late real handoff response does not replace a later Reply Draft selection on reload", async () => {
  const consent = renderHandoff(<HandoffConsent client={createPlatformApiClient()} handoffToken="token_abc" canOpenTarget={() => true} />);
  fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
  await waitFor(() => expect(resolveAccept).toBeTypeOf("function"));
  consent.unmount();
  const page = open();
  fireEvent.click(await screen.findByRole("radio", { name: "Reply Draft" }));
  fireEvent.change(await screen.findByLabelText("Client message"), { target: { value: draft.clientMessage } });
  fireEvent.change(screen.getByLabelText("Reply goal"), { target: { value: draft.replyGoal } });
  await act(async () => { resolveAccept!(); });
  await waitFor(() => expect(readAttachSessionId(productId)).toBe("A"));
  page.unmount(); open();
  await expectB();
  expect(readProductDraft(draftKey)?.values).toMatchObject({ clientMessage: draft.clientMessage });
  expect(starts).toHaveLength(0);
});

it("a chosen handoff keeps another accepted operation while selecting its own result", async () => {
  saveAccepted("C");
  const consent = renderHandoff(<HandoffConsent client={createPlatformApiClient()} handoffToken="token_abc" canOpenTarget={() => true} />);
  fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
  await waitFor(() => expect(resolveAccept).toBeTypeOf("function"));
  await act(async () => { resolveAccept!(); });
  await waitFor(() => expect(readAttachSessionId(productId)).toBe("A"));
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ scenarioSessionId: "C" });
  consent.unmount(); open();
  await screen.findByText("Result A");
  expect(starts).toHaveLength(0);
});

it.each([false, true])("explicit C survives reload over completed recovery A (scenario hint=%s)", async (hint) => {
  saveAccepted();
  const page = open(`?session=C${hint ? `&scenario=${scenarioId}` : ""}`);
  await screen.findByText("Result C");
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ scenarioSessionId: "A" });
  page.unmount(); open();
  await screen.findByText("Result C");
  expect(starts).toHaveLength(0);
});

it("an interrupted bare link keeps C and its Update mode together across reload", async () => {
  saveAccepted(); saveB(); deferredSession = "C";
  const page = open("?session=C");
  await waitFor(() => expect(sessions).toContain("C"));
  expect(new URL(window.location.href).searchParams.get("session")).toBe("C");
  page.unmount(); deferredSession = undefined; open();
  await screen.findByText("Result C");
  expect((screen.getByRole("radio", { name: "Update" }) as HTMLInputElement).checked).toBe(true);
  expect(screen.queryByLabelText("Client message")).toBeNull();
  expect(readProductDraft(draftKey)?.values).toEqual(draft);
  expect(starts).toHaveLength(0);
});

it("invalid hinted C and its explicit discard preserve recovery and active A", async () => {
  saveAccepted(); chooseAttachSession(productId, "A", "2026-11-13T00:00:00Z"); missingSession = "C";
  open(`?session=C&scenario=${scenarioId}`);
  fireEvent.click(await screen.findByRole("button", { name: "New task" }));
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ scenarioSessionId: "A" });
  expect(readAttachSessionId(productId)).toBe("A");
  expect(new URL(window.location.href).searchParams.has("session")).toBe(false);
  expect(starts).toHaveLength(0);
});

it.each(["throws", "ignores"])("storage that %s keeps the result URL until an explicit mode switch leaves it", async (failure) => {
  const setItem = Storage.prototype.setItem;
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
    if (key.startsWith("anytoolai.attach_session.")) {
      if (failure === "throws") throw new DOMException("Storage unavailable");
      return;
    }
    return setItem.call(this, key, value);
  });
  open(`?session=C&scenario=${scenarioId}`);
  await screen.findByText("Result C");
  expect(new URL(window.location.href).searchParams.get("session")).toBe("C");
  fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
  await screen.findByLabelText("Client message");
  expect(new URL(window.location.href).searchParams.has("session")).toBe(false);
  expect(new URL(window.location.href).searchParams.has("scenario")).toBe(false);
});

it("a completed own run still yields to the saved B form", async () => {
  saveAccepted(); saveB(); open(); await expectB(); expect(starts).toHaveLength(0);
});

it("a real own Update preserves its form binding and then yields to edited Reply Draft", async () => {
  let page = open();
  fireEvent.change(await screen.findByLabelText("Progress notes"), { target: { value: "Original update input" } });
  fireEvent.click(screen.getByRole("radio", { name: /warm/i }));
  fireEvent.click(screen.getByRole("button", { name: "Write update" }));
  await screen.findByText("Result A");
  page.unmount(); page = open();
  await screen.findByText("Result A");
  expect((screen.getByLabelText("Progress notes") as HTMLTextAreaElement).value).toBe("Original update input");
  fireEvent.click(screen.getByRole("radio", { name: "Reply Draft" }));
  fireEvent.change(await screen.findByLabelText("Client message"), { target: { value: draft.clientMessage } });
  fireEvent.change(screen.getByLabelText("Reply goal"), { target: { value: draft.replyGoal } });
  page.unmount(); open(); await expectB();
  expect(starts).toHaveLength(1);
});

it("running recovery wins while retaining chosen C for after it completes", async () => {
  saveAccepted(); chooseAttachSession(productId, "C", "2026-11-13T00:00:00Z"); runningA = true;
  const page = open();
  await waitFor(() => expect(sessions.filter((id) => id === "A").length).toBeGreaterThanOrEqual(2));
  expect(sessions).not.toContain("C");
  expect(readAttachSessionId(productId)).toBe("C");
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ scenarioSessionId: "A" });
  page.unmount(); runningA = false; open();
  await screen.findByText("Result C");
  expect(starts).toHaveLength(0);
});

it("visiting C preserves pending A and reload replays its original request and key", async () => {
  const request = { ...ids, frontendId: "web_mirror", input: { progress_notes: "Frozen A", tone: "friendly" } };
  persistPaidStartRecovery(recovery(), { version: 1, kind: "pending", owner, ...ids, idempotencyKey: "original_key", request });
  const page = open(`?session=C&scenario=${scenarioId}`);
  await screen.findByText("Result C");
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ kind: "pending", request });
  page.unmount(); open();
  await screen.findByText("Result A");
  expect(starts).toHaveLength(1);
  expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("original_key");
  const body = starts[0].body;
  if (typeof body !== "string") throw new Error("Expected a JSON request body");
  expect(JSON.parse(body)).toMatchObject({ input: request.input });
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  expect(readAttachSessionId(productId)).toBeUndefined();
});


it("single-mode ProposalAI also restores explicit C over old completed recovery A", async () => {
  responseDefinitions = [proposalAiDefinition];
  const { productId, scenarioId } = proposalAiDefinition;
  persistPaidStartRecovery(recovery(), { version: 1, kind: "accepted", owner, productId, scenarioId, scenarioSessionId: "A" });
  const page = open("?session=C", productId);
  await screen.findByText("Result C");
  page.unmount(); open(undefined, productId);
  await screen.findByText("Result C");
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ scenarioSessionId: "A" });
  expect(starts).toHaveLength(0);
});

it.each(["pending", "accepted", "storage-refused"])("a new %s start leaves an unpersisted result URL only after saving recovery", async (outcome) => {
  const setItem = Storage.prototype.setItem;
  const refusal = vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
    if (key.startsWith("anytoolai.attach_session.") ||
      (outcome === "storage-refused" && key.startsWith("anytoolai.paid_start."))) {
      throw new DOMException("Storage unavailable");
    }
    return setItem.call(this, key, value);
  });
  const page = open(`?session=C&scenario=${scenarioId}`);
  await screen.findByText("Result C");
  expect(new URL(window.location.href).searchParams.get("session")).toBe("C");
  if (outcome !== "storage-refused") refusal.mockRestore();
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (outcome === "pending" && path.endsWith("/start") && starts.length === 0) {
      starts.push(init!);
      return new Promise<Response>((resolve) => resolveSession.push(() => resolve(startResponse({ scenario_session_id: "A" }))));
    }
    return original(url, init);
  });
  deferredSession = "A";
  fireEvent.change(screen.getByLabelText("Progress notes"), { target: { value: "A newer own start" } });
  fireEvent.click(screen.getByRole("radio", { name: /warm/i }));
  fireEvent.click(screen.getByRole("button", { name: "Write update" }));
  if (outcome === "storage-refused") {
    await screen.findByRole("button", { name: "Try again" });
    expect(starts).toHaveLength(0);
    expect(readPaidStartRecovery(recovery(), productId)).toBeNull();
    expect(new URL(window.location.href).searchParams.get("session")).toBe("C");
    return;
  }
  await waitFor(() => expect(readPaidStartRecovery(recovery(), productId)?.kind).toBe(outcome));
  if (outcome === "accepted") await waitFor(() => expect(sessions).toContain("A"));
  expect(new URL(window.location.href).searchParams.has("session")).toBe(false);
  expect(new URL(window.location.href).searchParams.has("scenario")).toBe(false);
  page.unmount(); deferredSession = undefined; sessions.length = 0; open();
  await screen.findByText("Result A");
  expect(sessions).not.toContain("C");
  expect(starts).toHaveLength(outcome === "pending" ? 2 : 1);
  expect(new Set(starts.map((start) => new Headers(start.headers).get("Idempotency-Key"))).size).toBe(1);
  expect(new Set(starts.map((start) => start.body)).size).toBe(1);
});

it.each([false, true])("a missing old recovery does not hide selected C (single mode=%s)", async (singleMode) => {
  if (singleMode) responseDefinitions = [proposalAiDefinition];
  const { productId, scenarioId } = responseDefinitions[0];
  persistPaidStartRecovery(recovery(), { version: 1, kind: "accepted", owner, productId, scenarioId, scenarioSessionId: "A" });
  const page = open("?session=C", productId);
  await screen.findByText("Result C");
  page.unmount(); missingSession = "A"; sessions.length = 0; open(undefined, productId);
  await screen.findByText("Result C");
  expect(sessions).toContain("A");
  expect(sessions).toContain("C");
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ scenarioSessionId: "A" });
  expect(readAttachSessionId(productId)).toBe("C");
  expect(starts).toHaveLength(0);
});

it("an uncertain old recovery still gates selected C until retry resolves its status", async () => {
  saveAccepted(); chooseAttachSession(productId, "C", "2026-11-13T00:00:00Z");
  const original = fetcher.getMockImplementation()!;
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (path === "/v1/scenario-sessions/A") return errorResponse(503, "temporarily_unavailable");
    return original(url, init);
  });
  open();
  const retry = await screen.findByRole("button", { name: "Try again" });
  expect(sessions).not.toContain("C");
  expect(readPaidStartRecovery(recovery(), productId)).toMatchObject({ scenarioSessionId: "A" });
  fetcher.mockImplementation(original);
  fireEvent.click(retry);
  await screen.findByText("Result C");
  expect(starts).toHaveLength(0);
});
