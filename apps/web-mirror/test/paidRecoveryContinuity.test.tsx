import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { Suspense } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { persistPaidStartRecovery, readPaidStartRecovery, writePortalSession, type PlatformApiClient } from "@anytoolai/ce-kit";
import { createPlatformApiClient } from "../src/lib/apiClient";
import { getPaidPersistence, getPortalIdentity, installPortalSession, requirePortalAuthorization, tabStorage } from "../src/lib/portalSession";
import { chooseAttachSession, rememberAttachSession, readAttachSessionId, useAttachSession } from "../src/products/runtime/attachSession";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import { MultiModeProduct } from "../src/products/shared/MultiModeProduct";
import { PortalIdentityBoundary } from "../src/components/PortalIdentityBoundary";
import ProductPage from "../src/app/products/[productId]/page";
import { testProductDefinition, TEST_PRODUCT_MESSAGES_EN } from "./fixtures/testProductDefinition";
import { errorResponse, resultResponse, runtimeConfigResponse, sessionResponse, startResponse } from "./fixtures/platformResponses";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const render = makeRender(englishForAllLocales(TEST_PRODUCT_MESSAGES_EN));
const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const ids = { productId: "proposal_ai", scenarioId: "proposal_ai.generate_v1" };
const definition = { ...testProductDefinition, ...ids };
const fetched: string[] = [];
const fetcher = vi.fn<typeof fetch>();
function fetchUrl(url: Parameters<typeof fetch>[0]): URL {
  return new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url);
}
beforeEach(() => {
  window.sessionStorage.clear();
  window.history.replaceState(null, "", "/products/proposal_ai");
  requirePortalAuthorization(true);
  installPortalSession({ consumerId: "platform-kernel", consumerPolicyRevision: 1, owner, accessToken: "t".repeat(43), expiresAt: "2099-01-01T00:00:00Z" });
  fetched.length = 0;
  fetcher.mockReset();
  vi.stubGlobal("fetch", fetcher);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function AttachedProduct({ client }: { client: PlatformApiClient }) {
  const attach = useAttachSession(ids.productId, undefined);
  return <ProductRunPage client={client} definition={definition} {...attach} />;
}

it.each(["before", "after"])("a restored result document preserves a newer pending written %s New task", async (when) => {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  const starts: RequestInit[] = [];
  fetcher.mockImplementation(async (url, init) => {
    const path = fetchUrl(url).pathname;
    if (path.endsWith("runtime-config")) return runtimeConfigResponse(ids);
    if (path.endsWith("/start")) { starts.push(init!); return startResponse(); }
    if (path.startsWith("/v1/scenario-sessions/")) return sessionResponse();
    if (path.startsWith("/v1/results/")) return resultResponse(ids);
    throw new Error("unexpected request");
  });
  render(<ProductRunPage client={client} definition={definition} />);
  fireEvent.change(await screen.findByLabelText("Text"), { target: { value: "Old document input" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Generated result text.");
  const pending = { version: 1 as const, kind: "pending" as const, owner, ...ids, idempotencyKey: "newer_document_key",
    request: { ...ids, frontendId: "web_mirror", input: { text: "Frozen newer document input" } } };
  if (when === "before") persistPaidStartRecovery(persistence, pending);
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  if (when === "after") persistPaidStartRecovery(persistence, pending);
  const generation = getPortalIdentity().generation;
  act(() => { window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true })); });
  expect(getPortalIdentity().generation).toBe(generation);
  fireEvent.change(screen.getByLabelText("Text"), { target: { value: "A fresh stale-document request" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("An unfinished operation is saved. Choose Try again to reload and continue it.");
  expect(readPaidStartRecovery(persistence, ids.productId)).toEqual(pending);
  expect(starts).toHaveLength(1);
});

it.each(["accepted", "pending"])("reload after starting from a handoff result recovers the new %s operation", async (outcome) => {
  let reloaded = false;
  let finishFirstPoll: ((response: Response) => void) | undefined;
  const starts: RequestInit[] = [];
  fetcher.mockImplementation(async (url, init) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return runtimeConfigResponse(ids);
    if (path.endsWith("/start")) {
      starts.push(init!);
      if (outcome === "pending" && !reloaded) throw new TypeError("lost start response");
      return startResponse({ scenario_session_id: "new_session" });
    }
    if (path.endsWith("/old_session")) return sessionResponse({ scenario_session_id: "old_session", result_artifact_id: "old_result" });
    if (path.endsWith("/old_result")) return resultResponse(ids, { scenario_session_id: "old_session", result_artifact_id: "old_result", output: { text: "Previous handoff result" } });
    if (path.endsWith("/new_session")) return reloaded
      ? sessionResponse({ scenario_session_id: "new_session", result_artifact_id: "new_result" })
      : new Promise<Response>((resolve) => { finishFirstPoll = resolve; });
    if (path.endsWith("/new_result")) return resultResponse(ids, { scenario_session_id: "new_session", result_artifact_id: "new_result", output: { text: "New paid result" } });
    throw new Error("unexpected request");
  });
  chooseAttachSession(ids.productId, "old_session", "2026-11-10T00:00:00Z");
  const client = createPlatformApiClient();
  const first = render(<AttachedProduct client={client} />);
  await screen.findByText("Previous handoff result");
  fireEvent.change(screen.getByLabelText("Text"), { target: { value: "New paid input" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  if (outcome === "accepted") {
    await waitFor(() => expect(finishFirstPoll).toBeDefined());
    expect(readPaidStartRecovery(getPaidPersistence(client)!, ids.productId)).toMatchObject({ kind: "accepted", scenarioSessionId: "new_session" });
  } else {
    await screen.findByText("Could not start Test Product. Please try again.");
    expect(readPaidStartRecovery(getPaidPersistence(client)!, ids.productId)?.kind).toBe("pending");
  }
  first.unmount();
  await act(async () => { finishFirstPoll?.(sessionResponse()); });
  reloaded = true;
  fetched.length = 0;
  render(<AttachedProduct client={createPlatformApiClient()} />);
  await screen.findByText("New paid result");
  expect(screen.queryByText("Previous handoff result")).toBeNull();
  expect(fetched.filter((path) => path.startsWith("/v1/scenario-sessions/"))).toEqual(["/v1/scenario-sessions/new_session"]);
  expect(starts).toHaveLength(outcome === "accepted" ? 1 : 3);
  expect(new Set(starts.map((start) => new Headers(start.headers).get("Idempotency-Key"))).size).toBe(1);
  expect(new Set(starts.map((start) => start.body)).size).toBe(1);
  expect(readAttachSessionId(ids.productId)).toBeUndefined();
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  expect(readPaidStartRecovery(getPaidPersistence(createPlatformApiClient())!, ids.productId)).toBeNull();
});

it("a scenario left in the URL by an earlier deep link must not override pending recovery in another mode", async () => {
  const client = createPlatformApiClient();
  const productId = "acceptance_builder";
  const scenarioId = "acceptance_builder.check_v1";
  persistPaidStartRecovery(getPaidPersistence(client)!, { version: 1, kind: "pending", owner, productId, scenarioId, idempotencyKey: "original_key",
    request: { productId, scenarioId, frontendId: "web_mirror", input: { text: "Frozen check input" } } });
  fetcher.mockImplementation(async (url) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return runtimeConfigResponse({ productId, scenarioId });
    if (path.endsWith("/start")) return startResponse();
    if (path.startsWith("/v1/scenario-sessions/")) return sessionResponse();
    if (path.startsWith("/v1/results/")) return resultResponse({ productId, scenarioId });
    throw new Error("unexpected request");
  });
  render(<MultiModeProduct client={client} legend="Mode" name="mode" attachScenarioId="acceptance_builder.draft_v1" modes={[
    { id: "draft", label: "Draft", definition: { ...testProductDefinition, productId, scenarioId: "acceptance_builder.draft_v1" } },
    { id: "check", label: "Check", definition: { ...testProductDefinition, productId, scenarioId } },
  ]} />);
  await screen.findByText("Generated result text.");
  expect((screen.getByRole("radio", { name: "Check" }) as HTMLInputElement).checked).toBe(true);
  const start = fetcher.mock.calls.find(([url]) => fetchUrl(url).pathname.endsWith("/start"));
  expect(new Headers(start?.[1]?.headers).get("Idempotency-Key")).toBe("original_key");
});

it("an explicitly selected result chooses its scenario before a different saved recovery", async () => {
  const client = createPlatformApiClient();
  const productId = "acceptance_builder";
  const scenarioId = "acceptance_builder.check_v1";
  persistPaidStartRecovery(getPaidPersistence(client)!, { version: 1, kind: "accepted", owner, productId,
    scenarioId: "acceptance_builder.draft_v1", scenarioSessionId: "previous_session" });
  fetcher.mockImplementation(async (url) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return runtimeConfigResponse({ productId, scenarioId });
    if (path.endsWith("/selected_session")) return sessionResponse({ scenario_id: scenarioId, scenario_session_id: "selected_session" });
    if (path.startsWith("/v1/results/")) return resultResponse({ productId, scenarioId });
    throw new Error("unexpected request");
  });
  render(<MultiModeProduct client={client} legend="Mode" name="mode" attachFromUrl attachSessionId="selected_session" attachScenarioId="acceptance_builder.draft_v1" modes={[
    { id: "draft", label: "Draft", definition: { ...testProductDefinition, productId, scenarioId: "acceptance_builder.draft_v1" } },
    { id: "check", label: "Check", definition: { ...testProductDefinition, productId, scenarioId } },
  ]} />);
  await screen.findByText("Generated result text.");
  expect((screen.getByRole("radio", { name: "Check" }) as HTMLInputElement).checked).toBe(true);
  expect(fetched.some((path) => path.endsWith("/start") || path.endsWith("/previous_session"))).toBe(false);
});

it("the product route keeps an explicit result's scenario while consuming the URL before boot completes", async () => {
  const productId = "acceptance_builder";
  const scenarioId = "acceptance_builder.check_v1";
  window.history.replaceState(null, "", `/products/${productId}?session=selected_session&scenario=${scenarioId}&paid=1`);
  let finishRuntime: ((response: Response) => void) | undefined;
  fetcher.mockImplementation(async (url) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return new Promise<Response>((resolve) => { finishRuntime = resolve; });
    if (path.endsWith("/selected_session")) return sessionResponse({ scenario_id: scenarioId, scenario_session_id: "selected_session", status: "failed", result_artifact_id: null });
    if (path === "/v1/client-events") return Response.json({ event_id: "event_1", event_type: "web.product_viewed" });
    throw new Error("unexpected request");
  });
  const params = Promise.resolve({ productId });
  const searchParams = Promise.resolve({ session: "selected_session", scenario: scenarioId, paid: "1" });
  let view!: ReturnType<typeof render>;
  await act(async () => {
    view = render(<Suspense fallback={null}><ProductPage params={params} searchParams={searchParams} /></Suspense>);
    await params;
    await searchParams;
  });
  await waitFor(() => expect(finishRuntime).toBeDefined());
  expect(window.location.search).toBe("?paid=1");
  const consumed = Promise.resolve({ paid: "1" });
  await act(async () => {
    view.rerender(<Suspense fallback={null}><ProductPage params={params} searchParams={consumed} /></Suspense>);
  });
  await act(async () => { finishRuntime!(runtimeConfigResponse({ productId, scenarioId })); });
  await waitFor(() => expect(fetched).toContain("/v1/scenario-sessions/selected_session"));
  expect((screen.getAllByRole("radio").find((radio) => (radio as HTMLInputElement).value === "check") as HTMLInputElement).checked).toBe(true);
  expect(fetched.some((path) => path.endsWith("/start"))).toBe(false);
});

it("a historical check link preserves a pending draft before boot, after failure and across reload", async () => {
  const productId = "acceptance_builder";
  const scenarioId = "acceptance_builder.check_v1";
  const draftId = "acceptance_builder.draft_v1";
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  const pending = { version: 1 as const, kind: "pending" as const, owner, productId, scenarioId: draftId, idempotencyKey: "original_key",
    request: { productId, scenarioId: draftId, frontendId: "web_mirror", input: { brief_text: "Frozen original draft" } } };
  persistPaidStartRecovery(persistence, pending);
  window.history.replaceState(null, "", `/products/${productId}?session=historical_check&scenario=${scenarioId}&paid=1`);
  let finishRuntime: ((response: Response) => void) | undefined;
  let finishPoll: ((response: Response) => void) | undefined;
  const starts: RequestInit[] = [];
  const productConfig = () => runtimeConfigResponse({ productId, scenarioId }, {
    scenario_ids: [scenarioId, draftId],
    scenarios: [scenarioId, draftId].map((id) => ({
      scenario_id: id, version: 1, allowed_next_actions: ["copy_result"],
      input_renderer_hint: { renderer: "json_schema", schema_ref: `${productId}.input_v1`, schema_version: 1 },
      output_renderer_hint: { renderer: "json_schema", schema_ref: `${productId}.output_v1`, schema_version: 1 },
    })),
  });
  fetcher.mockImplementation(async (url, init) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return finishRuntime ? productConfig()
      : new Promise<Response>((resolve) => { finishRuntime = resolve; });
    if (path.endsWith("/historical_check")) return sessionResponse({ scenario_id: scenarioId, scenario_session_id: "historical_check", status: "failed", result_artifact_id: null });
    if (path.endsWith("/start")) { starts.push(init!); return startResponse({ scenario_session_id: "original_draft" }); }
    if (path.endsWith("/original_draft")) return new Promise<Response>((resolve) => { finishPoll = resolve; });
    if (path === "/v1/client-events") return Response.json({ event_id: "event_1", event_type: "web.product_viewed" });
    throw new Error("unexpected request");
  });
  const params = Promise.resolve({ productId });
  const searchParams = Promise.resolve({ session: "historical_check", scenario: scenarioId, paid: "1" });
  let first!: ReturnType<typeof render>;
  await act(async () => {
    first = render(<Suspense fallback={null}><ProductPage params={params} searchParams={searchParams} /></Suspense>);
    await params; await searchParams;
  });
  await waitFor(() => expect(finishRuntime).toBeDefined());
  expect(readPaidStartRecovery(persistence, productId)).toEqual(pending);
  await act(async () => { finishRuntime!(productConfig()); });
  await screen.findByRole("alert");
  expect(fetched).toContain("/v1/scenario-sessions/historical_check");
  expect(readPaidStartRecovery(persistence, productId)).toEqual(pending);
  expect(starts).toHaveLength(0);
  first.unmount();
  const consumed = Promise.resolve({ paid: "1" });
  await act(async () => {
    render(<Suspense fallback={null}><ProductPage params={params} searchParams={consumed} /></Suspense>);
    await consumed;
  });
  await waitFor(() => expect(finishPoll).toBeDefined());
  expect(starts).toHaveLength(1);
  expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("original_key");
  expect(starts[0].body).toContain('"input":{"brief_text":"Frozen original draft"}');
  expect(fetched).toContain(`/v1/products/${productId}/scenarios/${draftId}/start`);
  cleanup();
  await act(async () => { finishPoll!(sessionResponse({ status: "failed", result_artifact_id: null })); });
});

it.each(["same", "different"])("leaving a selected result preserves a pending operation in the %s scenario and refuses a fresh key", async (scenario) => {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  const pendingScenarioId = scenario === "same" ? ids.scenarioId : "proposal_ai.other_v1";
  const pending = { version: 1 as const, kind: "pending" as const, owner, productId: ids.productId, scenarioId: pendingScenarioId, idempotencyKey: "original_key",
    request: { productId: ids.productId, scenarioId: pendingScenarioId, frontendId: "web_mirror", input: { text: "Frozen original input" } } };
  persistPaidStartRecovery(persistence, pending);
  fetcher.mockImplementation(async (url) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return runtimeConfigResponse(ids);
    if (path.endsWith("/historical_session")) return sessionResponse({ scenario_id: ids.scenarioId, scenario_session_id: "historical_session" });
    if (path.startsWith("/v1/results/")) return resultResponse(ids, { scenario_session_id: "historical_session" });
    throw new Error("unexpected request");
  });
  render(<ProductRunPage client={client} definition={definition} attachFromUrl attachSessionId="historical_session" />);
  await screen.findByText("Generated result text.");
  expect(readPaidStartRecovery(persistence, ids.productId)).toEqual(pending);
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  expect(readPaidStartRecovery(persistence, ids.productId)).toEqual(pending);
  fireEvent.change(screen.getByLabelText("Text"), { target: { value: "A fresh request" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("An unfinished operation is saved. Choose Try again to reload and continue it.");
  expect(readPaidStartRecovery(persistence, ids.productId)).toEqual(pending);
  expect(fetched.some((path) => path.endsWith("/start"))).toBe(false);
});

it("a document restored from history must discard identity cleared by logout in a newer document", async () => {
  render(<PortalIdentityBoundary>{() => <p>Private result belonging to previous owner</p>}</PortalIdentityBoundary>);
  expect(await screen.findByText("Private result belonging to previous owner")).toBeTruthy();
  // While this document is in BFCache another same-tab document signs out. Its memory is
  // separate, but sessionStorage is shared; these are requirePortalAuthorization(true)'s writes.
  window.sessionStorage.removeItem("anytoolai.portal_session.v1");
  window.sessionStorage.setItem("anytoolai.portal_mode.v1", JSON.stringify({ version: 1, owner: null, custodyId: "logout_document_custody" }));
  await act(async () => { window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true })); });
  expect(screen.queryByText("Private result belonging to previous owner")).toBeNull();
});

it.each(["logout", "clear", "invalid"])("refuses stale-client sends after another document changes custody: %s", async (change) => {
  const client = createPlatformApiClient();
  if (change === "logout") {
    window.sessionStorage.removeItem("anytoolai.portal_session.v1");
    window.sessionStorage.setItem("anytoolai.portal_mode.v1", JSON.stringify({ version: 1, owner: null, custodyId: "logout_document_custody" }));
  } else if (change === "clear") {
    window.sessionStorage.clear();
  } else {
    window.sessionStorage.setItem("anytoolai.portal_session.v1", "malformed JSON");
  }
  expect(await client.request({ path: "/v1/scenario-sessions/old_session" })).toEqual({ ok: false, error: { type: "aborted" } });
  expect(getPortalIdentity().kind).toBe("required");
  expect(fetcher).not.toHaveBeenCalled();
});

it("discards a late result from the previous owner without removing the new owner's recovery", async () => {
  render(<PortalIdentityBoundary>{(client) => <p>Owner: {client.portalIdentity?.owner.userId}</p>}</PortalIdentityBoundary>);
  const client = createPlatformApiClient();
  let finish!: (response: Response) => void;
  fetcher.mockReturnValueOnce(new Promise<Response>((resolve) => { finish = resolve; }));
  const pending = client.request({ path: "/v1/scenario-sessions/old_session" });
  const nextOwner = { ...owner, userId: "22222222-2222-2222-2222-222222222222" };
  // These writes belong to a newer document in the same tab; this document's module is still cached.
  writePortalSession(tabStorage, { consumerId: "platform-kernel", consumerPolicyRevision: 1, owner: nextOwner, accessToken: "n".repeat(43), expiresAt: "2099-01-01T00:00:00Z" });
  window.sessionStorage.setItem("anytoolai.portal_mode.v1", JSON.stringify({ version: 1, owner: nextOwner, custodyId: "newer_document_custody" }));
  const recovery = { version: 1, kind: "accepted", owner: nextOwner, ...ids, scenarioSessionId: "new_owner_session" };
  window.sessionStorage.setItem(`anytoolai.paid_start.v1.${ids.productId}`, JSON.stringify(recovery));
  await act(async () => { finish(sessionResponse()); });
  expect(await pending).toEqual({ ok: false, error: { type: "aborted" } });
  expect(screen.queryByText(`Owner: ${owner.userId}`)).toBeNull();
  expect(await screen.findByText(`Owner: ${nextOwner.userId}`)).toBeTruthy();
  expect(readPaidStartRecovery(getPaidPersistence(createPlatformApiClient())!, ids.productId)).toEqual(recovery);
});

it("keeps the current client on unchanged page restoration and replaces it on same-owner token renewal", async () => {
  let displayedClient: PlatformApiClient | undefined;
  render(<PortalIdentityBoundary>{(client) => { displayedClient = client; return <p>Authorized</p>; }}</PortalIdentityBoundary>);
  const original = displayedClient!;
  const persistence = getPaidPersistence(original)!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner, ...ids, scenarioSessionId: "session_1" });
  await act(async () => { window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true })); });
  expect(displayedClient).toBe(original);
  writePortalSession(tabStorage, { consumerId: "platform-kernel", consumerPolicyRevision: 1, owner, accessToken: "n".repeat(43), expiresAt: "2099-01-01T00:00:00Z" });
  await act(async () => { window.dispatchEvent(new Event("focus")); });
  expect(displayedClient).not.toBe(original);
  expect(readPaidStartRecovery(getPaidPersistence(displayedClient!)!, ids.productId)?.kind).toBe("accepted");
  expect(await original.request({ path: "/v1/scenario-sessions/session_1" })).toEqual({ ok: false, error: { type: "aborted" } });
  expect(fetcher).not.toHaveBeenCalled();
});

it.each(["pending", "accepted"] as const)("restores a %s non-default paid mode before a stale handoff when config is unavailable", async (kind) => {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  const productId = "acceptance_builder";
  const scenarioId = "acceptance_builder.check_v1";
  const product = { productId, scenarioId };
  const base = { version: 1 as const, owner, ...product };
  persistPaidStartRecovery(persistence, kind === "pending"
    ? { ...base, kind, idempotencyKey: "original_key", request: { ...product, frontendId: "web_mirror", input: { text: "Frozen check input" } } }
    : { ...base, kind, scenarioSessionId: "recovered_session" });
  rememberAttachSession(productId, "old_handoff", "2026-11-10T00:00:00Z");
  const starts: RequestInit[] = [];
  fetcher.mockImplementation(async (url, init) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return errorResponse(404, "product_not_found");
    if (path.endsWith("/start")) { starts.push(init!); return startResponse({ scenario_session_id: "recovered_session" }); }
    if (path.endsWith("/recovered_session")) return sessionResponse({ scenario_id: scenarioId, scenario_session_id: "recovered_session" });
    if (path.startsWith("/v1/results/")) return resultResponse(product, { scenario_session_id: "recovered_session" });
    throw new Error("unexpected request");
  });
  function Attached() {
    const attach = useAttachSession(productId, undefined);
    return <MultiModeProduct client={client} {...attach} legend="Mode" name="recovery-mode" modes={[
      { id: "draft", label: "Draft", definition: { ...testProductDefinition, productId, scenarioId: "acceptance_builder.draft_v1" } },
      { id: "check", label: "Check", definition: { ...testProductDefinition, ...product, outputSchema: { schemaRef: `${productId}.output_v1`, schemaVersion: 1 } } },
    ]} />;
  }
  const first = render(<Attached />);
  await screen.findByText("Generated result text.");
  expect((screen.getByRole("radio", { name: "Check" }) as HTMLInputElement).checked).toBe(true);
  expect(readAttachSessionId(productId)).toBe("old_handoff");
  expect(starts).toHaveLength(kind === "pending" ? 1 : 0);
  if (kind === "pending") {
    expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("original_key");
    expect(starts[0].body).toContain('"input":{"text":"Frozen check input"}');
  }
  first.unmount();
  render(<Attached />);
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(kind === "pending" ? 1 : 0);
  expect(fetched.some((path) => path.endsWith("/old_handoff") || path.includes("identity/guest") || path.endsWith("/quota"))).toBe(false);
});

it.each([false, true])("explicit discard of an unavailable paid session preserves a newer pending operation (newer=%s)", async (newer) => {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  const productId = "acceptance_builder";
  const scenarioId = "acceptance_builder.check_v1";
  const product = { productId, scenarioId };
  persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner, ...product, scenarioSessionId: "missing_session" });
  chooseAttachSession(productId, "other_handoff", "2026-11-10T00:00:00Z");
  window.history.replaceState(null, "", `/products/${productId}?session=missing_session`);
  const starts: RequestInit[] = [];
  fetcher.mockImplementation(async (url, init) => {
    const path = fetchUrl(url).pathname;
    fetched.push(path);
    if (path.endsWith("runtime-config")) return runtimeConfigResponse({ ...product,
      scenarioId: newer ? scenarioId : "acceptance_builder.draft_v1" });
    if (path.endsWith("/missing_session")) return errorResponse(404, "scenario_session_not_found");
    if (path.endsWith("/start")) { starts.push(init!); return startResponse(); }
    if (path.endsWith("/session_1")) return sessionResponse({ scenario_id: scenarioId });
    if (path.startsWith("/v1/results/")) return resultResponse(product);
    throw new Error("unexpected request");
  });
  function Attached() {
    const attach = useAttachSession(productId, "missing_session");
    return <MultiModeProduct client={client} {...attach} legend="Mode" name="discard-mode" modes={[
      { id: "draft", label: "Draft", definition: { ...testProductDefinition, productId, scenarioId: "acceptance_builder.draft_v1" } },
      { id: "check", label: "Check", definition: { ...testProductDefinition, ...product } },
    ]} />;
  }
  render(<Attached />);
  await screen.findByRole("button", { name: "New task" });
  expect(starts).toHaveLength(0);
  if (newer) persistPaidStartRecovery(persistence, { version: 1, kind: "pending", owner, ...product, idempotencyKey: "newer_key",
    request: { ...product, frontendId: "web_mirror", input: { text: "Frozen newer request" } } });
  fireEvent.click(screen.getByRole("button", { name: "New task" }));
  if (newer) {
    await screen.findByText("Generated result text.");
    expect(starts).toHaveLength(1);
    expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("newer_key");
    expect(starts[0].body).toContain('"input":{"text":"Frozen newer request"}');
  } else {
    await screen.findByRole("form");
    expect(readPaidStartRecovery(persistence, productId)).toBeNull();
    expect(starts).toHaveLength(0);
  }
  expect(readAttachSessionId(productId)).toBe("other_handoff");
  expect(fetched.some((path) => path.endsWith("/other_handoff"))).toBe(false);
});

it("an obsolete mode resolver leaves the current owner's pending request intact", async () => {
  const obsoleteClient = createPlatformApiClient();
  const nextOwner = { ...owner, userId: "22222222-2222-2222-2222-222222222222" };
  installPortalSession({ consumerId: "platform-kernel", consumerPolicyRevision: 1, owner: nextOwner,
    accessToken: "n".repeat(43), expiresAt: "2099-01-01T00:00:00Z" });
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  const pending = { version: 1 as const, kind: "pending" as const, owner: nextOwner, ...ids, idempotencyKey: "new_owner_key",
    request: { ...ids, frontendId: "web_mirror", input: { text: "Next owner's private input" } } };
  persistPaidStartRecovery(persistence, pending);
  render(<MultiModeProduct client={obsoleteClient} legend="Mode" name="obsolete-mode" modes={[
    { id: "main", label: "Main", definition },
  ]} />);
  await act(async () => {});
  expect(readPaidStartRecovery(persistence, ids.productId)).toEqual(pending);
  expect(fetcher).not.toHaveBeenCalled();
  expect(screen.queryByRole("form")).toBeNull();
});
