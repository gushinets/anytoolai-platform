import { writeFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';

const UI_TIMEOUT_MS = 120_000;

/** One fresh browser context per attempt; never retries. */
export async function collectLive(spec, { chromium, writeJournal = writeFileSync }) {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ locale: spec.language });
  const page = await context.newPage();
  const record = { ui_outcome: 'error', session_id: null, output: null };
  let startCapture = Promise.resolve();
  let resultResponse;
  page.on('response', response => {
    if (/\/scenarios\/client_update_writer\.update_v1\/start$/.test(response.url())) {
      startCapture = capture('start_response', async () => {
        record.start_status = response.status();
        record.start = await response.json();
        record.session_id = record.start.scenario_session_id ?? null;
        writeJournal(`${spec.trace}.journal.json`, JSON.stringify({ ...record, phase: 'started' }));
      });
    }
    if (/\/v1\/results\//.test(response.url())) resultResponse = response;
  });
  try {
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
    await collectPage(page, spec, record, writeJournal);
  } catch (error) {
    record.ui_outcome = 'error';
    record.error = String(error);
  } finally {
    record.ui_latency_ms ??= 0;
    await startCapture;
    if (resultResponse) {
      await capture('result_response', async () => {
        record.result_status = resultResponse.status();
        record.result = await resultResponse.json();
        record.output = record.result.output ?? null;
      });
    }
    await capture('screenshot', () => page.screenshot({ path: `${spec.trace}.png`, fullPage: true }));
    await capture('trace', () => context.tracing.stop({ path: spec.trace }));
    await capture('browser_close', () => browser.close());
  }
  if (record.diagnostic_errors || record.start_status >= 400 || record.result_status >= 400) {
    record.ui_outcome = 'error';
  }
  await capture('journal', () => {
    writeJournal(`${spec.trace}.journal.json`, JSON.stringify({ ...record, phase: 'complete' }));
  });
  return record;

  async function capture(stage, action) {
    try {
      await action();
    } catch (error) {
      record.ui_outcome = 'error';
      record.diagnostic_errors ??= {};
      record.diagnostic_errors[stage] = String(error);
    }
  }
}

async function collectPage(page, spec, record, writeJournal) {
  let submittedAt;
  try {
    await page.goto(`${spec.web_url}/products/client_update_writer`);
    await page.locator('#ui-language').selectOption(spec.language);
    await page.locator('#client-update-writer-progress-notes').fill(spec.progress_notes);
    await page.locator(`label[for="client-update-writer-tone-${spec.tone}"]`).click();
    submittedAt = performance.now();
    record.submitted_at = new Date().toISOString();
    writeJournal(`${spec.trace}.journal.json`, JSON.stringify({ ...record, phase: 'submitting' }));
    await page.locator('#product-inputs button[type="submit"]').click();
    await page.waitForFunction(() => {
      /* global document */
      const result = document.querySelector('section[aria-labelledby="product-result-heading"] p[style*="pre-wrap"]');
      const alert = document.querySelector('[role="alert"]');
      return Boolean(result?.textContent?.trim() || alert?.textContent?.trim());
    }, null, { timeout: UI_TIMEOUT_MS });
    record.ui_latency_ms = performance.now() - submittedAt;
    const result = page.locator('section[aria-labelledby="product-result-heading"] p[style*="pre-wrap"]');
    if (await result.count() && (await result.last().innerText()).trim()) {
      record.ui_outcome = 'result';
      record.visible_text = await result.last().innerText();
    } else {
      record.error = await page.locator('[role="alert"]').allTextContents();
    }
  } finally {
    record.ui_latency_ms ??= submittedAt === undefined ? 0 : performance.now() - submittedAt;
  }
}
