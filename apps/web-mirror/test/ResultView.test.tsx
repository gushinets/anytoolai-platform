import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ResultView } from "../src/components/ResultView";

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

  it("shows the manual-copy error state, without throwing, when no onCopy is provided", () => {
    render(<ResultView text="Dear client, ..." />);

    expect(() => fireEvent.click(screen.getByRole("button", { name: "Copy" }))).not.toThrow();
    expect(screen.getByRole("alert").textContent).toMatch(/could not copy to clipboard/i);
  });
});
