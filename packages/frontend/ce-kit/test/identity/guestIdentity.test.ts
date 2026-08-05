import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import type { AsyncStorage } from "../../src/storage/asyncStorage";
import { createInMemoryAsyncStorage } from "../../src/storage/inMemoryAsyncStorage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function makeClient(fetchImpl: typeof fetch): PlatformApiClient {
  return new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl });
}

/** AsyncStorage whose first get() call stays pending until resolveFirstGet() is called explicitly. */
function createDeferredFirstGetStorage(): AsyncStorage & { resolveFirstGet(value: string | undefined): void } {
  const store = new Map<string, string>();
  let firstCallPending = true;
  let resolveFirstGet!: (value: string | undefined) => void;
  const deferred = new Promise<string | undefined>((resolve) => {
    resolveFirstGet = resolve;
  });

  return {
    async get(key) {
      if (firstCallPending) {
        firstCallPending = false;
        return deferred;
      }
      return store.get(key);
    },
    async set(key, value) {
      store.set(key, value);
    },
    async remove(key) {
      store.delete(key);
    },
    resolveFirstGet,
  };
}

describe("PlatformApiClient.createGuestIdentity", () => {
  it("reuses a stored guest id without calling the backend", async () => {
    const storage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_existing" });
    const fetchImpl = vi.fn();
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({ ok: true, value: { guestId: "guest_existing" } });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("requests and persists a new guest id when none is stored", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_new" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({ ok: true, value: { guestId: "guest_new" } });
    expect(await storage.get("anytoolai.guest_id")).toBe("guest_new");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("makes at most one backend request for concurrent calls on the same client instance", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_concurrent" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const [first, second, third] = await Promise.all([
      client.createGuestIdentity({ storage }),
      client.createGuestIdentity({ storage }),
      client.createGuestIdentity({ storage }),
    ]);

    expect(first).toEqual({ ok: true, value: { guestId: "guest_concurrent" } });
    expect(second).toEqual({ ok: true, value: { guestId: "guest_concurrent" } });
    expect(third).toEqual({ ok: true, value: { guestId: "guest_concurrent" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("still makes at most one backend request when concurrent calls pass different storage keys, and each caller persists to its own key", async () => {
    // The acceptance criterion is "at most one backend request per client instance," full stop --
    // single-flight is not scoped by storageKey. But every successful caller must still persist
    // the shared result to its own storageKey, not just whichever call happened to trigger the
    // backend request -- otherwise a later call with that same key would miss the cache and make
    // a redundant request.
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_a" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const [a, b] = await Promise.all([
      client.createGuestIdentity({ storage, storageKey: "product_a.guest_id" }),
      client.createGuestIdentity({ storage, storageKey: "product_b.guest_id" }),
    ]);

    expect(a).toEqual({ ok: true, value: { guestId: "guest_a" } });
    expect(b).toEqual({ ok: true, value: { guestId: "guest_a" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(await storage.get("product_a.guest_id")).toBe("guest_a");
    expect(await storage.get("product_b.guest_id")).toBe("guest_a");
  });

  it("persists the shared result to each caller's own storage instance, not just the triggering call's", async () => {
    const storageA = createInMemoryAsyncStorage();
    const storageB = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_shared" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const [a, b] = await Promise.all([
      client.createGuestIdentity({ storage: storageA }),
      client.createGuestIdentity({ storage: storageB }),
    ]);

    expect(a).toEqual({ ok: true, value: { guestId: "guest_shared" } });
    expect(b).toEqual({ ok: true, value: { guestId: "guest_shared" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(await storageA.get("anytoolai.guest_id")).toBe("guest_shared");
    expect(await storageB.get("anytoolai.guest_id")).toBe("guest_shared");
  });

  it("does not start a second backend request when a slow storage lookup only resolves after another caller's request has already finished", async () => {
    // Reproduces: caller A's storage.get() is still pending when caller B (fast lookup) joins
    // no in-flight request, performs the backend call, persists, and fully finishes -- clearing
    // the single-flight state. If A only joins the in-flight promise *after* its own storage.get()
    // resolves, A now sees no in-flight request and wrongly starts a second one.
    const storageA = createDeferredFirstGetStorage();
    const storageB = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_shared" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const pendingA = client.createGuestIdentity({ storage: storageA, storageKey: "a_key" });

    // Caller B's fast lookup + full request/persist cycle completes first, while A's
    // storage.get() is still pending.
    const resultB = await client.createGuestIdentity({ storage: storageB, storageKey: "b_key" });
    expect(resultB).toEqual({ ok: true, value: { guestId: "guest_shared" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);

    // Now let A's deferred storage.get() resolve (empty -- no id was cached for A's key).
    storageA.resolveFirstGet(undefined);
    const resultA = await pendingA;

    expect(resultA).toEqual({ ok: true, value: { guestId: "guest_shared" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(await storageA.get("a_key")).toBe("guest_shared");
    expect(await storageB.get("b_key")).toBe("guest_shared");
  });

  it("allows a later, separate call to make its own request once the first has settled", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, { guest_id: "guest_a" }))
      .mockResolvedValueOnce(jsonResponse(200, { guest_id: "guest_b" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await client.createGuestIdentity({ storage, storageKey: "product_a.guest_id" });
    await client.createGuestIdentity({ storage, storageKey: "product_b.guest_id" });

    expect(fetchImpl).toHaveBeenCalledTimes(2);
    expect(await storage.get("product_a.guest_id")).toBe("guest_a");
    expect(await storage.get("product_b.guest_id")).toBe("guest_b");
  });

  it("returns invalid_response, not a thrown error, when the response payload has no guest id", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({
      ok: false,
      error: { type: "invalid_response", status: 200, message: "Guest identity response was invalid." },
    });
  });

  it("still resolves with the identity if persisting it to storage fails", async () => {
    const storage: AsyncStorage = {
      get: vi.fn(async () => undefined),
      set: vi.fn(async () => {
        throw new Error("storage full");
      }),
      remove: vi.fn(async () => {}),
    };
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_orphan_risk" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({ ok: true, value: { guestId: "guest_orphan_risk" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("returns the backend_error from the stable error union when the backend rejects guest creation", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () =>
      jsonResponse(500, { error: { code: "internal_error", message: "boom", request_id: "req_1" } }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({
      ok: false,
      error: {
        type: "backend_error",
        status: 500,
        code: "internal_error",
        message: "boom",
        requestId: "req_1",
      },
    });
  });

  it("returns network_error from the stable error union rather than throwing", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    });
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({
      ok: false,
      error: { type: "network_error", message: "Network request failed." },
    });
  });

  it("does not clobber a concurrently cached guest id when this call's own storage read failed", async () => {
    // Caller A's read succeeds and returns the already-cached id without touching the shared
    // backend request. Caller B's read on the *same key* fails and is treated as a miss, so it
    // falls through to the shared backend request and gets back a fresh id. B must not persist
    // that fresh id over the key A already read and returned -- doing so would orphan the id A is
    // already using.
    const store = new Map<string, string>([["anytoolai.guest_id", "guest_original"]]);
    let getCallCount = 0;
    const storage: AsyncStorage = {
      get: vi.fn(async (key) => {
        getCallCount += 1;
        if (getCallCount === 1) {
          return store.get(key);
        }
        throw new Error("storage read failed");
      }),
      set: vi.fn(async (key, value) => {
        store.set(key, value);
      }),
      remove: vi.fn(async (key) => {
        store.delete(key);
      }),
    };
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_new" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const [resultA, resultB] = await Promise.all([
      client.createGuestIdentity({ storage }),
      client.createGuestIdentity({ storage }),
    ]);

    expect(resultA).toEqual({ ok: true, value: { guestId: "guest_original" } });
    expect(resultB).toEqual({ ok: true, value: { guestId: "guest_new" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(store.get("anytoolai.guest_id")).toBe("guest_original");
  });

  it("does not overwrite a guest id cached concurrently between this call's own miss-read and its persist step", async () => {
    // This call's own initial read genuinely misses (no throw, no cached value yet). Before this
    // call persists the id it fetched from the backend, some other context (another tab, another
    // client instance, another caller with a successful cache-hit read of its own) writes a valid
    // id to the same key. The persist step must re-check and prefer that already-cached value
    // instead of blindly overwriting it with this call's own (different) fetched id.
    const store = new Map<string, string>();
    let getCallCount = 0;
    const storage: AsyncStorage = {
      get: vi.fn(async (key) => {
        getCallCount += 1;
        if (getCallCount === 1) {
          return undefined;
        }
        store.set(key, "guest_written_concurrently");
        return store.get(key);
      }),
      set: vi.fn(async (key, value) => {
        store.set(key, value);
      }),
      remove: vi.fn(async (key) => {
        store.delete(key);
      }),
    };
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_fetched" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({ ok: true, value: { guestId: "guest_fetched" } });
    expect(store.get("anytoolai.guest_id")).toBe("guest_written_concurrently");
    expect(storage.set).not.toHaveBeenCalled();
  });

  it("treats a rejected storage read as a cache miss and still returns a valid GuestIdentityResult, without throwing", async () => {
    const storage: AsyncStorage = {
      get: vi.fn(async () => {
        throw new Error("chrome.storage.local: QUOTA_BYTES exceeded");
      }),
      set: vi.fn(async () => {}),
      remove: vi.fn(async () => {}),
    };
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_after_read_failure" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const result = await client.createGuestIdentity({ storage });

    expect(result).toEqual({ ok: true, value: { guestId: "guest_after_read_failure" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    // Persistence is intentionally skipped when this call's own read failed -- a concurrent caller
    // on the same key may have read a genuinely cached id successfully and already returned it, and
    // this call has no reliable way to tell that apart from a real cache miss. See "does not
    // clobber a concurrently cached guest id..." above for the race this avoids.
    expect(storage.set).not.toHaveBeenCalled();
  });
});
