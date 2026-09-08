import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { ESLint } from "eslint";
import { afterEach, describe, expect, it } from "vitest";
import { baseConfig } from "../../../../../eslint.config.base.mjs";

// Regression coverage for team-lead review round 3: the react-hooks block in
// eslint.config.base.mjs was once scoped to `**/*.tsx` only, so a rules-of-hooks violation in a
// plain `.ts` custom hook (legal -- hooks don't require JSX) passed lint silently. Fixed by
// scoping it to the same `tsFiles` set the type-checked rules use; this proves that fix stays in
// place, independent of ce-kit's own source -- a future accidental narrowing back to `.tsx`-only
// would fail this test even if nothing under ce-kit's own `src/` ever defines a `.ts` hook.
const WORKSPACE_DIR = resolve(import.meta.dirname, "..", "..");
const FIXTURE_PATH = resolve(WORKSPACE_DIR, "test/eslintConfig/__fixtures__/useConditionalEffect.ts");

const VIOLATING_HOOK_SOURCE = `import { useEffect, useState } from "react";

export function useConditionalEffect(id: string) {
  const [value, setValue] = useState(0);
  if (id) {
    useEffect(() => {
      setValue(1);
    }, []);
  }
  return value;
}
`;

afterEach(() => {
  rmSync(FIXTURE_PATH, { force: true });
});

describe("react-hooks rules apply to plain .ts files, not just .tsx", () => {
  it("flags a rules-of-hooks violation in a .ts custom hook", async () => {
    mkdirSync(dirname(FIXTURE_PATH), { recursive: true });
    writeFileSync(FIXTURE_PATH, VIOLATING_HOOK_SOURCE);

    const eslint = new ESLint({
      cwd: WORKSPACE_DIR,
      overrideConfigFile: true,
      overrideConfig: baseConfig({ tsconfigRootDir: WORKSPACE_DIR, react: true }),
    });
    const [result] = await eslint.lintFiles([FIXTURE_PATH]);

    expect(result?.messages.map((message) => message.ruleId)).toContain(
      "react-hooks/rules-of-hooks",
    );
  });
});
