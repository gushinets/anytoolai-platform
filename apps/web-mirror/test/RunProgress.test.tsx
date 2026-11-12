import { act, cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatElapsed, RunProgress } from "../src/products/runtime/RunProgress";
import { englishForAllLocales, makeRender } from "./support/renderWithI18n";

const render = makeRender(englishForAllLocales({}));
const NOW = 1_800_000_000_000;

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(NOW);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("RunProgress", () => {
  it.each([[0, "0:00"], [65, "1:05"], [600, "10:00"]])("formats %i seconds", (seconds, expected) => {
    expect(formatElapsed(seconds)).toBe(expected);
  });

  it("ticks without changing the live status until the 30/60-second thresholds", async () => {
    const view = render(<RunProgress startedAtMs={NOW} statusText="Generating…" />);
    const progress = screen.getByTestId("run-progress");
    const initialStatus = screen.getByRole("status").textContent;
    expect(screen.getByText("Elapsed: 0:00").getAttribute("aria-hidden")).toBe("true");
    expect(progress.dataset.stage).toBe("normal");
    expect(initialStatus).toContain("This usually takes 10–40 seconds.");
    await act(() => vi.advanceTimersByTime(17_000));
    expect(screen.getByText("Elapsed: 0:17")).toBeTruthy();
    await act(() => vi.advanceTimersByTime(12_000));
    expect(screen.getByRole("status").textContent).toBe(initialStatus);
    expect(progress.dataset.stage).toBe("normal");
    await act(() => vi.advanceTimersByTime(1_000));
    expect(progress.dataset.stage).toBe("slow");
    expect(screen.getByRole("status").textContent).toContain("Still working.");
    await act(() => vi.advanceTimersByTime(29_000));
    expect(progress.dataset.stage).toBe("slow");
    await act(() => vi.advanceTimersByTime(1_000));
    expect(progress.dataset.stage).toBe("long");
    expect(screen.getByRole("status").textContent).toContain("Taking longer than usual.");
    expect(screen.getByRole("status").textContent).not.toContain("Elapsed");
    view.unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it.each([
    { start: NOW - 45_000, time: "0:45", stage: "slow" },
    { start: NOW + 30_000, time: "0:00", stage: "normal" },
  ])("handles restored or future start $start immediately", ({ start, time, stage }) => {
    render(<RunProgress startedAtMs={start} statusText="Generating…" />);
    expect(screen.getByText(`Elapsed: ${time}`)).toBeTruthy();
    expect(screen.getByTestId("run-progress").dataset.stage).toBe(stage);
  });

  it("reads wall time after throttling and restarts cleanly for a new run", async () => {
    const view = render(<RunProgress startedAtMs={NOW} statusText="Generating…" />);
    vi.setSystemTime(NOW + 90_000);
    await act(() => vi.advanceTimersByTime(1_000));
    expect(screen.getByText("Elapsed: 1:31")).toBeTruthy();
    view.rerender(<RunProgress startedAtMs={Date.now()} statusText="Generating…" />);
    expect(screen.getByText("Elapsed: 0:00")).toBeTruthy();
    expect(vi.getTimerCount()).toBe(1);
  });
});
