import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // Next.js keeps tsconfig.json's `jsx` at "preserve" (its own compiler does that transform),
  // which breaks Vite's default JSX handling in tests -- this plugin transforms JSX itself,
  // independent of tsconfig.
  plugins: [react()],
  test: {
    environment: "jsdom",
    include: ["test/**/*.test.tsx"],
  },
});
