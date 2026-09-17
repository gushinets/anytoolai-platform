import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Spinner } from "../src/Spinner";

afterEach(() => {
  cleanup();
});

describe("Spinner", () => {
  it("is purely decorative, so it never contributes its own accessible name to a surrounding status region", () => {
    const { container } = render(<Spinner />);
    const spinner = container.firstElementChild!;
    expect(spinner.getAttribute("aria-hidden")).toBe("true");
    expect(spinner.textContent).toBe("");
  });
});
