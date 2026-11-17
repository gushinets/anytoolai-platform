import { expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { restorePaidScenarioStart } from "../../src/scenarios/prepareScenarioStart";
import { persistPaidStartRecovery, readPaidStartRecovery, type PaidStartPersistence } from "../../src/scenarios/paidStartRecovery";
import { memoryTabStorage } from "../testUtils/tabStorage";

const owner = { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" };
const request = { productId: "proposal_ai", scenarioId: "proposal_ai.generate_v1", frontendId: "web_mirror",
  input: { task_text: "hello", freelancer_positioning: "hello", tone: "firm" } };
const pending = { version: 1 as const, kind: "pending" as const, owner, productId: request.productId,
  scenarioId: request.scenarioId, idempotencyKey: "original_key", request };
const compatible = { ...request.input, result_contract: "proposal_ai.field_errors_v1" };
const accepted = () => Response.json({ scenario_session_id: "session_1", job_id: "job_1", status: "started", allowed_next_actions: [], result_artifact_id: null });
const error = (status: number, code: string) => Response.json({ error: { code, message: code, request_id: "req_1" } }, { status });
const invalid = () => error(422, "scenario_input_invalid");
const conflict = () => error(409, "idempotency_key_conflict");

function setup(responses: (() => Response)[]) {
  const persistence: PaidStartPersistence = { storage: memoryTabStorage(), owner, isCurrent: () => true };
  persistPaidStartRecovery(persistence, pending);
  const fetchImpl = vi.fn<typeof fetch>(async () => {
    const next = responses.shift();
    if (!next) throw new Error("Unexpected request");
    return next();
  });
  const client = new PlatformApiClient({ baseUrl: "https://kernel.invalid", fetchImpl });
  const restore = () => restorePaidScenarioStart(pending, persistence, compatible);
  const inputs = () => fetchImpl.mock.calls.map(([, init]) => {
    expect(new Headers(init?.headers).get("Idempotency-Key")).toBe(pending.idempotencyKey);
    return (JSON.parse(init?.body as string) as { input: unknown }).input;
  });
  return { persistence, fetchImpl, client, restore, inputs };
}

it.each([
  { name: "legacy already accepted", responses: [accepted], inputs: [request.input] },
  { name: "legacy never accepted", responses: [invalid, accepted], inputs: [request.input, compatible] },
  { name: "compatible accepted before reload", responses: [conflict, accepted], inputs: [request.input, compatible] },
  { name: "in-flight legacy wins", responses: [invalid, conflict, accepted], inputs: [request.input, compatible, request.input] },
])("recovers $name under one key", async ({ responses, inputs }) => {
  const state = setup(responses);
  expect((await state.restore().execute(state.client)).ok).toBe(true);
  expect(state.inputs()).toEqual(inputs);
  expect(readPaidStartRecovery(state.persistence, request.productId)).toMatchObject({ kind: "accepted", scenarioSessionId: "session_1" });
});

it("retains original pending after a lost compatible response and recovers it after reload", async () => {
  const state = setup([invalid, () => { throw new TypeError("Lost accepted response"); }, conflict, accepted]);
  expect((await state.restore().execute(state.client)).ok).toBe(false);
  expect(readPaidStartRecovery(state.persistence, request.productId)).toEqual(pending);
  expect((await state.restore().execute(state.client)).ok).toBe(true);
  expect(state.inputs()).toEqual([request.input, compatible, request.input, compatible]);
});

it.each([
  () => { throw new TypeError("Lost original response"); },
  () => error(503, "unavailable"), () => error(429, "quota_capacity_reserved"),
  () => error(422, "scenario_frontend_invalid"),
])("does not negotiate on unrelated original failures (%#)", async response => {
  const state = setup([response]);
  expect((await state.restore().execute(state.client)).ok).toBe(false);
  expect(state.inputs()).toEqual([request.input]);
  expect(readPaidStartRecovery(state.persistence, request.productId)).toEqual(pending);
});

it.each([invalid, conflict, () => error(503, "unavailable")])("bounds unsuccessful negotiation and retains frozen recovery (%#)", async response => {
  const state = setup([invalid, conflict, response]);
  expect((await state.restore().execute(state.client)).ok).toBe(false);
  expect(state.inputs()).toEqual([request.input, compatible, request.input]);
  expect(readPaidStartRecovery(state.persistence, request.productId)).toEqual(pending);
});

it.each(["owner", "abort"])("stops negotiation after %s changes", async change => {
  const state = setup([]);
  const controller = new AbortController();
  state.fetchImpl.mockImplementationOnce(async () => {
    if (change === "owner") state.persistence.isCurrent = () => false;
    else controller.abort();
    return invalid();
  });
  expect(await state.restore().execute(state.client, { signal: controller.signal })).toMatchObject({ ok: false, error: { type: "aborted" } });
  expect(state.inputs()).toEqual([request.input]);
  expect(readPaidStartRecovery(state.persistence, request.productId)).toEqual(pending);
});

it("freezes the compatible variant and preserves the original persistent request", async () => {
  const state = setup([invalid, () => error(503, "unavailable")]);
  const input = { ...compatible };
  const prepared = restorePaidScenarioStart(pending, state.persistence, input);
  input.task_text = "Changed later";
  await prepared.execute(state.client);
  expect(state.inputs()).toEqual([request.input, compatible]);
  expect(readPaidStartRecovery(state.persistence, request.productId)).toEqual(pending);
});
