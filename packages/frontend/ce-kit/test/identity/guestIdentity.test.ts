import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { createGuestIdentity } from "../../src/identity/guestIdentity";
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

describe("createGuestIdentity", () => {
  it("reuses a stored guest id without calling the client", async () => {
    const storage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_existing" });
    const fetchImpl = vi.fn();
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const identity = await createGuestIdentity({ client, storage });

    expect(identity).toEqual({ guestId: "guest_existing" });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("requests and persists a new guest id when none is stored", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_new" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const identity = await createGuestIdentity({ client, storage });

    expect(identity).toEqual({ guestId: "guest_new" });
    expect(await storage.get("anytoolai.guest_id")).toBe("guest_new");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("makes at most one backend request for concurrent calls on the same client", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_concurrent" }));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    const [first, second, third] = await Promise.all([
      createGuestIdentity({ client, storage }),
      createGuestIdentity({ client, storage }),
      createGuestIdentity({ client, storage }),
    ]);

    expect(first).toEqual({ guestId: "guest_concurrent" });
    expect(second).toEqual({ guestId: "guest_concurrent" });
    expect(third).toEqual({ guestId: "guest_concurrent" });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("throws when the response payload has no guest id", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await expect(createGuestIdentity({ client, storage })).rejects.toThrow(
      "Guest identity response was invalid.",
    );
  });

  it("throws when the backend rejects guest creation", async () => {
    const storage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () =>
      jsonResponse(500, { error: { code: "internal_error", message: "boom", request_id: "req_1" } }),
    );
    const client = makeClient(fetchImpl as unknown as typeof fetch);

    await expect(createGuestIdentity({ client, storage })).rejects.toThrow(
      "Guest identity creation failed: backend_error",
    );
  });
});
