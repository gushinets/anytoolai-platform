import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Input } from "../src/Input";
import { Select } from "../src/Select";
import { TextArea } from "../src/TextArea";

afterEach(() => {
  cleanup();
});

describe("field components", () => {
  it("TextArea forwards id, disabled, and aria-invalid so label association and validation still work", () => {
    render(
      <>
        <label htmlFor="task">Task</label>
        <TextArea id="task" disabled aria-invalid />
      </>,
    );
    const field = screen.getByLabelText("Task") as HTMLTextAreaElement;
    expect(field.disabled).toBe(true);
    expect(field.getAttribute("aria-invalid")).toBe("true");
  });

  it("Input forwards standard props", () => {
    render(
      <>
        <label htmlFor="lang">Language</label>
        <Input id="lang" value="en" onChange={() => {}} />
      </>,
    );
    expect((screen.getByLabelText("Language") as HTMLInputElement).value).toBe("en");
  });

  it("Select renders its options and forwards value/disabled", () => {
    render(
      <>
        <label htmlFor="tone">Tone</label>
        <Select id="tone" value="warm" disabled onChange={() => {}}>
          <option value="warm">warm</option>
        </Select>
      </>,
    );
    const field = screen.getByLabelText("Tone") as HTMLSelectElement;
    expect(field.value).toBe("warm");
    expect(field.disabled).toBe(true);
  });
});
