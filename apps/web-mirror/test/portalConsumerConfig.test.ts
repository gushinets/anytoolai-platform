import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

describe("Portal frontend build audience", () => {
  it.each([undefined, "custom-kernel"])("derives the public audience from the single build input %s", async (consumer) => {
    vi.stubEnv("ANYTOOLAI_PORTAL_CONSUMER_ID", consumer);
    vi.stubEnv("NEXT_PUBLIC_PORTAL_CONSUMER_ID", "ignored-independent-setting");
    vi.resetModules();
    const { default: config } = await import("../next.config");
    expect(config.env?.NEXT_PUBLIC_PORTAL_CONSUMER_ID).toBe(consumer ?? "platform-kernel");
  });

  it.each(["", "WrongCase", "../consumer", "a".repeat(65)])("refuses invalid build audience %s", async (consumer) => {
    vi.stubEnv("ANYTOOLAI_PORTAL_CONSUMER_ID", consumer);
    vi.resetModules();
    await expect(import("../next.config")).rejects.toThrow("Invalid ANYTOOLAI_PORTAL_CONSUMER_ID");
  });
});
