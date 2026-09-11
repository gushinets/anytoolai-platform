import { expect, test, type Page } from "@playwright/test";

/**
 * ANY-243 browser-evidence smoke: proves the ProposalAI web vertical end to end against a real
 * running platform-api (deterministic fake-provider composition, see ANY-227) and a real served
 * web-mirror -- form -> start -> poll -> canonical result -> copy activation, plus the weak-input,
 * guest-identity-reuse, and quota-exhaustion paths required by the ticket.
 *
 * Requires (see proposal_ai_smoke() in scripts/agent/runner.py, which orchestrates this):
 *  - dev-up already running (platform-api + DB), base URL in PLATFORM_API_BASE_URL
 *  - web-mirror served (`next start`) at WEB_MIRROR_BASE_URL
 */
const WEB_MIRROR_BASE_URL = process.env.WEB_MIRROR_BASE_URL ?? "http://localhost:3100";
const PRODUCT_URL = `${WEB_MIRROR_BASE_URL}/products/proposal_ai`;

const START_ROUTE_PATTERN = /\/scenarios\/[^/]+\/start$/;
const COPY_NEXT_ACTION_PATTERN = /\/next-actions\/copy_result$/;

async function fillValidForm(page: Page): Promise<void> {
  await page.locator("#proposal-ai-task-text").fill("Write a landing page hero section for a bakery.");
  await page.locator("#proposal-ai-positioning").fill("Experienced copywriter for small businesses.");
}

async function submitAndWaitForResult(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Generate proposal" }).click();
  await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 30_000 });
}

test.describe("ProposalAI web product", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("happy path: submit, poll to completion, render canonical result, single copy activation", async ({ page }) => {
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

    // Exactly one copy_result next-action call from the browser's own single click -- backend-side
    // dedup/recording of `client.next_action_clicked` is already covered by ANY-17's own tests
    // (packages/backend/platform-core/tests/unit/test_scenario_runtime.py,
    // apps/platform-api/tests/test_scenario_runtime_api.py); this proves the frontend fires it
    // exactly once, not zero or twice.
    await expect.poll(() => nextActionRequests.length, { timeout: 5_000 }).toBe(1);
  });

  test("weak input: empty required fields show validation errors and never start a scenario", async ({ page }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("ProposalAI");

    let startRequested = false;
    page.on("request", (request) => {
      if (request.method() === "POST" && START_ROUTE_PATTERN.test(request.url())) {
        startRequested = true;
      }
    });

    await page.getByRole("button", { name: "Generate proposal" }).click();
    await expect(page.getByText("Task description is required.")).toBeVisible();
    await expect(page.getByText("Your positioning is required.")).toBeVisible();
    expect(startRequested).toBe(false);
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
