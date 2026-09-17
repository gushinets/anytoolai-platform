import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CopyButton } from "../src/CopyButton";

afterEach(() => {
  cleanup();
});

describe("CopyButton", () => {
  it("copies the text and calls onCopied on a successful clipboard write", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    const onCopied = vi.fn();

    render(<CopyButton text="Dear client, ..." onCopied={onCopied} />);
    fireEvent.click(screen.getByRole("button", { name: "Copy" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
    expect(writeText).toHaveBeenCalledWith("Dear client, ...");
    expect(onCopied).toHaveBeenCalledOnce();
  });

  it("shows a manual-copy alert, without throwing, when the Clipboard API is unavailable", () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    const onCopied = vi.fn();

    render(<CopyButton text="Dear client, ..." onCopied={onCopied} />);

    expect(() => fireEvent.click(screen.getByRole("button", { name: "Copy" }))).not.toThrow();
    expect(screen.getByRole("alert").textContent).toMatch(/could not copy to clipboard/i);
    expect(onCopied).not.toHaveBeenCalled();
  });

  it.each<{ label: string; onCopied: () => void }>([
    {
      label: "a throwing handler",
      onCopied: () => {
        throw new Error("onCopied boom");
      },
    },
    {
      label: "an async handler that rejects",
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      onCopied: () => Promise.reject(new Error("async onCopied boom")),
    },
  ])("still shows the Copied label with $label, without throwing", async ({ onCopied }) => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });

    render(<CopyButton text="Dear client, ..." onCopied={onCopied} />);

    expect(() => fireEvent.click(screen.getByRole("button", { name: "Copy" }))).not.toThrow();
    await waitFor(() => expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy());
  });
});
