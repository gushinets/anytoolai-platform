import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import {
  trackScenarioStarts,
  expectMobileTaskReset,
  countEvents,
  trackRun,
  expectWorkspaceLayout,
  expectNoHorizontalScroll,
  overrideResult,
  expectCorrelatedRun,
  expectCopyActivation,
  overrideFailedSession,
} from "@anytoolai/smoke-support";

// The happy path uses the real worker and deterministic provider. Weak input substitutes only
// the canonical response; backend bundle tests independently prove that fixture through A11+A02.
const WEB_MIRROR_BASE_URL = process.env.WEB_MIRROR_BASE_URL ?? "http://localhost:3500";
const PRODUCT_URL = `${WEB_MIRROR_BASE_URL}/products/task_finder`;
const FIXTURE_ROOT = join(import.meta.dirname, "../../../../tests/fixtures/provider/fake_provider_outputs");
const PRODUCTS_ROOT = join(import.meta.dirname, "../../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products");
const GUEST_QUOTA_LIMIT = Number(/limit_count:\s*(\d+)/.exec(readFileSync(join(PRODUCTS_ROOT, "task_finder/quotas.yaml"), "utf8"))![1]);
const ANY_START = /\/scenarios\/[^/]+\/start$/;
const QUOTA_ROUTE = /\/v1\/products\/task_finder\/quota/;
const TASK = "Build a React dashboard and a mobile app in six weeks.";
const PROFILE = "React and TypeScript developer with five years of dashboard experience; web projects only.";
const ACTIONS = ["task_finder.compare_v1", "task_finder.score_v1"];
type Output = {
  task_text: string; freelancer_positioning: string;
  comparison: { verdict: string; deltas: { criterion_id: string; status: string; evidence: string }[]; rationale: string };
  match: { score: number; criterion_scores: { criterion_id: string; score: number; rationale: string }[]; strengths: string[]; gaps: string[]; overall_rationale: string };
};
function fixture<T>(action: string, suffix: string): T {
  return (JSON.parse(readFileSync(join(FIXTURE_ROOT, `task_finder.${action}_v1${suffix}.json`), "utf8")) as { response_json: T }).response_json;
}
function composedOutput(suffix = ""): Output {
  return { task_text: TASK, freelancer_positioning: PROFILE, comparison: fixture("compare", suffix), match: fixture("score", suffix) };
}
function composeCopyText(output: Output): string {
  const labels = ["Skills fit", "Experience fit", "Scope fit", "Constraints fit"];
  return [
    `Fit\nFit score: ${output.match.score}/100. ${output.match.overall_rationale}\nVerdict: ${output.comparison.verdict.replace("_", " ")}. ${output.comparison.rationale}`,
    `Criteria\n${output.comparison.deltas.map((d, i) => `${labels[i]}: ${d.status}. ${d.evidence}`).join("\n")}`,
    `Criterion scores\n${output.match.criterion_scores.map((s, i) => `${labels[i]}: ${s.score}/100. ${s.rationale}`).join("\n")}`,
    `Strengths\n${output.match.strengths.length ? output.match.strengths.map((s) => `- ${s}`).join("\n") : "Not specified."}`,
    `Gaps\n${output.match.gaps.length ? output.match.gaps.map((s) => `- ${s}`).join("\n") : "Not specified."}`,
  ].join("\n\n");
}

async function submitFit(page: Page): Promise<void> {
  await page.locator("#task-finder-task-text").fill(TASK);
  await page.locator("#task-finder-positioning").fill(PROFILE);
  await expect(page.locator("#task-finder-task-text")).toHaveValue(TASK);
  await expect(page.locator("#task-finder-positioning")).toHaveValue(PROFILE);
  await page.getByRole("button", { name: "Check fit" }).click();
}

test.describe("Task Finder web product", () => {
  test.beforeEach(async ({ context }) => { await context.grantPermissions(["clipboard-read", "clipboard-write"]); });

  test("happy path: config, canonical artifact, ordered actions, rendering and exactly-once activation", async ({ page }) => {
    const run = trackRun(page);
    const config = await page.request.get(`${WEB_MIRROR_BASE_URL}/v1/products/task_finder/runtime-config`);
    expect(config.ok()).toBe(true);
    expect(await config.json()).toMatchObject({ product_id: "task_finder", scenario_ids: ["task_finder.fit_v1"] });
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("Task Finder");
    await submitFit(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { level: 2 })).toHaveText(["Your details", "Task fit"]);
    await expect(page.getByText("64 / 100", { exact: true })).toBeVisible();
    await expect(page.getByText("Weak fit", { exact: true })).toBeVisible();
    const canonical = await page.request.get(`${WEB_MIRROR_BASE_URL}/v1/results/${run.resultArtifactId()}`);
    expect(await canonical.json()).toMatchObject({ scenario_session_id: run.sessionId(), schema_ref: "task_finder.fit_output_v1", output: composedOutput() });
    await expectCorrelatedRun(run.sessionId(), run.resultArtifactId(), ACTIONS);
    await expect.poll(() => countEvents("scenario.completed", run.sessionId())).toBe(1);
    await expect.poll(() => countEvents("web.result_viewed", run.sessionId())).toBe(1);
    await expectCopyActivation(page, run.sessionId(), composeCopyText(composedOutput()));
    expect(await countEvents("web.result_viewed", run.sessionId())).toBe(1);
  });
  test("workspace: inputs and result side by side on wide screens, stacked on narrow, edited details and new task reset", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(PRODUCT_URL);
    await submitFit(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: "New task" })).toBeVisible();
    await expectWorkspaceLayout(page, "side-by-side");

    await page.locator("#task-finder-task-text").fill(`${TASK} Also a PDF preview.`);
    await expect(page.getByText("Created from previous details")).toBeVisible();

    await expectMobileTaskReset(page, "#task-finder-task-text");
  });

  test("validation: empty fields never start a scenario", async ({ page }) => {
    const starts = trackScenarioStarts(page, ANY_START);
    await page.goto(PRODUCT_URL);
    await page.getByRole("button", { name: "Check fit" }).click();
    await expect(page.getByText("Task description: required.")).toBeVisible();
    await expect(page.getByText("Your profile: required.")).toBeVisible();
    expect(starts).toEqual([]);
  });

  test("mobile: a long unbroken token in the result does not widen the page", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    const output = composedOutput();
    const longUrl = `https://example.com/${"a".repeat(200)}`;
    output.match.strengths = [longUrl];
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitFit(page);
    await expect(page.getByText(longUrl).first()).toBeVisible({ timeout: 60_000 });
    await expectNoHorizontalScroll(page);
  });

  test("terminal error: a failed session shows the run-failed text, keeps the brief, offers no copy", async ({ page }) => {
    await overrideFailedSession(page);
    await page.goto(PRODUCT_URL);
    await submitFit(page);
    await expect(page.getByText("Something went wrong checking your fit. Please try again.")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator("#task-finder-task-text")).toHaveValue(TASK);
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveCount(0);
  });

  test("quota: the guest's run beyond the product limit is rejected with the quota message", async ({ page }) => {
    // Three full start -> worker -> result cycles plus a fourth start: the config's 60s per-test cap is
    // too tight for a cold CI worker (the ProposalAI quota smoke does the same).
    test.setTimeout(240_000);
    // The advisory quota GET would disable the form after the last allowed run; abort it so the next
    // start reaches the authoritative 429 from the real backend.
    await page.route(QUOTA_ROUTE, (route) => route.abort());
    await page.goto(PRODUCT_URL);
    for (let run = 1; run <= GUEST_QUOTA_LIMIT; run += 1) {
      await submitFit(page);
      await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
      await page.getByRole("button", { name: "New task" }).click();
      await expect(page.locator("#task-finder-task-text")).toHaveValue("");
      await expect(page.locator("#task-finder-task-text")).toBeFocused();
    }
    await submitFit(page);
    await expect(page.getByText(/used all your/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
  });

  test("weak input: partial fit and unspecified strengths remain safe and copyable", async ({ page }) => {
    const run = trackRun(page); const output = composedOutput(".weak_input");
    await overrideResult(page, output); await page.goto(PRODUCT_URL); await submitFit(page);
    await expect(page.getByText("31 / 100", { exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("Partial fit", { exact: true })).toBeVisible();
    await expect(page.getByText("Not specified.", { exact: true })).toBeVisible();
    await expect.poll(() => countEvents("web.result_viewed", run.sessionId())).toBe(1);
    await expectCopyActivation(page, run.sessionId(), composeCopyText(output));
  });
});
