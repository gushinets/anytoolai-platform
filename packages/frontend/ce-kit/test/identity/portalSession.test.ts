import { webcrypto } from "node:crypto";
import { describe, expect, it, vi } from "vitest";
import { consumePortalCallback, parsePortalExchange, preparePortalAuthorization, readPortalAuthorization, readPortalSession, validatePortalReturnTarget, writePortalSession } from "../../src/identity/portalSession";

import { memoryTabStorage } from "../testUtils/tabStorage";
const session = { owner: { tenantId: "anytoolai", region: "ru", userId: "11111111-1111-1111-1111-111111111111" }, accessToken: "t".repeat(43), expiresAt: "2099-01-01T00:00:00Z" };

describe("Portal tab custody", () => {
  it("keeps a newer authorization when an older PKCE digest completes late", async () => {
    const storage = memoryTabStorage();
    let finish!: (value: ArrayBuffer) => void;
    const digest = vi.spyOn(webcrypto.subtle, "digest").mockImplementationOnce(() => new Promise<ArrayBuffer>((resolve) => { finish = resolve; }));
    try {
      const old = preparePortalAuthorization(storage, "/products/proposal_ai", "older_custody", webcrypto as Crypto);
      const newer = await preparePortalAuthorization(storage, "/products/proposal_ai", "newer_custody", webcrypto as Crypto);
      finish(new ArrayBuffer(32));
      await old;
      expect(readPortalAuthorization(storage)).toMatchObject({ state: newer.state, custodyId: "newer_custody" });
    } finally { digest.mockRestore(); }
  });
  it.each(["", "invalid custody"])("rejects an invalid authorization custody %s", async (custodyId) => {
    const storage = memoryTabStorage();
    await preparePortalAuthorization(storage, "/products/proposal_ai", custodyId, webcrypto as Crypto);
    expect(readPortalAuthorization(storage)).toBeNull();
  });
  it("stores the canonical owner/token in the supplied tab storage", () => {
    const storage = memoryTabStorage();
    writePortalSession(storage, session);
    expect(readPortalSession(storage)).toEqual(session);
  });
  it("uses secure S256 PKCE, checks state and consumes a callback once", async () => {
    const storage = memoryTabStorage();
    const { challenge, state } = await preparePortalAuthorization(storage, "/products/proposal_ai", "test_custody", webcrypto as Crypto);
    expect(challenge).toMatch(/^[A-Za-z0-9_-]{43}$/);
    const fragment = `#code=${"c".repeat(43)}&state=${state}`;
    expect(consumePortalCallback(storage, fragment + "&state=other")).toBeNull();
    expect(consumePortalCallback(storage, fragment.replace(state, "bad"))).toBeNull();
    const callback = consumePortalCallback(storage, fragment)!;
    const digest = Buffer.from(await webcrypto.subtle.digest("SHA-256", new TextEncoder().encode(callback.authorization.verifier))).toString("base64url");
    expect(digest).toBe(challenge);
    expect(consumePortalCallback(storage, fragment)).toBeNull();
  });
  it.each(["https://evil.invalid", "//evil.invalid", "/\\evil.invalid", "/products/missing", "/products/proposal_ai?callback=evil", "/products/proposal_ai?paid=guest", "/products/proposal_ai?session=a&session=b", "/products/proposal_ai#token", "/products/proposal_ai?session=%0afoo"])("rejects an invalid continuation %s", (target) => {
    expect(validatePortalReturnTarget(target, (id) => id === "proposal_ai")).toBeNull();
  });
  it("preserves owned result and handoff continuations", () => {
    const result = "/products/proposal_ai?session=session_1&scenario=proposal_ai.generate_v1";
    expect(validatePortalReturnTarget(result, () => true)).toBe(result);
    expect(validatePortalReturnTarget("/handoff/opaque_token", () => false)).toBe("/handoff/opaque_token");
    expect(validatePortalReturnTarget("/handoff/opaque_token?paid=1", () => false)).toBe("/handoff/opaque_token?paid=1");
    expect(validatePortalReturnTarget(result + "&paid=1", () => true)).toBe(result + "&paid=1");
  });
  it.each([
    { schema_version: 2 }, { token_type: "other" }, { user_id: "foreign-not-uuid" }, { expires_at: "tomorrow" }, { access_token: "bad token" },
  ])("rejects malformed exchange fields %o", (override) => {
    expect(parsePortalExchange({ schema_version: 1, token_type: "Bearer", tenant_id: "anytoolai", region: "ru", user_id: session.owner.userId,
      access_token: session.accessToken, expires_at: session.expiresAt, ...override })).toBeNull();
  });
  it("refuses authorization before navigation when storage rejects custody", async () => {
    const storage = memoryTabStorage();
    storage.setItem = () => { throw new Error("storage denied"); };
    await expect(preparePortalAuthorization(storage, "/products/proposal_ai", "test_custody", webcrypto as Crypto)).rejects.toThrow();
  });
});
