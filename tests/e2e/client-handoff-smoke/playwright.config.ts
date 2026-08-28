import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "playwright-report.json" }]],
});
