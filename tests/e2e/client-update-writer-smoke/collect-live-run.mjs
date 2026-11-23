import { writeFileSync } from 'node:fs';
import { performance } from 'node:perf_hooks';

const UI_TIMEOUT_MS = 120_000;

/** One fresh browser context per attempt; never retries. */
export async function collectLive(spec, { chromium, writeJournal = writeFileSync }) {
  const { mode = 'update' } = spec;
  if (mode !== 'update' && mode !== 'prepaid_request') {
    throw new Error(`Unsupported Client Update Writer mode: ${mode}`);
  }
  const startPath = `/scenarios/client_update_writer.${mode}_v1/start`;
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ locale: spec.language });
  const page = await context.newPage();
  const record = { ui_outcome: 'unknown', session_id: null, output: null };
  let startCapture = Promise.resolve();
  let resultResponse;
  page.on('response', response => {
    if (new URL(response.url()).pathname.endsWith(startPath) && response.request().method() === 'POST') {
      startCapture = capture('start_response', async () => {
        record.start_status = response.status();
        record.start_path = startPath;
        record.start = await response.json();
        record.session_id = record.start.scenario_session_id ?? null;
        await capture('start_journal', () => {
          writeJournal(`${spec.trace}.journal.json`, JSON.stringify({ ...record, phase: 'started' }));
        });
      });
    }
    if (/\/v1\/results\//.test(response.url())) resultResponse = response;
  });
  try {
    await capture('trace_start', () => context.tracing.start({ screenshots: true, snapshots: true, sources: true }));
    await collectPage(page, spec, record, writeJournal);
  } catch (error) {
    record.error = String(error);
  } finally {
    record.ui_latency_ms ??= null;
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
  if (record.start_status >= 400 || record.result_status >= 400) {
    record.ui_outcome = 'error';
  }
  if (mode === 'prepaid_request' && record.submitted) {
    const started = record.start_status >= 200 && record.start_status < 300
      && typeof record.session_id === 'string' && record.session_id.trim() !== '';
    if (!started) {
      record.error ??= `Missing successful POST to ${startPath} with a session ID`;
      record.ui_outcome = 'error';
      record.output = null;
    } else if (record.ui_outcome === 'result' && record.result?.scenario_session_id !== record.session_id) {
      record.error = 'Result does not belong to the started Prepaid Request session';
      record.ui_outcome = 'error';
      record.output = null;
    }
  }
  await capture('journal', () => {
    writeJournal(`${spec.trace}.journal.json`, JSON.stringify({ ...record, phase: 'complete' }));
  });
  return record;

  async function capture(stage, action) {
    try {
      await action();
    } catch (error) {
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
    if (spec.mode === 'prepaid_request') {
      await page.locator('label:has(input[name="client-update-writer-mode"][value="prepaid_request"])').click();
      const { notes, amount, due_date } = spec.billing_context;
      await page.locator('#client-update-writer-billing-notes').fill(notes);
      await page.locator('#client-update-writer-billing-amount').fill(amount);
      if (due_date != null) await page.locator('#client-update-writer-billing-due-date').fill(due_date);
    } else {
      await page.locator('#client-update-writer-progress-notes').fill(spec.progress_notes);
    }
    await page.locator(`label[for="client-update-writer-tone-${spec.tone}"]`).click();
    submittedAt = performance.now();
    record.submitted_at = new Date().toISOString();
    writeJournal(`${spec.trace}.journal.json`, JSON.stringify({ ...record, phase: 'submitting' }));
    record.submitted = true;
    await page.locator('#product-inputs button[type="submit"]').click();
    try {
      await page.waitForFunction(() => {
        /* global document */
        const result = document.querySelector('section[aria-labelledby="product-result-heading"] p[style*="pre-wrap"]');
        const alert = document.querySelector('[role="alert"]');
        return Boolean(result?.textContent?.trim() || alert?.textContent?.trim());
      }, null, { timeout: UI_TIMEOUT_MS });
    } catch (error) {
      if (error.name === 'TimeoutError') record.ui_outcome = 'error';
      throw error;
    }
    record.ui_latency_ms = performance.now() - submittedAt;
    const result = page.locator('section[aria-labelledby="product-result-heading"] p[style*="pre-wrap"]');
    const visibleText = await result.count() ? await result.last().innerText() : '';
    if (visibleText.trim()) {
      record.ui_outcome = 'result';
      record.visible_text = visibleText;
    } else {
      record.error = await page.locator('[role="alert"]').allTextContents();
      if (record.error.some(text => text.trim())) record.ui_outcome = 'error';
    }
  } finally {
    record.ui_latency_ms ??= submittedAt === undefined ? null : performance.now() - submittedAt;
  }
}
