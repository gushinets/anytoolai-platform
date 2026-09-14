import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_WEB_SESSION_STORAGE_KEY,
  WEB_SESSION_INACTIVITY_TIMEOUT_MS,
  getOrCreateWebSessionId,
} from "../../src/events/webSession";
import { createInMemoryAsyncStorage } from "../../src/storage/inMemoryAsyncStorage";
import type { AsyncStorage } from "../../src/storage/asyncStorage";

type StoredWebSession = { id: string; lastActivityAt: number } | null;

async function readStored(storage: AsyncStorage, key: string): Promise<StoredWebSession> {
  const raw = await storage.get(key);
  return raw === undefined ? null : (JSON.parse(raw) as StoredWebSession);
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-09T10:00:00.000Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("getOrCreateWebSessionId", () => {
  it("mints and persists a fresh id when none is stored", async () => {
    const storage = createInMemoryAsyncStorage();

    const id = await getOrCreateWebSessionId(storage);

    expect(typeof id).toBe("string");
    expect(id.length).toBeGreaterThan(0);
    const stored = await readStored(storage, DEFAULT_WEB_SESSION_STORAGE_KEY);
    expect(stored).toEqual({ id, lastActivityAt: Date.now() });
  });

  it("reuses the stored id and refreshes lastActivityAt when called within the inactivity window", async () => {
    const storage = createInMemoryAsyncStorage();
    const first = await getOrCreateWebSessionId(storage);

    vi.setSystemTime(new Date(Date.now() + WEB_SESSION_INACTIVITY_TIMEOUT_MS - 1));
    const second = await getOrCreateWebSessionId(storage);

    expect(second).toBe(first);
    const stored = await readStored(storage, DEFAULT_WEB_SESSION_STORAGE_KEY);
    expect(stored).toEqual({ id: first, lastActivityAt: Date.now() });
  });

  it("rotates to a new id once the gap exceeds the 30-minute inactivity window", async () => {
    const storage = createInMemoryAsyncStorage();
    const first = await getOrCreateWebSessionId(storage);

    vi.setSystemTime(new Date(Date.now() + WEB_SESSION_INACTIVITY_TIMEOUT_MS + 1));
    const second = await getOrCreateWebSessionId(storage);

    expect(second).not.toBe(first);
  });

  it("does not rotate at exactly the inactivity boundary", async () => {
    const storage = createInMemoryAsyncStorage();
    const first = await getOrCreateWebSessionId(storage);

    vi.setSystemTime(new Date(Date.now() + WEB_SESSION_INACTIVITY_TIMEOUT_MS));
    const second = await getOrCreateWebSessionId(storage);

    expect(second).toBe(first);
  });

  it("treats an unparseable stored value as absent and mints a fresh id", async () => {
    const storage = createInMemoryAsyncStorage({ [DEFAULT_WEB_SESSION_STORAGE_KEY]: "not-json" });

    const id = await getOrCreateWebSessionId(storage);

    expect(typeof id).toBe("string");
    expect(id.length).toBeGreaterThan(0);
  });

  it("treats a stored id that isn't a canonical UUID as absent and mints a fresh id", async () => {
    const storage = createInMemoryAsyncStorage({
      [DEFAULT_WEB_SESSION_STORAGE_KEY]: JSON.stringify({ id: "not-a-uuid", lastActivityAt: Date.now() }),
    });

    const id = await getOrCreateWebSessionId(storage);

    expect(id).not.toBe("not-a-uuid");
    expect(typeof id).toBe("string");
    expect(id.length).toBeGreaterThan(0);
  });

  it("falls back to a fresh unpersisted id when storage.get() rejects", async () => {
    const storage = createInMemoryAsyncStorage();
    storage.get = vi.fn().mockRejectedValue(new Error("storage unavailable"));

    const id = await getOrCreateWebSessionId(storage);

    expect(typeof id).toBe("string");
    expect(id.length).toBeGreaterThan(0);
  });

  it("still returns the minted id even when storage.set() rejects", async () => {
    const storage = createInMemoryAsyncStorage();
    storage.set = vi.fn().mockRejectedValue(new Error("storage unavailable"));

    const id = await getOrCreateWebSessionId(storage);

    expect(typeof id).toBe("string");
    expect(id.length).toBeGreaterThan(0);
  });

  it("coalesces concurrent calls into a single minted id instead of racing to different ids", async () => {
    const storage = createInMemoryAsyncStorage();

    const [first, second] = await Promise.all([
      getOrCreateWebSessionId(storage),
      getOrCreateWebSessionId(storage),
    ]);

    expect(second).toBe(first);
    const stored = await readStored(storage, DEFAULT_WEB_SESSION_STORAGE_KEY);
    expect(stored?.id).toBe(first);
  });

  it("does not coalesce concurrent calls for different storage keys", async () => {
    const storage = createInMemoryAsyncStorage();

    const [a, b] = await Promise.all([
      getOrCreateWebSessionId(storage, { storageKey: "key_a" }),
      getOrCreateWebSessionId(storage, { storageKey: "key_b" }),
    ]);

    expect(a).not.toBe(b);
  });

  it("rotates instead of extending forever when the system clock jumps backward", async () => {
    const storage = createInMemoryAsyncStorage();
    const first = await getOrCreateWebSessionId(storage);

    vi.setSystemTime(new Date(Date.now() - 5_000));
    const second = await getOrCreateWebSessionId(storage);

    expect(second).not.toBe(first);
  });

  it("uses a caller-supplied storageKey", async () => {
    const storage = createInMemoryAsyncStorage();

    const id = await getOrCreateWebSessionId(storage, { storageKey: "custom.web_session" });

    expect(await storage.get(DEFAULT_WEB_SESSION_STORAGE_KEY)).toBeUndefined();
    const stored = await readStored(storage, "custom.web_session");
    expect(stored).toEqual({ id, lastActivityAt: Date.now() });
  });
});
