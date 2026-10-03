import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { isTone, TONE_OPTIONS } from "../src/products/shared/tone";
// Input schemas sharing the neutral/warm/firm wire vocabulary.
const PRODUCTS_DIR =
  "../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products";
const SCHEMAS_USING_TONE = [
  "proposal_ai/schemas/generate_input.schema.json",
  "client_update_writer/schemas/update_input.schema.json",
  "client_update_writer/schemas/reply_draft_input.schema.json",
  "client_update_writer/schemas/prepaid_request_input.schema.json",
];

describe("TONE_OPTIONS", () => {
  it.each(SCHEMAS_USING_TONE)("matches the tone enum of %s", (relativePath) => {
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
