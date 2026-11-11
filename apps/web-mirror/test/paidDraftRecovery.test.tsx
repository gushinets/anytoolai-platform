import { StrictMode } from "react";
import { cleanup, fireEvent, screen } from "@testing-library/react";
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

const render = makeRender(englishForAllLocales(TEST_PRODUCT_MESSAGES_EN));
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
    if (path.endsWith("runtime-config")) return runtimeConfigResponse(TEST_PRODUCT_IDS);
    if (path.endsWith("/start")) { starts.push(init!); return startResponse(); }
    if (path.startsWith("/v1/scenario-sessions/")) return sessionResponse();
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
    { id: "second", label: "Second", definition: { ...definition, scenarioId: "test_product.other_v1" } },
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
