import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "../src/Button";

afterEach(() => {
  cleanup();
});

describe("Button", () => {
  it("defaults to a non-submitting button and fires onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);

    const button = screen.getByRole("button", { name: "Go" }) as HTMLButtonElement;
    expect(button.type).toBe("button");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("honors an explicit type, e.g. for a form submit button", () => {
    render(<Button type="submit">Submit</Button>);
    expect((screen.getByRole("button", { name: "Submit" }) as HTMLButtonElement).type).toBe("submit");
  });

  it("disables the button and marks it busy while loading", () => {
    render(<Button loading>Run</Button>);
    const button = screen.getByRole("button", { name: "Run" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("aria-busy")).toBe("true");
  });

  it("stays disabled when disabled is passed directly", () => {
    render(<Button disabled>Run</Button>);
    expect((screen.getByRole("button", { name: "Run" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
