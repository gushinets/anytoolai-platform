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

  it("layout.tsx actually renders a <link> to Fontshare's headline font (its license forbids a self-hosted binary in this public repo), at the same weight tokens.css's heading rule uses", () => {
    const layoutSource = readFileSync("src/app/layout.tsx", "utf-8");
    const slug = fontshareSlug(tokens.typography.headline);

    // Captures the identifier, the full URL, and the requested weight together -- a URL edited to
    // a different weight without touching tokens.css (or vice versa) is exactly what this test
    // must catch, so both values come from the same regex match, not two independent lookups.
    const urlMatch = layoutSource.match(
      new RegExp(`const (\\w+)\\s*=\\s*"(https://api\\.fontshare\\.com/v2/css\\?f\\[\\]=${slug}@(\\d+)[^"]*)"`),
    );
    if (!urlMatch) {
      throw new Error(`layout.tsx has no Fontshare CSS URL constant for slug "${slug}"`);
    }
    const [, identifier, , requestedWeight] = urlMatch as [string, string, string, string];

    // A `<link>` tag that never actually references the URL constant (e.g. left over after the
    // <link> itself was deleted, or pointed at a different constant) must fail this, not just the
    // constant's own existence.
    const linkPattern = new RegExp(`<link(?=[^>]*\\brel="stylesheet")(?=[^>]*\\bhref=\\{${identifier}\\})[^>]*/?>`);
    expect(layoutSource).toMatch(linkPattern);

    const tokensCss = readFileSync("../../packages/frontend/shared-ui/src/tokens.css", "utf-8");
    const headingBlock = tokensCss.match(/\bh1\b[\s\S]*?\{([\s\S]*?)\}/)?.[1];
    if (headingBlock === undefined) {
      throw new Error("tokens.css has no h1 rule block");
    }
    expect(headingBlock).toContain(`"${tokens.typography.headline}"`);
    // Bundle 3's roles pair a specific weight with a specific size (e.g. Display: 900/44-56px,
    // Section: 800/26-36px) -- the requested weight and the CSS weight must be the literal same
    // number, not just both present, or a delivery-driven weight change (like the one that
    // motivated 900 here) can silently mismatch the role its own size still implies.
    expect(headingBlock).toMatch(new RegExp(`font-weight:\\s*${requestedWeight}\\b`));
  });
});
