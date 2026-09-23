import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const REPO_ROOT = new URL("../../../", import.meta.url);
const MODULE_URL = new URL(
  "apps/platform-api/src/anytoolai_platform_api/static/atom_lab/atom_lab.mjs",
  REPO_ROOT,
);
const HTML_URL = new URL(
  "apps/platform-api/src/anytoolai_platform_api/static/atom_lab/index.html",
  REPO_ROOT,
);
const CSS_URL = new URL(
  "apps/platform-api/src/anytoolai_platform_api/static/atom_lab/atom_lab.css",
  REPO_ROOT,
);

const {
  applyJsonText,
  bootstrapAtomLab,
  collectSchemaFeatures,
  createRunSubmission,
  createDraftSession,
  describeModelOption,
  getDraftPayload,
  hasDraftPath,
  omitDraftPath,
  parseAcceptedRun,
  parsePresetExport,
  parsePresetList,
  parsePresetVersion,
  parsePresetVersionList,
  parseRunList,
  parseRunDetail,
  pollingTimedOut,
  presetContractMatchesAtom,
  replaceWithExample,
  resetPrompt,
  serializeDraft,
  setDraftPath,
  switchEditorMode,
  validateDraft,
} = await import(MODULE_URL);

const SCHEMAS = {
  A01: "extract_input.schema.json",
  A02: "score_match_input.schema.json",
  A03: "score_multidim_input.schema.json",
  A04: "issue_detection_input.schema.json",
  A05: "generate_questions_input.schema.json",
  A06: "compose_persuasive_text_input.schema.json",
  A07: "compose_reply_input.schema.json",
  A08: "generate_gap_rewrites_input.schema.json",
  A09: "synthesize_angle_input.schema.json",
  A10: "generate_document_input.schema.json",
  A11: "compare_classify_input.schema.json",
};

const EXAMPLES = {
  A01: {source_text: "Срок — 30 сентября", fields: [{name: "deadline", type: "date", description: "Срок", required: true}], strict: false},
  A02: {text_a: "Лаборатория", text_b: "Закрытая лаборатория", rubric: [{id: "scope", description: "Границы", weight: 2}]},
  A03: {text: "План измерим", axes: [{id: "clarity", description: "Ясность", weight: 1}]},
  A04: {source_text: "Бюджет неизвестен", context: "Проверка", taxonomy: ["бюджет"]},
  A05: {issues: [{category: "сроки", description: "Нет даты", severity: "high", evidence: "скоро"}], context: "Оценка", target_audience: "Заказчик", max_questions: 3},
  A06: {context: {product: "Сервис", active: false, budget: 0}, objective: "Согласовать пилот", audience: "Руководитель", constraints: {tone: "neutral", length: 900, language: "ru", format: "markdown"}},
  A07: {situation: "Запрос срока", intent: "Подтвердить", tone: "warm", constraints: {language: "ru", max_length: 600, output_format: "plain_text"}},
  A08: {source_text: "Сделаем быстро", gap: "Нет срока", n: 3, style: "moderate"},
  A09: {signals: [{id: "speed", label: "Запуск", value: {days: 14}, evidence: "Дизайн готов"}], objective: "Начать пилот", options: ["скорость", "риск"]},
  A10: {template_ref: "project_summary_v1", data: {project: "Atom Lab", status: "готово"}, style: "concise"},
  A11: {subject_text: "Пилот за две недели", reference_text: "Не позднее трёх недель", categories: ["соответствует", "не соответствует"], criteria: [{id: "deadline", description: "Срок", weight: 1}]},
};

class FakeClassList {
  constructor() { this.values = new Set(); }
  add(...values) { for (const value of values) this.values.add(value); }
  remove(...values) { for (const value of values) this.values.delete(value); }
  toggle(value, force) {
    const enabled = force === undefined ? !this.values.has(value) : force;
    if (enabled) this.values.add(value); else this.values.delete(value);
    return enabled;
  }
}

class FakeElement {
  constructor(tagName = "div", id = "") {
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.value = "";
    this.type = "";
    this.checked = false;
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    this.listeners = new Map();
    this.classList = new FakeClassList();
  }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  async dispatch(type) {
    for (const listener of this.listeners.get(type) ?? []) {
      await listener({preventDefault() {}, target: this, currentTarget: this});
    }
  }
  click() { return this.dispatch("click"); }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = [...children]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) { this.attributes.delete(name); }
  focus() { this.focused = true; }
  querySelector(selector) {
    return this.querySelectorAll(selector)[0] ?? null;
  }
  querySelectorAll(selector) {
    const results = [];
    const visit = (node) => {
      for (const child of node.children) {
        const tag = selector.toUpperCase();
        if (selector.startsWith("#") ? child.id === selector.slice(1) : child.tagName === tag) {
          results.push(child);
        }
        visit(child);
      }
    };
    visit(this);
    return results;
  }
}

class FakeLifecycleTarget {
  constructor() { this.listeners = new Map(); }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) ?? [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  removeEventListener(type, listener) {
    this.listeners.set(type, (this.listeners.get(type) ?? []).filter((item) => item !== listener));
  }
  async dispatch(type, event = {}) {
    for (const listener of this.listeners.get(type) ?? []) await listener(event);
  }
}

function createFakeDocument() {
  const ids = [
    "access-form", "access-code", "access-panel", "workspace", "status",
    "atom-navigation", "atom-title", "atom-action-type", "atom-description",
    "atom-transformation", "atom-passport", "input-schema", "output-schema",
    "input-tab", "prompt-tab", "input-panel", "prompt-panel", "form-mode", "json-mode", "input-editor",
    "json-panel", "json-editor", "json-error", "prompt-editor", "fill-example", "reset-prompt",
    "draft-state", "validation-errors", "result-placeholder", "presets-button",
    "history-button", "model-select", "reasoning-effort", "reasoning-help",
    "model-catalog-warning", "refresh-models", "run-button", "retry-submit", "retry-read", "run-state",
    "submitted-snapshot", "result-section", "result-readable", "result-json",
    "invalid-response", "invalid-response-code", "invalid-response-raw", "run-metadata",
    "run-diagnostics", "presets-panel", "close-presets", "preset-list", "load-more-presets",
    "preset-name", "preset-description", "fixed-fields", "preset-version-select", "new-preset",
    "load-more-versions",
    "save-preset", "export-preset", "preset-state", "preset-error", "preset-export",
    "preset-export-download", "preset-conflict", "open-latest-preset", "save-as-new-preset",
    "preset-compatibility", "adapt-preset", "preset-readonly",
    "history-panel", "close-history", "history-list", "load-more-history", "history-warning",
    "history-detail", "restore-history", "save-history-preset", "history-error",
  ];
  const elements = new Map(ids.map((id) => [id, new FakeElement(id.endsWith("editor") ? "textarea" : "div", id)]));
  elements.get("access-form").tagName = "FORM";
  elements.get("access-code").tagName = "INPUT";
  for (const id of ["input-tab", "prompt-tab", "form-mode", "json-mode", "fill-example", "reset-prompt", "presets-button", "history-button", "refresh-models", "run-button", "retry-submit", "retry-read", "close-presets", "load-more-presets", "load-more-versions", "new-preset", "save-preset", "export-preset", "open-latest-preset", "save-as-new-preset", "adapt-preset", "close-history", "load-more-history", "restore-history", "save-history-preset"]) {
    elements.get(id).tagName = "BUTTON";
  }
  for (const id of ["model-select", "reasoning-effort", "preset-version-select"]) elements.get(id).tagName = "SELECT";
  for (const id of ["preset-name"]) elements.get(id).tagName = "INPUT";
  elements.get("preset-description").tagName = "TEXTAREA";
  elements.get("preset-export-download").tagName = "A";
  const document = {
    createElement(tagName) { return new FakeElement(tagName); },
    querySelector(selector) { return selector.startsWith("#") ? elements.get(selector.slice(1)) ?? null : null; },
    getElementById(id) {
      if (elements.has(id)) return elements.get(id);
      let match = null;
      const visit = (node) => {
        if (node.id === id) match = node;
        for (const child of node.children) visit(child);
      };
      for (const node of elements.values()) visit(node);
      return match;
    },
  };
  return {document, elements};
}

async function schemaFor(atomId) {
  const url = new URL(`configs/kernel/schemas/${SCHEMAS[atomId]}`, REPO_ROOT);
  return JSON.parse(await readFile(url, "utf8"));
}

async function catalogAtom(atomId, overrides = {}) {
  return {
    atom_id: atomId,
    action_type: `test.${atomId.toLowerCase()}`,
    base_action_config_id: `config.${atomId.toLowerCase()}`,
    prompt: `Базовый промпт ${atomId}`,
    prompt_ref: `prompt.${atomId.toLowerCase()}`,
    input_schema: await schemaFor(atomId),
    output_schema: {type: "object", properties: {summary: {type: "string"}}, required: ["summary"], additionalProperties: false},
    schema_refs: {input: {schema_ref: `input.${atomId}`, version: 1}, output: {schema_ref: `output.${atomId}`, version: 1}},
    description: `Описание ${atomId}`,
    example_input: EXAMPLES[atomId],
    ...overrides,
  };
}

test("all eleven current atom examples survive form to JSON to form exactly", async () => {
  const featureMatrix = new Map();
  for (const atomId of Object.keys(SCHEMAS)) {
    const atom = await catalogAtom(atomId);
    const session = createDraftSession(atom);
    replaceWithExample(session);
    const expected = structuredClone(EXAMPLES[atomId]);

    assert.equal(switchEditorMode(session, "json"), true, atomId);
    const jsonText = serializeDraft(session);
    assert.equal(applyJsonText(session, jsonText), true, atomId);
    assert.equal(switchEditorMode(session, "form"), true, atomId);
    assert.deepEqual(getDraftPayload(session), expected, atomId);
    assert.deepEqual(validateDraft(session), [], atomId);
    featureMatrix.set(atomId, collectSchemaFeatures(atom.input_schema));
  }

  assert.deepEqual([...featureMatrix.keys()], Object.keys(SCHEMAS));
  const allFeatures = new Set([...featureMatrix.values()].flatMap((features) => [...features]));
  for (const feature of ["object", "array", "enum", "dynamic-dictionary", "boolean", "number", "integer", "untyped"]) {
    assert.equal(allFeatures.has(feature), true, `missing ${feature}`);
  }
});

test("all eleven current atom examples render through actual form controls", async () => {
  for (const atomId of Object.keys(SCHEMAS)) {
    const {document, elements} = createFakeDocument();
    const atom = await catalogAtom(atomId);
    const controller = bootstrapAtomLab({
      document,
      fetchImpl: async () => ({ok: true, async json() { return [atom]; }}),
      confirmImpl: () => true,
    });
    elements.get("access-code").value = "secret";
    await elements.get("access-form").dispatch("submit");

    await assert.doesNotReject(() => elements.get("fill-example").click(), atomId);
    assert.deepEqual(getDraftPayload(controller.getSession()), EXAMPLES[atomId], atomId);
    assert.ok(elements.get("input-editor").children.length > 0, atomId);
  }
});

test("omission remains distinct from null, empty string, false, and zero", async () => {
  const atom = await catalogAtom("A04", {
    input_schema: {
      type: "object",
      properties: {
        omitted: {type: ["string", "null"]},
        nullable: {type: ["string", "null"]},
        empty: {type: "string"},
        disabled: {type: "boolean"},
        count: {type: "integer"},
      },
      additionalProperties: false,
    },
    example_input: {},
  });
  const session = createDraftSession(atom);
  setDraftPath(session, ["nullable"], null);
  setDraftPath(session, ["empty"], "");
  setDraftPath(session, ["disabled"], false);
  setDraftPath(session, ["count"], 0);
  omitDraftPath(session, ["omitted"]);

  assert.equal(hasDraftPath(session, ["omitted"]), false);
  assert.deepEqual(getDraftPayload(session), {nullable: null, empty: "", disabled: false, count: 0});
  assert.deepEqual(JSON.parse(serializeDraft(session)), {nullable: null, empty: "", disabled: false, count: 0});
});

test("setting a __proto__ path creates an ordinary own JSON property", async () => {
  const session = createDraftSession(await catalogAtom("A06"));

  setDraftPath(session, ["__proto__"], "данные");

  assert.equal(Object.hasOwn(session.payload, "__proto__"), true);
  assert.equal(Object.getPrototypeOf(session.payload), Object.prototype);
  assert.deepEqual(getDraftPayload(session), {["__proto__"]: "данные"});

  setDraftPath(session, ["nested", "__proto__", "value"], 7);
  assert.equal(Object.hasOwn(session.payload.nested, "__proto__"), true);
  assert.equal(Object.getPrototypeOf(session.payload.nested), Object.prototype);
  assert.deepEqual(getDraftPayload(session).nested, {["__proto__"]: {value: 7}});
});

test("invalid JSON is retained verbatim and blocks returning to the form", async () => {
  const session = createDraftSession(await catalogAtom("A01"));
  replaceWithExample(session);
  const accepted = structuredClone(getDraftPayload(session));
  switchEditorMode(session, "json");

  assert.equal(applyJsonText(session, '{"source_text":'), false);
  assert.equal(session.jsonText, '{"source_text":');
  assert.match(session.jsonError, /JSON/);
  assert.deepEqual(getDraftPayload(session), accepted);
  assert.equal(switchEditorMode(session, "form"), false);
  assert.equal(session.mode, "json");
  assert.equal(session.dirty, true);
});

test("non-round-trippable JSON numbers are rejected without mutating the accepted payload", async () => {
  const session = createDraftSession(await catalogAtom("A06"));
  replaceWithExample(session);
  const accepted = getDraftPayload(session);

  assert.equal(applyJsonText(
    session,
    '{"context":{"id":9007199254740993},"objective":"pilot"}',
  ), false);
  assert.match(session.jsonError, /точност/);
  assert.deepEqual(getDraftPayload(session), accepted);
  assert.equal(applyJsonText(
    session,
    '{"context":{"ratio":0.1234567890123456789},"objective":"pilot"}',
  ), false);
  assert.deepEqual(getDraftPayload(session), accepted);
  assert.equal(applyJsonText(
    session,
    '{"context":{"exact":9007199254740992,"ratio":0.1,"note":"9007199254740993"},"objective":"pilot"}',
  ), true);
});

test("unrestricted schemas accept every JSON value including null", async () => {
  const session = createDraftSession(await catalogAtom("A09"));
  replaceWithExample(session);
  setDraftPath(session, ["signals", 0, "value"], null);

  assert.deepEqual(validateDraft(session), []);
});

test("reselecting form mode never restores stale JSON over form edits", async () => {
  const session = createDraftSession(await catalogAtom("A04"));
  replaceWithExample(session);
  setDraftPath(session, ["source_text"], "Изменено в форме");

  assert.equal(switchEditorMode(session, "form"), true);
  assert.equal(getDraftPayload(session).source_text, "Изменено в форме");
});

test("path validation reports nested controls without collapsing false or zero", async () => {
  const session = createDraftSession(await catalogAtom("A05"));
  replaceWithExample(session);
  setDraftPath(session, ["issues", 0, "severity"], "urgent");
  setDraftPath(session, ["max_questions"], 0);

  assert.deepEqual(validateDraft(session), [
    {path: "issues[0].severity", message: "Выберите одно из допустимых значений."},
    {path: "max_questions", message: "Значение должно быть не меньше 1."},
  ]);
});

test("current uniqueItems contracts reject duplicate array entries by path", async () => {
  const session = createDraftSession(await catalogAtom("A11"));
  replaceWithExample(session);
  setDraftPath(session, ["categories"], ["соответствует", "соответствует"]);

  assert.deepEqual(validateDraft(session), [
    {path: "categories", message: "Элементы списка не должны повторяться."},
  ]);
});

test("prompt reset and example replacement are explicit dirty-state transitions", async () => {
  const session = createDraftSession(await catalogAtom("A08"));
  session.prompt = "Изменённый промпт";
  assert.equal(session.dirty, true);
  resetPrompt(session);
  assert.equal(session.prompt, "Базовый промпт A08");
  replaceWithExample(session);
  assert.deepEqual(getDraftPayload(session), EXAMPLES.A08);
  assert.equal(session.dirty, true);
});

test("the interactive shell unlocks, safely renders catalog text, and keeps the code out of storage", async () => {
  const html = await readFile(HTML_URL, "utf8");
  assert.match(html, /id="access-form"/);
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01", {
    description: '<img src=x onerror="globalThis.compromised=true">',
  });
  const requests = [];
  const fetchImpl = async (url, options) => {
    requests.push({url, options});
    return {ok: true, async json() { return [atom]; }};
  };
  bootstrapAtomLab({document, fetchImpl, confirmImpl: () => true});
  const code = elements.get("access-code");
  code.value = "tab-only-secret";
  await elements.get("access-form").dispatch("submit");

  assert.equal(requests[0].options.headers["X-Atom-Lab-Access-Code"], "tab-only-secret");
  assert.equal(code.value, "");
  assert.equal(elements.get("atom-navigation").querySelector("button").textContent.includes("A01"), true);
  assert.equal(elements.get("atom-description").textContent, atom.description);
  assert.equal(elements.get("atom-passport").querySelector("img"), null);
});

test("repeated refresh requests share one bounded model-catalog polling chain", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const pendingCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-pending",
    last_success_at: null,
    stale: true,
    refresh_status: "pending",
    error: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let now = 0;
  const controller = bootstrapAtomLab({
    document,
    fetchImpl: async (url) => ({
      ok: true,
      status: url.endsWith("/refresh") ? 202 : 200,
      async json() { return url.endsWith("/atoms") ? [atom] : pendingCatalog; },
    }),
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
    nowImpl: () => now,
    pollTimeoutMs: 1_000,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");

  await elements.get("refresh-models").click();
  await elements.get("refresh-models").click();
  assert.equal(scheduled.size, 1);

  const [timerId, poll] = scheduled.entries().next().value;
  scheduled.delete(timerId);
  now = 1_000;
  await poll();
  assert.equal(scheduled.size, 0);

  await elements.get("refresh-models").click();
  assert.equal(scheduled.size, 1);
  controller.destroy();
  assert.equal(scheduled.size, 0);
});

test("catalog refresh retains the last-good selection through a transient read failure", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let modelReads = 0;
  const controller = bootstrapAtomLab({
    document,
    fetchImpl: async (url) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/refresh")) return {ok: true, status: 202, async json() { return {
        snapshot_id: "snapshot-current",
        last_success_at: "2026-09-21T00:00:00Z",
        stale: true,
        refresh_status: "pending",
        error: null,
      }; }};
      modelReads += 1;
      if (modelReads === 2) {
        return {ok: false, status: 503, async json() { return {error: {message: "Temporary catalog outage."}}; }};
      }
      return {ok: true, status: 200, async json() { return currentCatalog; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  const [failedTimerId, failedPoll] = scheduled.entries().next().value;
  scheduled.delete(failedTimerId);
  await failedPoll();

  assert.equal(elements.get("model-select").disabled, false);
  assert.equal(elements.get("model-select").value, "gpt");
  assert.match(elements.get("model-catalog-warning").textContent, /устарел/);
  assert.equal(scheduled.size, 1);

  const [recoveredTimerId, recoveredPoll] = scheduled.entries().next().value;
  scheduled.delete(recoveredTimerId);
  await recoveredPoll();

  assert.equal(elements.get("model-select").value, "gpt");
  assert.equal(elements.get("model-catalog-warning").textContent, "");
  assert.equal(scheduled.size, 0);
  controller.destroy();
});

test("catalog polling backs off repeated read failures and resets after recovery", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const pendingCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: true,
    refresh_status: "pending",
    error: null,
  };
  const currentCatalog = {...pendingCatalog, stale: false, refresh_status: "current"};
  const scheduled = new Map();
  const scheduledDelays = [];
  let nextTimerId = 0;
  let modelReads = 0;
  bootstrapAtomLab({
    document,
    fetchImpl: async (url) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/refresh")) return {ok: true, status: 202, async json() { return pendingCatalog; }};
      modelReads += 1;
      if (modelReads === 1) return {ok: true, status: 200, async json() { return currentCatalog; }};
      const refreshRead = modelReads - 1;
      if (refreshRead <= 6 || refreshRead === 8) {
        return {ok: false, status: 503, async json() { return {error: {message: "Temporary catalog outage."}}; }};
      }
      return {ok: true, status: 200, async json() {
        return refreshRead === 7 ? pendingCatalog : currentCatalog;
      }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      scheduledDelays.push(delay);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  while (scheduled.size > 0) {
    const [timerId, poll] = scheduled.entries().next().value;
    scheduled.delete(timerId);
    await poll();
  }

  assert.deepEqual(
    scheduledDelays.filter((delay) => delay <= 4_000),
    [250, 250, 500, 1_000, 2_000, 4_000, 4_000, 250, 250],
  );
  assert.equal(elements.get("model-catalog-warning").textContent, "");
});

test("catalog polling checks its deadline before I/O and caps delay to the remaining budget", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const pendingRefresh = {...currentCatalog, stale: true, refresh_status: "pending"};
  const scheduled = new Map();
  let nextTimerId = 0;
  let now = 0;
  let modelReads = 0;
  bootstrapAtomLab({
    document,
    nowImpl: () => now,
    pollTimeoutMs: 1_000,
    fetchImpl: async (url) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/refresh")) return {ok: true, status: 202, async json() { return pendingRefresh; }};
      modelReads += 1;
      if (modelReads === 1) return {ok: true, status: 200, async json() { return currentCatalog; }};
      return {ok: false, status: 503, async json() { return {error: {message: "Temporary catalog outage."}}; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  const [firstTimerId, firstTimer] = scheduled.entries().next().value;
  scheduled.delete(firstTimerId);
  now = 900;
  await firstTimer.callback();
  assert.equal(modelReads, 2);
  assert.equal(scheduled.size, 1);
  const [deadlineTimerId, deadlineTimer] = scheduled.entries().next().value;
  assert.equal(deadlineTimer.delay, 100);

  scheduled.delete(deadlineTimerId);
  now = 1_000;
  await deadlineTimer.callback();
  assert.equal(modelReads, 2);
  assert.equal(scheduled.size, 0);
  assert.match(elements.get("model-catalog-warning").textContent, /истекло/);
  assert.match(elements.get("model-catalog-warning").textContent, /2026-09-22T00:00:00Z/);
});

test("an in-flight catalog read is aborted at the polling deadline and a later refresh can restart", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const pendingRefresh = {...currentCatalog, stale: true, refresh_status: "pending"};
  const scheduled = new Map();
  let nextTimerId = 0;
  let now = 0;
  let modelReads = 0;
  let aborted = false;
  bootstrapAtomLab({
    document,
    nowImpl: () => now,
    pollTimeoutMs: 1_000,
    fetchImpl: (url, options = {}) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      if (url.endsWith("/refresh")) return Promise.resolve({ok: true, status: 202, async json() { return pendingRefresh; }});
      modelReads += 1;
      if (modelReads === 1) return Promise.resolve({ok: true, status: 200, async json() { return currentCatalog; }});
      return new Promise((resolve, reject) => {
        options.signal.addEventListener("abort", () => {
          aborted = true;
          reject(new DOMException("Aborted", "AbortError"));
        }, {once: true});
      });
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  const [pollTimerId, pollTimer] = scheduled.entries().next().value;
  scheduled.delete(pollTimerId);
  now = 250;
  const polling = pollTimer.callback();
  const [deadlineTimerId, deadlineTimer] = scheduled.entries().next().value;
  assert.equal(deadlineTimer.delay, 750);
  scheduled.delete(deadlineTimerId);
  now = 1_000;
  deadlineTimer.callback();
  await polling;

  assert.equal(aborted, true);
  assert.equal(scheduled.size, 0);
  assert.match(elements.get("model-catalog-warning").textContent, /истекло/);
  assert.match(elements.get("model-catalog-warning").textContent, /2026-09-22T00:00:00Z/);

  await elements.get("refresh-models").click();
  assert.equal(scheduled.size, 1);
});

test("initial catalog loading is aborted at its own deadline", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const scheduled = new Map();
  let nextTimerId = 0;
  let markCatalogStarted;
  const catalogStarted = new Promise((resolve) => { markCatalogStarted = resolve; });
  let aborted = false;
  bootstrapAtomLab({
    document,
    catalogLoadTimeoutMs: 1_000,
    fetchImpl: (url, options = {}) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      markCatalogStarted();
      return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => {
        aborted = true;
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      }, {once: true}));
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  const unlocking = elements.get("access-form").dispatch("submit");
  await catalogStarted;

  const [timeoutId, timeout] = scheduled.entries().next().value;
  assert.equal(timeout.delay, 1_000);
  scheduled.delete(timeoutId);
  timeout.callback();
  await unlocking;

  assert.equal(aborted, true);
  assert.equal(scheduled.size, 0);
  assert.equal(elements.get("run-button").disabled, true);
  assert.match(elements.get("model-catalog-warning").textContent, /истекло/);
});

test("an immediate-current refresh bounds its catalog reload and re-enables Refresh", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let modelReads = 0;
  let markReloadStarted;
  const reloadStarted = new Promise((resolve) => { markReloadStarted = resolve; });
  let aborted = false;
  bootstrapAtomLab({
    document,
    catalogLoadTimeoutMs: 1_000,
    fetchImpl: (url, options = {}) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      if (url.endsWith("/refresh")) return Promise.resolve({ok: true, status: 202, async json() { return currentCatalog; }});
      modelReads += 1;
      if (modelReads === 1) return Promise.resolve({ok: true, status: 200, async json() { return currentCatalog; }});
      markReloadStarted();
      return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => {
        aborted = true;
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      }, {once: true}));
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  const refreshing = elements.get("refresh-models").click();
  await reloadStarted;

  const [timeoutId, timeout] = scheduled.entries().next().value;
  assert.equal(timeout.delay, 1_000);
  scheduled.delete(timeoutId);
  timeout.callback();
  await refreshing;

  assert.equal(aborted, true);
  assert.equal(scheduled.size, 0);
  assert.equal(elements.get("refresh-models").disabled, false);
  assert.equal(elements.get("model-select").value, "gpt");
  assert.match(elements.get("model-catalog-warning").textContent, /истекло/);
  assert.match(elements.get("model-catalog-warning").textContent, /2026-09-22T00:00:00Z/);
});

test("a stalled catalog refresh POST is aborted and leaves the last-good catalog usable", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let markRefreshStarted;
  const refreshStarted = new Promise((resolve) => { markRefreshStarted = resolve; });
  let aborted = false;
  bootstrapAtomLab({
    document,
    catalogRefreshTimeoutMs: 1_000,
    fetchImpl: (url, options = {}) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      if (url.endsWith("/refresh")) {
        markRefreshStarted();
        return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => {
          aborted = true;
          const error = new Error("aborted");
          error.name = "AbortError";
          reject(error);
        }, {once: true}));
      }
      return Promise.resolve({ok: true, status: 200, async json() { return currentCatalog; }});
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  const refreshing = elements.get("refresh-models").click();
  await refreshStarted;

  assert.equal(elements.get("refresh-models").disabled, true);
  const [timeoutId, timeout] = scheduled.entries().next().value;
  assert.equal(timeout.delay, 1_000);
  scheduled.delete(timeoutId);
  timeout.callback();
  await refreshing;

  assert.equal(aborted, true);
  assert.equal(scheduled.size, 0);
  assert.equal(elements.get("refresh-models").disabled, false);
  assert.equal(elements.get("model-select").value, "gpt");
  assert.equal(elements.get("run-button").disabled, false);
  assert.match(elements.get("model-catalog-warning").textContent, /истекло/);
  assert.match(elements.get("model-catalog-warning").textContent, /2026-09-22T00:00:00Z/);
});

test("bfcache resume reloads a current catalog interrupted after refresh acceptance", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const model = (modelId) => ({model_id: modelId, compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}});
  const initialCatalog = {
    items: [model("gpt-old")],
    snapshot_id: "snapshot-old",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const refreshedCatalog = {
    ...initialCatalog,
    items: [model("gpt-old"), model("gpt-new")],
    snapshot_id: "snapshot-new",
    last_success_at: "2026-09-22T00:00:00Z",
  };
  let modelReads = 0;
  let markReloadStarted;
  const reloadStarted = new Promise((resolve) => { markReloadStarted = resolve; });
  let interrupted = false;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    fetchImpl: (url, options = {}) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      if (url.endsWith("/refresh")) return Promise.resolve({ok: true, status: 202, async json() { return refreshedCatalog; }});
      modelReads += 1;
      if (modelReads === 1) return Promise.resolve({ok: true, status: 200, async json() { return initialCatalog; }});
      if (modelReads === 2) {
        markReloadStarted();
        return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => {
          interrupted = true;
          const error = new Error("aborted");
          error.name = "AbortError";
          reject(error);
        }, {once: true}));
      }
      return Promise.resolve({ok: true, status: 200, async json() { return refreshedCatalog; }});
    },
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  const refreshing = elements.get("refresh-models").click();
  await reloadStarted;

  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  await refreshing;
  assert.equal(interrupted, true);
  assert.equal(modelReads, 2);

  await lifecycleTarget.dispatch("pageshow", {persisted: true});
  assert.equal(modelReads, 3);
  assert.equal(elements.get("model-select").value, "gpt-old");
  assert.equal(elements.get("model-select").children.some(({value}) => value === "gpt-new"), true);
  assert.equal(elements.get("model-catalog-warning").textContent, "");
});

test("bfcache resume retries an interrupted initial catalog load", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  let modelReads = 0;
  let markInitialReadStarted;
  const initialReadStarted = new Promise((resolve) => { markInitialReadStarted = resolve; });
  let interrupted = false;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    fetchImpl: (url, options = {}) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      modelReads += 1;
      if (modelReads === 1) {
        markInitialReadStarted();
        return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => {
          interrupted = true;
          const error = new Error("aborted");
          error.name = "AbortError";
          reject(error);
        }, {once: true}));
      }
      return Promise.resolve({ok: true, status: 200, async json() { return currentCatalog; }});
    },
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  const unlocking = elements.get("access-form").dispatch("submit");
  await initialReadStarted;

  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  await unlocking;
  assert.equal(interrupted, true);
  assert.equal(modelReads, 1);

  await lifecycleTarget.dispatch("pageshow", {persisted: true});
  assert.equal(modelReads, 2);
  assert.equal(elements.get("model-select").value, "gpt");
  assert.equal(elements.get("run-button").disabled, false);
});

test("a current refresh reloads the catalog without silently replacing a removed selection", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const staleCatalog = {
    items: [{model_id: "gpt-old", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-old",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: true,
    refresh_status: "current",
    error: "Previous refresh failed.",
  };
  const freshCatalog = {
    ...staleCatalog,
    items: [{model_id: "gpt-new", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-new",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    error: null,
  };
  let modelReads = 0;
  bootstrapAtomLab({
    document,
    fetchImpl: async (url) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/refresh")) return {ok: true, status: 202, async json() { return {
        snapshot_id: "snapshot-new",
        last_success_at: "2026-09-22T00:00:00Z",
        stale: false,
        refresh_status: "current",
        error: null,
      }; }};
      modelReads += 1;
      return {ok: true, status: 200, async json() { return modelReads === 1 ? staleCatalog : freshCatalog; }};
    },
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  assert.equal(elements.get("model-select").value, "gpt-old");
  assert.match(elements.get("model-catalog-warning").textContent, /устарел/);

  await elements.get("refresh-models").click();
  assert.equal(modelReads, 2);
  assert.equal(elements.get("model-select").value, "gpt-old");
  assert.match(elements.get("model-catalog-warning").textContent, /Выберите модель заново/);
  assert.equal(elements.get("run-button").disabled, true);
});

test("a superseded catalog read cannot overwrite a newer current refresh", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const catalogFor = (modelId, refreshStatus) => ({
    items: [{model_id: modelId, compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: `snapshot-${modelId}`,
    last_success_at: "2026-09-22T00:00:00Z",
    stale: refreshStatus !== "current",
    refresh_status: refreshStatus,
    error: null,
  });
  const scheduled = new Map();
  let nextTimerId = 0;
  let modelReads = 0;
  let refreshes = 0;
  let resolveOldRead;
  bootstrapAtomLab({
    document,
    fetchImpl: (url) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      if (url.endsWith("/refresh")) {
        refreshes += 1;
        const refresh = refreshes === 1
          ? catalogFor("gpt-initial", "pending")
          : catalogFor("gpt-initial", "current");
        return Promise.resolve({ok: true, status: 202, async json() {
          return {
            snapshot_id: refresh.snapshot_id,
            last_success_at: refresh.last_success_at,
            stale: refresh.stale,
            refresh_status: refresh.refresh_status,
            error: refresh.error,
          };
        }});
      }
      modelReads += 1;
      if (modelReads === 1) return Promise.resolve({ok: true, status: 200, async json() { return catalogFor("gpt-initial", "current"); }});
      if (modelReads === 2) return new Promise((resolve) => { resolveOldRead = resolve; });
      return Promise.resolve({ok: true, status: 200, async json() { return catalogFor("gpt-initial", "current"); }});
    },
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  const [pollTimerId, poll] = scheduled.entries().next().value;
  scheduled.delete(pollTimerId);
  const oldPolling = poll();
  assert.equal(typeof resolveOldRead, "function");

  await elements.get("refresh-models").click();
  assert.equal(elements.get("model-select").value, "gpt-initial");
  assert.equal(elements.get("model-catalog-warning").textContent, "");

  resolveOldRead({ok: true, status: 200, async json() { return catalogFor("gpt-stale", "pending"); }});
  await oldPolling;
  assert.equal(elements.get("model-select").value, "gpt-initial");
  assert.equal(elements.get("model-catalog-warning").textContent, "");
  assert.equal(scheduled.size, 0);
});

test("a persisted page resumes a model refresh accepted before its first catalog poll", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let modelReads = 0;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    fetchImpl: async (url) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/refresh")) return {ok: true, status: 202, async json() { return {
        snapshot_id: "snapshot-current",
        last_success_at: "2026-09-21T00:00:00Z",
        stale: true,
        refresh_status: "pending",
        error: null,
      }; }};
      modelReads += 1;
      return {ok: true, status: 200, async json() { return currentCatalog; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  assert.equal(scheduled.size, 1);
  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  assert.equal(scheduled.size, 0);
  await lifecycleTarget.dispatch("pageshow", {persisted: true});
  assert.equal(scheduled.size, 1);

  const [timerId, poll] = scheduled.entries().next().value;
  scheduled.delete(timerId);
  await poll();
  assert.equal(modelReads, 2);
  assert.equal(elements.get("model-catalog-warning").textContent, "");
  assert.equal(scheduled.size, 0);
});

test("persisted lifecycle resumes keep the original model-catalog polling deadline", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const pendingCatalog = {...currentCatalog, stale: true, refresh_status: "pending"};
  const scheduled = new Map();
  let nextTimerId = 0;
  let now = 0;
  let modelReads = 0;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    nowImpl: () => now,
    pollTimeoutMs: 1_000,
    fetchImpl: async (url) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/refresh")) return {ok: true, status: 202, async json() { return pendingCatalog; }};
      modelReads += 1;
      return {ok: true, status: 200, async json() { return currentCatalog; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  assert.equal(modelReads, 1);
  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  now = 1_000;
  await lifecycleTarget.dispatch("pageshow", {persisted: true});

  assert.equal(scheduled.size, 1);
  const [timerId, timer] = scheduled.entries().next().value;
  assert.equal(timer.delay, 0);
  scheduled.delete(timerId);
  await timer.callback();
  assert.equal(modelReads, 1);
  assert.equal(scheduled.size, 0);
  assert.match(elements.get("model-catalog-warning").textContent, /истекло/);
});

test("a persisted page resumes an accepted refresh without a last-good catalog", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const currentCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-recovered",
    last_success_at: "2026-09-22T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let modelReads = 0;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    fetchImpl: async (url) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/refresh")) return {ok: true, status: 202, async json() { return {
        snapshot_id: null,
        last_success_at: null,
        stale: true,
        refresh_status: "pending",
        error: null,
      }; }};
      modelReads += 1;
      if (modelReads === 1) {
        return {ok: false, status: 503, async json() { return {error: {message: "Catalog unavailable."}}; }};
      }
      return {ok: true, status: 200, async json() { return currentCatalog; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  assert.equal(elements.get("model-select").disabled, true);
  await elements.get("refresh-models").click();

  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  assert.equal(scheduled.size, 0);
  await lifecycleTarget.dispatch("pageshow", {persisted: true});
  assert.equal(scheduled.size, 1);

  const [timerId, poll] = scheduled.entries().next().value;
  scheduled.delete(timerId);
  await poll();
  assert.equal(modelReads, 2);
  assert.equal(elements.get("model-select").disabled, false);
  assert.equal(elements.get("model-catalog-warning").textContent, "");
});

test("an in-flight pre-pause catalog read cannot orphan the resumed polling timer", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const pendingCatalog = {
    items: [{model_id: "gpt", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: true,
    refresh_status: "pending",
    error: null,
  };
  const currentCatalog = {...pendingCatalog, stale: false, refresh_status: "current"};
  const scheduled = new Map();
  let nextTimerId = 0;
  let modelReads = 0;
  let resolveCatalogRead;
  const controller = bootstrapAtomLab({
    document,
    lifecycleTarget,
    fetchImpl: (url) => {
      if (url.endsWith("/atoms")) return Promise.resolve({ok: true, status: 200, async json() { return [atom]; }});
      if (url.endsWith("/refresh")) return Promise.resolve({ok: true, status: 202, async json() { return pendingCatalog; }});
      modelReads += 1;
      if (modelReads === 1) return Promise.resolve({ok: true, status: 200, async json() { return currentCatalog; }});
      return new Promise((resolve) => { resolveCatalogRead = resolve; });
    },
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("refresh-models").click();

  const [initialTimerId, initialPoll] = scheduled.entries().next().value;
  scheduled.delete(initialTimerId);
  const inFlightPoll = initialPoll();
  assert.equal(typeof resolveCatalogRead, "function");

  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  await lifecycleTarget.dispatch("pageshow", {persisted: true});
  assert.equal(scheduled.size, 1);

  resolveCatalogRead({ok: true, status: 200, async json() { return pendingCatalog; }});
  await inFlightPoll;
  assert.equal(scheduled.size, 1);
  controller.destroy();
  assert.equal(scheduled.size, 0);
});

test("destroy aborts an active run read and prevents another poll", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const modelCatalog = {
    items: [{
      model_id: "gpt-supported",
      compatibility: "compatible",
      reason: "confirmed_openai_text_gpt",
      reasoning_supported: false,
      allowed_reasoning_efforts: null,
      provenance: {},
    }],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let runReadSignal = null;
  const controller = bootstrapAtomLab({
    document,
    fetchImpl: async (url, options = {}) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/models")) return {ok: true, status: 200, async json() { return modelCatalog; }};
      if (url.endsWith("/runs") && options.method === "POST") {
        return {ok: true, status: 202, async json() { return {run_id: "run-active", scenario_session_id: "session-active", job_id: "job-active", status: "running"}; }};
      }
      runReadSignal = options.signal;
      return new Promise((resolve, reject) => {
        options.signal.addEventListener("abort", () => {
          const error = new Error("aborted");
          error.name = "AbortError";
          reject(error);
        }, {once: true});
      });
    },
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  await elements.get("run-button").click();

  const [pollTimerId, poll] = scheduled.entries().next().value;
  scheduled.delete(pollTimerId);
  const polling = poll();
  assert.ok(runReadSignal);
  controller.destroy();

  assert.equal(runReadSignal.aborted, true);
  await polling;
  assert.equal(scheduled.size, 0);
});

test("a persisted pagehide pauses polling and pageshow resumes the same accepted run", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const scheduled = new Map();
  let nextTimerId = 0;
  let posts = 0;
  let reads = 0;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    fetchImpl: async (url, options = {}) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/models")) return {ok: true, status: 200, async json() { return {
        items: [{model_id: "gpt-supported", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
        snapshot_id: "snapshot-current", last_success_at: "2026-09-21T00:00:00Z", stale: false, refresh_status: "current", error: null,
      }; }};
      if (url.endsWith("/runs") && options.method === "POST") {
        posts += 1;
        return {ok: true, status: 202, async json() { return {run_id: "run-bfcache", scenario_session_id: "session-bfcache", job_id: "job-bfcache", status: "running"}; }};
      }
      reads += 1;
      return {ok: true, status: 200, async json() { return {
        run_id: "run-bfcache", status: "succeeded", snapshot: {atom_id: "A01"},
        runtime_ids: {scenario_session_id: "session-bfcache", job_id: "job-bfcache", action_run_id: "action-bfcache", artifact_id: "artifact-bfcache"},
        result: {value: "restored"},
        diagnostics: {error_code: null, duration_ms: 1, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 1, transport_attempts: 1, physical_calls: 1, succeeded_first_attempt: true, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
        created_at: "2026-09-21T00:00:00Z", started_at: "2026-09-21T00:00:00Z", finished_at: "2026-09-21T00:00:01Z",
      }; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  await elements.get("run-button").click();

  assert.equal(scheduled.size, 1);
  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  assert.equal(scheduled.size, 0);
  await lifecycleTarget.dispatch("pageshow", {persisted: true});

  assert.equal(posts, 1);
  assert.equal(reads, 1);
  assert.match(elements.get("run-state").textContent, /Завершён/);
  assert.match(elements.get("run-diagnostics").textContent, /run-bfcache/);
});

test("persisted lifecycle resumes keep the accepted run polling deadline", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const scheduled = new Map();
  let nextTimerId = 0;
  let now = 0;
  let posts = 0;
  let reads = 0;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    nowImpl: () => now,
    pollTimeoutMs: 1_000,
    fetchImpl: async (url, options = {}) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/models")) return {ok: true, status: 200, async json() { return {
        items: [{model_id: "gpt-supported", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
        snapshot_id: "snapshot-current", last_success_at: "2026-09-22T00:00:00Z", stale: false, refresh_status: "current", error: null,
      }; }};
      if (url.endsWith("/runs") && options.method === "POST") {
        posts += 1;
        return {ok: true, status: 202, async json() { return {run_id: "run-deadline", scenario_session_id: "session-deadline", job_id: "job-deadline", status: "running"}; }};
      }
      reads += 1;
      return {ok: true, status: 200, async json() { return null; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  await elements.get("run-button").click();

  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  now = 1_000;
  await lifecycleTarget.dispatch("pageshow", {persisted: true});

  assert.equal(posts, 1);
  assert.equal(reads, 0);
  assert.equal(scheduled.size, 0);
  assert.match(elements.get("run-state").textContent, /истекло/);
  assert.equal(elements.get("retry-read").hidden, false);
});

test("resumed automatic polling hides a stale manual reread action", async () => {
  const {document, elements} = createFakeDocument();
  const lifecycleTarget = new FakeLifecycleTarget();
  const atom = await catalogAtom("A01");
  const scheduled = new Map();
  let nextTimerId = 0;
  let reads = 0;
  bootstrapAtomLab({
    document,
    lifecycleTarget,
    fetchImpl: async (url, options = {}) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/models")) return {ok: true, status: 200, async json() { return {
        items: [{model_id: "gpt-supported", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
        snapshot_id: "snapshot-current", last_success_at: "2026-09-21T00:00:00Z", stale: false, refresh_status: "current", error: null,
      }; }};
      if (url.endsWith("/runs") && options.method === "POST") {
        return {ok: true, status: 202, async json() { return {run_id: "run-reread", scenario_session_id: "session-reread", job_id: "job-reread", status: "running"}; }};
      }
      reads += 1;
      if (reads === 1) return {ok: false, status: 404, async json() { return {error: {code: "lab_resource_not_found", message: "Не найдено.", field_errors: []}}; }};
      return {ok: true, status: 200, async json() { return {
        run_id: "run-reread", status: "running", snapshot: {atom_id: "A01"},
        runtime_ids: {scenario_session_id: "session-reread", job_id: "job-reread", action_run_id: null, artifact_id: null},
        result: null,
        diagnostics: {error_code: null, duration_ms: null, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 0, physical_calls: 0, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
        created_at: "2026-09-21T00:00:00Z", started_at: "2026-09-21T00:00:00Z", finished_at: null,
      }; }};
    },
    confirmImpl: () => true,
    scheduleImpl(callback) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, callback);
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  await elements.get("run-button").click();

  const [pollTimerId, firstPoll] = scheduled.entries().next().value;
  scheduled.delete(pollTimerId);
  await firstPoll();
  assert.equal(elements.get("retry-read").hidden, false);

  await lifecycleTarget.dispatch("pagehide", {persisted: true});
  await lifecycleTarget.dispatch("pageshow", {persisted: true});
  assert.equal(reads, 2);
  assert.equal(elements.get("retry-read").hidden, true);
  assert.equal(scheduled.size, 1);
});

async function assertSubmissionDeadlinePreservesReplay(stallAt) {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const scheduled = new Map();
  const keys = [];
  const bodies = [];
  let nextTimerId = 0;
  bootstrapAtomLab({
    document,
    lifecycleTarget: new FakeLifecycleTarget(),
    submissionTimeoutMs: 1_000,
    fetchImpl: async (url, options = {}) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/models")) return {ok: true, status: 200, async json() { return {
        items: [{model_id: "gpt-supported", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
        snapshot_id: "snapshot-current", last_success_at: "2026-09-21T00:00:00Z", stale: false, refresh_status: "current", error: null,
      }; }};
      if (url.endsWith("/runs") && options.method === "POST") {
        keys.push(options.headers["Idempotency-Key"]);
        bodies.push(JSON.parse(options.body));
        if (keys.length > 1) return {ok: false, status: 422, async json() { return {error: {code: "confirmed_rejection", message: "Rejected after replay.", field_errors: []}}; }};
        if (stallAt === "fetch") {
          return new Promise((resolve, reject) => options.signal.addEventListener("abort", () => {
            const error = new Error("aborted");
            error.name = "AbortError";
            reject(error);
          }, {once: true}));
        }
        return {ok: true, status: 202, json: () => new Promise((resolve, reject) => {
          const rejectAborted = () => {
            const error = new Error("aborted");
            error.name = "AbortError";
            reject(error);
          };
          if (options.signal.aborted) rejectAborted();
          else options.signal.addEventListener("abort", rejectAborted, {once: true});
        })};
      }
      throw new Error(`Unexpected request: ${url}`);
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
    idempotencyKeyFactory: () => "stable-timeout-key",
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  const submitting = elements.get("run-button").click();

  assert.equal(scheduled.size, 1);
  const [timerId, timer] = scheduled.entries().next().value;
  scheduled.delete(timerId);
  assert.equal(timer.delay, 1_000);
  timer.callback();
  await submitting;

  assert.equal(elements.get("retry-submit").hidden, false);
  assert.equal(elements.get("run-button").disabled, true);
  assert.match(elements.get("run-state").textContent, /Результат отправки неизвестен/);
  await elements.get("retry-submit").click();
  assert.deepEqual(keys, ["stable-timeout-key", "stable-timeout-key"]);
  assert.deepEqual(bodies[1], bodies[0]);
}

test("a submission deadline recovers from a fetch that never resolves", async () => {
  await assertSubmissionDeadlinePreservesReplay("fetch");
});

test("a submission deadline recovers from a response body that never resolves", async () => {
  await assertSubmissionDeadlinePreservesReplay("body");
});

test("run-read retry scheduling is bounded by backoff, Retry-After, and deadline", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A01");
  const modelCatalog = {
    items: [{
      model_id: "gpt-supported",
      compatibility: "compatible",
      reason: "confirmed_openai_text_gpt",
      reasoning_supported: false,
      allowed_reasoning_efforts: null,
      provenance: {},
    }],
    snapshot_id: "snapshot-current",
    last_success_at: "2026-09-21T00:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  const runningDetail = {
    run_id: "run-backoff",
    status: "running",
    snapshot: {atom_id: "A01", input: EXAMPLES.A01, prompt: atom.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
    runtime_ids: {scenario_session_id: "session-backoff", job_id: "job-backoff", action_run_id: "action-backoff", artifact_id: null},
    result: null,
    diagnostics: {error_code: null, duration_ms: null, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 0, physical_calls: 0, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
    created_at: "2026-09-21T00:00:00Z",
    started_at: "2026-09-21T00:00:00Z",
    finished_at: null,
  };
  const scheduled = new Map();
  let nextTimerId = 0;
  let now = 0;
  let reads = 0;
  bootstrapAtomLab({
    document,
    fetchImpl: async (url, options = {}) => {
      if (url.endsWith("/atoms")) return {ok: true, status: 200, async json() { return [atom]; }};
      if (url.endsWith("/models")) return {ok: true, status: 200, async json() { return modelCatalog; }};
      if (url.endsWith("/runs") && options.method === "POST") {
        return {ok: true, status: 202, async json() { return {run_id: "run-backoff", scenario_session_id: "session-backoff", job_id: "job-backoff", status: "running"}; }};
      }
      reads += 1;
      if (reads <= 2) {
        return {ok: false, status: 503, headers: {get: () => null}, async json() { return null; }};
      }
      if (reads === 3) {
        return {ok: true, status: 200, headers: {get: () => null}, async json() { return runningDetail; }};
      }
      return {
        ok: false,
        status: 429,
        headers: {get: (name) => name.toLowerCase() === "retry-after" ? "10" : null},
        async json() { return null; },
      };
    },
    confirmImpl: () => true,
    scheduleImpl(callback, delay) {
      nextTimerId += 1;
      scheduled.set(nextTimerId, {callback, delay});
      return nextTimerId;
    },
    cancelScheduleImpl: (timerId) => scheduled.delete(timerId),
    nowImpl: () => now,
    pollTimeoutMs: 4_000,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  await elements.get("run-button").click();

  const runScheduledPoll = async () => {
    assert.equal(scheduled.size, 1);
    const [timerId, timer] = scheduled.entries().next().value;
    scheduled.delete(timerId);
    now += timer.delay;
    await timer.callback();
    return timer.delay;
  };

  assert.equal(await runScheduledPoll(), 0);
  assert.equal(await runScheduledPoll(), 250);
  assert.equal(await runScheduledPoll(), 500);
  assert.equal(await runScheduledPoll(), 250);
  assert.equal(await runScheduledPoll(), 3_000);
  assert.equal(reads, 4);
  assert.equal(scheduled.size, 0);
});

test("dirty atom navigation requires confirmation and preserves the current draft when declined", async () => {
  const {document, elements} = createFakeDocument();
  const atoms = [await catalogAtom("A01"), await catalogAtom("A02")];
  let allowNavigation = false;
  bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return atoms; }}),
    confirmImpl: () => allowNavigation,
  });
  const code = elements.get("access-code");
  code.value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  const buttons = elements.get("atom-navigation").querySelectorAll("button");

  await buttons[1].click();
  assert.match(elements.get("atom-title").textContent, /A01/);
  allowNavigation = true;
  await buttons[1].click();
  assert.match(elements.get("atom-title").textContent, /A02/);
});

test("invalid raw JSON requires confirmation before atom navigation", async () => {
  const {document, elements} = createFakeDocument();
  const atoms = [await catalogAtom("A01"), await catalogAtom("A02")];
  let confirmations = 0;
  bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return atoms; }}),
    confirmImpl: () => { confirmations += 1; return false; },
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("json-mode").click();
  elements.get("json-editor").value = '{"source_text":';
  await elements.get("json-editor").dispatch("input");
  await elements.get("atom-navigation").querySelectorAll("button")[1].click();

  assert.equal(confirmations, 1);
  assert.match(elements.get("atom-title").textContent, /A01/);
  assert.equal(elements.get("json-editor").value, '{"source_text":');
});

test("form mode recovers from schema-invalid object and array values", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A05");
  bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return [atom]; }}),
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("json-mode").click();
  elements.get("json-editor").value = '{"issues":null,"context":"x","target_audience":"y"}';
  await elements.get("json-editor").dispatch("input");

  await assert.doesNotReject(() => elements.get("form-mode").click());
  const errorItem = elements.get("validation-errors").querySelector("li");
  assert.match(errorItem.textContent || errorItem.querySelector("button").textContent, /issues/);
});

test("dynamic unrestricted values can be created and changed through form controls", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A06");
  const controller = bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return [atom]; }}),
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  const addKey = elements.get("input-editor").querySelectorAll("button")
    .find((node) => node.textContent === "Добавить ключ");

  await assert.doesNotReject(() => addKey.click());
  const typeSelect = elements.get("input-editor").querySelectorAll("select")
    .find((node) => node.attributes.get("aria-label")?.includes("key_1"));
  assert.ok(typeSelect);
  assert.equal(typeSelect.focused, true);
  typeSelect.value = "string";
  await typeSelect.dispatch("change");
  assert.equal(getDraftPayload(controller.getSession()).context.key_1, "");
  const productKey = elements.get("input-editor").querySelectorAll("input")
    .find((node) => node.value === "product");
  productKey.value = "__proto__";
  await productKey.dispatch("change");
  const context = getDraftPayload(controller.getSession()).context;
  assert.equal(Object.hasOwn(context, "__proto__"), true);
  assert.equal(context.__proto__, "Сервис");
});

test("removing an array item focuses the item shifted into its place", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A04", {
    input_schema: {
      type: "object",
      properties: {items: {type: "array", items: {type: "string"}}},
      required: ["items"],
      additionalProperties: false,
    },
    example_input: {items: ["первый", "второй", "третий"]},
  });
  bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return [atom]; }}),
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  const removeSecond = elements.get("input-editor").querySelectorAll("button")
    .find((node) => node.textContent === "Удалить элемент 2");

  await removeSecond.click();

  const shiftedThird = elements.get("input-editor").querySelectorAll("textarea")
    .find((node) => node.value === "третий");
  assert.equal(shiftedThird.focused, true);
});

test("integer controls never silently truncate decimal or empty text", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A05");
  const controller = bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return [atom]; }}),
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  const maxQuestions = elements.get("input-editor").querySelectorAll("input")
    .find((node) => node.attributes.get("aria-label") === "max_questions");

  maxQuestions.value = "2.9";
  await maxQuestions.dispatch("input");
  assert.equal(controller.getSession().payload.max_questions, 3);
  assert.match(validateDraft(controller.getSession()).at(-1).message, /целым числом/);
  maxQuestions.value = "";
  await maxQuestions.dispatch("input");
  assert.equal(controller.getSession().payload.max_questions, 3);
  assert.equal(controller.getSession().dirty, true);
});

test("Form numeric controls reject values that cannot round-trip without changing the draft", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A06", {
    input_schema: {
      type: "object",
      properties: {untyped: {}, score: {type: "number"}},
      required: ["untyped", "score"],
      additionalProperties: false,
    },
    example_input: {untyped: 1, score: 0.5},
  });
  const controller = bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return [atom]; }}),
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  await elements.get("fill-example").click();
  const inputByLabel = (label) => elements.get("input-editor").querySelectorAll("input")
    .find((node) => node.attributes.get("aria-label") === label);
  const untyped = inputByLabel("untyped");
  const score = inputByLabel("score");

  untyped.value = "9007199254740993";
  await untyped.dispatch("input");
  score.value = "0.1234567890123456789";
  await score.dispatch("input");

  assert.deepEqual(getDraftPayload(controller.getSession()), {untyped: 1, score: 0.5});
  assert.equal(validateDraft(controller.getSession()).filter(({message}) => /точност/.test(message)).length, 2);

  const rerenderedUntyped = inputByLabel("untyped");
  const rerenderedScore = inputByLabel("score");
  rerenderedUntyped.value = "9007199254740992";
  await rerenderedUntyped.dispatch("input");
  rerenderedScore.value = "0.1";
  await rerenderedScore.dispatch("input");
  assert.deepEqual(getDraftPayload(controller.getSession()), {untyped: 9007199254740992, score: 0.1});
  assert.deepEqual(validateDraft(controller.getSession()), []);
});

test("closed workspace and narrow content rules are explicit in CSS", async () => {
  const css = await readFile(CSS_URL, "utf8");
  assert.match(css, /\[hidden\]\s*\{\s*display:\s*none\s*!important/);
  assert.match(css, /overflow-wrap:\s*anywhere/);
  assert.match(css, /min-width:\s*0/);
});

test("input and prompt tabs are explicitly wired to their tab panels", async () => {
  const html = await readFile(HTML_URL, "utf8");
  assert.match(html, /id="input-tab"[^>]+aria-controls="input-panel"/);
  assert.match(html, /id="prompt-tab"[^>]+aria-controls="prompt-panel"/);
  assert.match(html, /id="input-panel"[^>]+role="tabpanel"[^>]+aria-labelledby="input-tab"/);
  assert.match(html, /id="prompt-panel"[^>]+role="tabpanel"[^>]+aria-labelledby="prompt-tab"/);
});

test("unknown closed-schema fields remain visible in form mode with a path error", async () => {
  const {document, elements} = createFakeDocument();
  const atom = await catalogAtom("A04");
  const controller = bootstrapAtomLab({
    document,
    fetchImpl: async () => ({ok: true, async json() { return [atom]; }}),
    confirmImpl: () => true,
  });
  elements.get("access-code").value = "secret";
  await elements.get("access-form").dispatch("submit");
  setDraftPath(controller.getSession(), ["unexpected"], "Сохранить на экране");
  await elements.get("json-mode").click();
  await elements.get("form-mode").click();
  const paths = [];
  const visit = (node) => {
    if (node.dataset.path) paths.push(node.dataset.path);
    for (const child of node.children) visit(child);
  };
  visit(elements.get("input-editor"));

  assert.equal(paths.includes("unexpected"), true);
  const messages = elements.get("validation-errors").querySelectorAll("li")
    .map((item) => item.textContent || item.querySelector("button")?.textContent);
  assert.equal(messages.some((message) => message.includes("unexpected")), true);
});

test("malformed model catalog closed values fail closed before becoming selectable", async () => {
  const atom = await catalogAtom("A01");
  const validItem = {
    model_id: "gpt-supported",
    compatibility: "compatible",
    reason: "confirmed_openai_text_gpt",
    reasoning_supported: true,
    allowed_reasoning_efforts: ["low", "high"],
    provenance: {},
  };
  const baseCatalog = {
    items: [validItem],
    snapshot_id: "snapshot-1",
    last_success_at: "2026-09-20T10:00:00Z",
    stale: false,
    refresh_status: "current",
    error: null,
  };
  for (const malformedCatalog of [
    {...baseCatalog, items: [{...validItem, model_id: 42}]},
    {...baseCatalog, items: [{...validItem, allowed_reasoning_efforts: ["turbo"]}]},
    {...baseCatalog, refresh_status: "invented"},
  ]) {
    const {document, elements} = createFakeDocument();
    bootstrapAtomLab({
      document,
      fetchImpl: async (url) => ({
        ok: true,
        async json() { return url.endsWith("/atoms") ? [atom] : malformedCatalog; },
      }),
      confirmImpl: () => true,
    });
    elements.get("access-code").value = "secret";
    await elements.get("access-form").dispatch("submit");

    assert.equal(elements.get("model-select").disabled, true);
    assert.equal(elements.get("run-button").disabled, true);
    assert.match(elements.get("model-catalog-warning").textContent, /некорректный ответ/);
  }
});

test("model options distinguish supported, unsupported, unknown, and incompatible choices", () => {
  assert.deepEqual(describeModelOption({
    model_id: "gpt-supported",
    compatibility: "compatible",
    reason: "confirmed_openai_text_gpt",
    reasoning_supported: true,
    allowed_reasoning_efforts: ["low", "high"],
    provenance: {},
  }), {
    modelId: "gpt-supported",
    selectable: true,
    compatibility: "compatible",
    reason: "confirmed_openai_text_gpt",
    reasoningMode: "supported",
    allowedEfforts: ["low", "high"],
  });
  assert.equal(describeModelOption({
    model_id: "gpt-no-reasoning",
    compatibility: "compatible",
    reason: "confirmed_openai_text_gpt",
    reasoning_supported: false,
    allowed_reasoning_efforts: null,
    provenance: {},
  }).reasoningMode, "unsupported");
  assert.equal(describeModelOption({
    model_id: "gpt-unknown",
    compatibility: "compatible",
    reason: "confirmed_openai_text_gpt",
    reasoning_supported: true,
    allowed_reasoning_efforts: null,
    provenance: {},
  }).reasoningMode, "unknown");
  assert.equal(describeModelOption({
    model_id: "not-for-this-path",
    compatibility: "unsupported",
    reason: "override_unsupported",
    reasoning_supported: null,
    allowed_reasoning_efforts: null,
    provenance: {},
  }).selectable, false);
  const unknown = describeModelOption({
    model_id: "not-confirmed",
    compatibility: "unknown",
    reason: "litellm_compatibility_incomplete",
    reasoning_supported: null,
    allowed_reasoning_efforts: null,
    provenance: {},
  });
  assert.equal(unknown.compatibility, "unknown");
  assert.equal(unknown.reason, "litellm_compatibility_incomplete");
});

test("a run submission freezes the current draft and uses the exact backend field names", async () => {
  const session = createDraftSession(await catalogAtom("A01"));
  replaceWithExample(session);
  const submission = createRunSubmission(session, {
    modelId: "gpt-supported",
    reasoningEffort: "high",
    idempotencyKey: "submission-1",
  });

  setDraftPath(session, ["source_text"], "Изменённый черновик");

  assert.equal(submission.idempotencyKey, "submission-1");
  assert.deepEqual(submission.body, {
    atom_id: "A01",
    input: EXAMPLES.A01,
    prompt: "Базовый промпт A01",
    model_id: "openai/gpt-supported",
    reasoning_effort: "high",
    preset_ref: null,
  });
  assert.equal(submission.snapshot.input.source_text, "Срок — 30 сентября");
});

test("accepted and detail response parsers reject incomplete or unknown lifecycle envelopes", () => {
  assert.equal(parseAcceptedRun({status: "queued"}), null);
  assert.equal(parseAcceptedRun({run_id: "run", scenario_session_id: "session", job_id: "job", status: "invented"}), null);
  assert.deepEqual(parseAcceptedRun({run_id: "run", scenario_session_id: "session", job_id: "job", status: "queued"}), {
    run_id: "run", scenario_session_id: "session", job_id: "job", status: "queued",
  });
  assert.equal(parseRunDetail({run_id: "run", status: "succeeded"}, "run"), null);
  assert.equal(parseRunDetail({run_id: "other", status: "running", snapshot: {}, runtime_ids: {}, result: null, diagnostics: {}}, "run"), null);
  const runtimeIds = {scenario_session_id: "session", job_id: "job", action_run_id: null, artifact_id: null};
  const diagnostics = {error_code: null, duration_ms: null, requested_model_id: "openai/gpt", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 0, physical_calls: 0, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false};
  const detail = {run_id: "run", status: "running", snapshot: {atom_id: "A01"}, runtime_ids: runtimeIds, result: null, diagnostics, created_at: "2026-09-20T10:00:00Z", started_at: null, finished_at: null};
  assert.equal(parseRunDetail({...detail, runtime_ids: {}}, "run"), null);
  assert.equal(parseRunDetail({...detail, diagnostics: {...diagnostics, provider_calls: {}}}, "run"), null);
  assert.equal(parseRunDetail({...detail, diagnostics: {...diagnostics, requested_reasoning_effort: "turbo"}}, "run"), null);
  assert.equal(parseRunDetail({...detail, diagnostics: {...diagnostics, provider_calls_truncated: undefined}}, "run"), null);
  assert.equal(parseRunDetail({...detail, diagnostics: {...diagnostics, provider_calls: [{provider_call_id: "call"}]}}, "run"), null);
  assert.equal(parseRunDetail({...detail, status: "succeeded"}, "run"), null);
  assert.equal(parseRunDetail({...detail, result: {value: "unexpected"}}, "run"), null);
  assert.equal(parseRunDetail({...detail, snapshot: {atom_id: "A99"}}, "run"), null);
  assert.deepEqual(parseRunDetail(detail, "run"), {
    run_id: "run", status: "running", snapshot: {atom_id: "A01"}, runtime_ids: runtimeIds, result: null, diagnostics,
  });
  assert.deepEqual(parseRunDetail({...detail, status: "succeeded", result: {value: "ok"}}, "run"), {
    run_id: "run", status: "succeeded", snapshot: {atom_id: "A01"}, runtime_ids: runtimeIds, result: {value: "ok"}, diagnostics,
  });
});

test("browser polling timeout is elapsed-time based and does not reinterpret the run status", () => {
  assert.equal(pollingTimedOut(1_000, 90_999, 90_000), false);
  assert.equal(pollingTimedOut(1_000, 91_000, 90_000), true);
});

test("preset and history parsers fail closed around immutable and paginated contracts", () => {
  const configuration = {
    name: "Набор",
    description: "Описание",
    atom_id: "A01",
    base_action_config_id: "config.a01",
    schema_refs: {
      input: {schema_ref: "input.A01", version: 1},
      output: {schema_ref: "output.A01", version: 1},
    },
    prompt: "Промпт",
    prompt_ref: "prompt.a01",
    model_id: "openai/gpt-5",
    reasoning_effort: "high",
    fixed_fields: ["fields"],
    example_input: {source_text: "Текст", fields: []},
    source_run_id: "run-1",
  };
  const detail = {...configuration, preset_id: "preset-1", version: 1, created_at: "2026-09-23T00:00:00Z"};
  assert.deepEqual(parsePresetVersion(detail, "preset-1", 1), detail);
  assert.equal(parsePresetVersion({...detail, atom_id: "A99"}, "preset-1", 1), null);
  assert.equal(parsePresetVersion({...detail, fixed_fields: ["fields", "fields"]}), null);
  assert.ok(parsePresetList({items: [{
    preset_id: "preset-1", latest_version: 2, name: "Набор", description: "Описание",
    atom_id: "A01", created_at: "2026-09-23T00:00:00Z", updated_at: "2026-09-23T01:00:00Z",
  }], next_cursor: "next"}));
  assert.equal(parsePresetList({items: [], next_cursor: 1}), null);
  assert.equal(parsePresetList({items: [{
    preset_id: "preset-1", latest_version: 2, name: "Набор", description: "Описание",
    atom_id: "A99", created_at: "2026-09-23T00:00:00Z", updated_at: "2026-09-23T01:00:00Z",
  }], next_cursor: null}), null);
  assert.ok(parsePresetVersionList({items: [{
    preset_id: "preset-1", version: 1, name: "Набор", description: "Описание",
    atom_id: "A01", created_at: "2026-09-23T00:00:00Z",
  }], next_cursor: null}));
  assert.ok(parsePresetExport({format_version: 1, preset_id: "preset-1", version: 1, configuration}, "preset-1", 1));
  assert.equal(parsePresetExport({format_version: 2, preset_id: "preset-1", version: 1, configuration}, "preset-1", 1), null);
  assert.ok(parseRunList({items: [{
    run_id: "run-1", status: "failed", atom_id: "A01", model_id: "openai/gpt-5",
    preset_id: null, preset_version: null, created_at: "2026-09-23T00:00:00Z",
    started_at: null, finished_at: "2026-09-23T00:01:00Z",
  }], next_cursor: null}));
  assert.equal(parseRunList({items: [{run_id: "run-1", status: "mystery"}], next_cursor: null}), null);
  assert.equal(parseRunList({items: [{
    run_id: "run-1", status: "failed", atom_id: "A99", model_id: "openai/gpt-5",
    preset_id: null, preset_version: null, created_at: "2026-09-23T00:00:00Z",
    started_at: null, finished_at: "2026-09-23T00:01:00Z",
  }], next_cursor: null}), null);
  assert.equal(presetContractMatchesAtom(configuration, configuration), true);
  assert.equal(presetContractMatchesAtom(configuration, {...configuration, base_action_config_id: "config.changed"}), false);
  assert.equal(presetContractMatchesAtom(configuration, {...configuration, prompt_ref: "prompt.changed"}), false);
  assert.equal(presetContractMatchesAtom(configuration, {
    ...configuration,
    schema_refs: {...configuration.schema_refs, input: {...configuration.schema_refs.input, version: 2}},
  }), false);
});
