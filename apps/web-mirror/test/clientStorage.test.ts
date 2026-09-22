import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createInMemoryAsyncStorage,
  DEFAULT_GUEST_STORAGE_KEY,
  DEFAULT_WEB_SESSION_STORAGE_KEY,
  getOrCreateWebSessionId,
  PlatformApiClient,
  type AsyncStorage,
} from "@anytoolai/ce-kit";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getPlatformApiClient } from "../src/lib/apiClient";
import { createResilientStorage, getClientStorage } from "../src/products/runtime/clientStorage";

afterEach(() => {
  vi.restoreAllMocks();
});

function throwingStorage(failing: Array<"get" | "set" | "remove">): AsyncStorage {
  const inner = createInMemoryAsyncStorage();
  const fail = () => Promise.reject(new Error("storage denied"));
  return {
    get: failing.includes("get") ? fail : (key) => inner.get(key),
    set: failing.includes("set") ? fail : (key, value) => inner.set(key, value),
    remove: failing.includes("remove") ? fail : (key) => inner.remove(key),
  };
}

describe("createResilientStorage", () => {
  it("is just the memory storage when there is no primary", async () => {
    const memory = createInMemoryAsyncStorage();
    expect(createResilientStorage(null, memory)).toBe(memory);
  });

  it("reads and writes through the primary while it works, so tabs keep sharing it", async () => {
    const primary = createInMemoryAsyncStorage();
    const storage = createResilientStorage(primary, createInMemoryAsyncStorage());

    await storage.set("k", "v");
    expect(await primary.get("k")).toBe("v");

    await primary.set("k", "changed-in-another-tab");
    expect(await storage.get("k")).toBe("changed-in-another-tab");

    await storage.remove("k");
    expect(await primary.get("k")).toBeUndefined();
  });

  it("keeps a value stable when the primary's writes throw", async () => {
    const storage = createResilientStorage(throwingStorage(["set"]), createInMemoryAsyncStorage());

    await storage.set("guest", "guest_A");

    expect(await storage.get("guest")).toBe("guest_A");
  });

  it("keeps a value stable when the primary's reads throw", async () => {
    const storage = createResilientStorage(throwingStorage(["get"]), createInMemoryAsyncStorage());

    await storage.set("guest", "guest_A");

    expect(await storage.get("guest")).toBe("guest_A");
  });

  it("does not bring back a value the primary failed to forget, until a write makes it current again", async () => {
    // remove() is what refreshGuestIdentity() uses to heal a guest id the backend no longer knows:
    // if the primary's removal fails but its reads still work, the stale id must not come back.
    const primary = createInMemoryAsyncStorage();
    await primary.set("guest", "stale");
    const failingRemove: AsyncStorage = { ...primary, remove: () => Promise.reject(new Error("denied")) };
    const storage = createResilientStorage(failingRemove, createInMemoryAsyncStorage());

    await storage.remove("guest");
    expect(await storage.get("guest")).toBeUndefined();

    await storage.set("guest", "fresh");
    expect(await primary.get("guest")).toBe("fresh");
    expect(await storage.get("guest")).toBe("fresh");
  });

  it("keeps trusting the primary for other keys when a write to one key fails", async () => {
    // Code review finding [P2]: a single trust flag shared by every key meant one failing write
    // (quota exceeded on web_session_id) also stopped the guest id being read from the primary.
    const primary = createInMemoryAsyncStorage();
    await primary.set("guest", "guest_A");
    const quotaOnSessionOnly: AsyncStorage = {
      ...primary,
      set: (key, value) => (key === "web_session" ? Promise.reject(new Error("quota")) : primary.set(key, value)),
    };
    const storage = createResilientStorage(quotaOnSessionOnly, createInMemoryAsyncStorage());

    await storage.set("web_session", "S1");
    await primary.set("guest", "guest_B_from_another_tab");

    expect(await storage.get("guest")).toBe("guest_B_from_another_tab");
  });

  it("keeps a value that was only ever read from the primary when the primary breaks later", async () => {
    // Code review finding [P2]: a guest id persisted by an earlier visit is only read, never
    // written, so memory used to hold nothing for it.
    const primary = createInMemoryAsyncStorage();
    await primary.set("guest", "guest_A");
    let broken = false;
    const flaky: AsyncStorage = {
      ...primary,
      get: (key) => (broken ? Promise.reject(new Error("denied")) : primary.get(key)),
    };
    const storage = createResilientStorage(flaky, createInMemoryAsyncStorage());

    expect(await storage.get("guest")).toBe("guest_A");
    broken = true;

    expect(await storage.get("guest")).toBe("guest_A");
  });

  it("falls back to memory when the primary accepts a write but forgets it", async () => {
    const forgetful: AsyncStorage = { get: async () => undefined, set: async () => undefined, remove: async () => undefined };
    const storage = createResilientStorage(forgetful, createInMemoryAsyncStorage());

    await storage.set("guest", "guest_A");

    expect(await storage.get("guest")).toBe("guest_A");
  });

  it("holds one guest id across a later web-session write failure, through ce-kit's real callers", async () => {
    // The reviewer's exact sequence: a guest persisted by an earlier visit is read, then the event
    // tracker's web_session write starts failing, then the page remounts and asks for the guest again.
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ guest_id: "guest_NEW" }), { status: 200 }));
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl: fetchImpl as unknown as typeof fetch });
    const primary = createInMemoryAsyncStorage();
    await primary.set(DEFAULT_GUEST_STORAGE_KEY, "guest_A");
    const quotaOnSession: AsyncStorage = {
      ...primary,
      set: (key, value) => (key === DEFAULT_WEB_SESSION_STORAGE_KEY ? Promise.reject(new Error("quota")) : primary.set(key, value)),
      get: (key) => (key === DEFAULT_WEB_SESSION_STORAGE_KEY ? Promise.reject(new Error("denied")) : primary.get(key)),
    };
    const storage = createResilientStorage(quotaOnSession, createInMemoryAsyncStorage());

    const first = await client.createGuestIdentity({ storage });
    await getOrCreateWebSessionId(storage);
    const afterRemount = await client.createGuestIdentity({ storage });

    expect(first.ok && first.value.guestId).toBe("guest_A");
    expect(afterRemount.ok && afterRemount.value.guestId).toBe("guest_A");
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("treats a failed read as a miss for that call only, and consults the primary again next time", async () => {
    // Code review finding [P2]: a read failure may be transient (ce-kit re-reads after minting a
    // guest for exactly that reason), so it must not stop the primary being used for that key.
    const primary = createInMemoryAsyncStorage();
    await primary.set("guest", "guest_P");
    let failNextRead = true;
    const flaky: AsyncStorage = {
      ...primary,
      get: (key) => {
        if (failNextRead) {
          failNextRead = false;
          return Promise.reject(new Error("locked"));
        }
        return primary.get(key);
      },
    };
    const storage = createResilientStorage(flaky, createInMemoryAsyncStorage());

    expect(await storage.get("guest")).toBeUndefined();
    expect(await storage.get("guest")).toBe("guest_P");
  });

  it("persists an identity minted after a transient read failure, so the next page load reuses it", async () => {
    // The reviewer's exact sequence, through ce-kit's real createGuestIdentity: the first read
    // rejects once, the backend mints guest_A, ce-kit's second read works, guest_A reaches the
    // primary -- and a fresh client and storage over the same primary (a reload) needs no backend.
    const primary = createInMemoryAsyncStorage();
    let failNextRead = true;
    const flaky: AsyncStorage = {
      ...primary,
      get: (key) => {
        if (failNextRead) {
          failNextRead = false;
          return Promise.reject(new Error("locked"));
        }
        return primary.get(key);
      },
    };
    const fetchImpl = vi.fn(async () => new Response(JSON.stringify({ guest_id: "guest_A" }), { status: 200 }));
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl: fetchImpl as unknown as typeof fetch });

    const first = await client.createGuestIdentity({ storage: createResilientStorage(flaky, createInMemoryAsyncStorage()) });

    const reloadedFetch = vi.fn();
    const reloadedClient = new PlatformApiClient({ baseUrl: "https://api.example.com", fetchImpl: reloadedFetch as unknown as typeof fetch });
    const afterReload = await reloadedClient.createGuestIdentity({
      storage: createResilientStorage(primary, createInMemoryAsyncStorage()),
    });

    expect(first.ok && first.value.guestId).toBe("guest_A");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(await primary.get(DEFAULT_GUEST_STORAGE_KEY)).toBe("guest_A");
    expect(afterReload.ok && afterReload.value.guestId).toBe("guest_A");
    expect(reloadedFetch).not.toHaveBeenCalled();
  });

  it("catches the primary up once a write succeeds again, so another tab's changes are visible again", async () => {
    const primary = createInMemoryAsyncStorage();
    let failWrites = true;
    const recovering: AsyncStorage = {
      ...primary,
      set: (key, value) => (failWrites ? Promise.reject(new Error("quota")) : primary.set(key, value)),
    };
    const storage = createResilientStorage(recovering, createInMemoryAsyncStorage());

    await storage.set("web_session", "S1");
    await primary.set("web_session", "older-in-primary");
    expect(await storage.get("web_session")).toBe("S1");

    failWrites = false;
    await storage.set("web_session", "S2");
    await primary.set("web_session", "S3_from_another_tab");

    expect(await storage.get("web_session")).toBe("S3_from_another_tab");
  });

  it("never throws from remove(), so a self-heal always sticks", async () => {
    const storage = createResilientStorage(throwingStorage(["remove"]), createInMemoryAsyncStorage());

    await expect(storage.remove("guest")).resolves.toBeUndefined();
  });
});

describe("getClientStorage", () => {
  it("returns one storage per client, and a different one for another client", () => {
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com" });
    const other = new PlatformApiClient({ baseUrl: "https://api.example.com" });

    expect(getClientStorage(client)).toBe(getClientStorage(client));
    expect(getClientStorage(client)).not.toBe(getClientStorage(other));
  });

  it("keeps one web_session_id across a product change when localStorage is unavailable", async () => {
    // Code review finding [P3]: the route built a fresh in-memory storage per productId, so
    // ProposalAI -> Client Update Writer rotated web_session_id long before the 30-minute
    // inactivity window. It now asks for the client's storage, which survives the change.
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    const client = new PlatformApiClient({ baseUrl: "https://api.example.com" });

    const onProductA = await getOrCreateWebSessionId(getClientStorage(client));
    const onProductB = await getOrCreateWebSessionId(getClientStorage(client));

    expect(onProductB).toBe(onProductA);
  });

  it("is what the product route hands the event tracker, on the page-load client", () => {
    // The route can't be rendered here (async params, next/navigation), so pin the wiring itself:
    // a client or `createInMemoryAsyncStorage()` built inside the page is exactly what let a remount
    // or a product change start from an empty identity.
    const here = dirname(fileURLToPath(import.meta.url));
    const source = readFileSync(resolve(here, "../src/app/products/[productId]/page.tsx"), "utf8");

    expect(source).toContain("createProductRunEventTracker(client, productId, getClientStorage(client))");
    expect(source).toContain("const client = getPlatformApiClient();");
    expect(source).not.toContain("createInMemoryAsyncStorage");
    expect(source).not.toContain("createPlatformApiClient");
  });

  it("gives the handoff page the same page-load client instead of its own", () => {
    const here = dirname(fileURLToPath(import.meta.url));
    const source = readFileSync(resolve(here, "../src/app/handoff/[handoffToken]/page.tsx"), "utf8");

    expect(source).toContain("const client = getPlatformApiClient();");
    expect(source).not.toContain("createPlatformApiClient");
  });
});

describe("getPlatformApiClient", () => {
  it("is one client for the whole page load, however many components ask for it", () => {
    expect(getPlatformApiClient()).toBe(getPlatformApiClient());
  });
});
