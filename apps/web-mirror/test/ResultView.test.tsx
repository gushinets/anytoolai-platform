import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResultView } from "../src/components/ResultView";
import { HOST_MESSAGES } from "../src/i18n/messages";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";
const render = makeRender(englishForAllLocales({}));


afterEach(() => {
  cleanup();
});

describe("ResultView", () => {
  it("calls onCopy with the displayed text and shows Copied when it resolves true", async () => {
    const onCopy = vi.fn(() => Promise.resolve(true));

    render(<ResultView text="Dear client, ..." onCopy={onCopy} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(onCopy).toHaveBeenCalledWith("Dear client, ...");
  });

  it("shows the manual-copy error state, without throwing, when onCopy resolves false", async () => {
    const onCopy = vi.fn(() => Promise.resolve(false));

    render(<ResultView text="Dear client, ..." onCopy={onCopy} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toMatch(/could not copy to clipboard/i));
  });

  it.each([true, false])(
    "leaves focus where the user moved it while the copy was pending (copied: %s)",
    async (copied) => {
      let finishCopy: (value: boolean) => void = () => {};
      const onCopy = vi.fn(() => new Promise<boolean>((resolve) => (finishCopy = resolve)));

      render(
        <>
          <ResultView text="Dear client, ..." onCopy={onCopy} />
          <button type="button">Elsewhere</button>
        </>,
      );
      const copyButton = screen.getByRole("button", { name: "Copy" });
      copyButton.focus();
      fireEvent.click(copyButton);
      await waitFor(() => expect(screen.getByRole("button", { name: "Copying…" })).toBeTruthy());
      const elsewhere = screen.getByRole("button", { name: "Elsewhere" });
      elsewhere.focus();

      finishCopy(copied);
      await waitFor(() => expect(screen.queryByRole("button", { name: "Copying…" })).toBeNull());
      expect(document.activeElement).toBe(elsewhere);
    },
  );

  it("gives focus back to Copy when disabling it dropped focus", async () => {
    let finishCopy: (value: boolean) => void = () => {};
    const onCopy = vi.fn(() => new Promise<boolean>((resolve) => (finishCopy = resolve)));

    render(<ResultView text="Dear client, ..." onCopy={onCopy} />);
    const copyButton = screen.getByRole("button", { name: "Copy" });
    copyButton.focus();
    fireEvent.click(copyButton);
    copyButton.blur(); // what a browser does to a focused button once it is disabled

    finishCopy(true);
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(document.activeElement).toBe(copyButton);
  });

  it("shows the manual-copy error state, without throwing, when no onCopy is provided", () => {
    render(<ResultView text="Dear client, ..." />);

    expect(() => fireEvent.click(screen.getByRole("button", { name: "Copy" }))).not.toThrow();
    expect(screen.getByRole("alert").textContent).toMatch(/could not copy to clipboard/i);
  });
});

describe("ResultView localization", () => {
  it.each(["fr", "ru", "pt"] as const)("shows its copy states and clipboard failure in %s", async (locale) => {
    window.localStorage.setItem("anytoolai.ui_locale", locale);
    const messages = HOST_MESSAGES[locale].result;
    render(<ResultView text="Dear client, ..." onCopy={vi.fn().mockResolvedValue(false)} />);

    fireEvent.click(await screen.findByRole("button", { name: messages.copy }));

    expect(await screen.findByText(messages.copyFailed)).toBeTruthy();
    window.localStorage.clear();
  });
});
