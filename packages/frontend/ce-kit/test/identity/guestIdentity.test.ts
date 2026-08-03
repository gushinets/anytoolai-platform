import { describe, expect, it, vi } from "vitest";
import { createGuestIdentity } from "../../src/identity/guestIdentity";

function fakeStorage(initial: Record<string, string> = {}): Storage {
  const store = new Map(Object.entries(initial));
  return {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    clear: () => store.clear(),
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
  };
}

describe("createGuestIdentity", () => {
  it("reuses a stored guest id without calling fetch", async () => {
    const storage = fakeStorage({ "anytoolai.guest_id": "guest_existing" });
    const fetchImpl = vi.fn();

    const identity = await createGuestIdentity({ storage, fetchImpl });

    expect(identity).toEqual({ guestId: "guest_existing" });
    expect(fetchImpl).not.toHaveBeenCalled();
  });

  it("requests and persists a new guest id when none is stored", async () => {
    const storage = fakeStorage();
    const fetchImpl = vi.fn(async () => ({
      ok: true,
      json: async () => ({ guest_id: "guest_new" }),
    })) as unknown as typeof fetch;

    const identity = await createGuestIdentity({ storage, fetchImpl });

    expect(identity).toEqual({ guestId: "guest_new" });
    expect(storage.getItem("anytoolai.guest_id")).toBe("guest_new");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });
});
