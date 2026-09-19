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
  createDraftSession,
  getDraftPayload,
  hasDraftPath,
  omitDraftPath,
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

function createFakeDocument() {
  const ids = [
    "access-form", "access-code", "access-panel", "workspace", "status",
    "atom-navigation", "atom-title", "atom-action-type", "atom-description",
    "atom-transformation", "atom-passport", "input-schema", "output-schema",
    "input-tab", "prompt-tab", "input-panel", "prompt-panel", "form-mode", "json-mode", "input-editor",
    "json-panel", "json-editor", "json-error", "prompt-editor", "fill-example", "reset-prompt",
    "draft-state", "validation-errors", "result-placeholder", "presets-button",
    "history-button",
  ];
  const elements = new Map(ids.map((id) => [id, new FakeElement(id.endsWith("editor") ? "textarea" : "div", id)]));
  elements.get("access-form").tagName = "FORM";
  elements.get("access-code").tagName = "INPUT";
  for (const id of ["input-tab", "prompt-tab", "form-mode", "json-mode", "fill-example", "reset-prompt", "presets-button", "history-button"]) {
    elements.get(id).tagName = "BUTTON";
  }
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

test("closed workspace and narrow content rules are explicit in CSS", async () => {
  const css = await readFile(CSS_URL, "utf8");
  assert.match(css, /\[hidden\]\s*\{\s*display:\s*none\s*!important/);
  assert.match(css, /overflow-wrap:\s*anywhere/);
  assert.match(css, /min-width:\s*0/);
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
