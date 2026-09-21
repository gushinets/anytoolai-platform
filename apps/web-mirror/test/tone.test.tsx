import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TONE_OPTIONS, ToneSelect } from "../src/products/runtime/tone";

afterEach(cleanup);

function schemaFilesUnder(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    return entry.isDirectory() ? schemaFilesUnder(path) : entry.name.endsWith(".schema.json") ? [path] : [];
  });
}

describe("TONE_OPTIONS", () => {
  it("matches the tone enum of every freelancer-suite input schema that declares one", () => {
    // fileURLToPath, not `new URL(..., import.meta.url)`: see registry.test.tsx.
    const here = dirname(fileURLToPath(import.meta.url));
    const productsDir = resolve(
      here,
      "../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products",
    );
    const enums = schemaFilesUnder(productsDir).flatMap((file) => {
      const schema = JSON.parse(readFileSync(file, "utf8")) as { properties?: { tone?: { enum?: string[] } } };
      const tone = schema.properties?.tone;
      return tone ? [{ file, values: tone.enum }] : [];
    });

    // ProposalAI's generate_input + Client Update Writer's three mode inputs; a silently empty
    // scan (moved directory) must not pass vacuously.
    expect(enums.length).toBeGreaterThanOrEqual(4);
    for (const { file, values } of enums) {
      expect({ file, values }).toEqual({ file, values: [...TONE_OPTIONS] });
    }
  });
});

describe("ToneSelect", () => {
  it("reports a chosen tone, and the empty placeholder as an empty string", () => {
    const onChange = vi.fn();
    render(
      <ToneSelect id="tone" value="" onChange={onChange} disabled={false} placeholderLabel="Default" />,
    );
    const select = screen.getByRole("combobox");

    fireEvent.change(select, { target: { value: "warm" } });
    expect(onChange).toHaveBeenLastCalledWith("warm");

    fireEvent.change(select, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith("");
  });
});
