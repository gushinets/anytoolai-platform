import { baseConfig } from "../../eslint.config.base.mjs";

export default baseConfig({
  tsconfigRootDir: import.meta.dirname,
  react: true,
  // Next.js (re)generates this at the project root on every `next dev`/`next build`; it's
  // gitignored for the same reason.
  ignores: ["next-env.d.ts"],
});
