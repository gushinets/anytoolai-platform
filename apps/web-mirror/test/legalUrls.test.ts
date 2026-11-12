import { afterEach, describe, expect, it, vi } from "vitest";
import { privacyPolicyUrl } from "../src/lib/legalUrls";

afterEach(() => vi.unstubAllEnvs());

describe("privacyPolicyUrl", () => {
  it.each([undefined, "", "   ", "/privacy", "//example.com/privacy", "not a URL",
    "javascript:alert(1)", "data:text/html,x", "ftp://example.com/privacy"])(
    "hides missing or unsupported URL %s", (value) => {
      vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", value);
      expect(privacyPolicyUrl()).toBeNull();
    },
  );

  it.each([
    ["https://example.com/privacy", "https://example.com/privacy"],
    ["  https://example.com/privacy  ", "https://example.com/privacy"],
    ["http://localhost:3000/privacy", "http://localhost:3000/privacy"],
  ])("accepts absolute HTTP(S) URL %s", (value, expected) => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", value);
    expect(privacyPolicyUrl()).toBe(expected);
  });
});
