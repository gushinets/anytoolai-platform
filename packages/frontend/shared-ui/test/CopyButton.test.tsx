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
});
