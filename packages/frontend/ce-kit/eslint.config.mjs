import { baseConfig } from "../../../eslint.config.base.mjs";

export default [
  ...baseConfig({
    tsconfigRootDir: import.meta.dirname,
    react: true,
    ignores: ["src/api/generated/**"],
  }),
  {
    // `async` here isn't test-mock boilerplate (the base config's test-file exemption doesn't
    // apply -- these are production adapters): `AsyncStorage`'s Promise-returning contract means
    // every implementation's failures should surface as rejections, not synchronous throws.
    // `localStorageAdapter`'s backing calls (`localStorage.setItem`/`removeItem`) genuinely can
    // throw synchronously (QuotaExceededError, SecurityError in a privacy-hardened/private-mode
    // browser) -- `async` is what turns that into a rejected Promise instead of a bypassed one, so
    // removing it (as `require-await` suggests) would be a real behavior change, not a style fix.
    // `inMemoryAsyncStorage`'s Map-backed calls can't throw today, but it's kept `async` too so
    // every `AsyncStorage` implementation honors the same contract uniformly rather than only the
    // one adapter that currently needs it.
    files: ["src/storage/inMemoryAsyncStorage.ts", "src/storage/localStorageAdapter.ts"],
    rules: { "@typescript-eslint/require-await": "off" },
  },
];
