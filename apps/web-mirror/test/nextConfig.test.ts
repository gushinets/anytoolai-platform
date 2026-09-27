import { afterEach, describe, expect, it, vi } from "vitest";

const originalBasePath = process.env.ANYTOOLAI_WEB_BASE_PATH;

afterEach(() => {
  if (originalBasePath === undefined) {
    delete process.env.ANYTOOLAI_WEB_BASE_PATH;
  } else {
    process.env.ANYTOOLAI_WEB_BASE_PATH = originalBasePath;
  }
  vi.resetModules();
});

describe("Next.js deployment paths", () => {
  it("uses /tools in production while keeping /v1 at the origin root", async () => {
    process.env.ANYTOOLAI_WEB_BASE_PATH = "/tools";
    vi.resetModules();

    const config = (await import("../next.config")).default;

    expect(config.basePath).toBe("/tools");
    await expect(config.rewrites?.()).resolves.toEqual([
      {
        source: "/v1/:path*",
        destination: "http://localhost:18000/v1/:path*",
        basePath: false,
      },
    ]);
  });

  it("keeps development unprefixed", async () => {
    delete process.env.ANYTOOLAI_WEB_BASE_PATH;
    vi.resetModules();

    const config = (await import("../next.config")).default;

    expect(config.basePath).toBeUndefined();
  });
});
