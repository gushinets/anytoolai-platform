import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "playwright-report.json" }]],
  // a failed run keeps a screenshot and its page snapshot (error-context.md) in test-results/; no
  // trace: recording one slows the page enough to hide the timing races these smokes must catch
  use: { screenshot: "only-on-failure" },
});
