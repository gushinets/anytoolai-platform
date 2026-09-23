import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Functional tests can't see a control silently losing its shared-ui styling (vitest doesn't
// process CSS modules), so this pins it structurally: these files must render `Button`/`Select`/
// `TextArea`/`Input` from @anytoolai/shared-ui, not the bare HTML elements. Radio inputs are the
// one exception -- shared-ui has no radio component.
const here = dirname(fileURLToPath(import.meta.url));
const FILES = [
  "../src/components/ResultView.tsx",
  "../src/products/shared/tone.tsx",
  "../src/products/clientUpdateWriter/ClientUpdateWriterProduct.tsx",
  "../src/products/briefDecoder/BriefDecoderProduct.tsx",
  "../src/products/briefDecoder/BriefDecoderResult.tsx",
];

describe("shared-ui control usage", () => {
  it.each(FILES)("%s renders no bare button/select/textarea or non-radio input", (file) => {
    const source = readFileSync(resolve(here, file), "utf8");
    // Comments mention these element names in prose, so only JSX openings (`<tag` at a line start).
    const bare = (tag: string) => (source.match(new RegExp(`^\\s*<${tag}\\b`, "gm")) ?? []).length;

    expect(bare("button")).toBe(0);
    expect(bare("select")).toBe(0);
    expect(bare("textarea")).toBe(0);
    expect(bare("input")).toBe((source.match(/type="radio"/g) ?? []).length);
  });
});
