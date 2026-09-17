import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import tokens from "../src/tokens.json";

// Resolved relative to vitest's cwd (the package root), matching this config's own
// `test.include` glob rather than import.meta.url, which vitest's module transform doesn't
// guarantee resolves to a real file:// URL for every test file.
const css = readFileSync("src/tokens.css", "utf-8");

function toKebabCase(name: string): string {
  return name.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
}

/**
 * tokens.json is the canonical source; tokens.css hand-derives CSS custom properties from it with
 * no generator. The expected set is built programmatically from tokens.json itself (not a
 * hand-maintained list), so this fails both on a value drift AND on a key-set drift: a token added
 * to tokens.json but never wired into CSS, or a stale CSS custom property whose JSON source was
 * removed. typography.* is excluded: those map to next/font-loaded families in layout.tsx, not a
 * 1:1 custom property.
 */
const PREFIXES = { colors: "color", gradients: "gradient", layout: "layout", radius: "radius" } as const;

const expected = new Map<string, string>();
for (const [group, prefix] of Object.entries(PREFIXES) as [keyof typeof PREFIXES, string][]) {
  for (const [key, value] of Object.entries(tokens[group])) {
    expected.set(`--${prefix}-${toKebabCase(key)}`, value);
  }
}

const rootBlock = css.match(/:root\s*{([^}]*)}/s)?.[1];
if (rootBlock === undefined) {
  throw new Error("tokens.css has no :root block");
}
const actual = new Map<string, string>();
for (const match of rootBlock.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/g)) {
  actual.set(match[1]!, match[2]!.trim());
}

describe("tokens.css stays in sync with tokens.json", () => {
  it("declares exactly the custom properties tokens.json's colors/gradients/layout/radius define -- no more, no fewer", () => {
    expect([...actual.keys()].sort()).toEqual([...expected.keys()].sort());
  });

  it.each([...expected.entries()])("%s matches tokens.json", (name, value) => {
    expect(actual.get(name)).toBe(value);
  });
});
