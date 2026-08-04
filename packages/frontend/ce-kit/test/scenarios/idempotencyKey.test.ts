import { describe, expect, it } from "vitest";
import { generateIdempotencyKey } from "../../src/scenarios/idempotencyKey";

describe("generateIdempotencyKey", () => {
  it("generates a non-empty string", () => {
    expect(typeof generateIdempotencyKey()).toBe("string");
    expect(generateIdempotencyKey().length).toBeGreaterThan(0);
  });

  it("generates a different key on every call", () => {
    const keys = new Set(Array.from({ length: 50 }, () => generateIdempotencyKey()));
    expect(keys.size).toBe(50);
  });

  it("generates a UUID-shaped key", () => {
    const key = generateIdempotencyKey();
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
  });
});
