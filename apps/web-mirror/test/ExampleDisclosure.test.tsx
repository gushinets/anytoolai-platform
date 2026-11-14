import { cleanup, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ExampleDisclosure } from "../src/products/shared/ExampleDisclosure";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const render = makeRender(englishForAllLocales({ title: "T" }));

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("ExampleDisclosure", () => {
  it("starts collapsed and contains only reference content, with no form controls", () => {
    render(<ExampleDisclosure intro="Sample context" items={[{ label: "Brief", value: "A bakery website" }]} output="Sample result" />);
    const details = screen.getByTestId("first-run-example");
    expect(details.hasAttribute("open")).toBe(false);
    expect(details.querySelector("summary")?.textContent).toBe("Show an example");
    for (const text of ["Sample context", "What to enter", "Brief", "A bakery website", "What you get", "Sample result", "For reference only. Your own text stays as it is."]) {
      expect(screen.getByText(text)).toBeTruthy();
    }
    expect(details.querySelector("button, input, textarea, select")).toBeNull();
  });

  it("uses localized host copy independently of the product content", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "ru");
    render(<ExampleDisclosure intro="Sample context" items={[]} output="Sample result" />);
    expect(screen.getByText("Показать пример")).toBeTruthy();
    expect(screen.getByText("Что ввести")).toBeTruthy();
    expect(screen.getByText("Что получится")).toBeTruthy();
  });
});
