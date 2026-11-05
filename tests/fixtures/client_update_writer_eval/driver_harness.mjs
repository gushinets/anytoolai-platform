/** Execute the real collector with deterministic browser/network and artifact failures. */
import { readFileSync, writeFileSync } from 'node:fs';
import { collectLive } from '../../e2e/client-update-writer-smoke/collect-live-run.mjs';

const spec = JSON.parse(readFileSync(0, 'utf8'));
const calls = [];
let listener;
const failure = spec.failure;
function response(kind) {
  return {
    url: () => kind === 'start'
      ? 'https://api/scenarios/client_update_writer.update_v1/start'
      : 'https://api/v1/results/result1',
    status: () => failure === `html-${kind}` || failure === `plain-${kind}` || failure === 'json-error' ? 502 : 200,
    json: async () => {
      if (kind === 'start') await new Promise(resolve => setTimeout(resolve, 5));
      if (failure === `body-${kind}`) throw new Error('Response body unavailable');
      if (failure === `html-${kind}`) return JSON.parse('<html>Bad gateway</html>');
      if (failure === `plain-${kind}`) return JSON.parse('Bad gateway');
      if (failure === 'json-error') return { error: 'gateway error' };
      return kind === 'start' ? { scenario_session_id: 'scenario_session_test' } : { output: { text: 'Done' } };
    },
  };
}
const page = {
  on: (_event, callback) => { listener = callback; },
  goto: async () => {},
  waitForFunction: async () => {},
  screenshot: async ({ path }) => {
    calls.push('screenshot');
    if (failure === 'screenshot') throw new Error('Screenshot unavailable');
    writeFileSync(path, 'screenshot fixture');
  },
  locator: selector => ({
    selectOption: async () => {},
    fill: async () => {},
    click: async () => {
      if (!selector.includes('submit')) return;
      calls.push('submit');
      listener(response('start'));
      if (!failure.endsWith('-start') && failure !== 'json-error') listener(response('result'));
    },
    count: async () => failure.includes('-') ? 0 : 1,
    last: () => ({ innerText: async () => 'Done' }),
    allTextContents: async () => ['API error'],
  }),
};
const chromium = {
  launch: async () => ({
    newContext: async () => ({
      newPage: async () => page,
      tracing: {
        start: async () => {},
        stop: async ({ path }) => {
          calls.push('trace');
          if (failure === 'trace') throw new Error('Trace unavailable');
          writeFileSync(path, 'trace fixture');
        },
      },
    }),
    close: async () => {
      calls.push('close');
      if (failure === 'close') throw new Error('Close failed');
    },
  }),
};
const record = await collectLive(spec, {
  chromium,
  writeJournal: (path, content) => {
    const { phase } = JSON.parse(content);
    calls.push(phase);
    if (phase === 'complete' && failure === 'journal') throw new Error('Journal unavailable');
    writeFileSync(path, content);
  },
});
process.stdout.write(JSON.stringify({ record, calls }));
