import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "../src/Button";
import { simulateBrowserTranslation } from "./support/simulateBrowserTranslation";

afterEach(() => {
  cleanup();
});

describe("Button", () => {
  it("survives a translator replacing its label before and after loading (ANY-840)", () => {
    const { rerender } = render(<Button>Составить предложение</Button>);
    const button = screen.getByRole("button") as HTMLButtonElement;
    simulateBrowserTranslation(button);
    expect(button.textContent).toBe("EN: Составить предложение");

    expect(() => rerender(<Button loading>Запускаем…</Button>)).not.toThrow();
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(button.textContent).toBe("Запускаем…");

    simulateBrowserTranslation(button);
    expect(() => rerender(<Button>Пересоставить предложение</Button>)).not.toThrow();
    expect(button.disabled).toBe(false);
    expect(button.hasAttribute("aria-busy")).toBe(false);
    expect(button.querySelector('[aria-hidden="true"]')).toBeNull();
    expect(screen.getByRole("button", { name: "Пересоставить предложение" })).toBe(button);
  });

  it("keeps the label inside a stable wrapper element", () => {
    const { rerender } = render(<Button>Run</Button>);
    const button = screen.getByRole("button", { name: "Run" });
    const label = button.lastElementChild;
    expect(label?.tagName).toBe("SPAN");
    expect(label?.textContent).toBe("Run");
    rerender(<Button loading>Starting</Button>);
    expect(button.lastElementChild).toBe(label);
  });

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
