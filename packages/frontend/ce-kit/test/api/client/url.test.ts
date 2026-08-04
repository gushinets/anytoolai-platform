import { describe, expect, it } from "vitest";
import { joinUrl, normalizeBaseUrl } from "../../../src/api/client/url";

describe("normalizeBaseUrl", () => {
  it("trims surrounding whitespace", () => {
    expect(normalizeBaseUrl("  https://api.example.com  ")).toBe("https://api.example.com");
  });

  it("strips a single trailing slash", () => {
    expect(normalizeBaseUrl("https://api.example.com/")).toBe("https://api.example.com");
  });

  it("leaves a base URL without a trailing slash unchanged", () => {
    expect(normalizeBaseUrl("https://api.example.com")).toBe("https://api.example.com");
  });

  it("throws for an empty base URL", () => {
    expect(() => normalizeBaseUrl("")).toThrow(/non-empty baseUrl/);
    expect(() => normalizeBaseUrl("   ")).toThrow(/non-empty baseUrl/);
  });
});

describe("joinUrl", () => {
  it("joins a base URL and a path that already has a leading slash", () => {
    expect(joinUrl("https://api.example.com", "/v1/x")).toBe("https://api.example.com/v1/x");
  });

  it("adds a leading slash to the path when missing", () => {
    expect(joinUrl("https://api.example.com", "v1/x")).toBe("https://api.example.com/v1/x");
  });

  it("does not introduce a double slash for a root path", () => {
    expect(joinUrl("https://api.example.com", "/")).toBe("https://api.example.com/");
  });
});
