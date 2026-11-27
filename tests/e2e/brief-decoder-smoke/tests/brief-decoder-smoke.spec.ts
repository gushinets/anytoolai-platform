import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import {
  trackScenarioStarts,
  expectMobileTaskReset,
  countEvents,
  trackRun,
  expectWorkspaceLayout,
  overrideResult,
  expectCorrelatedRun,
  expectNoHorizontalScroll,
  overrideFailedSession,
} from "@anytoolai/smoke-support";

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

type Suffix = "" | ".weak_input" | ".no_issues" | ".missing_task";
type Output = {
  brief: { values: Partial<Record<BriefField, string | string[]>>; missing_fields: BriefField[] };
  issues: { category: keyof typeof CATEGORY_LABELS; severity: keyof typeof SEVERITY_LABELS; description: string; evidence?: string }[];
  questions: { question: string }[];
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
    brief: fixture("extract_brief", suffix) as Output["brief"],
    issues: (fixture("detect_issues", suffix) as { issues: Output["issues"] }).issues,
    questions:
      suffix === ".no_issues" ? [] : (fixture("generate_questions", suffix) as { questions: Output["questions"] }).questions,
    document: fixture("generate_summary", suffix) as Output["document"],
  };
}

const FIELD_LABELS = {
  project_goal: "Project goal", deliverables: "Deliverables", deadline: "Deadline",
  budget: "Budget", target_audience: "Target audience", constraints: "Constraints",
} as const;
type BriefField = keyof typeof FIELD_LABELS;
const CATEGORY_LABELS = {
  missing_information: "Missing information", ambiguity: "Ambiguity", scope_risk: "Scope risk",
  timeline_risk: "Timeline risk", budget_risk: "Budget risk", contradiction: "Contradiction",
} as const;
const SEVERITY_LABELS = { low: "Low severity", medium: "Medium severity", high: "High severity" } as const;

/** Mirrors parseBriefDecoder.ts#composeCopyText for the en locale. */
function composeCopyText({ brief, issues, questions }: Output): string {
  const fields = Object.keys(FIELD_LABELS) as BriefField[];
  const briefLines = ["Brief"];
  for (const field of fields) {
    const value = brief.values[field];
    if (value === undefined) continue;
    briefLines.push(...(Array.isArray(value)
      ? [`${FIELD_LABELS[field]}:`, ...value.map((item) => `- ${item}`)]
      : [`${FIELD_LABELS[field]}: ${value}`]));
  }
  const blocks = [briefLines.join("\n")];
  if (brief.missing_fields.length > 0) {
    blocks.push(["Not stated in the brief", ...fields.filter((field) => brief.missing_fields.includes(field)).map((field) => `- ${FIELD_LABELS[field]}`)].join("\n"));
  }
  blocks.push(["Issues", ...(issues.length === 0 ? ["No issues found."] : issues.flatMap((issue) => [
    `- ${CATEGORY_LABELS[issue.category]} · ${SEVERITY_LABELS[issue.severity]}: ${issue.description}`,
    ...(issue.evidence ? [`  Evidence: ${issue.evidence}`] : []),
  ]))].join("\n"));
  blocks.push([
    `${questions.length} clarifying question${questions.length === 1 ? "" : "s"}`,
    ...(questions.length === 0 ? ["No clarifying questions were generated."] : questions.map((question, index) => `${index + 1}. ${question.question}`)),
  ].join("\n"));
  return blocks.join("\n\n");
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

test.describe("Brief Decoder web product", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("happy path: four actions in order, artifact correlation, four-part render, one result_viewed, one copy activation", async ({
    page,
  }) => {
    const run = trackRun(page, START_ROUTE_PATTERN);
    const copyRequests: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && COPY_NEXT_ACTION_PATTERN.test(request.url())) {
        copyRequests.push(request.url());
      }
    });

    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("Brief Decoder");
    await submitBrief(page);
    const copyButton = page.getByRole("button", { name: "Copy", exact: true });
    await expect(copyButton).toBeVisible({ timeout: 60_000 });

    const expected = composedOutput("");
    await expect(page.getByRole("heading", { level: 2 })).toHaveText(["Your details", "Decoded brief"]);
    await expect(page.getByRole("heading", { level: 3 })).toHaveText([
      "Brief",
      "Issues",
      `${expected.questions.length} clarifying questions`,
      "Summary document",
    ]);
    await expect(page.locator("ol > li")).toHaveCount(expected.questions.length);

    // Runtime correlation: the backend's own rows for this exact session.
    const sessionId = run.sessionId();
    expect(sessionId).toBeTruthy();
    await expectCorrelatedRun(sessionId, run.resultArtifactId(), ACTION_CONFIG_IDS);
    await expect.poll(() => countEvents("scenario.completed", sessionId), { timeout: 10_000 }).toBe(1);
    await expect.poll(() => countEvents("web.result_viewed", sessionId), { timeout: 10_000 }).toBe(1);

    await copyButton.click();
    await expect(page.getByRole("button", { name: "Copied", exact: true })).toBeVisible();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toBe(composeCopyText(expected));
    expect(copied).not.toContain(expected.document.summary);
    for (const question of expected.questions) expect(copied).toContain(question.question);
    expect(copied.match(/^\d+\. /gm)).toHaveLength(expected.questions.length);
    await expect.poll(() => copyRequests.length, { timeout: 5_000 }).toBe(1);
    await expect.poll(() => countEvents("client.next_action_clicked", sessionId), { timeout: 5_000 }).toBe(1);
    // Copy is independent of activation: still exactly one result_viewed.
    expect(await countEvents("web.result_viewed", sessionId)).toBe(1);
  });

  test("workspace: brief and result side by side on wide screens, stacked on narrow, repeat and new task reset", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByRole("button", { name: "Copy", exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: "New task" })).toBeVisible();
    await expect(page.locator("#brief-decoder-brief-text")).toHaveValue(BRIEF);
    await expectWorkspaceLayout(page, "side-by-side");

    // Edited brief: the earlier result stays, marked as made from earlier details, then repeats.
    await page.locator("#brief-decoder-brief-text").fill(`${BRIEF} Also a logo.`);
    await expect(page.getByText("Created from previous details")).toBeVisible();
    await page.getByRole("button", { name: "Decode brief again" }).click();
    // The progress line sits next to the "previous details" notice, both announced as status.
    await expect(page.getByRole("status").filter({ hasText: "Decoding your brief" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy", exact: true })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0, { timeout: 60_000 });
    await expect(page.getByRole("button", { name: "New task" })).toBeVisible();

    await expectMobileTaskReset(page, "#brief-decoder-brief-text");
  });

  test("validation: an empty brief shows the error and never starts a scenario", async ({ page }) => {
    const starts = trackScenarioStarts(page, START_ROUTE_PATTERN);
    await page.goto(PRODUCT_URL);
    await page.getByRole("button", { name: "Decode brief" }).click();
    await expect(page.getByText("Client brief: required.")).toBeVisible();
    expect(starts).toEqual([]);
  });

  test("missing task: shows field feedback and accepts a corrected brief", async ({ page }) => {
    const starts = trackScenarioStarts(page, START_ROUTE_PATTERN);
    const clientEvents = trackClientEvents(page);
    const junk = "asdf ::: 12345 !!!";
    await page.route("**/v1/results/**", async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as Record<string, unknown>;
      await route.fulfill({
        response,
        json: { ...body, output: { ...composedOutput(".missing_task"), brief_text: junk } },
      });
    }, { times: 1 });
    await page.goto(PRODUCT_URL);
    const field = page.getByRole("textbox", { name: "Client brief" });
    const submit = page.getByRole("button", { name: "Decode brief", exact: true });
    const copy = page.getByRole("button", { name: "Copy", exact: true });
    const handoff = page.getByRole("button", { name: "Create acceptance criteria" });
    await field.fill(junk);
    await submit.click();
    const hint = page.locator("#brief-decoder-brief-text-error");
    await expect(hint).toContainText("Describe what the client wants you to do or deliver.", { timeout: 60_000 });
    await expect(field).toHaveAttribute("aria-invalid", "true");
    await expect(field).toBeFocused();
    await expect(field).toHaveValue(junk);
    await expect(copy).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Copy questions", exact: true })).toHaveCount(0);
    await expect(handoff).toHaveCount(0);
    expect(clientEvents).not.toContain("web.result_viewed");

    await field.fill(` ${junk}\n`);
    await submit.click();
    await expect(hint).toBeVisible();
    expect(starts).toHaveLength(1);

    await field.fill("Write a borscht recipe.");
    await expect(hint).toHaveCount(0);
    await submit.click();
    await expect(copy).toBeVisible({ timeout: 60_000 });
    await expect(handoff).toBeVisible();
    expect(starts).toHaveLength(2);
  });

  test("weak input: four questions copied as plain text with one copy activation and one result_viewed", async ({
    page,
  }) => {
    const run = trackRun(page, START_ROUTE_PATTERN);
    const output = composedOutput(".weak_input");
    const copyRequests: { url: string; body: unknown }[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && COPY_NEXT_ACTION_PATTERN.test(request.url())) {
        copyRequests.push({ url: request.url(), body: request.postDataJSON() });
      }
    });
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByRole("button", { name: "Copy", exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { name: "4 clarifying questions" })).toBeVisible();
    await expect(page.locator("ol > li")).toHaveCount(4);
    const section = page.getByRole("region", { name: "4 clarifying questions" });
    const copy = section.getByRole("button", { name: "Copy questions", exact: true });
    const sessionId = run.sessionId();
    expect(sessionId).toBeTruthy();
    await expect.poll(() => countEvents("web.result_viewed", sessionId), { timeout: 10_000 }).toBe(1);
    await copy.focus();
    await copy.press("Enter");
    await expect(section.getByRole("button", { name: "Questions copied", exact: true })).toBeVisible();
    const clipboardTypes = await page.evaluate(async () => (await navigator.clipboard.read()).flatMap((item) => item.types));
    expect(clipboardTypes).toEqual(["text/plain"]);
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied.replace(/\r\n/g, "\n")).toBe(output.questions.map(({ question }) => question).join("\n"));
    await expect(page.getByRole("button", { name: "Copy", exact: true })).toBeVisible();
    await expect.poll(() => copyRequests.length, { timeout: 5_000 }).toBe(1);
    expect(new URL(copyRequests[0]!.url).pathname.endsWith(`/scenario-sessions/${sessionId}/next-actions/copy_result`)).toBe(true);
    expect(copyRequests[0]!.body).toEqual({ checkpoint_id: "result_ready" });
    await expect.poll(() => countEvents("client.next_action_clicked", sessionId), { timeout: 5_000 }).toBe(1);
    expect(await countEvents("web.result_viewed", sessionId)).toBe(1);
  });

  test("zero questions: both empty states, no readiness claim, no result_viewed, structured result still copyable", async ({
    page,
  }) => {
    const run = trackRun(page, START_ROUTE_PATTERN);
    const clientEvents = trackClientEvents(page);
    const output = composedOutput(".no_issues");
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByRole("button", { name: "Copy", exact: true })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("No issues found.")).toBeVisible();
    await expect(page.getByText("No clarifying questions were generated.")).toBeVisible();
    await expect(page.locator("ol > li")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Copy questions", exact: true })).toHaveCount(0);

    // The backend records completion; the browser must not report a "viewed" activation.
    await expect.poll(() => countEvents("scenario.completed", run.sessionId()), { timeout: 10_000 }).toBe(1);

    await page.getByRole("button", { name: "Copy", exact: true }).click();
    await expect(page.getByRole("button", { name: "Copied", exact: true })).toBeVisible();
    const copied = await page.evaluate(() => navigator.clipboard.readText());
    expect(copied).toBe(composeCopyText(output));
    expect(copied).toContain("No clarifying questions were generated.");
    // Fence, not a sleep: the copy activation is recorded after the result rendered, so a
    // web.result_viewed POST (sent at render) would already have been issued by now.
    await expect.poll(() => countEvents("client.next_action_clicked", run.sessionId()), { timeout: 5_000 }).toBe(1);
    expect(clientEvents).toContain("web.form_submitted");
    expect(clientEvents).not.toContain("web.result_viewed");
    expect(await countEvents("web.result_viewed", run.sessionId())).toBe(0);
  });

  test("mobile: long tokens fit and document whitespace is preserved", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    const output = composedOutput("");
    const longUrl = `https://example.com/${"a".repeat(200)}`;
    output.issues = [{ category: "ambiguity", severity: "low", description: "Long link", evidence: longUrl }];
    output.document.sections[0]!.content = `Item    Qty\nDesign\t\t2\n${longUrl}`;
    output.document.summary = "Confirm    scope\nThen\t\tstart.";
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByText(`Evidence: ${longUrl}`)).toBeVisible({ timeout: 60_000 });
    const documentSection = page.getByRole("region", { name: "Summary document" });
    for (const text of [output.document.sections[0]!.content, output.document.summary]) {
      const content = documentSection.getByText(text, { exact: true });
      expect(await content.innerText()).toBe(text);
    }
    await expectNoHorizontalScroll(page);
  });

  test("terminal error: a failed session shows the run-failed text, keeps the brief, offers no copy", async ({
    page,
  }) => {
    await overrideFailedSession(page);
    await page.goto(PRODUCT_URL);
    await submitBrief(page);
    await expect(page.getByText("Something went wrong decoding your brief. Please try again.")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator("#brief-decoder-brief-text")).toHaveValue(BRIEF);
    await expect(page.getByRole("button", { name: "Copy", exact: true })).toHaveCount(0);
    await expect(page.getByRole("status")).toHaveCount(0);
  });

  test("quota: the guest's fourth run is rejected with the quota message", async ({ page }) => {
    // The advisory quota GET would disable the form after the third run; abort it so the fourth
    // start reaches the authoritative 429 from the real backend.
    await page.route(QUOTA_ROUTE_PATTERN, (route) => route.abort());
    await page.goto(PRODUCT_URL);
    for (let run = 1; run <= GUEST_QUOTA_LIMIT; run += 1) {
      await submitBrief(page);
      await expect(page.getByRole("button", { name: "Copy", exact: true })).toBeVisible({ timeout: 60_000 });
      await page.getByRole("button", { name: "New task" }).click();
      await expect(page.locator("#brief-decoder-brief-text")).toHaveValue("");
    }
    await submitBrief(page);
    await expect(page.getByText(/used all your/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Copy", exact: true })).toHaveCount(0);
  });
});
