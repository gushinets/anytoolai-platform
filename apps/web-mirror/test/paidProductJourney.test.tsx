import { webcrypto } from "node:crypto";
import { act, cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { readPaidStartRecovery, persistPaidStartRecovery, prepareScenarioStart, preparePortalAuthorization, readPortalAuthorization, readPortalSession, writePortalSession } from "@anytoolai/ce-kit";
import { ProductRunPage } from "../src/products/runtime/ProductRunPage";
import { MultiModeProduct } from "../src/products/shared/MultiModeProduct";
import { createPlatformApiClient, getPlatformApiClient } from "../src/lib/apiClient";
import { getPaidPersistence, getPortalIdentity, installPortalSession, requirePortalAuthorization, synchronizePortalIdentity, tabStorage } from "../src/lib/portalSession";
import { beginPortalAuthorization, completePortalAuthorization, readPortalContinuation } from "../src/lib/portalAuthorization";
import { PortalIdentityBoundary } from "../src/components/PortalIdentityBoundary";
import { PortalSessionFlow } from "../src/components/PortalSessionFlow";
import { HandoffConsent } from "../src/components/HandoffConsent";
import { HANDOFF_MESSAGES } from "../src/components/handoffMessages";
import { handoffPreviewPayload } from "@anytoolai/ce-kit/test/handoffs/fixtures";
import { testProductDefinition, TEST_PRODUCT_MESSAGES_EN } from "./fixtures/testProductDefinition";
import { errorResponse, resultResponse, runtimeConfigResponse, sessionResponse, startResponse } from "./fixtures/platformResponses";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const routerPush = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: routerPush }) }));
const render = makeRender(englishForAllLocales(TEST_PRODUCT_MESSAGES_EN));
const renderHandoff = makeRender(HANDOFF_MESSAGES);
const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const token = "t".repeat(43);
const session = { consumerId: "platform-kernel", consumerPolicyRevision: 1, owner, accessToken: token, expiresAt: "2099-01-01T00:00:00Z" };
const ids = { productId: "proposal_ai", scenarioId: "proposal_ai.generate_v1" };
const scenarios = ["proposal_ai.generate_v1", "client_update_writer.update_v1", "client_update_writer.prepaid_request_v1", "client_update_writer.reply_draft_v1", "brief_decoder.decode_v1", "acceptance_builder.draft_v1", "acceptance_builder.check_v1"];
const fetcher = vi.fn<typeof fetch>();
function parseBody(body: BodyInit | null | undefined): unknown {
  if (typeof body !== "string") throw new Error("JSON string expected");
  const parsed: unknown = JSON.parse(body);
  return parsed;
}
const starts: RequestInit[] = [];
const events: unknown[] = [];
function routeFetch(scenarioId = ids.scenarioId) {
  const product = { productId: scenarioId.split(".")[0], scenarioId };
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (path.endsWith("runtime-config")) return runtimeConfigResponse(product);
    if (path.endsWith("/start")) { starts.push(init!); return startResponse(); }
    if (path.startsWith("/v1/scenario-sessions/")) return sessionResponse({ scenario_id: scenarioId });
    if (path.startsWith("/v1/results/")) return resultResponse(product);
    if (path === "/v1/client-events") {
      const body: unknown = parseBody(init?.body);
      events.push(body);
      return Response.json({ event_id: "event_1", event_type: "web.product_viewed" });
    }
    throw new Error("unexpected guest/quota/network request");
  });
}
beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
  window.history.replaceState(null, "", "/products/proposal_ai");
  requirePortalAuthorization(true);
  installPortalSession(session);
  starts.length = 0;
  events.length = 0;
  fetcher.mockReset();
  vi.stubGlobal("fetch", fetcher);
  vi.stubEnv("NEXT_PUBLIC_PORTAL_AUTHORIZE_URL", "https://portal.invalid/ru/backend/authorize");
  routerPush.mockClear();
});
afterEach(() => { cleanup(); vi.unstubAllEnvs(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it.each(scenarios)("reload restores %s with no guest or new key", async (scenarioId) => {
  routeFetch(scenarioId);
  const productId = scenarioId.split(".")[0];
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  // A network response was lost after a real logical submission; emulate a reload of its tab descriptor.
  fetcher.mockRejectedValueOnce(new TypeError("lost start response"));
  await prepareScenarioStart({ productId, scenarioId, frontendId: "web_mirror", input: { text: "frozen private input" } }, persistence).execute(client);
  const pending = readPaidStartRecovery(persistence, productId)!;
  expect(pending.kind).toBe("pending");
  const nextClient = createPlatformApiClient();
  render(<ProductRunPage definition={{ ...testProductDefinition, productId, scenarioId }} client={nextClient} />);
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(1);
  if (pending.kind !== "pending") throw new Error("pending expected");
  expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe(pending.idempotencyKey);
  expect(parseBody(starts[0].body)).toMatchObject({ input: { text: "frozen private input" } });
  expect(readPaidStartRecovery(persistence, productId)).toMatchObject({ kind: "accepted", scenarioSessionId: "session_1" });
  const paths = fetcher.mock.calls.map(([url]) => new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname);
  expect(paths.some((path) => path.includes("identity/guest") || path.endsWith("/quota"))).toBe(false);
});

it("restores the selected mode and accepted result without a start", async () => {
  const scenarioId = "acceptance_builder.check_v1";
  routeFetch(scenarioId);
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  persistPaidStartRecovery(persistence, { version: 1, owner, productId: "acceptance_builder", scenarioId, kind: "accepted", scenarioSessionId: "session_1" });
  render(<MultiModeProduct client={client} legend="Mode" name="mode" modes={[
    { id: "draft", label: "Draft", definition: { ...testProductDefinition, productId: "acceptance_builder", scenarioId: "acceptance_builder.draft_v1" } },
    { id: "check", label: "Check", definition: { ...testProductDefinition, productId: "acceptance_builder", scenarioId } },
  ]} />);
  await screen.findByText("Generated result text.");
  expect((screen.getByRole("radio", { name: "Check" }) as HTMLInputElement).checked).toBe(true);
  expect(starts).toHaveLength(0);
});

it("retries a restored uncertain request without validating an empty product form", async () => {
  routeFetch();
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "pending", owner, ...ids, idempotencyKey: "original_key",
    request: { ...ids, frontendId: "web_mirror", input: { text: "frozen private input" } } });
  const routed = fetcher.getMockImplementation()!;
  let failures = 2;
  fetcher.mockImplementation(async (url, init) => {
    if (typeof url === "string" && url.endsWith("/start") && failures-- > 0) throw new TypeError("lost response");
    return routed(url, init);
  });
  render(<ProductRunPage client={client} definition={{ ...testProductDefinition, ...ids }} />);
  await screen.findByText("Could not start Test Product. Please try again.");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(1);
  expect(new Headers(starts[0].headers).get("Idempotency-Key")).toBe("original_key");
  expect(parseBody(starts[0].body)).toMatchObject({ input: { text: "frozen private input" } });
});

it.each([false, true])("retries a definitely rejected paid start with a new key only for edited input (%s)", async (edited) => {
  routeFetch();
  const routed = fetcher.getMockImplementation()!;
  let rejected: RequestInit | undefined;
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (path.endsWith("/start") && !rejected) { rejected = init!; return errorResponse(429, "quota_capacity_reserved"); }
    return routed(url, init);
  });
  render(<ProductRunPage client={createPlatformApiClient()} definition={{ ...testProductDefinition, ...ids }} />);
  fireEvent.change(await screen.findByLabelText("Text"), { target: { value: "Original input" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Capacity is temporarily in use. Please try again shortly.");
  // A definite rejection has no reservation; another mode or a reload may start new work.
  expect(readPaidStartRecovery(getPaidPersistence(createPlatformApiClient())!, ids.productId)).toBeNull();
  if (edited) fireEvent.change(screen.getByLabelText("Text"), { target: { value: "Edited input" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Generated result text.");
  const originalKey = new Headers(rejected?.headers).get("Idempotency-Key");
  const retryKey = new Headers(starts[0].headers).get("Idempotency-Key");
  expect(retryKey === originalKey).toBe(!edited);
  expect(parseBody(starts[0].body)).toMatchObject({ input: { text: edited ? "Edited input" : "Original input" } });
});

it("keeps an uncertain paid key when a later attempt gets a definite capacity rejection", async () => {
  routeFetch();
  const routed = fetcher.getMockImplementation()!;
  const attempts: RequestInit[] = [];
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (path.endsWith("/start")) {
      attempts.push(init!);
      if (attempts.length === 1) throw new TypeError("lost response");
      if (attempts.length === 2) return errorResponse(429, "quota_capacity_reserved");
    }
    return routed(url, init);
  });
  const client = createPlatformApiClient();
  render(<ProductRunPage client={client} definition={{ ...testProductDefinition, ...ids }} />);
  fireEvent.change(await screen.findByLabelText("Text"), { target: { value: "Original input" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Capacity is temporarily in use. Please try again shortly.");
  const pending = readPaidStartRecovery(getPaidPersistence(client)!, ids.productId);
  expect(pending).toMatchObject({ kind: "pending", idempotencyKey: new Headers(attempts[0].headers).get("Idempotency-Key") });
  expect((screen.getByLabelText("Text") as HTMLTextAreaElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  await screen.findByText("Generated result text.");
  expect(new Set(attempts.map((attempt) => new Headers(attempt.headers).get("Idempotency-Key"))).size).toBe(1);
});

it("opens an explicit result deep link with no new paid start", async () => {
  routeFetch();
  render(<ProductRunPage client={createPlatformApiClient()} definition={{ ...testProductDefinition, ...ids }} attachSessionId="session_1" />);
  await screen.findByText("Generated result text.");
  expect(starts).toHaveLength(0);
});

it("refuses a new send when tab persistence is unavailable, while result reads still work", async () => {
  routeFetch();
  const client = createPlatformApiClient();
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("storage denied"); });
  const view = render(<ProductRunPage client={client} definition={{ ...testProductDefinition, ...ids }} />);
  fireEvent.change(await screen.findByLabelText("Text"), { target: { value: "private input" } });
  fireEvent.click(screen.getByRole("button", { name: "Run" }));
  await screen.findByText("Browser storage is unavailable. Enable it and retry the same request.");
  expect(starts).toHaveLength(0);
  view.unmount();
  render(<ProductRunPage client={client} definition={{ ...testProductDefinition, ...ids }} attachSessionId="session_1" />);
  await screen.findByText("Generated result text.");
});

it("rebuilds clients on reauthorization, preserving same-owner recovery and clearing different-owner data", async () => {
  routeFetch();
  const client = getPlatformApiClient();
  expect(getPlatformApiClient()).toBe(client);
  const persistence = getPaidPersistence(client)!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner, ...ids, scenarioSessionId: "session_1" });
  requirePortalAuthorization();
  installPortalSession({ ...session, accessToken: "n".repeat(43) });
  expect(getPlatformApiClient()).not.toBe(client);
  expect(readPaidStartRecovery(getPaidPersistence(getPlatformApiClient())!, ids.productId)?.kind).toBe("accepted");
  installPortalSession({ ...session, owner: { ...owner, userId: "22222222-2222-2222-2222-222222222222" } });
  expect(readPaidStartRecovery(getPaidPersistence(getPlatformApiClient())!, ids.productId)).toBeNull();
});

it.each(["backend_delegation_expired", "backend_parent_authority_invalid"])("handles %s without guest fallback", async (code) => {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner, ...ids, scenarioSessionId: "session_1" });
  fetcher.mockResolvedValue(errorResponse(401, code));
  await client.request({ path: "/v1/scenario-sessions/session_1" });
  expect(getPortalIdentity().kind).toBe("required");
  expect(readPaidStartRecovery(persistence, ids.productId)?.kind ?? null).toBe(code === "backend_delegation_expired" ? "accepted" : null);
  expect(fetcher).toHaveBeenCalledOnce();
});

it("removes displayed private results and discards late replies on logout", async () => {
  routeFetch();
  render(<PortalIdentityBoundary>{(client) => <ProductRunPage client={client} definition={{ ...testProductDefinition, ...ids }} attachSessionId="session_1" />}</PortalIdentityBoundary>);
  await screen.findByText("Generated result text.");
  act(() => { requirePortalAuthorization(true); });
  expect(screen.queryByText("Generated result text.")).toBeNull();
  expect(await screen.findByText("Sign in again to continue the same operation.")).toBeTruthy();
  let resolve!: (response: Response) => void;
  act(() => installPortalSession(session));
  const old = getPlatformApiClient();
  fetcher.mockReturnValueOnce(new Promise<Response>((done) => { resolve = done; }));
  const late = old.request({ path: "/v1/scenario-sessions/session_1" });
  act(() => installPortalSession({ ...session, owner: { ...owner, userId: "22222222-2222-2222-2222-222222222222" } }));
  await act(async () => { resolve(sessionResponse()); });
  expect(await late).toEqual({ ok: false, error: { type: "aborted" } });
});

it("restarts a lost exchange while retaining the original frozen request/key and continuation", async () => {
  const client = createPlatformApiClient();
  fetcher.mockRejectedValue(new TypeError("lost response"));
  await prepareScenarioStart({ ...ids, frontendId: "web_mirror", input: { text: "private" } }, getPaidPersistence(client)).execute(client);
  const original = readPaidStartRecovery(getPaidPersistence(client)!, ids.productId);
  const target = "/products/proposal_ai?session=session_1";
  const first = new URL(await beginPortalAuthorization(target));
  fetcher.mockRejectedValueOnce(new TypeError("lost exchange response"));
  await expect(completePortalAuthorization(`#code=${"c".repeat(43)}&state=${first.searchParams.get("state")}`)).rejects.toThrow();
  expect(readPortalContinuation()).toBe(target);
  const second = new URL(await beginPortalAuthorization(target));
  expect(second.searchParams.get("state")).not.toBe(first.searchParams.get("state"));
  fetcher.mockResolvedValue(Response.json({ schema_version: 2, consumer_id: "platform-kernel", consumer_policy_revision: 1, token_type: "Bearer", tenant_id: owner.tenantId, region: owner.region,
    user_id: owner.userId, expires_at: session.expiresAt, access_token: token }));
  expect(await completePortalAuthorization(`#code=${"d".repeat(43)}&state=${second.searchParams.get("state")}`)).toBe(target);
  expect(readPaidStartRecovery(getPaidPersistence(createPlatformApiClient())!, ids.productId)).toEqual(original);
});

it("rejects invalid callback state without exchanging any credential", async () => {
  await preparePortalAuthorization(tabStorage, "/products/proposal_ai", getPortalIdentity().custodyId!, webcrypto as Crypto);
  await expect(completePortalAuthorization(`#code=${"c".repeat(43)}&state=invalid`)).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
});

it("refuses a locally expired token before a new request and preserves the original recovery", async () => {
  routeFetch();
  vi.useFakeTimers();
  try {
    installPortalSession({ ...session, expiresAt: new Date(Date.now() + 1000).toISOString() });
    const client = getPlatformApiClient();
    const persistence = getPaidPersistence(client)!;
    persistPaidStartRecovery(persistence, { version: 1, kind: "accepted", owner, ...ids, scenarioSessionId: "session_1" });
    vi.advanceTimersByTime(1001);
    expect(await client.request({ path: "/v1/scenario-sessions/session_1" })).toEqual({ ok: false, error: { type: "aborted" } });
    expect(fetcher).not.toHaveBeenCalled();
    expect(getPortalIdentity().kind).toBe("required");
    installPortalSession(session);
    expect(readPaidStartRecovery(getPaidPersistence(getPlatformApiClient())!, ids.productId)?.kind).toBe("accepted");
  } finally { vi.useRealTimers(); }
});

it("ignores a successful exchange completed after explicit logout", async () => {
  const authorization = await preparePortalAuthorization(tabStorage, "/products/proposal_ai", getPortalIdentity().custodyId!, webcrypto as Crypto);
  let resolve!: (response: Response) => void;
  fetcher.mockReturnValue(new Promise<Response>((done) => { resolve = done; }));
  const result = completePortalAuthorization(`#code=${"c".repeat(43)}&state=${authorization.state}`);
  requirePortalAuthorization(true);
  resolve(Response.json({ schema_version: 2, consumer_id: "platform-kernel", consumer_policy_revision: 1, token_type: "Bearer", tenant_id: owner.tenantId, region: owner.region,
    user_id: owner.userId, expires_at: session.expiresAt, access_token: token }));
  await expect(result).rejects.toThrow();
  expect(getPortalIdentity().kind).toBe("required");
});

it.each([false, true])("ignores a first-login callback after a newer document signs in and out (logout write refused: %s)", async (refused) => {
  requirePortalAuthorization(true);
  const authorization = await preparePortalAuthorization(tabStorage, "/products/proposal_ai", getPortalIdentity().custodyId!, webcrypto as Crypto);
  let finish!: (response: Response) => void;
  fetcher.mockReturnValue(new Promise<Response>((resolve) => { finish = resolve; }));
  const exchange = completePortalAuthorization(`#code=${"c".repeat(43)}&state=${authorization.state}`);
  await waitFor(() => expect(finish).toBeDefined());
  const generation = getPortalIdentity().generation;
  const initialMode = tabStorage.getItem("anytoolai.portal_mode.v1");
  // Separate module memory models a newer document while the callback stays in BFCache.
  vi.resetModules();
  const newer = await import("../src/lib/portalSession");
  newer.installPortalSession(session);
  if (refused) vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota exceeded"); });
  newer.requirePortalAuthorization(true);
  expect(getPortalIdentity()).toMatchObject({ kind: "required", owner: null, generation });
  finish(Response.json({ schema_version: 2, consumer_id: "platform-kernel", consumer_policy_revision: 1, token_type: "Bearer", tenant_id: owner.tenantId, region: owner.region,
    user_id: owner.userId, expires_at: session.expiresAt, access_token: token }));
  await expect(exchange).rejects.toThrow("portal_exchange_failed");
  expect(tabStorage.getItem("anytoolai.portal_mode.v1")).not.toBe(initialMode);
  expect(readPortalSession(tabStorage)).toBeNull();
  expect(getPortalIdentity()).toMatchObject({ kind: "required", owner: null });
});

it("refuses an old authorization callback when the newer document has already signed out before exchange", async () => {
  requirePortalAuthorization(true);
  const launch = new URL(await beginPortalAuthorization("/products/proposal_ai"));
  vi.resetModules();
  const newer = await import("../src/lib/portalSession");
  newer.installPortalSession(session);
  newer.requirePortalAuthorization(true);
  fetcher.mockResolvedValue(Response.json({ schema_version: 2, consumer_id: "platform-kernel", consumer_policy_revision: 1, token_type: "Bearer", tenant_id: owner.tenantId, region: owner.region,
    user_id: owner.userId, expires_at: session.expiresAt, access_token: token }));
  await expect(completePortalAuthorization(`#code=${"c".repeat(43)}&state=${launch.searchParams.get("state")}`)).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled();
  expect(readPortalSession(tabStorage)).toBeNull();
});

it("refuses a suspended launch without overwriting a newer document's authorization", async () => {
  let finish!: (value: ArrayBuffer) => void;
  vi.spyOn(crypto.subtle, "digest").mockImplementationOnce(() => new Promise<ArrayBuffer>((resolve) => { finish = resolve; }));
  const older = beginPortalAuthorization("/products/proposal_ai");
  vi.resetModules();
  const newer = await import("../src/lib/portalAuthorization");
  const launch = new URL(await newer.beginPortalAuthorization("/products/client_update_writer"));
  finish(new ArrayBuffer(32));
  await expect(older).rejects.toThrow("portal_authorization_invalid");
  expect(readPortalAuthorization(tabStorage)).toMatchObject({ state: launch.searchParams.get("state"), returnTarget: "/products/client_update_writer" });
});

it("invalidates an old client after another document returns to the identical authorized token and owner", async () => {
  const client = createPlatformApiClient();
  const initial = tabStorage.getItem("anytoolai.portal_mode.v1");
  vi.resetModules();
  const newer = await import("../src/lib/portalSession");
  newer.requirePortalAuthorization(true);
  newer.installPortalSession(session);
  expect(readPortalSession(tabStorage)).toEqual(session);
  expect(tabStorage.getItem("anytoolai.portal_mode.v1")).not.toBe(initial);
  expect(await client.request({ path: "/v1/scenario-sessions/session_1" })).toEqual({ ok: false, error: { type: "aborted" } });
  expect(fetcher).not.toHaveBeenCalled();
});

it.each([undefined, "", 7])("requires reauthorization for legacy or invalid custody %s without deleting recovery", (custodyId) => {
  const client = createPlatformApiClient();
  const persistence = getPaidPersistence(client)!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "pending", owner, ...ids, idempotencyKey: "original_key",
    request: { ...ids, frontendId: "web_mirror", input: { text: "Frozen input" } } });
  const saved = readPaidStartRecovery(persistence, ids.productId);
  tabStorage.setItem("anytoolai.portal_mode.v1", JSON.stringify({ version: 1, owner, custodyId }));
  expect(synchronizePortalIdentity()).toMatchObject({ kind: "required", owner, custodyId: null });
  requirePortalAuthorization();
  installPortalSession(session);
  expect(readPaidStartRecovery(getPaidPersistence(createPlatformApiClient())!, ids.productId)).toEqual(saved);
});

it.each(["custody", "token"])("refuses silently lost %s writes before authorizing a client", (lost) => {
  const setItem = Storage.prototype.setItem;
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(function (this: Storage, key, value) {
    if (key === (lost === "custody" ? "anytoolai.portal_mode.v1" : "anytoolai.portal_session.v1")) return;
    setItem.call(this, key, value);
  });
  expect(() => installPortalSession(session)).toThrow("portal_storage_unavailable");
  expect(synchronizePortalIdentity().kind).toBe("required");
  expect(readPortalSession(tabStorage)).toBeNull();
});

it.each(["different owner", "renewed token", "logout"])("ignores late exchange after another document installs %s without a browser event", async (change) => {
  requirePortalAuthorization();
  const authorization = await preparePortalAuthorization(tabStorage, "/products/proposal_ai", getPortalIdentity().custodyId!, webcrypto as Crypto);
  let finish!: (response: Response) => void;
  fetcher.mockReturnValue(new Promise<Response>((resolve) => { finish = resolve; }));
  const exchange = completePortalAuthorization(`#code=${"c".repeat(43)}&state=${authorization.state}`);
  await waitFor(() => expect(fetcher).toHaveBeenCalledOnce());
  const generation = getPortalIdentity().generation;
  const nextOwner = change === "different owner" ? { ...owner, userId: "22222222-2222-2222-2222-222222222222" } : owner;
  const nextSession = { ...session, owner: nextOwner, accessToken: "n".repeat(43) };
  if (change === "logout") {
    tabStorage.removeItem("anytoolai.portal_session.v1");
    tabStorage.setItem("anytoolai.portal_mode.v1", JSON.stringify({ version: 1, owner: null, custodyId: "logout_document_custody" }));
  } else {
    writePortalSession(tabStorage, nextSession);
    tabStorage.setItem("anytoolai.portal_mode.v1", JSON.stringify({ version: 1, owner: nextOwner, custodyId: "newer_document_custody" }));
  }
  const recovery = { version: 1, kind: "accepted", owner: nextOwner, ...ids, scenarioSessionId: "new_document_session" };
  const recoveryKey = `anytoolai.paid_start.v1.${ids.productId}`;
  tabStorage.setItem(recoveryKey, JSON.stringify(recovery));
  expect(getPortalIdentity().generation).toBe(generation);
  finish(Response.json({ schema_version: 2, consumer_id: "platform-kernel", consumer_policy_revision: 1, token_type: "Bearer", tenant_id: owner.tenantId, region: owner.region,
    user_id: owner.userId, expires_at: session.expiresAt, access_token: token }));
  await expect(exchange).rejects.toThrow("portal_exchange_failed");
  expect(readPortalSession(tabStorage)).toEqual(change === "logout" ? null : nextSession);
  expect(tabStorage.getItem(recoveryKey)).toBe(JSON.stringify(recovery));
  expect(getPortalIdentity().generation).toBeGreaterThan(generation);
});

it.each(["pageshow", "focus"])("callback reconciles custody on %s while its exchange is suspended", async (event) => {
  requirePortalAuthorization();
  const authorization = await preparePortalAuthorization(tabStorage, "/products/proposal_ai", getPortalIdentity().custodyId!, webcrypto as Crypto);
  window.history.replaceState(null, "", `/portal-session/callback#code=${"c".repeat(43)}&state=${authorization.state}`);
  let finish!: (response: Response) => void;
  fetcher.mockImplementation(() => {
    expect(window.location.hash).toBe("");
    return new Promise<Response>((resolve) => { finish = resolve; });
  });
  render(<PortalSessionFlow callback />);
  await waitFor(() => expect(finish).toBeDefined());
  const nextSession = { ...session, owner: { ...owner, userId: "22222222-2222-2222-2222-222222222222" }, accessToken: "n".repeat(43) };
  writePortalSession(tabStorage, nextSession);
  tabStorage.setItem("anytoolai.portal_mode.v1", JSON.stringify({ version: 1, owner: nextSession.owner, custodyId: "newer_document_custody" }));
  act(() => { window.dispatchEvent(event === "pageshow" ? new PageTransitionEvent(event, { persisted: true }) : new Event(event)); });
  expect(getPortalIdentity()).toMatchObject({ kind: "authorized", session: nextSession });
  await act(async () => { finish(Response.json({ schema_version: 2, consumer_id: "platform-kernel", consumer_policy_revision: 1, token_type: "Bearer", tenant_id: owner.tenantId, region: owner.region,
    user_id: owner.userId, expires_at: session.expiresAt, access_token: token })); });
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(readPortalSession(tabStorage)).toEqual(nextSession);
  expect(fetcher).toHaveBeenCalledOnce();
});

it("removes the token and frozen inputs on logout even when new storage writes are refused", () => {
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  persistPaidStartRecovery(persistence, { version: 1, kind: "pending", owner, ...ids, idempotencyKey: "original_key",
    request: { ...ids, frontendId: "web_mirror", input: { text: "private" } } });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("quota exceeded"); });
  requirePortalAuthorization(true);
  expect(window.sessionStorage.getItem("anytoolai.portal_session.v1")).toBeNull();
  expect(readPaidStartRecovery(persistence, ids.productId)).toBeNull();
});

it.each([false, true])("accepts paid handoff without a guest and preserves unresolved target recovery (%s)", async (hasPending) => {
  const preview = handoffPreviewPayload();
  const persistence = getPaidPersistence(createPlatformApiClient())!;
  const pending = { version: 1 as const, kind: "pending" as const, owner, productId: "freelancer_demo", scenarioId: "scenario_1", idempotencyKey: "original_key",
    request: { productId: "freelancer_demo", scenarioId: "scenario_1", frontendId: "web_mirror", input: { text: "Frozen input" } } };
  if (hasPending) persistPaidStartRecovery(persistence, pending);
  fetcher.mockImplementation(async (url) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (path.endsWith("/accept")) return Response.json({ ...preview, status: "accepted", target_scenario_session_id: "target_session", target_job_id: "target_job" });
    if (path === "/v1/handoffs/token_abc") return Response.json(preview);
    throw new Error("unexpected guest request");
  });
  renderHandoff(<HandoffConsent client={createPlatformApiClient()} handoffToken="token_abc" canOpenTarget={() => true} />);
  fireEvent.click(await screen.findByRole("button", { name: "Accept" }));
  await waitFor(() => expect(routerPush).toHaveBeenCalledOnce());
  const acceptedCall = fetcher.mock.calls.find(([url]) => (typeof url === "string" ? url : url instanceof URL ? url.href : url.url).endsWith("/accept"))!;
  expect(parseBody(acceptedCall[1]?.body)).not.toHaveProperty("guest_id");
  expect(new Headers(acceptedCall[1]?.headers).get("Authorization")).toBe(`Bearer ${token}`);
  expect(readPaidStartRecovery(persistence, "freelancer_demo")).toMatchObject(hasPending ? pending : { kind: "accepted", scenarioSessionId: "target_session" });
});

it("quarantines a Step 8 token while retaining the exact uncertain start across same-owner V2 authorization", async () => {
  const client = createPlatformApiClient();
  const original = { request: { ...ids, frontendId: "web", input: { text: "frozen before cutover" } }, idempotencyKey: "original_cutover_key" };
  const recovery = { version: 1, kind: "pending", owner, ...ids, idempotencyKey: original.idempotencyKey, request: original.request } as const;
  persistPaidStartRecovery(getPaidPersistence(client)!, recovery);
  window.sessionStorage.setItem("anytoolai.portal_session.v1", JSON.stringify({ version: 1, owner, accessToken: "old".repeat(15), expiresAt: session.expiresAt }));
  expect(synchronizePortalIdentity()).toMatchObject({ kind: "required", owner });
  expect(() => createPlatformApiClient()).toThrow("portal_authorization_required");
  requirePortalAuthorization();
  installPortalSession({ ...session, accessToken: "n".repeat(43) });
  const restored = readPaidStartRecovery(getPaidPersistence(createPlatformApiClient())!, ids.productId);
  expect(restored).toEqual(recovery);
  const sends: RequestInit[] = [];
  fetcher.mockImplementation(async (url, init) => {
    const path = new URL(typeof url === "string" ? url : url instanceof URL ? url.href : url.url).pathname;
    if (path.endsWith("runtime-config")) return runtimeConfigResponse(ids);
    if (path.endsWith("/start")) { sends.push(init!); return startResponse(); }
    if (path.startsWith("/v1/scenario-sessions/")) return sessionResponse({ scenario_id: ids.scenarioId });
    if (path.startsWith("/v1/results/")) return resultResponse(ids);
    throw new Error("unexpected request after cutover");
  });
  render(<ProductRunPage client={createPlatformApiClient()} definition={{ ...testProductDefinition, ...ids }} />);
  await screen.findByText("Generated result text.");
  expect(sends).toHaveLength(1);
  expect(new Headers(sends[0].headers).get("Idempotency-Key")).toBe(original.idempotencyKey);
  expect(parseBody(sends[0].body)).toMatchObject({ input: { text: "frozen before cutover" } });
});
