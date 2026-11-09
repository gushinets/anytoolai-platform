import { expect, type Page } from "@playwright/test";
import { Client as PgClient } from "pg";

export async function withDb<T>(fn: (db: PgClient) => Promise<T>): Promise<T> {
  const db = new PgClient({ connectionString: process.env.DATABASE_URL });
  await db.connect();
  try {
    return await fn(db);
  } finally {
    await db.end();
  }
}

export async function countEvents(eventType: string, scenarioSessionId: string): Promise<number> {
  return withDb(async (db) => {
    const result = await db.query<{ count: number }>(
      "SELECT count(*)::int AS count FROM platform.event_log WHERE event_type = $1 AND scenario_session_id = $2",
      [eventType, scenarioSessionId],
    );
    return result.rows[0].count;
  });
}

const ANY_START = /\/scenarios\/[^/]+\/start$/;
const RESULT_ROUTE = /\/v1\/results\/([^/?]+)/;
const SESSION_ROUTE = /\/v1\/scenario-sessions\/([^/?]+)$/;
const COPY_NEXT_ACTION = /\/scenario-sessions\/[^/]+\/next-actions\/copy_result$/;

/** Records the session id the start response returns and the artifact id the browser's result GET
 * used, so backend rows can be tied to this exact run. */
export function trackRun(page: Page, startRoute: RegExp = ANY_START): { sessionId: () => string; resultArtifactId: () => string } {
  let sessionId = "";
  let resultArtifactId = "";
  page.on("response", (response) => {
    const url = response.url();
    if (response.request().method() === "POST" && startRoute.test(url)) {
      void response
        .json()
        .then((body: { scenario_session_id: string }) => {
          sessionId = body.scenario_session_id;
        })
        .catch(() => undefined); // a failed start has no session; the assertions below then fail on the empty id
    }
    const resultMatch = response.request().method() === "GET" ? RESULT_ROUTE.exec(url) : null;
    if (resultMatch) {
      resultArtifactId = decodeURIComponent(resultMatch[1]);
    }
  });
  return { sessionId: () => sessionId, resultArtifactId: () => resultArtifactId };
}

/** Wide screens: result card right of the inputs card; narrow: stacked. Nothing overflows sideways. */
export async function expectWorkspaceLayout(page: Page, layout: "side-by-side" | "stacked"): Promise<void> {
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

export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);
}

/** Keeps the real run and response metadata; replaces only its canonical output. */
export async function overrideResult(page: Page, output: unknown): Promise<void> {
  await page.route("**/v1/results/**", async (route) => {
    const response = await route.fetch();
    const body = (await response.json()) as { output: unknown };
    body.output = output;
    await route.fulfill({ response, json: body });
  });
}

/** The backend's own rows for one session: job, ordered action runs, provider calls. */
export async function expectCorrelatedRun(sessionId: string, resultArtifactId: string, actionIds: string[]): Promise<void> {
  expect(sessionId).toBeTruthy();
  await withDb(async (db) => {
    const job = await db.query<{ id: string; status: string; result_artifact_id: string }>(
      "SELECT id, status::text AS status, result_artifact_id FROM platform.jobs WHERE scenario_session_id = $1",
      [sessionId],
    );
    expect(job.rows).toHaveLength(1);
    expect(job.rows[0].status).toBe("succeeded");
    expect(job.rows[0].result_artifact_id).toBe(resultArtifactId);

    const actions = await db.query<{ id: string; action_config_id: string; status: string }>(
      "SELECT id, action_config_id, status::text AS status FROM platform.action_runs WHERE scenario_session_id = $1 AND job_id = $2 ORDER BY created_at, id",
      [sessionId, job.rows[0].id],
    );
    expect(actions.rows.map((row) => row.action_config_id)).toEqual(actionIds);
    expect(actions.rows.map((row) => row.status)).toEqual(actionIds.map(() => "succeeded"));

    const calls = await db.query<{ action_run_id: string; status: string }>(
      "SELECT action_run_id, status::text AS status FROM platform.provider_calls WHERE scenario_session_id = $1 AND job_id = $2 ORDER BY created_at, id",
      [sessionId, job.rows[0].id],
    );
    expect(calls.rows.map((row) => row.action_run_id)).toEqual(actions.rows.map((row) => row.id));
    expect(calls.rows.map((row) => row.status)).toEqual(actionIds.map(() => "succeeded"));
  });
}

export async function expectCopyActivation(page: Page, sessionId: string, expectedText: string): Promise<void> {
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

export async function overrideFailedSession(page: Page): Promise<void> {
  await page.route(SESSION_ROUTE, async (route) => {
    if (route.request().method() !== "GET") {
      await route.continue();
      return;
    }
    const response = await route.fetch();
    const body = (await response.json()) as Record<string, unknown>;
    await route.fulfill({ response, json: { ...body, status: "failed", result_artifact_id: null } });
  });
}
