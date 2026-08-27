import { createServer } from "node:http";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { chromium, test, expect, type BrowserContext, type Page } from "@playwright/test";

/**
 * ANY-224 browser-evidence smoke: proves the client journey from a source CE through web consent
 * to the backend-created target session, against a real running platform-api + web-mirror + the
 * built kernel-demo-ce extension. Requires:
 *  - dev-up already running (platform-api + DB), base URL in PLATFORM_API_BASE_URL
 *  - web-mirror served (`next start`/`next dev`) at WEB_CONSENT_BASE_URL
 *  - the extension already built (`wxt build`) with those same two URLs baked in via
 *    WXT_PLATFORM_API_BASE_URL/WXT_WEB_CONSENT_BASE_URL, at EXTENSION_PATH
 * See client_handoff_smoke() in scripts/agent/runner.py, which orchestrates all of the above
 * before running this spec via `python scripts/agent/runner.py client-handoff-smoke`.
 */

const EXTENSION_PATH =
  process.env.EXTENSION_PATH ??
  join(import.meta.dirname, "../../../../extensions/kernel-demo-ce/.output/chrome-mv3");
const WEB_CONSENT_BASE_URL = process.env.WEB_CONSENT_BASE_URL ?? "http://localhost:3000";
const PLATFORM_API_BASE_URL = process.env.PLATFORM_API_BASE_URL ?? "http://localhost:18000";

async function serveSourcePage(): Promise<{ url: string; close: () => Promise<void> }> {
  const server = createServer((_req, res) => {
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end("<html><body>Project brief: deadline next Friday, budget $5,000.</body></html>");
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("Failed to bind the local source-page server.");
  }
  return {
    url: `http://127.0.0.1:${address.port}/`,
    // Chromium keeps its HTTP/1.1 connection to this server alive for reuse even after
    // navigating away -- server.close() alone waits for every open connection to end first,
    // which otherwise stalls this close (and the whole test) for however long Chromium keeps
    // that idle socket open.
    close: () => {
      server.closeAllConnections();
      return new Promise<void>((resolve) => server.close(() => resolve()));
    },
  };
}

async function getExtensionId(context: BrowserContext): Promise<string> {
  let [worker] = context.serviceWorkers();
  worker ??= await context.waitForEvent("serviceworker");
  return new URL(worker.url()).host;
}

/**
 * Fresh persistent context + a fresh source/sidepanel/consent page trio per call -- kept isolated
 * per test rather than shared across the describe block, since a shared context's leftover tabs
 * from a prior journey made `chrome.tabs.query({active:true})` (and thus which tab the extension
 * captures input from) unreliable for a second run in the same window.
 */
async function withHandoffJourney(
  run: (pages: { consentPage: Page; platformApiBaseUrl: string }) => Promise<void>,
): Promise<void> {
  const userDataDir = await mkdtemp(join(tmpdir(), "kernel-demo-ce-"));
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    args: [`--disable-extensions-except=${EXTENSION_PATH}`, `--load-extension=${EXTENSION_PATH}`],
  });
  const source = await serveSourcePage();
  try {
    const extensionId = await getExtensionId(context);

    const sourcePage = await context.newPage();
    await sourcePage.goto(source.url);

    const sidepanelPage = await context.newPage();
    await sidepanelPage.goto(`chrome-extension://${extensionId}/sidepanel.html`);

    // The extension captures input from whichever tab chrome.tabs.query({active:true}) reports --
    // opening the sidepanel page above made IT the active tab, so it must be brought back manually.
    await sourcePage.bringToFront();

    const [consentPage] = await Promise.all([
      context.waitForEvent("page", { predicate: (page) => page.url().startsWith(WEB_CONSENT_BASE_URL) }),
      sidepanelPage.getByRole("button", { name: "Run handoff smoke journey" }).click(),
    ]);
    await consentPage.waitForLoadState("domcontentloaded");

    await run({ consentPage, platformApiBaseUrl: PLATFORM_API_BASE_URL });
  } finally {
    await source.close();
    await context.close();
    await rm(userDataDir, { recursive: true, force: true });
  }
}

test.describe("ANY-224 client handoff integration smoke", () => {
  test("accept: consent preview is safe and acceptance creates the linked target session", async () => {
    await withHandoffJourney(async ({ consentPage, platformApiBaseUrl }) => {
      // Safe preview: only the backend-mapped values/missing_fields, never provider/model/prompt data.
      await expect(consentPage.getByText("Kernel Demo").first()).toBeVisible();
      await expect(consentPage.getByText(/next Friday/)).toBeVisible();
      await expect(consentPage.getByText(/\$5,000/)).toBeVisible();
      for (const forbidden of ["provider", "prompt", "model", "openai", "anthropic"]) {
        expect((await consentPage.content()).toLowerCase()).not.toContain(forbidden);
      }

      const handoffToken = new URL(consentPage.url()).pathname.split("/").pop();
      expect(handoffToken).toBeTruthy();

      await consentPage.getByRole("button", { name: "Accept" }).click();
      await expect(consentPage.getByText(/consumed|accepted/i)).toBeVisible();
      await expect(consentPage.getByRole("button", { name: "Accept" })).toHaveCount(0);

      const preview = await consentPage.request.get(`${platformApiBaseUrl}/v1/handoffs/${handoffToken}`);
      const body = await preview.json();
      expect(body.target_scenario_session_id).toBeTruthy();
      expect(body.target_job_id).toBeTruthy();

      // A consumed token is unreplayable from the client's side: reloading must not resurrect
      // Accept/Decline -- this doubles as this smoke's expiry-shaped coverage (a terminal token
      // stays terminal), since waiting out a real expires_at isn't practical in a smoke test.
      await consentPage.reload();
      await expect(consentPage.getByRole("button", { name: "Accept" })).toHaveCount(0);
      await expect(consentPage.getByRole("button", { name: "Decline" })).toHaveCount(0);
    });
  });

  test("decline: declining leaves no target session", async () => {
    await withHandoffJourney(async ({ consentPage, platformApiBaseUrl }) => {
      const handoffToken = new URL(consentPage.url()).pathname.split("/").pop();

      await consentPage.getByRole("button", { name: "Decline" }).click();
      await expect(consentPage.getByText(/declined/i)).toBeVisible();

      const preview = await consentPage.request.get(`${platformApiBaseUrl}/v1/handoffs/${handoffToken}`);
      const body = await preview.json();
      expect(body.target_scenario_session_id).toBeNull();
    });
  });
});
