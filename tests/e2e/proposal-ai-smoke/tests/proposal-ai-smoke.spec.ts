import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { Client as PgClient } from "pg";

/**
 * ANY-243 browser-evidence smoke: proves the ProposalAI web vertical end to end against a real
 * running platform-api (deterministic fake-provider composition, see ANY-227) and a real served
 * web-mirror -- form -> start -> poll -> canonical result -> copy activation, plus the weak-input,
 * validation, idempotent-retry, quota, and safe-error paths required by the ticket.
 *
 * Requires (see proposal_ai_smoke() in scripts/agent/runner.py, which orchestrates this):
 *  - dev-up already running (platform-api + DB), base URL in PLATFORM_API_BASE_URL
 *  - web-mirror served (`next start`) at WEB_MIRROR_BASE_URL
 *  - DATABASE_URL pointing at the same dev-up Postgres, for the backend-recorded-event assertion
 */
const WEB_MIRROR_BASE_URL = process.env.WEB_MIRROR_BASE_URL ?? "http://localhost:3100";
const PRODUCT_URL = `${WEB_MIRROR_BASE_URL}/products/proposal_ai`;

const START_ROUTE_PATTERN = /\/scenarios\/[^/]+\/start$/;
const COPY_NEXT_ACTION_PATTERN = /\/scenario-sessions\/([^/]+)\/next-actions\/copy_result$/;

// The real fake-provider adapter (packages/backend/platform-core/.../providers/adapters/fake.py,
// FakeProviderAdapter._fixture_key_for()) resolves its fixture strictly from the action config id
// -- never from request content -- and ProposalAI's workflow has exactly one action config. So the
// real running dev-up stack (this Playwright suite's own backend) has no way to select this
// fixture via genuine input text; only a test-only _FixedFixtureProviderAdapter can pin a worker
// run to it. Selecting it via input content in the real system would need a Provider Gateway/
// mapping-DSL change, which ANY-243 explicitly forbids introducing.
//
// The worker/workflow -> canonical-artifact half of this path is therefore already proven for
// real, end to end, by
// apps/platform-api/tests/test_proposal_ai_bundle.py::test_proposal_ai_weak_input_end_to_end_produces_the_checked_in_weak_fixture_artifact
// (a real ASGI app + a real worker.process_next_job() call with that adapter injected, asserting
// the persisted result matches this exact fixture file) -- runs on every quick-check/full-check,
// not a one-off. Duplicating that as a second, Docker-based worker composition just to reach it
// from a browser would add real orchestration fragility (racing or pausing the live dev-up
// worker) for coverage that already exists and already passes. What this Playwright test proves
// instead, complementing that backend test rather than re-deriving it: a real start against the
// real backend/worker, and that the frontend correctly renders whatever canonical artifact the
// backend legitimately returns for this documented case -- verified against the same fixture file
// read here (not hand-copied), never a fabricated one.
const WEAK_INPUT_FIXTURE_PATH = join(
  import.meta.dirname,
  "../../../../tests/fixtures/provider/fake_provider_outputs/proposal_ai.compose_persuasive_text_v1.weak_input.json",
);

async function fillValidForm(page: Page): Promise<void> {
  await page.locator("#proposal-ai-task-text").fill("Write a landing page hero section for a bakery.");
  await page.locator("#proposal-ai-positioning").fill("Experienced copywriter for small businesses.");
}

async function submitAndWaitForResult(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Generate proposal" }).click();
  await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 30_000 });
}

/** Queries the real `event_log` table directly -- the acceptance criterion is that the backend,
 * not just the browser, recorded this event for this specific run; ANY-17's own generic backend
 * tests prove the endpoint works in isolation, not that this vertical's E2E run actually persisted
 * it. `DATABASE_URL` is dev-up's own Postgres, host-reachable via its published compose port. */
async function countBackendEvents(eventType: string, scenarioSessionId: string): Promise<number> {
  const client = new PgClient({ connectionString: process.env.DATABASE_URL });
  await client.connect();
  try {
    const result = await client.query<{ count: number }>(
      "SELECT count(*)::int AS count FROM platform.event_log WHERE event_type = $1 AND scenario_session_id = $2",
      [eventType, scenarioSessionId],
    );
    return result.rows[0]!.count;
  } finally {
    await client.end();
  }
}

test.describe("ProposalAI web product", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("happy path: submit, poll to completion, render canonical result, single backend-recorded copy activation", async ({
    page,
  }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("ProposalAI");
    await expect(page.getByText("3 of 3 proposals remaining.")).toBeVisible();

    const nextActionRequests: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && COPY_NEXT_ACTION_PATTERN.test(request.url())) {
        nextActionRequests.push(request.url());
      }
    });

    await fillValidForm(page);
    await page.getByRole("button", { name: "Generate proposal" }).click();
    await expect(page.getByRole("status")).toHaveText(/Generating your proposal/);
    const copyButton = page.getByRole("button", { name: "Copy" });
    await expect(copyButton).toBeVisible({ timeout: 30_000 });

    // `.last()`, not `.first()`: the advisory quota line is also a `<p>` inside `<main>`, rendered
    // before the result.
    const resultText = await page.locator("main p").last().innerText();
    expect(resultText.trim().length).toBeGreaterThan(0);

    await copyButton.click();
    await expect(page.getByRole("button", { name: "Copied" })).toBeVisible();
    const clipboardText = await page.evaluate(() => navigator.clipboard.readText());
    expect(clipboardText).toBe(resultText);

    // Exactly one copy_result next-action call from the browser's own single click.
    await expect.poll(() => nextActionRequests.length, { timeout: 5_000 }).toBe(1);
    const scenarioSessionId = COPY_NEXT_ACTION_PATTERN.exec(nextActionRequests[0]!)?.[1];
    expect(scenarioSessionId).toBeTruthy();

    // And the backend actually persisted it for *this* run's session -- not just that the browser
    // sent the request -- exactly once.
    await expect
      .poll(() => countBackendEvents("client.next_action_clicked", scenarioSessionId!), { timeout: 5_000 })
      .toBe(1);
  });

  test("validation: empty required fields show validation errors and never start a scenario", async ({ page }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("ProposalAI");

    let startRequested = false;
    page.on("request", (request) => {
      if (request.method() === "POST" && START_ROUTE_PATTERN.test(request.url())) {
        startRequested = true;
      }
    });

    await page.getByRole("button", { name: "Generate proposal" }).click();
    await expect(page.getByText("Task description: required.")).toBeVisible();
    await expect(page.getByText("Your positioning: required.")).toBeVisible();
    expect(startRequested).toBe(false);
  });

  test("weak input: a vague-but-schema-valid task reaches the real backend and renders the documented safe result", async ({
    page,
  }) => {
    const weakInputFixture = JSON.parse(readFileSync(WEAK_INPUT_FIXTURE_PATH, "utf8")) as {
      response_json: { text: string };
    };
    const weakInputText = weakInputFixture.response_json.text;

    await page.goto(PRODUCT_URL);
    // Vague but schema-valid: passes both client and backend validation (non-empty, no leading/
    // trailing whitespace, under the length cap), so this is a genuine start against the real
    // backend/worker -- only the final canonical-result fetch is substituted below with the real
    // documented weak-input fixture content (see WEAK_INPUT_FIXTURE_PATH's own comment for why the
    // real fake provider can't be made to select it by content alone).
    await page.locator("#proposal-ai-task-text").fill("website");
    await page.locator("#proposal-ai-positioning").fill("freelancer");

    await page.route("**/v1/results/**", async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as { output: { text: string } };
      body.output = { text: weakInputText };
      await route.fulfill({ response, json: body });
    });

    await page.getByRole("button", { name: "Generate proposal" }).click();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(weakInputText)).toBeVisible();
  });

  test("idempotent retry: retrying the same prepared start after a transient failure consumes no additional quota", async ({
    page,
  }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.getByText("3 of 3 proposals remaining.")).toBeVisible();
    await fillValidForm(page);

    const idempotencyKeys: (string | null)[] = [];
    let startAttempts = 0;
    await page.route(START_ROUTE_PATTERN, async (route) => {
      idempotencyKeys.push(route.request().headers()["idempotency-key"] ?? null);
      startAttempts += 1;
      if (startAttempts === 1) {
        // Let the request reach the real backend for real -- it genuinely starts the scenario and
        // consumes a quota unit server-side -- then simulate the client never durably seeing that
        // response (e.g. a dropped connection after the server already committed the write). This
        // is exactly the ambiguous-outcome class the backend's idempotency-key contract exists
        // for: fulfilling this from a canned response without ever calling route.fetch() would
        // mean the "first" attempt never reached the backend at all, so the retry below would be
        // the *only* real start -- proving nothing about idempotency (a prior version of this test
        // had exactly that bug: the 3->2 transition it asserted would have passed even with
        // completely broken backend idempotency).
        await route.fetch();
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ error: { code: "internal_error", message: "x", request_id: "req_1" } }),
        });
        return;
      }
      await route.continue();
    });

    await page.getByRole("button", { name: "Generate proposal" }).click();
    await expect(page.getByText("Could not start ProposalAI. Please try again.")).toBeVisible();

    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 30_000 });

    expect(startAttempts).toBe(2);
    expect(idempotencyKeys[0]).toBeTruthy();
    expect(idempotencyKeys[1]).toBe(idempotencyKeys[0]);

    // Both attempts reached the real backend with the identical Idempotency-Key; the backend's own
    // replay semantics must return the first attempt's already-accepted session on the second
    // call rather than starting (and charging) a new one -- confirmed by exactly one unit gone.
    await page.unroute(START_ROUTE_PATTERN);
    await page.goto(PRODUCT_URL);
    await expect(page.getByText("2 of 3 proposals remaining.")).toBeVisible();
  });

  test("safe-error: a terminal backend failure preserves entered form values and shows no fake progress or result", async ({
    page,
  }) => {
    await page.goto(PRODUCT_URL);
    await fillValidForm(page);

    await page.route("**/v1/scenario-sessions/**", async (route) => {
      if (route.request().method() !== "GET") {
        await route.continue();
        return;
      }
      const response = await route.fetch();
      const body = (await response.json()) as { status: string; result_artifact_id: string | null };
      // Force the very first poll to already be terminal-failed, regardless of the real session's
      // actual (likely still in-progress) status -- deterministic and fast, no need to wait out a
      // real backend failure this product's fake-provider composition can't produce on demand.
      body.status = "failed";
      body.result_artifact_id = null;
      await route.fulfill({ response, json: body });
    });

    await page.getByRole("button", { name: "Generate proposal" }).click();
    await expect(page.getByText("Something went wrong generating your proposal. Please try again.")).toBeVisible({
      timeout: 15_000,
    });

    // Entered values are preserved -- the form re-renders underneath the error, unchanged.
    await expect(page.locator("#proposal-ai-task-text")).toHaveValue("Write a landing page hero section for a bakery.");
    await expect(page.locator("#proposal-ai-positioning")).toHaveValue("Experienced copywriter for small businesses.");
    // No fake progress or result for the failed attempt.
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
  });

  test("guest identity persists across reload instead of minting a new one", async ({ page }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("ProposalAI");
    const firstGuestId = await page.evaluate(() => window.localStorage.getItem("anytoolai.guest_id"));
    expect(firstGuestId).toBeTruthy();

    await page.reload();
    await expect(page.locator("h1")).toHaveText("ProposalAI");
    const secondGuestId = await page.evaluate(() => window.localStorage.getItem("anytoolai.guest_id"));
    expect(secondGuestId).toBe(firstGuestId);
  });

  test("language switch: the UI changes and persists across reload, entered values stay, and the output-language field is untouched", async ({
    page,
  }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.getByRole("button", { name: "Generate proposal" })).toBeVisible();
    await page.locator("#proposal-ai-task-text").fill("Write a landing page hero section for a bakery.");
    await page.locator("#proposal-ai-language").fill("de");

    await page.locator("#ui-language").selectOption("ru");

    // The Russian submit label is asserted by the visible selector state and the document language,
    // not by re-typing translated copy here (the vitest suite owns per-locale copy).
    await expect(page.locator("html")).toHaveAttribute("lang", "ru");
    await expect(page.getByRole("button", { name: "Generate proposal" })).toHaveCount(0);
    await expect(page.locator("h1")).toHaveText("ProposalAI");
    await expect(page.locator("#proposal-ai-task-text")).toHaveValue("Write a landing page hero section for a bakery.");
    await expect(page.locator("#proposal-ai-language")).toHaveValue("de");

    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "ru");
    await expect(page.locator("#ui-language")).toHaveValue("ru");
    await expect(page.getByRole("button", { name: "Generate proposal" })).toHaveCount(0);
  });

  test("quota: advisory display reflects consumption, and the next genuinely new start is authoritatively rejected", async ({
    page,
  }) => {
    // 3 full submit-and-wait cycles plus a 4th submit, each against a real (if fake-provider-backed)
    // job/worker round trip -- comfortably over the file's default 60s under any CI load.
    test.setTimeout(120_000);
    await page.goto(PRODUCT_URL);
    await expect(page.getByText("3 of 3 proposals remaining.")).toBeVisible();

    for (const remainingAfter of [2, 1, 0]) {
      await fillValidForm(page);
      await submitAndWaitForResult(page);
      // Each run only has one shot at the form (no "run another" affordance on the result view by
      // design -- MVP-A2's the-page-is-the-run-record shape), so the next run is a fresh
      // navigation, whose boot-time advisory GET now reflects the just-consumed unit.
      await page.goto(PRODUCT_URL);
      await expect(page.getByText(`${remainingAfter} of 3 proposals remaining.`)).toBeVisible();
    }

    // The advisory GET itself would already short-circuit into quota-exhausted before any submit,
    // which is correct behavior but wouldn't prove the *authoritative* 429 path -- so this last
    // navigation blocks that one advisory call, forcing a genuine submit against the real backend.
    await page.route("**/v1/products/proposal_ai/quota**", (route) => route.abort());
    await page.goto(PRODUCT_URL);
    await fillValidForm(page);
    await page.getByRole("button", { name: "Generate proposal" }).click();

    // Next.js's own route-announcer div also carries role="alert" (empty text) -- scope to the
    // one this app renders.
    const quotaAlert = page.getByRole("alert").filter({ hasText: "used all your" });
    await expect(quotaAlert).toHaveText("You've used all your ProposalAI runs for now.", { timeout: 10_000 });
    // No fake progress, scenario session, or job for the rejected attempt.
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
  });
});
