import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { isTone, TONE_OPTIONS, ToneSelect } from "../src/products/shared/tone";

afterEach(cleanup);

// The input schemas of the products that render this shared ToneSelect. A product with its own
// tone vocabulary simply doesn't use ToneSelect and isn't listed; a product that adopts it adds
// its schema here.
const PRODUCTS_DIR =
  "../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products";
const SCHEMAS_USING_TONE_SELECT = [
  "proposal_ai/schemas/generate_input.schema.json",
  "client_update_writer/schemas/update_input.schema.json",
  "client_update_writer/schemas/reply_draft_input.schema.json",
  "client_update_writer/schemas/prepaid_request_input.schema.json",
];

describe("TONE_OPTIONS", () => {
  it.each(SCHEMAS_USING_TONE_SELECT)("matches the tone enum of %s", (relativePath) => {
    // fileURLToPath, not `new URL(..., import.meta.url)`: see registry.test.tsx.
    const here = dirname(fileURLToPath(import.meta.url));
    const schema = JSON.parse(readFileSync(resolve(here, PRODUCTS_DIR, relativePath), "utf8")) as {
      properties?: { tone?: { enum?: string[] } };
    };

    expect(schema.properties?.tone?.enum).toEqual([...TONE_OPTIONS]);
  });
});

describe("isTone", () => {
  it("accepts every known tone", () => {
    for (const tone of TONE_OPTIONS) {
      expect(isTone(tone)).toBe(true);
    }
  });

  it.each(["", "playful", "NEUTRAL", " warm", "toString", "__proto__", "constructor", "hasOwnProperty"])(
    "rejects %j, including inherited Object.prototype keys",
    (value) => {
      expect(isTone(value)).toBe(false);
    },
  );
});

describe("ToneSelect", () => {
  it("reports a chosen tone, and the empty placeholder as an empty string", () => {
    const onChange = vi.fn();
    render(<ToneSelect id="tone" value="" onChange={onChange} disabled={false} placeholderLabel="Default" />);
    const select = screen.getByRole("combobox");

    fireEvent.change(select, { target: { value: "warm" } });
    expect(onChange).toHaveBeenLastCalledWith("warm");

    fireEvent.change(select, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith("");
  });
});
