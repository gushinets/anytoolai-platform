/** Execute the real collector with deterministic browser/network and artifact failures. */
import { readFileSync, writeFileSync } from 'node:fs';
import { collectLive } from '../../e2e/client-update-writer-smoke/collect-live-run.mjs';

const spec = JSON.parse(readFileSync(0, 'utf8'));
const calls = [];
let selectedMode = 'update';
let listener;
const failure = spec.failure;
const apiFailure = /^(json-error|(html|plain|body)-(start|result))$/.test(failure);
function response(kind) {
  return {
    url: () => kind === 'start'
      ? `https://api/scenarios/client_update_writer.${failure === 'wrong-start' ? 'update' : selectedMode}_v1/start`
      : 'https://api/v1/results/result1',
    request: () => ({ method: () => failure === 'wrong-method' ? 'GET' : 'POST' }),
    status: () => failure === `html-${kind}` || failure === `plain-${kind}` || failure === 'json-error' ? 502 : 200,
    json: async () => {
      if (kind === 'start') await new Promise(resolve => setTimeout(resolve, 5));
      if (failure === `body-${kind}`) throw new Error('Response body unavailable');
      if (failure === 'capture-result' && kind === 'result') throw new Error('Body capture failed');
      if (failure === `html-${kind}`) return JSON.parse('<html>Bad gateway</html>');
      if (failure === `plain-${kind}`) return JSON.parse('Bad gateway');
      if (failure === 'json-error') return { error: 'gateway error' };
      if (kind === 'start') return { scenario_session_id: failure === 'empty-session' ? '' : 'scenario_session_test' };
      return {
        scenario_session_id: failure === 'wrong-session' ? 'another_session' : 'scenario_session_test',
        output: { text: 'Done' },
      };
    },
  };
}
const page = {
  on: (_event, callback) => { listener = callback; },
  goto: async () => { if (failure === 'pre-submit') throw new Error('Page unavailable'); },
  waitForFunction: async () => {
    if (failure === 'submit-timeout') throw Object.assign(new Error('UI timeout'), { name: 'TimeoutError' });
  },
  screenshot: async ({ path }) => {
    calls.push('screenshot');
    if (failure === 'screenshot') throw new Error('Screenshot unavailable');
    writeFileSync(path, 'screenshot fixture');
  },
  locator: selector => ({
    selectOption: async () => {},
    fill: async value => { calls.push(['fill', selector, value]); },
    click: async () => {
      if (selector === 'label:has(input[name="client-update-writer-mode"][value="prepaid_request"])') {
        selectedMode = 'prepaid_request';
      }
      if (!selector.includes('submit')) return;
      calls.push('submit');
      listener(response('start'));
      if (!failure.endsWith('-start') && failure !== 'json-error') listener(response('result'));
    },
    count: async () => apiFailure ? 0 : 1,
    last: () => ({ innerText: async () => {
      if (failure === 'capture-visible') throw new Error('Browser disconnected while reading text');
      return 'Done';
    } }),
    allTextContents: async () => ['API error'],
  }),
};
const chromium = {
  launch: async () => ({
    newContext: async () => ({
      newPage: async () => page,
      tracing: {
        start: async () => { if (failure === 'trace-start') throw new Error('Trace start failed'); },
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
    if (phase === 'started' && failure === 'start-journal') throw new Error('Journal unavailable');
    if (phase === 'submitting' && failure === 'submit-journal') throw new Error('Journal unavailable');
    writeFileSync(path, content);
  },
});
process.stdout.write(JSON.stringify({ record, calls }));
