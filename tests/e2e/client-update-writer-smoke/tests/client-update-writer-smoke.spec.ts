import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { Client as PgClient } from "pg";

/**
 * ANY-414 browser-evidence smoke: proves the Client Update Writer web vertical end to end against
 * a real running platform-api (deterministic fake-provider composition, see ANY-227) and a real
 * served web-mirror -- form -> start -> poll -> canonical result -> copy activation, plus the
 * client-side-validation and weak-input paths, closing the "no test crosses the real client ->
 * backend seam" code review finding (the routed-fake Vitest suite and the backend-only pytest
 * suite each individually stop short of it). Mirrors tests/e2e/proposal-ai-smoke's own scope and
 * structure; Update mode is this product's representative mode here, the same way ProposalAI's
 * own single scenario is proposal-ai-smoke's whole scope -- the other two modes' meaning (mapping,
 * renderer composition, weak-input fixtures) is already proven end to end at the backend-pipeline
 * level by apps/platform-api/tests/test_client_update_writer_bundle.py, including PrepaidRequest's
 * two-step chain; this suite's job is the client<->backend seam itself, not re-proving every mode.
 *
 * Requires (see client_update_writer_smoke() in scripts/agent/runner.py, which orchestrates this):
 *  - dev-up already running (platform-api + DB), base URL in PLATFORM_API_BASE_URL
 *  - web-mirror served (`next start`) at WEB_MIRROR_BASE_URL
 *  - DATABASE_URL pointing at the same dev-up Postgres, for the backend-recorded-event assertion
 */
const WEB_MIRROR_BASE_URL = process.env.WEB_MIRROR_BASE_URL ?? "http://localhost:3200";
const PRODUCT_URL = `${WEB_MIRROR_BASE_URL}/products/client_update_writer`;

const START_ROUTE_PATTERN = /\/scenarios\/[^/]+\/start$/;
const COPY_NEXT_ACTION_PATTERN = /\/scenario-sessions\/([^/]+)\/next-actions\/copy_result$/;

// Same reasoning as proposal-ai-smoke's own WEAK_INPUT_FIXTURE_PATH: the real fake-provider
// adapter resolves its fixture strictly from the action config id, never from request content, so
// the real running dev-up stack has no way to select this fixture via genuine input text alone.
// The worker/workflow -> canonical-artifact half of the weak-input path is already proven for real
// by apps/platform-api/tests/test_client_update_writer_bundle.py::test_weak_input_fixture_is_reachable_end_to_end
// (a real ASGI app + a real worker.process_next_job() call with a fixed-fixture adapter injected).
// What this Playwright test proves instead: a real start against the real backend/worker, and that
// the frontend correctly renders whatever canonical artifact the backend legitimately returns --
// verified against the same checked-in fixture file read here, never a fabricated one.
const WEAK_INPUT_FIXTURE_PATH = join(
  import.meta.dirname,
  "../../../../tests/fixtures/provider/fake_provider_outputs/client_update_writer.update_compose_reply_v1.weak_input.json",
);

/** Wide screens: the result card sits right of the inputs card on the same top line; narrow screens:
 * the two cards are stacked. Either way nothing overflows horizontally. */
async function expectWorkspaceLayout(page: Page, layout: "side-by-side" | "stacked"): Promise<void> {
  const inputs = await page.locator("#product-inputs").boundingBox();
  const result = await page.locator('section[aria-labelledby="product-result-heading"]').boundingBox();
  expect(inputs).not.toBeNull();
  expect(result).not.toBeNull();
  if (layout === "side-by-side") {
    expect(result!.x).toBeGreaterThanOrEqual(inputs!.x + inputs!.width - 1);
    expect(Math.abs(result!.y - inputs!.y)).toBeLessThanOrEqual(2);
    // Two equal cards: same width (height follows content and may differ).
    expect(Math.abs(result!.width - inputs!.width)).toBeLessThanOrEqual(2);
  } else {
    expect(result!.y).toBeGreaterThanOrEqual(inputs!.y + inputs!.height - 1);
    expect(Math.abs(result!.x - inputs!.x)).toBeLessThanOrEqual(2);
  }
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}

async function fillValidForm(page: Page): Promise<void> {
  await page
    .locator("#client-update-writer-progress-notes")
    .fill("Homepage redesign is done and ready for review by Friday.");
  await page.locator('label[for="client-update-writer-tone-warm"]').click();
}

/** Queries the real `event_log` table directly -- the acceptance criterion is that the backend,
 * not just the browser, recorded this event for this specific run. `DATABASE_URL` is dev-up's own
 * Postgres, host-reachable via its published compose port. */
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

test.describe("Client Update Writer web product (Update mode)", () => {
  test.beforeEach(async ({ context }) => {
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  });

  test("happy path: submit, poll to completion, render canonical result, single backend-recorded copy activation", async ({
    page,
  }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("Client Update Writer");

    const nextActionRequests: string[] = [];
    page.on("request", (request) => {
      if (request.method() === "POST" && COPY_NEXT_ACTION_PATTERN.test(request.url())) {
        nextActionRequests.push(request.url());
      }
    });

    await fillValidForm(page);
    await page.getByRole("button", { name: "Write update" }).click();
    await expect(page.getByRole("status")).toHaveText(/Writing your update/);
    const copyButton = page.getByRole("button", { name: "Copy" });
    await expect(copyButton).toBeVisible({ timeout: 30_000 });

    // Scoped to the result card: the form card's own `<p>`s (and any quota line) sit outside it.
    const resultText = await page
      .locator('section[aria-labelledby="product-result-heading"] p')
      .last()
      .innerText();
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

  test("workspace: inputs and result side by side on wide screens, stacked on narrow, repeat and new task reset", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto(PRODUCT_URL);
    await fillValidForm(page);
    await page.getByRole("button", { name: "Write update" }).click();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "New task" })).toBeVisible();
    await expect(page.locator("#client-update-writer-progress-notes")).not.toBeEmpty();
    await expect(page.locator("#client-update-writer-tone-warm")).toBeChecked();
    await expectWorkspaceLayout(page, "side-by-side");

    // Edited notes: the earlier result stays, marked as made from earlier details, then repeats.
    await page.locator("#client-update-writer-progress-notes").fill("Homepage redesign shipped a day early.");
    await expect(page.getByText("Created from previous details")).toBeVisible();
    await page.getByRole("button", { name: "Rewrite update" }).click();
    // The progress line sits next to the "previous details" notice, both announced as status.
    await expect(page.getByRole("status").filter({ hasText: "Writing your update" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0, { timeout: 30_000 });

    await page.setViewportSize({ width: 390, height: 844 });
    await expectWorkspaceLayout(page, "stacked");

    await page.getByRole("button", { name: "New task" }).click();
    await expect(page.locator("#client-update-writer-progress-notes")).toBeEmpty();
    await expect(page.locator("#client-update-writer-tone-neutral")).toBeChecked();
    await expect(page.locator("#client-update-writer-progress-notes")).toBeFocused();
    await expect(page.getByRole("button", { name: "Copy" })).toHaveCount(0);
  });

  test("validation: empty required fields show validation errors and never start a scenario", async ({ page }) => {
    await page.goto(PRODUCT_URL);
    await expect(page.locator("h1")).toHaveText("Client Update Writer");

    let startRequested = false;
    page.on("request", (request) => {
      if (request.method() === "POST" && START_ROUTE_PATTERN.test(request.url())) {
        startRequested = true;
      }
    });

    await page.getByRole("button", { name: "Write update" }).click();
    await expect(page.getByText("Progress notes: required.")).toBeVisible();
    await expect(page.locator("#client-update-writer-tone-neutral")).toBeChecked();
    await expect(page.getByText("Tone: required.")).toHaveCount(0);
    expect(startRequested).toBe(false);
    const toneGroup = page.getByRole("radiogroup", { name: "Tone" });
    await expect(toneGroup.getByRole("radio")).toHaveCount(3);
    await page.locator('label[for="client-update-writer-tone-warm"]').click();
    await expect(page.locator("#client-update-writer-tone-warm")).toBeChecked();
    await expect(page.getByText("Tone: required.")).toHaveCount(0);
    expect(startRequested).toBe(false);
  });

  test("weak input: a vague-but-schema-valid update reaches the real backend and renders the documented safe result", async ({
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
    // documented weak-input fixture content (see WEAK_INPUT_FIXTURE_PATH's own comment for why).
    await page.locator("#client-update-writer-progress-notes").fill("Still working on it.");
    await page.locator('label[for="client-update-writer-tone-neutral"]').click();

    await page.route("**/v1/results/**", async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as { output: { text: string } };
      body.output = { text: weakInputText };
      await route.fulfill({ response, json: body });
    });

    await page.getByRole("button", { name: "Write update" }).click();
    await expect(page.getByRole("button", { name: "Copy" })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(weakInputText)).toBeVisible();
  });
});
