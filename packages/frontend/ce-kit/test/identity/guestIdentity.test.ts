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

  it("still makes at most one backend request when concurrent calls pass different storage keys", async () => {
    // The acceptance criterion is "at most one backend request per client instance," full stop --
    // single-flight is not scoped by storageKey. Only the call that actually performs the request
    // persists to its own storageKey; a racing call with a different key gets that call's result
    // but does not get its own key populated.
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

    expect(result).toEqual({ ok: false, error: { type: "network_error", message: "Failed to fetch" } });
  });
});
