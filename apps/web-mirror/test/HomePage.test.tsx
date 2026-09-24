// The home page is the one host page with its own copy: it must follow the language selector like
// the product pages do, and list every enabled product.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import HomePage from "../src/app/page";
import { HOME_MESSAGES } from "../src/app/homeMessages";
import { LOCALE_STORAGE_KEY } from "../src/i18n/localeStorage";

describe("HomePage", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(cleanup);

  it("links every enabled product in English by default", () => {
    render(<HomePage />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("AnytoolAI");
    expect(screen.getByRole("link", { name: "ProposalAI" }).getAttribute("href")).toBe("/products/proposal_ai");
    expect(screen.getByRole("link", { name: "Client Update Writer" }).getAttribute("href")).toBe(
      "/products/client_update_writer",
    );
    expect(screen.getByText(HOME_MESSAGES.en.lead)).toBeTruthy();
  });

  it("shows the stored language and switches it from the selector", () => {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, "ru");
    render(<HomePage />);
    expect(screen.getByText(HOME_MESSAGES.ru.lead)).toBeTruthy();
    expect(screen.getByText(HOME_MESSAGES.ru.cards.client_update_writer.tags.replyDraft)).toBeTruthy();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "de" } });
    expect(screen.getByText(HOME_MESSAGES.de.lead)).toBeTruthy();
    expect(screen.queryByText(HOME_MESSAGES.ru.lead)).toBeNull();
  });
});
