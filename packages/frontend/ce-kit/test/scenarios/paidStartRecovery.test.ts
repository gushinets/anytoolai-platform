import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { prepareScenarioStart, restorePaidScenarioStart } from "../../src/scenarios/prepareScenarioStart";
import { parsePaidStartRecovery, persistPaidStartRecovery, readPaidStartRecovery, rememberPaidResult, type PaidStartPersistence } from "../../src/scenarios/paidStartRecovery";
import { memoryTabStorage } from "../testUtils/tabStorage";

const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const accepted = () => Response.json({ scenario_session_id: "session_1", job_id: "job_1", status: "started", allowed_next_actions: [], result_artifact_id: null });
const scenarios = ["proposal_ai.generate_v1", "client_update_writer.update_v1", "client_update_writer.prepaid_request_v1", "client_update_writer.reply_draft_v1", "brief_decoder.decode_v1", "acceptance_builder.draft_v1", "acceptance_builder.check_v1"];
function persistence(): PaidStartPersistence { return { storage: memoryTabStorage(), owner, isCurrent: () => true }; }

describe("paid prepared starts", () => {
  it("keeps a newer pending across late acceptance and dismissal of the older handle", async () => {
    const saved = persistence();
    let finish!: (response: Response) => void;
    const fetchImpl = vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; }));
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl });
    const request = { productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: { text: "Old request" } };
    const old = prepareScenarioStart(request, saved);
    const inFlight = old.execute(client);
    const newer = { version: 1, kind: "pending", owner, productId: request.productId, scenarioId: request.scenarioId, idempotencyKey: "newer_key",
      request: { ...request, input: { text: "Newer frozen request" } } };
    // Emulate an already-restored newer document, independently of this handle's memory.
    saved.storage.setItem(`anytoolai.paid_start.v1.${request.productId}`, JSON.stringify(newer));
    finish(accepted());
    expect((await inFlight).ok).toBe(true);
    old.forgetRecovery();
    expect(readPaidStartRecovery(saved, request.productId)).toEqual(newer);
    expect(await old.execute(client)).toEqual({ ok: false, error: { type: "local_error", code: "paid_recovery_pending" } });
    expect(fetchImpl).toHaveBeenCalledOnce();
  });
  it("does not let an old handle dismiss a newer accepted result", async () => {
    const saved = persistence();
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl: vi.fn(async () => accepted()) });
    const request = { productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: {} };
    const old = prepareScenarioStart(request, saved);
    await old.execute(client);
    const newer = { version: 1 as const, kind: "accepted" as const, owner, productId: request.productId, scenarioId: request.scenarioId, scenarioSessionId: "newer_session" };
    persistPaidStartRecovery(saved, newer);
    old.forgetRecovery();
    expect(readPaidStartRecovery(saved, request.productId)).toEqual(newer);
  });
  it("does not replace a newer accepted reference with an older late acceptance", async () => {
    const saved = persistence();
    let finish!: (response: Response) => void;
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl: vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; })) });
    const productId = "proposal_ai";
    const old = prepareScenarioStart({ productId, scenarioId: scenarios[0], frontendId: "web_mirror", input: {} }, saved);
    const inFlight = old.execute(client);
    const newer = { version: 1, kind: "accepted", owner, productId, scenarioId: scenarios[0], scenarioSessionId: "newer_session" };
    saved.storage.setItem(`anytoolai.paid_start.v1.${productId}`, JSON.stringify(newer));
    finish(accepted());
    expect((await inFlight).ok).toBe(true);
    old.forgetRecovery();
    expect(readPaidStartRecovery(saved, productId)).toEqual(newer);
  });
  it("releases only its own definitely rejected request so edited input can use a fresh key", async () => {
    const saved = persistence();
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValueOnce(Response.json({ error: { code: "quota_capacity_reserved", message: "Busy", request_id: "req_1" } }, { status: 429 })).mockImplementation(async () => accepted());
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl });
    const request = { productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: { text: "Original input" } };
    const prepared = prepareScenarioStart(request, saved);
    expect((await prepared.execute(client)).ok).toBe(false);
    prepared.forgetRecovery();
    expect(readPaidStartRecovery(saved, request.productId)).toBeNull();
    expect((await prepareScenarioStart({ ...request, input: { text: "Edited input" } }, saved).execute(client)).ok).toBe(true);
    expect(fetchImpl.mock.calls[1][1]?.headers).not.toEqual(fetchImpl.mock.calls[0][1]?.headers);
  });
  it("does not replace the frozen request under the same pending key", async () => {
    const saved = persistence();
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl: vi.fn().mockRejectedValue(new TypeError("lost response")) });
    const request = { productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: { text: "Original input" } };
    await prepareScenarioStart(request, saved).execute(client);
    const pending = readPaidStartRecovery(saved, request.productId)!;
    if (pending.kind !== "pending") throw new Error("pending expected");
    expect(() => persistPaidStartRecovery(saved, { ...pending, request: { ...request, input: { text: "Changed input" } } })).toThrow("paid_recovery_pending");
    expect(readPaidStartRecovery(saved, request.productId)).toEqual(pending);
  });
  it("refuses a fresh key when another pending is current and still permits its same-key recovery", async () => {
    const saved = persistence();
    const fetchImpl = vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError("lost response")).mockImplementation(async () => accepted());
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl });
    const request = { productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: { text: "Frozen request" } };
    await prepareScenarioStart(request, saved).execute(client);
    const pending = readPaidStartRecovery(saved, request.productId)!;
    expect(await prepareScenarioStart({ ...request, input: { text: "New request" } }, saved).execute(client)).toEqual({
      ok: false, error: { type: "local_error", code: "paid_recovery_pending" },
    });
    expect(fetchImpl).toHaveBeenCalledOnce();
    expect(readPaidStartRecovery(saved, request.productId)).toEqual(pending);
    if (pending.kind !== "pending") throw new Error("pending expected");
    expect((await restorePaidScenarioStart(pending, saved).execute(client)).ok).toBe(true);
    expect(fetchImpl.mock.calls[1][1]?.headers).toEqual(fetchImpl.mock.calls[0][1]?.headers);
    expect(fetchImpl.mock.calls[1][1]?.body).toBe(fetchImpl.mock.calls[0][1]?.body);
  });
  it("preserves a pending request/key when selecting a historical result in another scenario", () => {
    const saved = persistence();
    const productId = "acceptance_builder";
    const scenarioId = "acceptance_builder.draft_v1";
    const pending = { version: 1 as const, kind: "pending" as const, owner, productId, scenarioId, idempotencyKey: "original_key",
      request: { productId, scenarioId, frontendId: "web_mirror", input: { brief_text: "Frozen input" } } };
    persistPaidStartRecovery(saved, pending);
    rememberPaidResult(saved, { version: 1, kind: "accepted", owner, productId, scenarioId: "acceptance_builder.check_v1", scenarioSessionId: "historical_check" });
    expect(readPaidStartRecovery(saved, productId)).toEqual(pending);
  });
  it("remembers a selected result when there is no pending operation", () => {
    const saved = persistence();
    const selected = { version: 1 as const, kind: "accepted" as const, owner, productId: "proposal_ai", scenarioId: scenarios[0], scenarioSessionId: "selected" };
    rememberPaidResult(saved, { ...selected, scenarioSessionId: "old" });
    rememberPaidResult(saved, selected);
    expect(readPaidStartRecovery(saved, selected.productId)).toEqual(selected);
  });
  it.each(scenarios)("replays %s with the original frozen body/key after a lost response and reload", async (scenarioId) => {
    const saved = persistence();
    const requests: RequestInit[] = [];
    const fetchImpl = vi.fn<typeof fetch>().mockImplementation(async (_, init) => {
      requests.push(init!);
      if (requests.length === 1) throw new TypeError("lost response");
      return accepted();
    });
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl });
    const request = { productId: scenarioId.split(".")[0], scenarioId, frontendId: "web_mirror", input: { text: "original" } };
    expect((await prepareScenarioStart(request, saved).execute(client)).ok).toBe(false);
    request.input.text = "changed";
    const recovery = readPaidStartRecovery(saved, request.productId)!;
    expect(recovery.kind).toBe("pending");
    if (recovery.kind !== "pending") throw new Error("pending expected");
    await restorePaidScenarioStart(recovery, saved).execute(client);
    expect(requests[1].headers).toEqual(requests[0].headers);
    expect(requests[1].body).toBe(requests[0].body);
    expect(requests[1].body).toContain("original");
    const final = readPaidStartRecovery(saved, request.productId)!;
    expect(final).toMatchObject({ version: 1, kind: "accepted", scenarioSessionId: "session_1", owner });
    expect(final).not.toHaveProperty("request");
  });
  it("refuses new paid sends when persistence fails, including silent refusal", async () => {
    for (const setItem of [() => { throw new Error("storage denied"); }, () => {}]) {
      const saved = persistence();
      saved.storage.setItem = setItem;
      const fetchImpl = vi.fn<typeof fetch>();
      const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl });
      const result = await prepareScenarioStart({ productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: {} }, saved).execute(client);
      expect(result).toEqual({ ok: false, error: { type: "local_error", code: "paid_storage_unavailable" } });
      expect(fetchImpl).not.toHaveBeenCalled();
    }
  });
  it("clears a different owner's frozen input", async () => {
    const saved = persistence();
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl: vi.fn().mockRejectedValue(new Error()) });
    await prepareScenarioStart({ productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: { private: "text" } }, saved).execute(client);
    expect(readPaidStartRecovery({ ...saved, owner: { ...owner, userId: "22222222-2222-2222-2222-222222222222" } }, "proposal_ai")).toBeNull();
    expect(readPaidStartRecovery(saved, "proposal_ai")).toBeNull();
  });
  it("ignores late acceptance after the identity generation changed", async () => {
    const saved = persistence();
    let current = true;
    saved.isCurrent = () => current;
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl: vi.fn().mockImplementation(async () => { current = false; return accepted(); }) });
    expect(await prepareScenarioStart({ productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: {} }, saved).execute(client)).toEqual({ ok: false, error: { type: "aborted" } });
    expect(readPaidStartRecovery(saved, "proposal_ai")?.kind).toBe("pending");
  });
  it("keeps an accepted response readable if replacing its pending descriptor fails", async () => {
    const saved = persistence();
    const write = saved.storage.setItem;
    let writes = 0;
    saved.storage.setItem = (key, value) => {
      if (++writes > 1) throw new Error("storage became full");
      write(key, value);
    };
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl: vi.fn().mockImplementation(async () => accepted()) });
    const result = await prepareScenarioStart({ productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: {} }, saved).execute(client);
    expect(result.ok).toBe(true);
    expect(readPaidStartRecovery(saved, "proposal_ai")?.kind).toBe("pending");
  });
  it("refuses paid execution without the owner's required persistence", async () => {
    const fetchImpl = vi.fn<typeof fetch>();
    const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl, portalIdentity: { owner, isCurrent: () => true, refuse: () => {} } });
    const result = await prepareScenarioStart({ productId: "proposal_ai", scenarioId: scenarios[0], frontendId: "web_mirror", input: {} }).execute(client);
    expect(result).toEqual({ ok: false, error: { type: "local_error", code: "paid_storage_unavailable" } });
    expect(fetchImpl).not.toHaveBeenCalled();
  });
  it.each([null, { version: 2 }, { version: 1, kind: "unknown", owner, productId: "proposal_ai", scenarioId: scenarios[0] }])("rejects invalid recovery %o", (value) => {
    expect(parsePaidStartRecovery(value)).toBeNull();
  });
});
