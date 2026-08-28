import { describe, expect, it, vi } from "vitest";
import { PlatformApiClient } from "../../src/api/client";
import { refreshGuestIdentity } from "../../src/identity/refreshGuestIdentity";
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

describe("refreshGuestIdentity", () => {
  it("clears the stale id and mints a fresh one via backingStorage when removal succeeds", async () => {
    const backingStorage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_stale" });
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_fresh" }));

    const result = await refreshGuestIdentity(makeClient(fetchImpl as unknown as typeof fetch), backingStorage);

    expect(result).toEqual({ ok: true, value: { guestId: "guest_fresh" } });
    await expect(backingStorage.get("anytoolai.guest_id")).resolves.toBe("guest_fresh");
  });

  // Regression: a first cut of this function fell back to `backingStorage` itself when its own
  // remove() failed, so the self-heal silently no-op'd for any caller that didn't also pass its
  // own fallbackStorage (found in HandoffView.tsx, which didn't) -- createGuestIdentity() would
  // just read the still-stale id straight back out of the same storage.
  it("mints via a fresh in-memory adapter, not backingStorage, when remove() fails and no fallback is given", async () => {
    const backingStorage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_stale" });
    backingStorage.remove = vi.fn().mockRejectedValue(new Error("extension context invalidated"));
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_fresh" }));

    const result = await refreshGuestIdentity(makeClient(fetchImpl as unknown as typeof fetch), backingStorage);

    expect(result).toEqual({ ok: true, value: { guestId: "guest_fresh" } });
    // The still-stale value in backingStorage must never come back as this call's result.
    await expect(backingStorage.get("anytoolai.guest_id")).resolves.toBe("guest_stale");
  });

  it("mints via the given fallbackStorage instead of a throwaway adapter when remove() fails", async () => {
    const backingStorage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_stale" });
    backingStorage.remove = vi.fn().mockRejectedValue(new Error("write restricted"));
    const fallbackStorage = createInMemoryAsyncStorage();
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_fresh" }));

    const result = await refreshGuestIdentity(
      makeClient(fetchImpl as unknown as typeof fetch),
      backingStorage,
      { fallbackStorage },
    );

    expect(result).toEqual({ ok: true, value: { guestId: "guest_fresh" } });
    await expect(fallbackStorage.get("anytoolai.guest_id")).resolves.toBe("guest_fresh");
  });

  // Regression: a caller-supplied fallbackStorage isn't necessarily empty -- e.g. one already
  // reused across an earlier heal in the same component lifetime. If it isn't cleared before
  // reuse, createGuestIdentity() reads its pre-populated id straight back out instead of minting a
  // genuinely fresh one, silently no-op'ing the self-heal on a second failure.
  it("mints a genuinely fresh id via the fallback even when it already has a cached id from an earlier heal", async () => {
    const backingStorage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_stale" });
    backingStorage.remove = vi.fn().mockRejectedValue(new Error("write restricted"));
    const fallbackStorage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_previously_healed" });
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_fresh" }));

    const result = await refreshGuestIdentity(
      makeClient(fetchImpl as unknown as typeof fetch),
      backingStorage,
      { fallbackStorage },
    );

    expect(result).toEqual({ ok: true, value: { guestId: "guest_fresh" } });
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    await expect(fallbackStorage.get("anytoolai.guest_id")).resolves.toBe("guest_fresh");
  });

  it("falls back to a throwaway in-memory adapter when both backingStorage and fallbackStorage fail to clear", async () => {
    const backingStorage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_stale" });
    backingStorage.remove = vi.fn().mockRejectedValue(new Error("write restricted"));
    const fallbackStorage = createInMemoryAsyncStorage({ "anytoolai.guest_id": "guest_also_stale" });
    fallbackStorage.remove = vi.fn().mockRejectedValue(new Error("write restricted"));
    const fetchImpl = vi.fn(async () => jsonResponse(200, { guest_id: "guest_fresh" }));

    const result = await refreshGuestIdentity(
      makeClient(fetchImpl as unknown as typeof fetch),
      backingStorage,
      { fallbackStorage },
    );

    expect(result).toEqual({ ok: true, value: { guestId: "guest_fresh" } });
    // Neither still-stale value must ever come back as this call's result.
    await expect(backingStorage.get("anytoolai.guest_id")).resolves.toBe("guest_stale");
    await expect(fallbackStorage.get("anytoolai.guest_id")).resolves.toBe("guest_also_stale");
  });
});
