import { afterEach, describe, expect, it, vi } from "vitest";
import type { RuntimeQuotaSummary } from "@anytoolai/ce-kit";
import { ProductQuotaStore } from "../src/products/runtime/quotaAdmission";
import { errorResponse, makeClientCapturingRequests, makeClientWithDeferredCalls, quotaResponse, routesFor } from "./fixtures/platformResponses";

const ids = { productId: "test_product", scenarioId: "test_product.first" };
const route = routesFor(ids).QUOTA;
const request = { ...ids, guestId: "guest_1" };
const policy: RuntimeQuotaSummary = {
  quotaPolicyId: "test_product.guest_quota_v1", dimension: "product", unit: "scenario_run", period: "lifetime", limitCount: 3,
};
afterEach(() => vi.useRealTimers());

function setup(count = 4) {
  const routed = makeClientWithDeferredCalls({}, { [route]: count });
  const store = new ProductQuotaStore();
  return { ...routed, store, admission: store.get(routed.client, request, policy) };
}

describe("page-owned quota admission", () => {
  it.each([false, true])("bounds an execution read and preserves known exhaustion=%s after timeout", async (exhausted) => {
    vi.useFakeTimers();
    let reads = 0;
    let resolveLate!: (response: Response) => void;
    const routed = makeClientCapturingRequests({
      [route]: [quotaResponse(ids, { used_count: exhausted ? 3 : 2, remaining_count: exhausted ? 0 : 1, exhausted })],
    }, (_key, init) => {
      if (++reads === 1) return undefined;
      return new Promise<Response>((resolve, reject) => {
        resolveLate = resolve;
        init.signal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
      });
    });
    const admission = new ProductQuotaStore().get(routed.client, request, policy);
    admission.refresh("advisory");
    expect(admission.blocksNewRun()).toBe(false);
    await vi.advanceTimersByTimeAsync(0);
    admission.refresh("execution");
    expect(admission.blocksNewRun()).toBe(true);
    await vi.advanceTimersByTimeAsync(10_000);
    expect(admission.getSnapshot().status).toBe(exhausted ? "exhausted" : "unknown");
    expect(admission.blocksNewRun()).toBe(exhausted);
    // A transport that resolves after its timeout cannot silently revive the expired read.
    resolveLate(quotaResponse(ids));
    await vi.advanceTimersByTimeAsync(0);
    expect(admission.getSnapshot().status).toBe(exhausted ? "exhausted" : "unknown");
  });

  it("retains authoritative exhaustion across failed reads, then accepts a genuine reset", async () => {
    const { admission, resolveCall } = setup();
    admission.refresh("advisory");
    admission.markExhausted();
    resolveCall(route, 0, quotaResponse(ids));
    const settled = vi.fn();
    admission.subscribe(settled);
    admission.refresh("advisory");
    resolveCall(route, 1, errorResponse(503, "unavailable"));
    await vi.waitFor(() => expect(settled).toHaveBeenCalledOnce());
    expect(admission.getSnapshot().status).toBe("exhausted");
    admission.refresh("execution");
    resolveCall(route, 2, quotaResponse(ids));
    await vi.waitFor(() => expect(admission.getSnapshot().status).toBe("available"));
    expect(admission.blocksNewRun()).toBe(false);
  });

  it("keeps the pending answer across subscriber replacement and ignores old generations", async () => {
    const { admission, resolveCall, calls } = setup();
    const oldForm = vi.fn();
    const nextForm = vi.fn();
    const unsubscribe = admission.subscribe(oldForm);
    admission.refresh("advisory");
    admission.refresh("execution");
    unsubscribe();
    oldForm.mockClear();
    admission.subscribe(nextForm);
    admission.refresh("advisory");
    expect(calls).toHaveLength(2);
    resolveCall(route, 1, quotaResponse(ids, { used_count: 3, remaining_count: 0, exhausted: true }));
    await vi.waitFor(() => expect(admission.getSnapshot().status).toBe("exhausted"));
    resolveCall(route, 0, quotaResponse(ids));
    await vi.waitFor(() => expect(nextForm).toHaveBeenCalledOnce());
    expect(oldForm).not.toHaveBeenCalled();
    expect(admission.blocksNewRun()).toBe(true);
  });

  it("shares product quota between modes but isolates guest, product, policy, client, page and scenario scopes", () => {
    const { admission, client, store } = setup();
    admission.markExhausted();
    const otherMode = { ...request, scenarioId: "test_product.second" };
    expect(store.get(client, otherMode, policy)).toBe(admission);
    const isolated = [
      store.get(client, { ...request, guestId: "guest_2" }, policy),
      store.get(client, { ...request, productId: "other_product" }, policy),
      store.get(client, request, { ...policy, quotaPolicyId: "other_policy" }),
      store.get(makeClientWithDeferredCalls({}, {}).client, request, policy),
      new ProductQuotaStore().get(client, request, policy),
    ];
    const scenarioPolicy = { ...policy, dimension: "scenario" as const };
    const firstScenario = store.get(client, request, scenarioPolicy);
    firstScenario.markExhausted();
    isolated.push(store.get(client, otherMode, scenarioPolicy));
    for (const scope of isolated) expect(scope.blocksNewRun()).toBe(false);
  });

  it("does not let an old guest's pending answer change the new guest's admission", async () => {
    const { admission, resolveCall, client, store } = setup();
    admission.refresh("execution");
    const current = store.get(client, { ...request, guestId: "guest_2" }, policy);
    current.refresh("advisory");
    resolveCall(route, 1, quotaResponse(ids, { guest_id: "guest_2" }));
    await vi.waitFor(() => expect(current.getSnapshot().status).toBe("available"));
    resolveCall(route, 0, quotaResponse(ids, { used_count: 3, remaining_count: 0, exhausted: true }));
    await vi.waitFor(() => expect(admission.getSnapshot().status).toBe("exhausted"));
    expect(current.getSnapshot().status).toBe("available");
    expect(current.getSnapshot().quota?.guestId).toBe("guest_2");
  });
});
