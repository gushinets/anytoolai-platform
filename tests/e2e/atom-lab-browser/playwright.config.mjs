import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  testMatch: "atom-lab.browser.spec.mjs",
  reporter: "list",
  use: {headless: true},
});
