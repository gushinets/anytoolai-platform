import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createInMemoryAsyncStorage, getOrCreateWebSessionId, PlatformApiClient, type AsyncStorage } from "@anytoolai/ce-kit";
import { afterEach, describe, expect, it, vi } from "vitest";
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

  it("stops trusting the primary after its first failure, so a stale value it failed to forget is not read back", async () => {
    // remove() is what refreshGuestIdentity() uses to heal a guest id the backend no longer knows:
    // if the primary's removal fails but its reads still work, the stale id must not come back.
    const primary = createInMemoryAsyncStorage();
    await primary.set("guest", "stale");
    const failingRemove: AsyncStorage = { ...primary, remove: () => Promise.reject(new Error("denied")) };
    const storage = createResilientStorage(failingRemove, createInMemoryAsyncStorage());

    await storage.remove("guest");
    await storage.set("guest", "fresh");

    expect(await primary.get("guest")).toBe("stale");
    expect(await storage.get("guest")).toBe("fresh");
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

  it("is what the product route hands the event tracker, not a fresh in-memory storage per product", () => {
    // The route can't be rendered here (async params, next/navigation), so pin the wiring itself:
    // a `createInMemoryAsyncStorage()` inside its `useMemo` is exactly what rotated web_session_id.
    const here = dirname(fileURLToPath(import.meta.url));
    const source = readFileSync(resolve(here, "../src/app/products/[productId]/page.tsx"), "utf8");

    expect(source).toContain("createProductRunEventTracker(client, productId, getClientStorage(client))");
    expect(source).not.toContain("createInMemoryAsyncStorage");
  });
});
