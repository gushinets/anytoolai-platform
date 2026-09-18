import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Toast } from "../src/Toast";

afterEach(() => {
  cleanup();
});

describe("Toast", () => {
  it("renders the error variant as an alert", () => {
    render(<Toast variant="error">Something went wrong.</Toast>);
    expect(screen.getByRole("alert").textContent).toBe("Something went wrong.");
  });

  it("renders the success variant as a status region, not an alert", () => {
    render(<Toast variant="success">Saved.</Toast>);
    expect(screen.getByRole("status").textContent).toBe("Saved.");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
