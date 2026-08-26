import { describe, expect, it, vi } from "vitest";
import { createLocalStorageAdapter } from "../../src/storage/localStorageAdapter";

/** Minimal fake matching the synchronous `Storage` interface (`window.localStorage`'s shape). */
function createFakeStorage(initial: Record<string, string> = {}): Storage {
  const store = new Map(Object.entries(initial));
  return {
    getItem: vi.fn((key: string) => store.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      store.delete(key);
    }),
    clear: vi.fn(() => store.clear()),
    key: vi.fn((index: number) => Array.from(store.keys())[index] ?? null),
    get length() {
      return store.size;
    },
  } as Storage;
}

describe("createLocalStorageAdapter", () => {
  it("returns undefined for a key that was never set", async () => {
    const storage = createLocalStorageAdapter(createFakeStorage());
    await expect(storage.get("missing")).resolves.toBeUndefined();
  });

  it("stores and retrieves a value scoped to a single key, without touching others", async () => {
    const backing = createFakeStorage({ unrelated_key: "leave_me_alone" });
    const storage = createLocalStorageAdapter(backing);

    await storage.set("guest_id", "guest_123");

    await expect(storage.get("guest_id")).resolves.toBe("guest_123");
    expect(backing.setItem).toHaveBeenCalledWith("guest_id", "guest_123");
    await expect(storage.get("unrelated_key")).resolves.toBe("leave_me_alone");
  });

  it("removes a stored value", async () => {
    const storage = createLocalStorageAdapter(createFakeStorage({ guest_id: "guest_123" }));

    await storage.remove("guest_id");

    await expect(storage.get("guest_id")).resolves.toBeUndefined();
  });
});
