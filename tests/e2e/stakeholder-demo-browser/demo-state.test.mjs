import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const SCRIPT_URL = new URL(
  "../../../apps/platform-api/src/anytoolai_platform_api/static/demo/demo.js",
  import.meta.url,
);
const SCRIPT = await readFile(SCRIPT_URL, "utf8");

class FakeElement {
  constructor(value = "") {
    this.value = value;
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.dataset = {};
    this.children = [];
    this.listeners = new Map();
    this.focused = false;
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  async dispatch(type) {
    const listener = this.listeners.get(type);
    if (listener) {
      return listener({ preventDefault() {} });
    }
  }

  append(...children) {
    this.children.push(...children);
  }

  replaceChildren(...children) {
    this.children = [...children];
  }

  focus() {
    this.focused = true;
  }

  scrollIntoView() {}
}

class FakeClock {
  constructor() {
    this.now = 0;
    this.nextId = 1;
    this.timers = new Map();
  }

  setTimeout(callback, delay) {
    const id = this.nextId++;
    this.timers.set(id, { at: this.now + delay, callback, interval: 0 });
    return id;
  }

  clearTimeout(id) {
    this.timers.delete(id);
  }

  setInterval(callback, delay) {
    const id = this.nextId++;
    this.timers.set(id, { at: this.now + delay, callback, interval: delay });
    return id;
  }

  clearInterval(id) {
    this.timers.delete(id);
  }

  async advance(milliseconds) {
    const target = this.now + milliseconds;
    let callbacks = 0;
    while (true) {
      const due = [...this.timers.entries()]
        .filter(([, timer]) => timer.at <= target)
        .sort((left, right) => left[1].at - right[1].at)[0];
      if (!due) break;
      const [id, timer] = due;
      this.now = timer.at;
      if (timer.interval) {
        timer.at += timer.interval;
      } else {
        this.timers.delete(id);
      }
      timer.callback();
      await flush();
      callbacks += 1;
      if (callbacks > 1000) {
        throw new Error("fake clock exceeded 1000 callbacks");
      }
    }
    this.now = target;
    await flush();
  }
}

function jsonResponse(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => null },
    async json() { return payload; },
  };
}

async function flush() {
  for (let index = 0; index < 20; index += 1) {
    await Promise.resolve();
  }
}

function createHarness(fetchImpl) {
  const clock = new FakeClock();
  const selectors = [
    "#access-form", "#access-code", "#access-panel", "#workflow-section",
    "#source-text", "#character-count", "#run-button", "#run-panel",
    "#running-workflow", "#elapsed-time", "#status-message", "#result-panel",
    "#result-content", "#raw-json", "#technical-proof-list", "#rerun-button",
  ];
  const elements = new Map(selectors.map((selector) => [selector, new FakeElement()]));
  elements.get("#workflow-section").hidden = true;
  elements.get("#run-panel").hidden = true;
  elements.get("#result-panel").hidden = true;
  const radios = [new FakeElement("analyze"), new FakeElement("evaluate"), new FakeElement("write")];
  radios[0].checked = true;
  const document = {
    querySelector(selector) {
      if (selector === 'input[name="demo-workflow"]:checked') {
        return radios.find((radio) => radio.checked);
      }
      return elements.get(selector);
    },
    querySelectorAll() { return radios; },
    createElement() { return new FakeElement(); },
  };
  class FakeDate extends Date {
    static now() { return clock.now; }
  }
  const context = {
    document,
    window: {
      matchMedia: () => ({ matches: true }),
      setTimeout: clock.setTimeout.bind(clock),
      clearTimeout: clock.clearTimeout.bind(clock),
      setInterval: clock.setInterval.bind(clock),
      clearInterval: clock.clearInterval.bind(clock),
    },
    fetch: fetchImpl,
    AbortController,
    Date: FakeDate,
    JSON,
    Object,
    Array,
    String,
    Error,
  };
  vm.runInNewContext(SCRIPT, context, { filename: SCRIPT_URL.pathname });
  return { clock, elements };
}

async function unlock(harness, code = "secret") {
  harness.elements.get("#access-code").value = code;
  await harness.elements.get("#access-form").dispatch("submit");
}

test("an access denial clears the in-memory code and restores the focused access form", async () => {
  const harness = createHarness(async () => jsonResponse(401, {
    error: { code: "demo_access_denied", request_id: "req_denied" },
  }));
  await unlock(harness, "wrong");
  harness.elements.get("#source-text").value = "Пользовательский текст";
  const originalText = harness.elements.get("#source-text").value;

  await harness.elements.get("#run-button").dispatch("click");

  assert.equal(harness.elements.get("#access-panel").hidden, false);
  assert.equal(harness.elements.get("#workflow-section").hidden, true);
  assert.equal(harness.elements.get("#access-code").focused, true);
  assert.equal(harness.elements.get("#source-text").value, originalText);
  harness.elements.get("#access-code").value = "correct";
  await harness.elements.get("#access-form").dispatch("submit");
  assert.equal(harness.elements.get("#source-text").value, originalText);
});

test("a completed run renders the result and rerun returns to the editor", async () => {
  const responses = [
    jsonResponse(200, { scenario_session_id: "session-1", job_id: "job-1" }),
    jsonResponse(200, { status: "completed", result_artifact_id: "artifact-1" }),
    jsonResponse(200, {
      scenario_session_id: "session-1",
      job_id: "job-1",
      result_artifact_id: "artifact-1",
      output: { summary: "Готово" },
    }),
  ];
  const harness = createHarness(async () => responses.shift());
  await unlock(harness);
  const run = harness.elements.get("#run-button").dispatch("click");
  await flush();
  await harness.clock.advance(2000);
  await run;

  assert.equal(harness.elements.get("#result-panel").hidden, false);
  assert.equal(harness.elements.get("#workflow-section").hidden, true);
  assert.match(harness.elements.get("#raw-json").textContent, /Готово/);
  await harness.elements.get("#rerun-button").dispatch("click");
  assert.equal(harness.elements.get("#result-panel").hidden, true);
  assert.equal(harness.elements.get("#workflow-section").hidden, false);
});

test("a transient server failure reconnects and a permanent client failure stops", async () => {
  const responses = [
    jsonResponse(200, { scenario_session_id: "session-2", job_id: "job-2" }),
    jsonResponse(503, { error: { code: "temporarily_unavailable" } }),
    jsonResponse(404, { error: { code: "scenario_session_not_found", request_id: "req_404" } }),
  ];
  const harness = createHarness(async () => responses.shift());
  await unlock(harness);
  const run = harness.elements.get("#run-button").dispatch("click");
  await flush();
  await harness.clock.advance(2000);
  assert.match(harness.elements.get("#status-message").textContent, /подключиться снова/);
  await harness.clock.advance(2000);
  await run;

  assert.match(harness.elements.get("#status-message").textContent, /Код запроса: req_404/);
  assert.equal(responses.length, 0);
});

test("a never-resolving request is aborted at the overall 90 second deadline", async () => {
  const harness = createHarness((_url, options) => new Promise((_resolve, reject) => {
    options.signal.addEventListener("abort", () => {
      const error = new Error("aborted");
      error.name = "AbortError";
      reject(error);
    });
  }));
  await unlock(harness);
  const run = harness.elements.get("#run-button").dispatch("click");
  await flush();
  await harness.clock.advance(90000);
  await run;

  assert.match(harness.elements.get("#status-message").textContent, /больше 90 секунд/);
  assert.equal(harness.elements.get("#run-button").disabled, false);
});

test("a never-resolving response body is covered by the same deadline", async () => {
  let aborted = false;
  const harness = createHarness((_url, options) => Promise.resolve({
    ok: true,
    status: 200,
    headers: { get: () => null },
    json: () => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => {
        aborted = true;
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      });
    }),
  }));
  await unlock(harness);
  const run = harness.elements.get("#run-button").dispatch("click");
  await flush();
  await harness.clock.advance(90000);

  assert.equal(aborted, true);
  await run;
  assert.match(harness.elements.get("#status-message").textContent, /больше 90 секунд/);
});

test("the input limit counts Unicode code points rather than UTF-16 units", async () => {
  let requestCount = 0;
  const harness = createHarness(async () => {
    requestCount += 1;
    return jsonResponse(422, { error: { code: "demo_input_invalid" } });
  });
  await unlock(harness);
  const source = harness.elements.get("#source-text");

  source.value = "😀".repeat(4000);
  await source.dispatch("input");
  await harness.elements.get("#run-button").dispatch("click");
  assert.equal(harness.elements.get("#character-count").textContent, "4000 / 4000");
  assert.equal(requestCount, 1);

  source.value = "😀".repeat(4001);
  await source.dispatch("input");
  await harness.elements.get("#run-button").dispatch("click");
  assert.equal(harness.elements.get("#character-count").textContent, "4001 / 4000");
  assert.equal(requestCount, 1);
});
