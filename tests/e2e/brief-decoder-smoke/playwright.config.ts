import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "playwright-report.json" }]],
  // a failed run keeps its trace (DOM, console, network) and a screenshot in test-results/
  use: { trace: "retain-on-failure", screenshot: "only-on-failure" },
});
