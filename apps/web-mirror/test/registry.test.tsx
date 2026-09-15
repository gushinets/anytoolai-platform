import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { getRegisteredProduct } from "../src/products/registry";
import { TEST_PRODUCT_IDS } from "./fixtures/testProductDefinition";

describe("getRegisteredProduct", () => {
  it("returns the enabled ProposalAI product", () => {
    expect(getRegisteredProduct("proposal_ai")?.productId).toBe("proposal_ai");
  });

  it("returns null for an unknown product id", () => {
    expect(getRegisteredProduct("does_not_exist")).toBeNull();
  });

  it("never registers the test-only product definition as a production product", () => {
    expect(getRegisteredProduct(TEST_PRODUCT_IDS.productId)).toBeNull();
  });
});

describe("shared runtime boundary", () => {
  // ANY-453: "Common runtime imports no product-specific module or business semantics." The
  // composition layer (registry.ts) is the only place allowed to import products.
  it("ProductRunPage imports no product module", () => {
    // fileURLToPath, not `new URL(..., import.meta.url)`: under the jsdom test environment that
    // global is jsdom's URL class, which Node's fs rejects as "must be of scheme file".
    const here = dirname(fileURLToPath(import.meta.url));
    const source = readFileSync(resolve(here, "../src/products/runtime/ProductRunPage.tsx"), "utf8");
    // `[\s\S]*?` (not `.` with `^$`/`m`), so a genuinely multi-line `import {\n  ...\n} from "...";`
    // (e.g. this file's own ce-kit import) is still captured -- a single-line-anchored regex here
    // previously skipped it silently, so this boundary check never actually inspected that import.
    const imports = source.match(/import[\s\S]*?from "(.*)";/g) ?? [];
    // Self-check that the regex above missed no import statement at all (multi-line or not): every
    // line starting with `import` must belong to exactly one matched import statement. (Not a raw
    // count of `from "` substrings -- a comment can coincidentally contain that text, e.g. this
    // file's own prose quoting a string literal, without being an import.)
    const importStatementCount = (source.match(/^import\b/gm) ?? []).length;
    expect(imports.length).toBe(importStatementCount);
    expect(imports.length).toBeGreaterThan(0);
    for (const line of imports) {
      // From src/products/runtime/, exactly one level up (`../x/...`, not `../../x/...`) is a
      // sibling product directory -- the only way a product module could be reached from here.
      expect(line).not.toMatch(/from "\.\.\/(?!\.\.\/)/);
    }
  });
});
