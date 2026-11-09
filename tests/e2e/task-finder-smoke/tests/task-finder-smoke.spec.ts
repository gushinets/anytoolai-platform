import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { withDb, countEvents } from "@anytoolai/smoke-support";

// The happy path uses the real worker and deterministic provider. Weak input substitutes only
// the canonical response; backend bundle tests independently prove that fixture through A11+A02.
const WEB_MIRROR_BASE_URL = process.env.WEB_MIRROR_BASE_URL ?? "http://localhost:3500";
const PRODUCT_URL = `${WEB_MIRROR_BASE_URL}/products/task_finder`;
const FIXTURE_ROOT = join(import.meta.dirname, "../../../../tests/fixtures/provider/fake_provider_outputs");
const PRODUCTS_ROOT = join(import.meta.dirname, "../../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products");
const GUEST_QUOTA_LIMIT = Number(/limit_count:\s*(\d+)/.exec(readFileSync(join(PRODUCTS_ROOT, "task_finder/quotas.yaml"), "utf8"))![1]);
const ANY_START = /\/scenarios\/[^/]+\/start$/;
const RESULT_ROUTE = /\/v1\/results\/([^/?]+)/;
const SESSION_ROUTE = /\/v1\/scenario-sessions\/([^/?]+)$/;
const COPY_NEXT_ACTION = /\/scenario-sessions\/[^/]+\/next-actions\/copy_result$/;
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

/** Records the session id the start response returns and the artifact id the browser's result GET
 * used, so backend rows can be tied to this exact run. */
function trackRun(page: Page): { sessionId: () => string; resultArtifactId: () => string } {
  let sessionId = "";
  let resultArtifactId = "";
  page.on("response", (response) => {
    const url = response.url();
    if (response.request().method() === "POST" && ANY_START.test(url)) {
      void response
        .json()
        .then((body: { scenario_session_id: string }) => {
          sessionId = body.scenario_session_id;
        })
        .catch(() => undefined); // a failed start has no session; the assertions below then fail on the empty id
    }
    const resultMatch = response.request().method() === "GET" ? RESULT_ROUTE.exec(url) : null;
    if (resultMatch) {
      resultArtifactId = decodeURIComponent(resultMatch[1]!);
    }
  });
  return { sessionId: () => sessionId, resultArtifactId: () => resultArtifactId };
}

/** Wide screens: result card right of the inputs card; narrow: stacked. Nothing overflows sideways. */
async function expectWorkspaceLayout(page: Page, layout: "side-by-side" | "stacked"): Promise<void> {
  const inputs = await page.locator("#product-inputs").boundingBox();
  const result = await page.locator('section[aria-labelledby="product-result-heading"]').boundingBox();
  expect(inputs).not.toBeNull();
  expect(result).not.toBeNull();
  if (layout === "side-by-side") {
    expect(result!.x).toBeGreaterThanOrEqual(inputs!.x + inputs!.width - 1);
    expect(Math.abs(result!.y - inputs!.y)).toBeLessThanOrEqual(2);
    expect(Math.abs(result!.width - inputs!.width)).toBeLessThanOrEqual(2);
  } else {
    expect(result!.y).toBeGreaterThanOrEqual(inputs!.y + inputs!.height - 1);
    expect(Math.abs(result!.x - inputs!.x)).toBeLessThanOrEqual(2);
  }
  await expectNoHorizontalScroll(page);
}

async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}

async function submitFit(page: Page): Promise<void> {
  await page.locator("#task-finder-task-text").fill(TASK);
  await page.locator("#task-finder-positioning").fill(PROFILE);
  await page.getByRole("button", { name: "Check fit" }).click();
}

/** Real run; only the canonical result body is replaced with `output` (see file header). */
async function overrideResult(page: Page, output: Output): Promise<void> {
  await page.route("**/v1/results/**", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as { output: unknown };
    body.output = output;
    await route.fulfill({ response, json: body });
  });
}

/** The backend's own rows for one session: job, ordered action runs, provider calls. */
async function expectCorrelatedRun(sessionId: string, resultArtifactId: string, actionIds: string[]): Promise<void> {
  expect(sessionId).toBeTruthy();
  await withDb(async (db) => {
    const job = await db.query<{ id: string; status: string; result_artifact_id: string }>(
      "SELECT id, status::text AS status, result_artifact_id FROM platform.jobs WHERE scenario_session_id = $1",
      [sessionId],
    );
    expect(job.rows).toHaveLength(1);
    expect(job.rows[0]!.status).toBe("succeeded");
    expect(job.rows[0]!.result_artifact_id).toBe(resultArtifactId);

    const actions = await db.query<{ id: string; action_config_id: string; status: string }>(
      "SELECT id, action_config_id, status::text AS status FROM platform.action_runs WHERE scenario_session_id = $1 AND job_id = $2 ORDER BY created_at, id",
      [sessionId, job.rows[0]!.id],
    );
    expect(actions.rows.map((row) => row.action_config_id)).toEqual(actionIds);
    expect(actions.rows.map((row) => row.status)).toEqual(actionIds.map(() => "succeeded"));

    const calls = await db.query<{ action_run_id: string; status: string }>(
      "SELECT action_run_id, status::text AS status FROM platform.provider_calls WHERE scenario_session_id = $1 AND job_id = $2 ORDER BY created_at, id",
      [sessionId, job.rows[0]!.id],
    );
    expect(calls.rows.map((row) => row.action_run_id)).toEqual(actions.rows.map((row) => row.id));
    expect(calls.rows.map((row) => row.status)).toEqual(actionIds.map(() => "succeeded"));
  });
}

async function expectCopyActivation(page: Page, sessionId: string, expectedText: string): Promise<void> {
  const copyRequests: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && COPY_NEXT_ACTION.test(request.url())) {
      copyRequests.push(request.url());
    }
  });
  await page.getByRole("button", { name: "Copy" }).click();
  await expect(page.getByRole("button", { name: "Copied" })).toBeVisible();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(expectedText);
  await expect.poll(() => copyRequests.length, { timeout: 5_000 }).toBe(1);
  await expect.poll(() => countEvents("client.next_action_clicked", sessionId), { timeout: 5_000 }).toBe(1);
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

    await page.setViewportSize({ width: 390, height: 844 });
    await expectWorkspaceLayout(page, "stacked");

    await page.getByRole("button", { name: "New task" }).click();
    await expect(page.locator("#task-finder-task-text")).toHaveValue("");
    await expect(page.locator("#task-finder-task-text")).toBeFocused();
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
  });

  test("validation: empty fields never start a scenario", async ({ page }) => {
    const starts: string[] = [];
    page.on("request", (request) => { if (request.method() === "POST" && ANY_START.test(request.url())) starts.push(request.url()); });
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
    await page.route(SESSION_ROUTE, async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      const body = (await response.json()) as Record<string, unknown>;
      await route.fulfill({ response, json: { ...body, status: "failed", result_artifact_id: null } });
    });
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
