import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import tokens from "../src/tokens.json";

// Resolved relative to vitest's cwd (the package root), matching this config's own
// `test.include` glob rather than import.meta.url, which vitest's module transform doesn't
// guarantee resolves to a real file:// URL for every test file.
const css = readFileSync("src/tokens.css", "utf-8");

/**
 * tokens.json is the canonical source; tokens.css hand-derives CSS custom properties from it with
 * no generator, so this is the sync guarantee -- it fails the moment a value drifts between the
 * two. typography.* is excluded: those map to next/font-loaded families in layout.tsx, not a
 * 1:1 custom property.
 */
const EXPECTED: Record<string, string> = {
  "--color-background": tokens.colors.background,
  "--color-background-secondary": tokens.colors.backgroundSecondary,
  "--color-background-tertiary": tokens.colors.backgroundTertiary,
  "--color-surface-card": tokens.colors.surfaceCard,
  "--color-surface-hover": tokens.colors.surfaceHover,
  "--color-surface-active": tokens.colors.surfaceActive,
  "--color-border": tokens.colors.border,
  "--color-border-strong": tokens.colors.borderStrong,
  "--color-text": tokens.colors.text,
  "--color-text-secondary": tokens.colors.textSecondary,
  "--color-text-disabled": tokens.colors.textDisabled,
  "--color-accent": tokens.colors.accent,
  "--color-accent-deep": tokens.colors.accentDeep,
  "--color-accent-glow": tokens.colors.accentGlow,
  "--color-teal": tokens.colors.teal,
  "--color-teal-glow": tokens.colors.tealGlow,
  "--color-success": tokens.colors.success,
  "--color-success-background": tokens.colors.successBackground,
  "--color-success-border": tokens.colors.successBorder,
  "--color-error": tokens.colors.error,
  "--color-error-background": tokens.colors.errorBackground,
  "--color-warning": tokens.colors.warning,
  "--gradient-accent": tokens.gradients.accent,
  "--gradient-headline": tokens.gradients.headline,
  "--layout-max-width": tokens.layout.maxWidth,
  "--layout-grid-gap": tokens.layout.gridGap,
  "--radius-input": tokens.radius.input,
  "--radius-button": tokens.radius.button,
  "--radius-card": tokens.radius.card,
  "--radius-panel": tokens.radius.panel,
  "--radius-hero": tokens.radius.hero,
  "--radius-pill": tokens.radius.pill,
};

function cssValueOf(name: string): string {
  const match = css.match(new RegExp(`${name}:\\s*([^;]+);`));
  if (!match) {
    throw new Error(`tokens.css has no declaration for ${name}`);
  }
  return match[1]!.trim();
}

describe("tokens.css stays in sync with tokens.json", () => {
  it.each(Object.entries(EXPECTED))("%s matches tokens.json", (name, expected) => {
    expect(cssValueOf(name)).toBe(expected);
  });
});
