import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { Client as PgClient } from "pg";

/**
 * ANY-248 browser-evidence smoke for the Brief Decoder web vertical, scoped like its siblings to
 * "prove the client<->backend seam once": product page -> shared client -> Platform API -> scenario
 * session -> job/worker -> A01+A04->A05 workflow -> canonical artifact -> product renderer ->
 * activation. Per-product meaning (mapping, validation, every renderer branch) is proven by
 * apps/web-mirror/test/BriefDecoderProduct.test.tsx and the backend pytest bundle tests.
 *
 * A real HTTP run never sets `fixture_key`, so the real stack only ever serves the happy fixtures.
 * The weak-input and zero-question tests therefore run a real start and substitute only the final
 * canonical-result body with the same checked-in fixtures the backend tests use (the
 * proposal-ai-smoke / client-update-writer-smoke precedent). The worker-to-artifact half of those
 * variants is proven by apps/platform-api/tests/test_brief_decoder_bundle.py.
 *
 * Requires (see brief_decoder_smoke() in scripts/agent/runner.py): dev-up running, web-mirror served
 * at WEB_MIRROR_BASE_URL, DATABASE_URL pointing at the dev-up Postgres.
 */
const WEB_MIRROR_BASE_URL = process.env.WEB_MIRROR_BASE_URL ?? "http://localhost:3300";
const PRODUCT_URL = `${WEB_MIRROR_BASE_URL}/products/brief_decoder`;
const FIXTURE_ROOT = join(import.meta.dirname, "../../../../tests/fixtures/provider/fake_provider_outputs");

const START_ROUTE_PATTERN = /\/scenarios\/brief_decoder\.decode_v1\/start$/;
const RESULT_ROUTE_PATTERN = /\/v1\/results\/([^/?]+)/;
const SESSION_ROUTE_PATTERN = /\/v1\/scenario-sessions\/[^/?]+$/;
const COPY_NEXT_ACTION_PATTERN = /\/scenario-sessions\/[^/]+\/next-actions\/copy_result$/;
const QUOTA_ROUTE_PATTERN = /\/v1\/products\/brief_decoder\/quota/;
const CLIENT_EVENTS_ROUTE_PATTERN = /\/v1\/client-events$/;
const PRODUCT_DIR = join(
  import.meta.dirname,
  "../../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/brief_decoder",
);
// The guest quota this test exhausts, read from the product's own config instead of a second copy.
const GUEST_QUOTA_LIMIT = Number(/limit_count:\s*(\d+)/.exec(readFileSync(join(PRODUCT_DIR, "quotas.yaml"), "utf8"))![1]);

const BRIEF = "Need a website for my bakery by the holidays, modern but traditional.";
const ACTION_CONFIG_IDS = [
  "brief_decoder.extract_brief_v1",
  "brief_decoder.detect_issues_v1",
  "brief_decoder.generate_questions_v1",
  "brief_decoder.generate_summary_v1",
];

type Suffix = "" | ".weak_input" | ".no_issues";
type Output = {
  brief: unknown;
  issues: unknown[];
  questions: unknown[];
  document: { sections: { title: string; content: string }[]; summary: string };
};

function fixture(action: string, suffix: Suffix): Record<string, unknown> {
  const path = join(FIXTURE_ROOT, `brief_decoder.${action}_v1${suffix}.json`);
  return (JSON.parse(readFileSync(path, "utf8")) as { response_json: Record<string, unknown> }).response_json;
}

/** Composed workflow output, exactly as apps/platform-api/tests/test_brief_decoder_bundle.py builds
 * it. A05 is skipped for `.no_issues`, so there is no question fixture and questions is empty. */
function composedOutput(suffix: Suffix): Output {
  return {
    brief: fixture("extract_brief", suffix),
    issues: (fixture("detect_issues", suffix) as { issues: unknown[] }).issues,
    questions:
      suffix === ".no_issues" ? [] : (fixture("generate_questions", suffix) as { questions: unknown[] }).questions,
    document: fixture("generate_summary", suffix) as Output["document"],
  };
}

/** renderer_contract.yaml `canonical_field_composition`. */
function composeCopyText({ sections, summary }: Output["document"]): string {
  return [...sections.map((section) => `${section.title}\n${section.content}`), summary].join("\n\n");
}

async function withDb<T>(fn: (db: PgClient) => Promise<T>): Promise<T> {
  const db = new PgClient({ connectionString: process.env.DATABASE_URL });
  await db.connect();
  try {
    return await fn(db);
  } finally {
    await db.end();
  }
}

async function countEvents(eventType: string, scenarioSessionId: string): Promise<number> {
  return withDb(async (db) => {
    const result = await db.query<{ count: number }>(
      "SELECT count(*)::int AS count FROM platform.event_log WHERE event_type = $1 AND scenario_session_id = $2",
      [eventType, scenarioSessionId],
    );
    return result.rows[0]!.count;
  });
}

/** Records the session id the start response returns and the artifact id the browser's result GET
 * used, so backend rows can be tied to this exact run. */
function trackRun(page: Page): { sessionId: () => string; resultArtifactId: () => string } {
  let sessionId = "";
  let resultArtifactId = "";
  page.on("response", (response) => {
    const url = response.url();
    if (response.request().method() === "POST" && START_ROUTE_PATTERN.test(url)) {
      void response
        .json()
        .then((body: { scenario_session_id: string }) => {
          sessionId = body.scenario_session_id;
        })
        .catch(() => undefined); // a failed start has no session; the assertions below then fail on the empty id
    }
    const resultMatch = response.request().method() === "GET" ? RESULT_ROUTE_PATTERN.exec(url) : null;
    if (resultMatch) {
      resultArtifactId = decodeURIComponent(resultMatch[1]!);
    }
  });
  return { sessionId: () => sessionId, resultArtifactId: () => resultArtifactId };
}

async function submitBrief(page: Page): Promise<void> {
  await page.locator("#brief-decoder-brief-text").fill(BRIEF);
  await page.getByRole("button", { name: "Decode brief" }).click();
}

/** Client-event types the browser POSTed, from the request bodies (deterministic: no waiting). */
function trackClientEvents(page: Page): string[] {
  const eventTypes: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST" && CLIENT_EVENTS_ROUTE_PATTERN.test(request.url())) {
      eventTypes.push((request.postDataJSON() as { event_type: string }).event_type);
    }
  });
  return eventTypes;
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

test.describe("Brief Decoder web product", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("happy path: four actions in order, artifact correlation, four-part render, one result_viewed, one copy activation", async ({
    page,
  }) => {
    const run = trackRun(page);
    const copyRequests: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && COPY_NEXT_ACTION_PATTERN.test(request.url())) {
        copyRequests.push(request.url());
      }
    });

    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("Brief Decoder");
    await submitBrief(page);
    const copyButton = page.getByRole("button", { name: "Copy" });
    await expect(copyButton).toBeVisible({ timeout: 60_000 });

    const expected = composedOutput("");
    await expect(page.getByRole("heading", { level: 2 })).toHaveText([
      "Brief",
      "Issues",
      `${expected.questions.length} clarifying questions`,
      "Summary document",
    ]);
    await expect(page.locator("ol > li")).toHaveCount(expected.questions.length);

    // Runtime correlation: the backend's own rows for this exact session.
    const sessionId = run.sessionId();
    expect(sessionId).toBeTruthy();
    await withDb(async (db) => {
      const job = await db.query<{ id: string; status: string; result_artifact_id: string }>(
        "SELECT id, status::text AS status, result_artifact_id FROM platform.jobs WHERE scenario_session_id = $1",
        [sessionId],
      );
      expect(job.rows).toHaveLength(1);
      expect(job.rows[0]!.status).toBe("succeeded");
      expect(job.rows[0]!.result_artifact_id).toBe(run.resultArtifactId());

      const actions = await db.query<{ id: string; action_config_id: string; status: string }>(
        "SELECT id, action_config_id, status::text AS status FROM platform.action_runs WHERE scenario_session_id = $1 AND job_id = $2 ORDER BY created_at, id",
        [sessionId, job.rows[0]!.id],
      );
      expect(actions.rows.map((row) => row.action_config_id)).toEqual(ACTION_CONFIG_IDS);
      expect(actions.rows.map((row) => row.status)).toEqual(ACTION_CONFIG_IDS.map(() => "succeeded"));

      const calls = await db.query<{ action_run_id: string; status: string }>(
        "SELECT action_run_id, status::text AS status FROM platform.provider_calls WHERE scenario_session_id = $1 AND job_id = $2 ORDER BY created_at, id",
        [sessionId, job.rows[0]!.id],
      );
      expect(calls.rows.map((row) => row.action_run_id)).toEqual(actions.rows.map((row) => row.id));
      expect(calls.rows.map((row) => row.status)).toEqual(ACTION_CONFIG_IDS.map(() => "succeeded"));
    });
    await expect.poll(() => countEvents("scenario.completed", sessionId), { timeout: 10_000 }).toBe(1);
    await expect.poll(() => countEvents("web.result_viewed", sessionId), { timeout: 10_000 }).toBe(1);

    await copyButton.click();
    await expect(page.getByRole("button", { name: "Copied" })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(composeCopyText(expected.document));
    await expect.poll(() => copyRequests.length, { timeout: 5_000 }).toBe(1);
    await expect.poll(() => countEvents("client.next_action_clicked", sessionId), { timeout: 5_000 }).toBe(1);
    // Copy is independent of activation: still exactly one result_viewed.
    expect(await countEvents("web.result_viewed", sessionId)).toBe(1);
  });

  test("validation: an empty brief shows the error and never starts a scenario", async ({ page }) => {
    let startRequested = false;
    page.on("request", (request) => {
      if (request.method() === "POST" && START_ROUTE_PATTERN.test(request.url())) {
        startRequested = true;
      }
    });
    await page.goto(PRODUCT_URL);
    await page.getByRole("button", { name: "Decode brief" }).click();
    await expect(page.getByText("Client brief: required.")).toBeVisible();
    expect(startRequested).toBe(false);
  });

  test("weak input: the vague-brief fixtures render a full result with four questions and one result_viewed", async ({
    page,
  }) => {
    const run = trackRun(page);
    await overrideResult(page, composedOutput(".weak_input"));
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { name: "4 clarifying questions" })).toBeVisible();
    await expect(page.locator("ol > li")).toHaveCount(4);
    await expect.poll(() => countEvents("web.result_viewed", run.sessionId()), { timeout: 10_000 }).toBe(1);
  });

  test("zero questions: both empty states, no readiness claim, no result_viewed, summary still copyable", async ({
    page,
  }) => {
    const run = trackRun(page);
    const clientEvents = trackClientEvents(page);
    const output = composedOutput(".no_issues");
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("No issues found.")).toBeVisible();
    await expect(page.getByText("No clarifying questions were generated.")).toBeVisible();
    await expect(page.locator("ol > li")).toHaveCount(0);

    // The backend records completion; the browser must not report a "viewed" activation.
    await expect.poll(() => countEvents("scenario.completed", run.sessionId()), { timeout: 10_000 }).toBe(1);

    await page.getByRole("button", { name: "Copy" }).click();
    await expect(page.getByRole("button", { name: "Copied" })).toBeVisible();
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(composeCopyText(output.document));
    // Fence, not a sleep: the copy activation is recorded after the result rendered, so a
    // web.result_viewed POST (sent at render) would already have been issued by now.
    await expect.poll(() => countEvents("client.next_action_clicked", run.sessionId()), { timeout: 5_000 }).toBe(1);
    expect(clientEvents).toContain("web.form_submitted");
    expect(clientEvents).not.toContain("web.result_viewed");
    expect(await countEvents("web.result_viewed", run.sessionId())).toBe(0);
  });

  test("mobile: a long unbroken token in the result does not widen the page", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    const output = composedOutput("");
    const longUrl = `https://example.com/${"a".repeat(200)}`;
    output.issues = [{ category: "ambiguity", severity: "low", description: "Long link", evidence: longUrl }];
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByText(`Evidence: ${longUrl}`)).toBeVisible({ timeout: 60_000 });
    const { scrollWidth, clientWidth } = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
  });

  test("terminal error: a failed session shows the run-failed text, keeps the brief, offers no copy", async ({
    page,
  }) => {
    await page.route(SESSION_ROUTE_PATTERN, async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      const body = (await response.json()) as Record<string, unknown>;
      await route.fulfill({ response, json: { ...body, status: "failed", result_artifact_id: null } });
    });
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByText("Something went wrong decoding your brief. Please try again.")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator("#brief-decoder-brief-text")).toHaveValue(BRIEF);
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveCount(0);
  });

  test("quota: the guest's fourth run is rejected with the quota message", async ({ page }) => {
    // The advisory quota GET would disable the form after the third run; abort it so the fourth
    // start reaches the authoritative 429 from the real backend.
    await page.route(QUOTA_ROUTE_PATTERN, (route) => route.abort());
    await page.goto(PRODUCT_URL);
    for (let run = 1; run <= GUEST_QUOTA_LIMIT; run += 1) {
      await submitBrief(page);
      await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
      await page.getByRole("button", { name: "Decode another brief" }).click();
    }
    await submitBrief(page);
    await expect(page.getByText(/used all your/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
  });
});
