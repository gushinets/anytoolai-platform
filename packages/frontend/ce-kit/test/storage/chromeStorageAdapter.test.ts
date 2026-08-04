import { describe, expect, it, vi } from "vitest";
import type { ChromeStorageArea } from "../../src/storage/chromeStorageAdapter";
import { createChromeStorageAdapter } from "../../src/storage/chromeStorageAdapter";

/** Minimal fake matching chrome.storage.local's promise-based multi-key API. */
function createFakeChromeStorageArea(initial: Record<string, unknown> = {}): ChromeStorageArea {
  const store = new Map(Object.entries(initial));
  return {
    get: vi.fn(async (keys: string[]) => {
      const result: Record<string, unknown> = {};
      for (const key of keys) {
        if (store.has(key)) {
          result[key] = store.get(key);
        }
      }
      return result;
    }),
    set: vi.fn(async (items: Record<string, unknown>) => {
      for (const [key, value] of Object.entries(items)) {
        store.set(key, value);
      }
    }),
    remove: vi.fn(async (keys: string[]) => {
      for (const key of keys) {
        store.delete(key);
      }
    }),
  };
}

describe("createChromeStorageAdapter", () => {
  it("returns undefined for a key that was never set", async () => {
    const storage = createChromeStorageAdapter(createFakeChromeStorageArea());
    await expect(storage.get("missing")).resolves.toBeUndefined();
  });

  it("stores and retrieves a value scoped to a single key, without touching others", async () => {
    const area = createFakeChromeStorageArea({ unrelated_key: "leave_me_alone" });
    const storage = createChromeStorageAdapter(area);

    await storage.set("guest_id", "guest_123");

    await expect(storage.get("guest_id")).resolves.toBe("guest_123");
    expect(area.set).toHaveBeenCalledWith({ guest_id: "guest_123" });
    await expect(storage.get("unrelated_key")).resolves.toBe("leave_me_alone");
  });

  it("removes a stored value", async () => {
    const storage = createChromeStorageAdapter(createFakeChromeStorageArea({ guest_id: "guest_123" }));

    await storage.remove("guest_id");

    await expect(storage.get("guest_id")).resolves.toBeUndefined();
  });

  it("treats a non-string stored value as absent rather than returning it as-is", async () => {
    const storage = createChromeStorageAdapter(createFakeChromeStorageArea({ guest_id: 12345 }));

    await expect(storage.get("guest_id")).resolves.toBeUndefined();
  });
});
