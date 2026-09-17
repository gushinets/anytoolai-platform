import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { tokens } from "@anytoolai/shared-ui";

/**
 * Neither `next/font/google` nor a Fontshare API URL can be driven by an arbitrary runtime string
 * -- both require a literal, statically-analyzable value -- so layout.tsx's font wiring can't
 * actually read tokens.json's typography section at runtime. This is the invariant that keeps
 * that hardcoding honest instead of silently drifting: it fails the moment tokens.json's
 * typography values change without a matching update here and in layout.tsx, or a font call's
 * `variable` option gets swapped/detached from `<html>`'s className.
 */
const EXPECTED_TYPOGRAPHY = {
  headline: "Cabinet Grotesk",
  body: "DM Sans",
  mono: "DM Mono",
};

// next/font/google's actual loaded face has no runtime representation to introspect (only the
// generated --font-* CSS variable it sets), so the only way to check layout.tsx's import matches
// tokens.json is to look at its source text directly. Each entry also names the CSS custom
// property tokens.css itself consumes for that role (body { font-family: var(--font-body, ...) }),
// so a swapped/wrong `variable` option fails here instead of only being caught visually.
const GOOGLE_FONT_CONFIG: Record<string, { importName: string; variable: string }> = {
  "DM Sans": { importName: "DM_Sans", variable: "--font-body" },
  "DM Mono": { importName: "DM_Mono", variable: "--font-mono" },
};

function extractFontCall(source: string, importName: string): { identifier: string; args: string } {
  const match = source.match(new RegExp(`const (\\w+)\\s*=\\s*${importName}\\(([^)]*)\\)`));
  if (!match) {
    throw new Error(`layout.tsx has no "const x = ${importName}(...)" call`);
  }
  return { identifier: match[1]!, args: match[2]! };
}

function requireHtmlTag(source: string): string {
  // The whole opening tag, not just a captured className value: className's own template literal
  // contains nested `${...}` braces that a `[^}]*`-style capture would stop at early.
  const htmlTag = source.match(/<html[\s\S]*?>/)?.[0];
  if (htmlTag === undefined) {
    throw new Error("layout.tsx has no <html> opening tag");
  }
  return htmlTag;
}

// Fontshare's font-family slug is the family name, lowercased and hyphen-joined
// (e.g. "Cabinet Grotesk" -> "cabinet-grotesk") -- matches every family path on fontshare.com.
function fontshareSlug(family: string): string {
  return family.toLowerCase().replace(/\s+/g, "-");
}

describe("layout.tsx's fonts stay in sync with tokens.json's typography", () => {
  it("tokens.json's typography section still has the values this test (and layout.tsx) assume", () => {
    expect(tokens.typography).toEqual(EXPECTED_TYPOGRAPHY);
  });

  it("layout.tsx configures each Google font's variable option to what tokens.css consumes, and applies it on <html>", () => {
    const source = readFileSync("src/app/layout.tsx", "utf-8");
    const htmlTag = requireHtmlTag(source);

    for (const role of ["body", "mono"] as const) {
      const config = GOOGLE_FONT_CONFIG[tokens.typography[role]];
      if (!config) {
        throw new Error(`No known next/font/google mapping for typography.${role} = "${tokens.typography[role]}"`);
      }
      const call = extractFontCall(source, config.importName);
      expect(call.args).toContain(`variable: "${config.variable}"`);
      expect(htmlTag).toContain(`${call.identifier}.variable`);
    }
  });

  it("layout.tsx loads the headline font from Fontshare's API (its license forbids a self-hosted binary in this public repo), and tokens.css references its exact family name", () => {
    const layoutSource = readFileSync("src/app/layout.tsx", "utf-8");
    const slug = fontshareSlug(tokens.typography.headline);
    expect(layoutSource).toMatch(new RegExp(`api\\.fontshare\\.com/v2/css\\?f\\[\\]=${slug}@`));

    const tokensCss = readFileSync("../../packages/frontend/shared-ui/src/tokens.css", "utf-8");
    expect(tokensCss).toContain(`"${tokens.typography.headline}"`);
  });
});
