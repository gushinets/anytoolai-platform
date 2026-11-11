import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import {
  trackScenarioStarts,
  expectMobileTaskReset,
  withDb,
  countEvents,
  trackRun,
  expectWorkspaceLayout,
  expectNoHorizontalScroll,
  overrideResult,
  expectCorrelatedRun,
  expectCopyActivation,
  overrideFailedSession,
} from "@anytoolai/smoke-support";

/**
 * ANY-244 browser-evidence smoke for the Acceptance Builder web vertical, scoped like its siblings
 * to "prove the client<->backend seam once": product page -> shared client -> Platform API ->
 * scenario session -> job/worker -> A01 (+A11) -> A10 workflow -> canonical artifact -> product
 * renderer -> activation. Per-product meaning (mapping, validation, parser, every renderer branch)
 * is proven by apps/web-mirror/test/AcceptanceBuilderProduct.test.tsx and the backend bundle tests.
 *
 * It also proves the accepted immediate same-tab handoff Brief Decoder -> Acceptance Builder: a real
 * Brief Decoder run, the consent page, Accept, and the queued target workflow shown in the same tab
 * without a second submit, with the backend rows that tie the two sessions together.
 *
 * A real HTTP run never sets `fixture_key`, so the real stack only ever serves the happy fixtures.
 * The weak-input tests therefore run a real start and substitute only the final canonical-result
 * body with the checked-in fixtures the backend tests use (the brief-decoder-smoke precedent).
 *
 * Requires (see acceptance_builder_smoke() in scripts/agent/runner.py): dev-up running, web-mirror
 * served at WEB_MIRROR_BASE_URL, DATABASE_URL pointing at the dev-up Postgres.
 */
const WEB_MIRROR_BASE_URL = process.env.WEB_MIRROR_BASE_URL ?? "http://localhost:3400";
const PRODUCT_URL = `${WEB_MIRROR_BASE_URL}/products/acceptance_builder`;
const BRIEF_DECODER_URL = `${WEB_MIRROR_BASE_URL}/products/brief_decoder`;
const FIXTURE_ROOT = join(import.meta.dirname, "../../../../tests/fixtures/provider/fake_provider_outputs");
const PRODUCTS_ROOT = join(
  import.meta.dirname,
  "../../../../packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products",
);
// The guest quota this test exhausts, read from the product's own config instead of a second copy.
const GUEST_QUOTA_LIMIT = Number(
  /limit_count:\s*(\d+)/.exec(readFileSync(join(PRODUCTS_ROOT, "acceptance_builder/quotas.yaml"), "utf8"))![1],
);

const ANY_START = /\/scenarios\/[^/]+\/start$/;
const SESSION_ROUTE = /\/v1\/scenario-sessions\/([^/?]+)$/;
const QUOTA_ROUTE = /\/v1\/products\/acceptance_builder\/quota/;

const BRIEF = "Build a certificate that students receive by email after finishing any course, in our brand colors.";
const DELIVERABLE = "We built the certificate template and the PDF generation for 12 courses; 5 legacy courses are not connected.";
const BRIEF_DECODER_BRIEF = "Need a website for my bakery by the holidays, modern but traditional.";

const DRAFT_ACTIONS = ["acceptance_builder.extract_v1", "acceptance_builder.draft_document_v1"];
const CHECK_ACTIONS = ["acceptance_builder.extract_v1", "acceptance_builder.compare_v1", "acceptance_builder.check_document_v1"];

type Suffix = "" | ".weak_input";
type Output = { extracted: Extracted; comparison?: Comparison; document: unknown };
type Extracted = { values: Partial<Record<ListField, string[]>>; missing_fields: ListField[] };
type ListField = "acceptance_criteria" | "assumptions" | "deliverables";
type Comparison = { verdict: string; deltas: { criterion_id: string; status: string; evidence: string }[]; rationale: string };

function fixture(action: string, suffix: Suffix): Record<string, unknown> {
  const path = join(FIXTURE_ROOT, `acceptance_builder.${action}_v1${suffix}.json`);
  return (JSON.parse(readFileSync(path, "utf8")) as { response_json: Record<string, unknown> }).response_json;
}

/** The composed workflow output, as the backend bundle test builds it. */
function composedOutput(mode: "draft" | "check", suffix: Suffix): Output {
  return {
    extracted: fixture("extract", suffix) as unknown as Extracted,
    ...(mode === "check" ? { comparison: fixture("compare", suffix) as unknown as Comparison } : {}),
    document: fixture(`${mode}_document`, suffix),
  };
}

const VERDICT_WORDS: Record<string, string> = {
  meets_expectations: "meets expectations",
  partially_meets: "partially meets expectations",
  does_not_meet: "does not meet expectations",
};
const DELTA_LABELS: Record<string, string> = {
  scope_coverage: "Scope coverage",
  requirement_fit: "Requirement fit",
  completeness: "Completeness",
  clarity: "Clarity",
};
const LISTS: [ListField, string][] = [
  ["acceptance_criteria", "Acceptance criteria"],
  ["assumptions", "Assumptions"],
  ["deliverables", "Deliverables"],
];

/** renderer_contract.yaml `copy_text`, written out independently of the renderer under test. */
function composeCopyText({ extracted, comparison }: Output): string {
  const blocks: string[] = [];
  if (comparison) {
    const lines = comparison.deltas.map((d) => `${DELTA_LABELS[d.criterion_id]}: ${d.status}. ${d.evidence}`);
    blocks.push(`Verdict\n${[`Verdict: ${VERDICT_WORDS[comparison.verdict]}.`, ...lines, comparison.rationale].join("\n")}`);
  }
  for (const [field, title] of LISTS) {
    const items = extracted.values[field];
    blocks.push(`${title}\n${items ? items.map((item) => `- ${item}`).join("\n") : "Not specified in the brief."}`);
  }
  const gaps = extracted.missing_fields.length
    ? extracted.missing_fields.map((f) => `- ${f.replace("_", " ")}: the client should confirm it.`).join("\n")
    : "The brief states all three lists.";
  blocks.push(`Open gaps\n${gaps}`);
  return blocks.join("\n\n");
}

async function submitDraft(page: Page): Promise<void> {
  await page.locator("#acceptance-builder-brief-text").fill(BRIEF);
  await page.getByRole("button", { name: "Draft criteria" }).click();
}

async function submitCheck(page: Page): Promise<void> {
  await page.getByRole("radio", { name: "Check deliverable" }).check({ force: true });
  await page.locator("#acceptance-builder-brief-text").fill(BRIEF);
  await page.locator("#acceptance-builder-deliverable-text").fill(DELIVERABLE);
  await page.getByRole("button", { name: "Check deliverable" }).click();
}

test.describe("Acceptance Builder web product", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("draft happy path: two actions in order, artifact correlation, copy text from the structured fields, one result_viewed, one copy activation", async ({
    page,
  }) => {
    const run = trackRun(page);
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("Acceptance Builder");
    await submitDraft(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { level: 2 })).toHaveText(["Your details", "Acceptance criteria"]);

    const expected = composedOutput("draft", "");
    const copyText = composeCopyText(expected);
    await expect(page.locator("main")).toContainText(expected.extracted.values.acceptance_criteria![0]!);
    // The narrative recap is display-only and starts collapsed.
    await expect(page.locator("details")).not.toHaveAttribute("open", "");

    await expectCorrelatedRun(run.sessionId(), run.resultArtifactId(), DRAFT_ACTIONS);
    await expect.poll(() => countEvents("scenario.completed", run.sessionId()), { timeout: 10_000 }).toBe(1);
    await expect.poll(() => countEvents("web.result_viewed", run.sessionId()), { timeout: 10_000 }).toBe(1);
    await expectCopyActivation(page, run.sessionId(), copyText);
    // Copy is independent of activation: still exactly one result_viewed.
    expect(await countEvents("web.result_viewed", run.sessionId())).toBe(1);
  });

  test("check happy path: three actions in order, the verdict leads the copy text, one result_viewed", async ({ page }) => {
    const run = trackRun(page);
    await page.goto(PRODUCT_URL);
    await submitCheck(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("heading", { level: 2 })).toHaveText(["Your details", "Deliverable check"]);
    // The verdict is scoped to the four general criteria, not to the extracted list.
    await expect(page.getByText(/^The verdict is judged on four general review criteria/)).toBeVisible();

    const expected = composedOutput("check", "");
    await expectCorrelatedRun(run.sessionId(), run.resultArtifactId(), CHECK_ACTIONS);
    await expect.poll(() => countEvents("web.result_viewed", run.sessionId()), { timeout: 10_000 }).toBe(1);
    await expectCopyActivation(page, run.sessionId(), composeCopyText(expected));
  });

  test("workspace: inputs and result side by side on wide screens, stacked on narrow, edited details and new task reset", async ({
    page,
  }) => {
    test.setTimeout(150_000);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(PRODUCT_URL);
    await submitDraft(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("button", { name: "New task" })).toBeVisible();
    await expectWorkspaceLayout(page, "side-by-side");

    await page.locator("#acceptance-builder-brief-text").fill(`${BRIEF} Also a PDF preview.`);
    await expect(page.getByText("Created from previous details")).toBeVisible();

    await expectMobileTaskReset(page, "#acceptance-builder-brief-text");
  });

  test("validation: empty fields show the errors and never start a scenario", async ({ page }) => {
    const starts = trackScenarioStarts(page, ANY_START);
    await page.goto(PRODUCT_URL);
    await page.getByRole("button", { name: "Draft criteria" }).click();
    await expect(page.getByText("Client brief: required.")).toBeVisible();

    await page.getByRole("radio", { name: "Check deliverable" }).check({ force: true });
    await page.locator("#acceptance-builder-brief-text").fill(BRIEF);
    await page.getByRole("button", { name: "Check deliverable" }).click();
    await expect(page.getByText("Finished work: required.")).toBeVisible();
    expect(starts).toEqual([]);
  });

  test("weak input (draft): a brief with no criteria renders the documented gaps, completes, and reports no result_viewed", async ({
    page,
  }) => {
    const run = trackRun(page);
    const output = composedOutput("draft", ".weak_input");
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitDraft(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.locator("main")).toContainText("Not specified in the brief.");
    await expect(page.locator("main")).toContainText("acceptance criteria: the client should confirm it.");
    await expect.poll(() => countEvents("scenario.completed", run.sessionId()), { timeout: 10_000 }).toBe(1);

    await expectCopyActivation(page, run.sessionId(), composeCopyText(output));
    // The draft has no verdict, so a criteria-less draft is not a "viewed" activation.
    expect(await countEvents("web.result_viewed", run.sessionId())).toBe(0);
  });

  test("weak input (check): a mismatching deliverable renders a does-not-meet verdict with its evidence", async ({ page }) => {
    const run = trackRun(page);
    const output = composedOutput("check", ".weak_input");
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitCheck(page);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await expect(page.locator("main")).toContainText("Verdict: does not meet expectations.");
    await expect.poll(() => countEvents("web.result_viewed", run.sessionId()), { timeout: 10_000 }).toBe(1);
    await expectCopyActivation(page, run.sessionId(), composeCopyText(output));
  });

  test("mobile: a long unbroken token in the result does not widen the page", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    const output = composedOutput("draft", "");
    const longUrl = `https://example.com/${"a".repeat(200)}`;
    output.extracted.values.acceptance_criteria = [longUrl];
    await overrideResult(page, output);
    await page.goto(PRODUCT_URL);
    await submitDraft(page);
    await expect(page.getByText(longUrl).first()).toBeVisible({ timeout: 60_000 });
    await expectNoHorizontalScroll(page);
  });

  test("terminal error: a failed session shows the run-failed text, keeps the brief, offers no copy", async ({ page }) => {
    await overrideFailedSession(page);
    await page.goto(PRODUCT_URL);
    await submitDraft(page);
    await expect(page.getByText("Something went wrong drafting the criteria. Please try again.")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.locator("#acceptance-builder-brief-text")).toHaveValue(BRIEF);
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
      await submitDraft(page);
      await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
      await page.getByRole("button", { name: "New task" }).click();
      await expect(page.locator("#acceptance-builder-brief-text")).toHaveValue("");
    }
    await submitDraft(page);
    await expect(page.getByText(/used all your/)).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
  });
});

/** The handoff test runs in its own browser context (a fresh guest, so its one quota unit and the
 * two provider-call chains never depend on another test) and makes six provider calls end to end:
 * four for Brief Decoder, two for the queued Acceptance Builder draft. */
test.describe("Brief Decoder -> Acceptance Builder handoff", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("accepted handoff: consent preview, same-tab redirect, queued draft shown without a submit, consumed handoff, owner replay reuses result", async ({
    page,
  }) => {
    test.setTimeout(240_000);
    const run = trackRun(page);
    const startRequests: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && ANY_START.test(request.url())) {
        startRequests.push(request.url());
      }
    });
    let targetSessionId = "";
    page.on("response", (response) => {
      const match = response.request().method() === "GET" ? SESSION_ROUTE.exec(response.url()) : null;
      if (match && match[1] !== run.sessionId()) {
        targetSessionId = decodeURIComponent(match[1]!);
      }
    });

    // 1. A real Brief Decoder run, then the source-side button.
    await page.goto(BRIEF_DECODER_URL);
    await page.locator("#brief-decoder-brief-text").fill(BRIEF_DECODER_BRIEF);
    await page.getByRole("button", { name: "Decode brief" }).click();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    const sourceSessionId = run.sessionId();
    expect(sourceSessionId).toBeTruthy();
    await page.getByRole("button", { name: "Create acceptance criteria" }).click();

    // 2. Consent page: only the mapped preview, no provider/prompt/model internals.
    await page.waitForURL(/\/handoff\/[^/?]+$/);
    const token = decodeURIComponent(new URL(page.url()).pathname.split("/").pop()!);
    await expect(page.getByRole("button", { name: "Accept" })).toBeVisible();
    await expect(page.getByText("Acceptance Builder").first()).toBeVisible();
    await expect(page.locator("dt", { hasText: "Summary" })).toBeVisible();
    await expect(page.locator("dt", { hasText: "Missing details" })).toBeVisible();
    expect(await page.locator("main").innerText()).not.toMatch(/provider|prompt|model|openai|anthropic/i);
    const guestId = await page.evaluate(() => window.localStorage.getItem("anytoolai.guest_id"));
    expect(guestId).toBeTruthy();

    // 3. Accept: the same tab goes to the target product and shows the queued run, no submit.
    const startsBeforeAccept = startRequests.length;
    await page.getByRole("button", { name: "Accept" }).click();
    await page.waitForURL(/\/products\/acceptance_builder(\?|$)/);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    expect(startRequests.length).toBe(startsBeforeAccept);
    await expect(page.getByRole("heading", { level: 2 })).toHaveText(["Your details", "Acceptance criteria"]);
    await expect(page.locator("#acceptance-builder-brief-text")).toHaveValue("");
    // The session id is removed from the address bar once read.
    expect(new URL(page.url()).search).toBe("");
    expect(targetSessionId).toBeTruthy();

    // 4. Backend rows: consumed handoff, linked sessions, the queued workflow, events.
    await withDb(async (db) => {
      const handoff = await db.query<{
        id: string;
        status: string;
        target_scenario_session_id: string;
        target_job_id: string;
        context_payload: { brief_text: string };
      }>(
        "SELECT id, status::text AS status, target_scenario_session_id, target_job_id, context_payload FROM platform.product_handoffs WHERE source_scenario_session_id = $1",
        [sourceSessionId],
      );
      expect(handoff.rows).toHaveLength(1);
      const row = handoff.rows[0]!;
      expect(row.status).toBe("consumed");
      expect(row.target_scenario_session_id).toBe(targetSessionId);
      // The target extracts from the caller's original brief, not from a summary.
      expect(row.context_payload.brief_text).toBe(BRIEF_DECODER_BRIEF);

      const sessions = await db.query<{
        id: string;
        product_id: string;
        scenario_id: string;
        parent_scenario_session_id: string | null;
        scenario_chain_id: string | null;
        guest_id: string;
      }>(
        "SELECT id, product_id, scenario_id, parent_scenario_session_id, scenario_chain_id, guest_id FROM platform.scenario_sessions WHERE id = ANY($1)",
        [[sourceSessionId, targetSessionId]],
      );
      const target = sessions.rows.find((s) => s.id === targetSessionId)!;
      const source = sessions.rows.find((s) => s.id === sourceSessionId)!;
      expect(target.product_id).toBe("acceptance_builder");
      expect(target.scenario_id).toBe("acceptance_builder.draft_v1");
      expect(target.parent_scenario_session_id).toBe(sourceSessionId);
      expect(target.scenario_chain_id).toBeTruthy();
      if (source.scenario_chain_id) {
        expect(target.scenario_chain_id).toBe(source.scenario_chain_id);
      }
      // Accept attributes the target (and its quota unit) to the accepting guest.
      expect(target.guest_id).toBe(guestId);

      const events = await db.query<{ event_type: string }>(
        "SELECT DISTINCT event_type FROM platform.event_log WHERE handoff_id = $1",
        [row.id],
      );
      const types = events.rows.map((event) => event.event_type);
      for (const expected of ["handoff.created", "handoff.viewed", "handoff.accepted", "handoff.consumed"]) {
        expect(types).toContain(expected);
      }
    });
    await expectCorrelatedRun(targetSessionId, run.resultArtifactId(), DRAFT_ACTIONS);
    await expect.poll(() => countEvents("scenario.completed", targetSessionId), { timeout: 10_000 }).toBe(1);
    await expect.poll(() => countEvents("web.result_viewed", targetSessionId), { timeout: 10_000 }).toBe(1);

    // 5. A reload in the same tab still shows the queued result the accept already paid for.
    await page.reload();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    expect(await countEvents("web.result_viewed", targetSessionId)).toBe(1);

    // 5b. Moving on ("New task") makes a later reload start clean instead of restoring the old result.
    await page.getByRole("button", { name: "New task" }).click();
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
    await page.reload();
    await expect(page.locator("#acceptance-builder-brief-text")).toHaveValue("");
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);

    // 6. Consent stays terminal, but the original owner can replay Accept without another debit.
    const readTargetExecution = () => withDb(async (db) => {
      const jobs = await db.query<{ id: string; scenario_session_id: string }>(
        "SELECT j.id, j.scenario_session_id FROM platform.jobs j JOIN platform.scenario_sessions s ON s.id = j.scenario_session_id WHERE s.parent_scenario_session_id = $1 ORDER BY j.id",
        [sourceSessionId],
      );
      const reservations = await db.query<{
        id: string;
        job_id: string;
        scenario_session_id: string;
        state: string;
        used_count: number;
        reserved_count: number;
        legacy_used_count: number;
      }>(
        "SELECT r.id, r.job_id, r.scenario_session_id, r.state::text AS state, q.used_count, q.reserved_count, q.legacy_used_count FROM platform.execution_reservations r JOIN platform.guest_quota_usage q ON q.id = r.guest_quota_usage_id WHERE r.owner_kind = 'guest' AND r.owner_id = $1 AND r.product_id = 'acceptance_builder' ORDER BY r.id",
        [guestId],
      );
      return { jobs: jobs.rows, reservations: reservations.rows };
    });
    const beforeReplay = await readTargetExecution();
    expect(beforeReplay.jobs).toHaveLength(1);
    expect(beforeReplay.reservations).toHaveLength(1);
    expect(beforeReplay.reservations[0]).toMatchObject({
      job_id: beforeReplay.jobs[0]!.id,
      scenario_session_id: targetSessionId,
      state: "consumed",
      used_count: 1,
      reserved_count: 0,
      legacy_used_count: 0,
    });
    await page.goto(`${WEB_MIRROR_BASE_URL}/handoff/${encodeURIComponent(token)}`);
    await expect(page.getByRole("button", { name: "Accept" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Decline" })).toHaveCount(0);
    const preview = await page.request.get(`${WEB_MIRROR_BASE_URL}/v1/handoffs/${encodeURIComponent(token)}`);
    expect(((await preview.json()) as { target_scenario_session_id: string }).target_scenario_session_id).toBe(targetSessionId);
    const replay = await page.request.post(`${WEB_MIRROR_BASE_URL}/v1/handoffs/${encodeURIComponent(token)}/accept`, {
      data: { guest_id: guestId },
    });
    expect(replay.status()).toBe(200);
    expect(await replay.json()).toMatchObject({
      status: "consumed",
      target_scenario_session_id: targetSessionId,
      target_job_id: beforeReplay.jobs[0]!.id,
    });
    expect(await readTargetExecution()).toEqual(beforeReplay);

    // 7. The spent token still names the queued target, so a reload after a lost Accept response can
    // reach it: an explicit "Open result" (no automatic jump), which shows the same paid result.
    await expect(page.getByRole("button", { name: "Open result" })).toBeVisible();
    await page.getByRole("button", { name: "Open result" }).click();
    await page.waitForURL(/\/products\/acceptance_builder(\?|$)/);
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    expect(await countEvents("web.result_viewed", targetSessionId)).toBe(1);
  });

  test("declined handoff: no target session is created and the token cannot be accepted afterwards", async ({ page }) => {
    test.setTimeout(150_000);
    const run = trackRun(page);
    await page.goto(BRIEF_DECODER_URL);
    await page.locator("#brief-decoder-brief-text").fill(BRIEF_DECODER_BRIEF);
    await page.getByRole("button", { name: "Decode brief" }).click();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: "Create acceptance criteria" }).click();
    await page.waitForURL(/\/handoff\/[^/?]+$/);
    await page.getByRole("button", { name: "Decline" }).click();
    await expect(page.getByRole("button", { name: "Accept" })).toHaveCount(0);
    expect(new URL(page.url()).pathname).toMatch(/^\/handoff\//);

    await withDb(async (db) => {
      const handoff = await db.query<{ status: string; target_scenario_session_id: string | null }>(
        "SELECT status::text AS status, target_scenario_session_id FROM platform.product_handoffs WHERE source_scenario_session_id = $1",
        [run.sessionId()],
      );
      expect(handoff.rows).toHaveLength(1);
      expect(handoff.rows[0]!.status).toBe("declined");
      expect(handoff.rows[0]!.target_scenario_session_id).toBeNull();
      const children = await db.query<{ count: number }>(
        "SELECT count(*)::int AS count FROM platform.scenario_sessions WHERE parent_scenario_session_id = $1",
        [run.sessionId()],
      );
      expect(children.rows[0]!.count).toBe(0);
    });
  });
});
