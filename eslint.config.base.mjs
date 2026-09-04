import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

const generatedIgnores = [
  "**/.next/**",
  "**/.wxt/**",
  "**/.output/**",
  "**/dist/**",
  "**/build/**",
  "**/*.tsbuildinfo",
];

const tsFiles = ["**/*.ts", "**/*.mts", "**/*.cts", "**/*.tsx"];
// Build/config scripts (eslint.config.mjs itself, generate-api-types.mjs, ...) run under Node
// and aren't part of any tsconfig "include", so they only get plain (non-type-checked) js rules.
const nodeScriptFiles = ["**/*.js", "**/*.mjs", "**/*.cjs"];

export function baseConfig({ tsconfigRootDir, react = false, ignores = [] } = {}) {
  return tseslint.config(
    { ignores: [...generatedIgnores, ...ignores] },
    js.configs.recommended,
    {
      files: nodeScriptFiles,
      languageOptions: { globals: globals.node },
    },
    {
      files: tsFiles,
      extends: [...tseslint.configs.recommendedTypeChecked],
      languageOptions: {
        parserOptions: { projectService: true, tsconfigRootDir },
      },
      rules: {
        // TypeScript already flags any identifier that doesn't resolve, and eslint's core
        // `no-undef` doesn't understand ambient lib/DOM/webextension globals -- typescript-eslint's
        // own docs recommend disabling it for TS files rather than hand-listing every global.
        "no-undef": "off",
        // This codebase's convention for an intentionally-unused binding is a leading underscore.
        "@typescript-eslint/no-unused-vars": [
          "error",
          { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
        ],
      },
    },
    {
      // Test-only relaxations: `expect(mock.method)` (mock objects made of `vi.fn()`s, never real
      // bound methods) is the standard vitest/jest assertion shape and trips `unbound-method` on
      // every occurrence -- a known false positive for spy-style mocks, which never read `this`.
      // `require-await`/`no-unnecessary-type-assertion` catch no unsafe/untyped value or real
      // defect, just technically-redundant syntax (an `async` with no `await`, an `as T` inference
      // already produced) that test doubles here use deliberately for interface conformance and
      // reader clarity -- kept on for production code (src/), where the same syntax is a much
      // rarer, more likely-accidental pattern. Covers spec files by suffix and test-helper files
      // that live under a test(s)/ directory without one (fakePlatformServer.ts, mock fetch
      // clients, ...), which are just as mock-heavy as the specs that use them.
      files: ["**/*.test.ts", "**/*.test.tsx", "**/test/**", "**/tests/**"],
      rules: {
        "@typescript-eslint/unbound-method": "off",
        "@typescript-eslint/require-await": "off",
        "@typescript-eslint/no-unnecessary-type-assertion": "off",
      },
    },
    ...(react
      ? [
          {
            files: ["**/*.tsx"],
            plugins: reactHooks.configs.flat.recommended.plugins,
            rules: reactHooks.configs.flat.recommended.rules,
          },
        ]
      : []),
  );
}
