import { StrictMode } from "react";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { persistPaidStartRecovery, readPaidStartRecovery } from "@anytoolai/ce-kit";
import { createPlatformApiClient } from "../src/lib/apiClient";
import { getPaidPersistence, installPortalSession, requirePortalAuthorization } from "../src/lib/portalSession";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import { MultiModeProduct } from "../src/products/shared/MultiModeProduct";
import { productDraftKey, readProductDraft, readProductDraftScenario, saveDraftRun, saveDraftValues, saveProductDraftScenario } from "../src/products/runtime/draftStorage";
import { testProductDefinition, TEST_PRODUCT_IDS, TEST_PRODUCT_MESSAGES_EN } from "./fixtures/testProductDefinition";
import { resultResponse, runtimeConfigResponse, sessionResponse, startResponse } from "./fixtures/platformResponses";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const render = makeRender(englishForAllLocales({ ...TEST_PRODUCT_MESSAGES_EN, other: TEST_PRODUCT_MESSAGES_EN.run }));
const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const otherOwner = { ...owner, userId: "22222222-2222-2222-2222-222222222222" };
const definition = {
  ...testProductDefinition,
  draft: { parseValues: (raw: unknown) => typeof raw === "object" && raw !== null && "text" in raw && typeof raw.text === "string"
    ? { text: raw.text } : null },
};
const fetcher = vi.fn<typeof fetch>();
const paths: string[] = [];
const starts: RequestInit[] = [];

function authorize(nextOwner = owner) {
  installPortalSession({ consumerId: "platform-kernel", consumerPolicyRevision: 1, owner: nextOwner,
    accessToken: "t".repeat(43), expiresAt: "2099-01-01T00:00:00Z" });
}
function open() {
  return render(<StrictMode><ProductRunPage client={createPlatformApiClient()} definition={definition} /></StrictMode>);
}
function textField() { return screen.getByLabelText<HTMLTextAreaElement>("Text"); }

beforeEach(() => {
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/products/test_product");
  requirePortalAuthorization(true);
  authorize();
  paths.length = 0;
  starts.length = 0;
  fetcher.mockReset().mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    paths.push(path);
    if (path.endsWith("runtime-config")) {
      const config = await runtimeConfigResponse(TEST_PRODUCT_IDS).json() as { scenarios: Record<string, unknown>[]; scenario_ids: string[] };
      config.scenarios.push({ ...config.scenarios[0], scenario_id: "test_product.other_v1" });
      config.scenario_ids.push("test_product.other_v1");
      return Response.json(config);
    }
    if (path.endsWith("/start")) { starts.push(init!); return startResponse(); }
    if (path.startsWith("/v1/scenario-sessions/")) return sessionResponse({ scenario_id: TEST_PRODUCT_IDS.scenarioId });
    if (path.startsWith("/v1/results/")) return resultResponse(TEST_PRODUCT_IDS);
    throw new Error("Unexpected guest/quota request: " + path);
  });
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it("does not restore a guest draft in a Portal-owned form", async () => {
  saveDraftValues(productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope), { text: "Guest private text" });
  open();
  await screen.findByLabelText("Text");
  expect(textField().value).toBe("");
});

it.each(["reauthorize", "change-owner", "logout"] as const)("restores only the current owner's form after %s", async (change) => {
  const page = open();
  await screen.findByLabelText("Text");
  fireEvent.change(textField(), { target: { value: "Owner A private draft" } });
  page.unmount();
  requirePortalAuthorization(change === "logout");
  authorize(change === "change-owner" ? otherOwner : owner);
  open();
  await screen.findByLabelText("Text");
  expect(textField().value).toBe(change === "reauthorize" ? "Owner A private draft" : "");
  expect(starts).toHaveLength(0);
});

it.each((["pending", "accepted"] as const).flatMap((kind) => (["guest", "paid"] as const).map((scope) => ({ kind, scope }))))(
  "restores paid $kind without polling a $scope draft's saved run", async ({ kind, scope }) => {
  const key = productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope, scope === "paid" ? owner : undefined);
  saveDraftValues(key, { text: "Old guest draft" });
  saveDraftRun(key, { scenarioSessionId: "stale_session", input: { text: "Old guest input" } });
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  persistPaidStartRecovery(persistence, kind === "pending"
    ? { version: 1, kind, owner, ...TEST_PRODUCT_IDS, idempotencyKey: "original_key",
      request: { ...TEST_PRODUCT_IDS, frontendId: "web_mirror", input: { text: "Frozen paid input" } } }
    : { version: 1, kind, owner, ...TEST_PRODUCT_IDS, scenarioSessionId: "session_1" });
  open();
  await screen.findByText("Generated result text.");
  expect(paths).not.toContain("/v1/scenario-sessions/stale_session");
  expect(starts).toHaveLength(kind === "pending" ? 1 : 0);
  if (kind === "pending") {
    expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("original_key");
    expect(starts[0].body).toContain("Frozen paid input");
  }
  expect(readPaidStartRecovery(persistence, TEST_PRODUCT_IDS.productId)).toMatchObject({ kind: "accepted", scenarioSessionId: "session_1" });
});

it("keeps the paid draft and selected mode isolated even when another owner's entries remain", () => {
  const key = productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope, otherOwner);
  saveDraftValues(key, { text: "Other owner private text" });
  saveProductDraftScenario(TEST_PRODUCT_IDS.productId, "other_scenario", otherOwner);
  expect(readProductDraft(productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope, owner))).toBeUndefined();
  expect(readProductDraftScenario(TEST_PRODUCT_IDS.productId, owner)).toBeUndefined();
  expect(readProductDraft(productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope))).toBeUndefined();
});

it.each(["reauthorize", "change-owner", "logout"] as const)("restores only the current owner's selected mode after %s", async (change) => {
  const modes = [
    { id: "first", label: "First", definition },
    { id: "second", label: "Second", definition: { ...definition, scenarioId: "test_product.other_v1", messageScope: "other" } },
  ] as const;
  function openModes() {
    return render(<StrictMode><MultiModeProduct client={createPlatformApiClient()} modes={modes} legend="Mode" name="mode" /></StrictMode>);
  }
  const page = openModes();
  fireEvent.click(await screen.findByRole("radio", { name: "Second" }));
  page.unmount();
  requirePortalAuthorization(change === "logout");
  authorize(change === "change-owner" ? otherOwner : owner);
  openModes();
  const selected = await screen.findByRole<HTMLInputElement>("radio", { name: change === "reauthorize" ? "Second" : "First" });
  expect(selected.checked).toBe(true);
  expect(starts).toHaveLength(0);
});

it("clears a paid form and accepted recovery on New task without affecting guest drafts", async () => {
  const guestKey = productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope);
  saveDraftValues(guestKey, { text: "Guest draft survives" });
  const page = open();
  await screen.findByLabelText("Text");
  fireEvent.change(textField(), { target: { value: "New paid task" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Generated result text.");
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  page.unmount();
  paths.length = 0;
  open();
  await screen.findByLabelText("Text");
  expect(textField().value).toBe("");
  expect(paths.some((path) => path.startsWith("/v1/scenario-sessions/"))).toBe(false);
  expect(window.sessionStorage.getItem(guestKey)).toContain("Guest draft survives");
});

it("restores own form after completed paid run and reload", async () => {
  const page = open();
  await screen.findByLabelText("Text");
  fireEvent.change(textField(), { target: { value: "Original paid task" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Generated result text.");
  page.unmount();
  const key = productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope, owner);
  expect(readProductDraft(key)?.values).toEqual({ text: "Original paid task" });
  open();
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(1);
  expect(textField().value).toBe("Original paid task");
});

it("preserves a later selected mode after completed paid run", async () => {
  const modes = [
    { id: "first", label: "First", definition },
    { id: "second", label: "Second", definition: { ...definition, scenarioId: "test_product.other_v1", messageScope: "other" } },
  ] as const;
  function openModes() {
    return render(<StrictMode><MultiModeProduct client={createPlatformApiClient()} modes={modes} legend="Mode" name="mode" /></StrictMode>);
  }
  const page = openModes();
  await screen.findByLabelText("Text");
  fireEvent.change(textField(), { target: { value: "Mode A task" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Generated result text.");
  fireEvent.click(screen.getByRole("radio", { name: "Second" }));
  expect(readProductDraftScenario(TEST_PRODUCT_IDS.productId, owner)).toBe("test_product.other_v1");
  page.unmount();
  openModes();
  await screen.findByLabelText("Text");
  expect(starts).toHaveLength(1);
  expect(screen.getByRole<HTMLInputElement>("radio", { name: "Second" }).checked).toBe(true);
});

it.each([false, true])("offers manual restoration only for unbound drafts (foreign binding: %s)", async (foreignBinding) => {
  const key = productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope, owner);
  saveDraftValues(key, { text: "Saved editable fields" });
  if (foreignBinding) saveDraftRun(key, { scenarioSessionId: "other_result", input: { text: "Other input" } });
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  const accepted = { version: 1, kind: "accepted", owner, ...TEST_PRODUCT_IDS, scenarioSessionId: "session_1" } as const;
  persistPaidStartRecovery(persistence, accepted);
  open();
  await screen.findByText("Generated result text.");
  expect(textField().value).toBe("");
  const before = [...paths];
  fireEvent.click(screen.getByRole("button", { name: "Restore saved draft" }));
  expect(textField().value).toBe("Saved editable fields");
  expect(paths).toEqual(before);
  expect(starts).toHaveLength(0);
  expect(readPaidStartRecovery(persistence, TEST_PRODUCT_IDS.productId)).toEqual(accepted);
  expect(readProductDraft(key)?.run?.scenarioSessionId).toBe(foreignBinding ? "other_result" : undefined);
});

it("restores editable values separately from original input even with unavailable config", async () => {
  const page = open();
  await screen.findByLabelText("Text");
  fireEvent.change(textField(), { target: { value: "Original input" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Generated result text.");
  fireEvent.change(textField(), { target: { value: "Next edited draft" } });
  page.unmount();
  const previous = fetcher.getMockImplementation()!;
  fetcher.mockImplementation((url, init) => (typeof url === "string" ? url : url instanceof URL ? url.href : url.url).includes("runtime-config")
    ? Promise.resolve(Response.json({}, { status: 503 })) : previous(url, init));
  open();
  await screen.findByText("Generated result text.");
  expect(textField().value).toBe("Next edited draft");
  expect(textField().disabled).toBe(true);
  expect(readProductDraft(productDraftKey(TEST_PRODUCT_IDS.productId, definition.messageScope, owner))?.run?.input)
    .toEqual({ text: "Original input" });
  expect(starts).toHaveLength(1);
});

it("explicitly opening result A replaces saved mode B for the following reload", async () => {
  const modes = [
    { id: "first", label: "First", definition },
    { id: "second", label: "Second", definition: { ...definition, scenarioId: "test_product.other_v1", messageScope: "other" } },
  ] as const;
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner, ...TEST_PRODUCT_IDS, scenarioSessionId: "session_1" });
  saveProductDraftScenario(TEST_PRODUCT_IDS.productId, "test_product.other_v1", owner);
  const page = render(<MultiModeProduct client={createPlatformApiClient()} modes={modes} legend="Mode" name="mode"
    attachSessionId="session_1" attachFromUrl />);
  await screen.findByText("Generated result text.");
  expect(readProductDraftScenario(TEST_PRODUCT_IDS.productId, owner)).toBe(TEST_PRODUCT_IDS.scenarioId);
  page.unmount();
  render(<MultiModeProduct client={createPlatformApiClient()} modes={modes} legend="Mode" name="mode" />);
  await screen.findByLabelText("Text");
  expect(screen.getByRole<HTMLInputElement>("radio", { name: "First" }).checked).toBe(true);
  expect(starts).toHaveLength(0);
});

it.each(["started", "running", "waiting_for_user"] as const)("keeps accepted %s above a saved later mode", async (status) => {
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner, ...TEST_PRODUCT_IDS, scenarioSessionId: "session_1" });
  saveProductDraftScenario(TEST_PRODUCT_IDS.productId, "test_product.other_v1", owner);
  const previous = fetcher.getMockImplementation()!;
  fetcher.mockImplementation((url, init) => (typeof url === "string" ? url : url instanceof URL ? url.href : url.url).includes("scenario-sessions")
    ? Promise.resolve(sessionResponse({ scenario_id: TEST_PRODUCT_IDS.scenarioId, status })) : previous(url, init));
  render(<MultiModeProduct client={createPlatformApiClient()} modes={[
    { id: "first", label: "First", definition },
    { id: "second", label: "Second", definition: { ...definition, scenarioId: "test_product.other_v1", messageScope: "other" } },
  ]} legend="Mode" name="mode" />);
  await screen.findByLabelText("Text");
  await waitFor(() => expect(screen.getByRole<HTMLInputElement>("radio", { name: "First" }).checked).toBe(true));
  expect(readProductDraftScenario(TEST_PRODUCT_IDS.productId, owner)).toBe("test_product.other_v1");
  expect(starts).toHaveLength(0);
});
