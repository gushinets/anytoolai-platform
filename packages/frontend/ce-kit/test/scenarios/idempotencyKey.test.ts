import { afterEach, describe, expect, it, vi } from "vitest";
import { generateIdempotencyKey } from "../../src/scenarios/idempotencyKey";

describe("generateIdempotencyKey", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

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

  it("falls back to crypto.getRandomValues, with correct version/variant bits, when randomUUID is unavailable", () => {
    const realCrypto = globalThis.crypto;
    const getRandomValues = vi.fn((array: Uint8Array) => realCrypto.getRandomValues(array));
    vi.stubGlobal("crypto", { getRandomValues });

    const key = generateIdempotencyKey();

    expect(getRandomValues).toHaveBeenCalledTimes(1);
    // Version 4 (the "4" nibble) and variant 10xx (the "8"/"9"/"a"/"b" nibble) -- the bits
    // `generateIdempotencyKey()` sets by hand on the `crypto.getRandomValues()` fallback path,
    // since that API only fills random bytes and doesn't format them as a UUID itself.
    expect(key).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  });
});
