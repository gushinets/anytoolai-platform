import { describe, expect, it } from "vitest";
import { createInMemoryAsyncStorage } from "../../src/storage/inMemoryAsyncStorage";

describe("createInMemoryAsyncStorage", () => {
  it("returns undefined for a key that was never set", async () => {
    const storage = createInMemoryAsyncStorage();
    await expect(storage.get("missing")).resolves.toBeUndefined();
  });

  it("returns a previously set value", async () => {
    const storage = createInMemoryAsyncStorage();
    await storage.set("guest_id", "guest_123");
    await expect(storage.get("guest_id")).resolves.toBe("guest_123");
  });

  it("overwrites an existing value", async () => {
    const storage = createInMemoryAsyncStorage();
    await storage.set("guest_id", "guest_123");
    await storage.set("guest_id", "guest_456");
    await expect(storage.get("guest_id")).resolves.toBe("guest_456");
  });

  it("removes a stored value", async () => {
    const storage = createInMemoryAsyncStorage();
    await storage.set("guest_id", "guest_123");
    await storage.remove("guest_id");
    await expect(storage.get("guest_id")).resolves.toBeUndefined();
  });

  it("seeds initial state without leaking it between separate instances", async () => {
    const storageA = createInMemoryAsyncStorage({ guest_id: "guest_seeded" });
    const storageB = createInMemoryAsyncStorage();

    await expect(storageA.get("guest_id")).resolves.toBe("guest_seeded");
    await expect(storageB.get("guest_id")).resolves.toBeUndefined();
  });
});
