import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DataProcessingNotice } from "../src/components/DataProcessingNotice";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const render = makeRender(englishForAllLocales({}));
const POLICY_URL = "https://example.com/privacy";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllEnvs();
});

describe("DataProcessingNotice", () => {
  it("explains processing and opens the configured policy safely in a new tab", () => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", POLICY_URL);
    render(<DataProcessingNotice />);
    expect(screen.getByText("Data processing.")).toBeTruthy();
    expect(screen.getByText(/sent to our service and to an AI model provider/)).toBeTruthy();
    expect(screen.getByText(/stored with your run on our servers/)).toBeTruthy();
    const link = screen.getByRole("link", { name: "Privacy policy (opens in a new tab)" });
    expect(link.getAttribute("href")).toBe(POLICY_URL);
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")?.split(" ")).toEqual(expect.arrayContaining(["noopener", "noreferrer"]));
  });

  it.each([undefined, "", "javascript:alert(1)"])("keeps the notice without a usable URL: %s", (url) => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", url);
    render(<DataProcessingNotice />);
    expect(screen.getByText("Data processing.")).toBeTruthy();
    expect(screen.getByText(/Do not enter passwords/)).toBeTruthy();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("uses explicit Russian privacy-policy wording", () => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", POLICY_URL);
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "ru");
    render(<DataProcessingNotice />);
    expect(screen.getByText("Обработка данных.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Политика конфиденциальности (откроется в новой вкладке)" })).toBeTruthy();
  });

  it.each([undefined, POLICY_URL])("wraps all translated text beside the optional link: %s", (url) => {
    vi.stubEnv("NEXT_PUBLIC_ANYTOOLAI_PRIVACY_POLICY_URL", url);
    render(<DataProcessingNotice />);
    const notice = screen.getByTestId("data-processing-notice");
    const bareText = Array.from(notice.childNodes).filter(
      (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
    );
    expect(bareText).toHaveLength(0);
  });
});
