import { describe, expect, it, vi } from "vitest";
import { createChromeTabNavigator } from "../../src/handoffs/chromeTabNavigator";
import type { ChromeTabsArea } from "../../src/handoffs/chromeTabNavigator";
import { openHandoffConsent } from "../../src/handoffs/openHandoffConsent";
import { createWindowNavigator } from "../../src/handoffs/windowNavigator";

describe("openHandoffConsent", () => {
  it("joins the base URL and token into a consent URL and navigates exactly once", async () => {
    const navigate = vi.fn();

    await openHandoffConsent({
      webConsentBaseUrl: "https://web.example.com",
      handoffToken: "token_abc",
      navigate,
    });

    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith("https://web.example.com/handoff/token_abc");
  });

  it("trims a trailing slash on the base URL before joining", async () => {
    const navigate = vi.fn();

    await openHandoffConsent({
      webConsentBaseUrl: "https://web.example.com/",
      handoffToken: "token_abc",
      navigate,
    });

    expect(navigate).toHaveBeenCalledWith("https://web.example.com/handoff/token_abc");
  });

  it("percent-encodes the token as an opaque path segment", async () => {
    const navigate = vi.fn();

    await openHandoffConsent({
      webConsentBaseUrl: "https://web.example.com",
      handoffToken: "token with spaces/slash",
      navigate,
    });

    expect(navigate).toHaveBeenCalledWith(
      "https://web.example.com/handoff/token%20with%20spaces%2Fslash",
    );
  });

  it("throws synchronously on an empty webConsentBaseUrl", () => {
    const navigate = vi.fn();

    expect(() =>
      openHandoffConsent({ webConsentBaseUrl: "", handoffToken: "token_abc", navigate }),
    ).toThrow(/openHandoffConsent requires a non-empty baseUrl/);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("throws synchronously on a whitespace-only webConsentBaseUrl", () => {
    const navigate = vi.fn();

    expect(() =>
      openHandoffConsent({ webConsentBaseUrl: "   ", handoffToken: "token_abc", navigate }),
    ).toThrow(/openHandoffConsent requires a non-empty baseUrl/);
    expect(navigate).not.toHaveBeenCalled();
  });
});

describe("createWindowNavigator", () => {
  it("calls through to the underlying location.assign() with the built URL", () => {
    const win = { location: { assign: vi.fn() } };
    const navigate = createWindowNavigator(win);

    void navigate("https://web.example.com/handoff/token_abc");

    expect(win.location.assign).toHaveBeenCalledWith("https://web.example.com/handoff/token_abc");
  });
});

describe("createChromeTabNavigator", () => {
  it("calls through to the underlying tabs.create() with the built URL", async () => {
    const tabs: ChromeTabsArea = { create: vi.fn(async () => ({})) };
    const navigate = createChromeTabNavigator(tabs);

    await navigate("https://web.example.com/handoff/token_abc");

    expect(tabs.create).toHaveBeenCalledWith({ url: "https://web.example.com/handoff/token_abc" });
  });
});
