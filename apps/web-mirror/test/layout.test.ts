import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { tokens } from "@anytoolai/shared-ui";

/**
 * `next/font/google` requires a literal, statically-analyzable import per font -- it can't be
 * driven by an arbitrary runtime string -- so layout.tsx's `DM_Sans`/`DM_Mono` imports can't
 * actually read tokens.json's typography section at runtime. This is the invariant that keeps
 * that hardcoding honest instead of silently drifting: it fails the moment tokens.json's
 * typography values change without a matching update here and in layout.tsx.
 *
 * `headline` (Cabinet Grotesk) isn't loaded by any font import yet -- documented follow-up debt
 * (exec-plan risk #3), not implemented -- but is still asserted so an unrelated edit to that value
 * is a deliberate, visible diff rather than a silent one.
 */
const EXPECTED_TYPOGRAPHY = {
  headline: "Cabinet Grotesk",
  body: "DM Sans",
  mono: "DM Mono",
};

// next/font/google's actual loaded face has no runtime representation to introspect (only the
// generated --font-* CSS variable it sets), so the only way to check layout.tsx's import matches
// tokens.json is to look at its source text directly.
const GOOGLE_FONT_IMPORT_NAMES: Record<string, string> = {
  "DM Sans": "DM_Sans",
  "DM Mono": "DM_Mono",
};

describe("layout.tsx's fonts stay in sync with tokens.json's typography", () => {
  it("tokens.json's typography section still has the values this test (and layout.tsx) assume", () => {
    expect(tokens.typography).toEqual(EXPECTED_TYPOGRAPHY);
  });

  it("layout.tsx imports the next/font/google face matching tokens.json's body/mono typography", () => {
    const source = readFileSync("src/app/layout.tsx", "utf-8");
    expect(source).toContain(GOOGLE_FONT_IMPORT_NAMES[tokens.typography.body]!);
    expect(source).toContain(GOOGLE_FONT_IMPORT_NAMES[tokens.typography.mono]!);
  });
});
