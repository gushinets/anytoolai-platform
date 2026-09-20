import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

const REPO_ROOT = new URL("../../../", import.meta.url);
const STATIC_ROOT = new URL(
  "apps/platform-api/src/anytoolai_platform_api/static/atom_lab/",
  REPO_ROOT,
);

async function schema(name) {
  return JSON.parse(await readFile(new URL(`configs/kernel/schemas/${name}`, REPO_ROOT), "utf8"));
}

const A05 = {
  atom_id: "A05",
  action_type: "kernel.generate_questions",
  base_action_config_id: "config.a05",
  prompt: "Базовый промпт A05",
  prompt_ref: "prompt.a05",
  input_schema: await schema("generate_questions_input.schema.json"),
  output_schema: {type: "object"},
  schema_refs: {input: {schema_ref: "input.A05", version: 1}, output: {schema_ref: "output.A05", version: 1}},
  description: "Формирует уточняющие вопросы по найденным проблемам.",
  example_input: {issues: [{category: "сроки", description: "Нет даты", severity: "high"}], context: "Оценка", target_audience: "Заказчик", max_questions: 3},
};

const A06 = {
  atom_id: "A06",
  action_type: "kernel.compose_persuasive_text",
  base_action_config_id: "config.a06",
  prompt: "Базовый промпт A06",
  prompt_ref: "prompt.a06",
  input_schema: await schema("compose_persuasive_text_input.schema.json"),
  output_schema: {type: "object"},
  schema_refs: {input: {schema_ref: "input.A06", version: 1}, output: {schema_ref: "output.A06", version: 1}},
  description: "Собирает убедительный текст из контекста.",
  example_input: {context: {product: "Сервис"}, objective: "Пилот"},
};

const A11 = {
  atom_id: "A11",
  action_type: "kernel.compare_classify",
  base_action_config_id: "config.a11",
  prompt: "Базовый промпт A11",
  prompt_ref: "prompt.a11",
  input_schema: await schema("compare_classify_input.schema.json"),
  output_schema: {type: "object"},
  schema_refs: {input: {schema_ref: "input.A11", version: 1}, output: {schema_ref: "output.A11", version: 1}},
  description: "Сравнивает и классифицирует текст.",
  example_input: {subject_text: "Пилот", reference_text: "Эталон", categories: ["да", "нет"], criteria: [{id: "scope", description: "Границы"}]},
};

function catalog() {
  return Array.from({length: 11}, (_, index) => {
    if (index === 4) return A05;
    if (index === 5) return A06;
    if (index === 10) return A11;
    return {...A05, atom_id: `A${String(index + 1).padStart(2, "0")}`, action_type: `kernel.atom_${index + 1}`};
  });
}

async function openLab(page) {
  await page.route("http://atom-lab.test/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/v1/atom-lab/atoms") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(catalog())});
      return;
    }
    const file = pathname === "/atom-lab/" ? "index.html" : pathname.split("/").at(-1);
    const contentType = file.endsWith(".css") ? "text/css" : file.endsWith(".mjs") ? "text/javascript" : "text/html";
    await route.fulfill({contentType, body: await readFile(new URL(file, STATIC_ROOT))});
  });
  await page.goto("http://atom-lab.test/atom-lab/");
}

async function unlockAtom(page, atomId) {
  await openLab(page);
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await page.getByRole("button", {name: new RegExp(atomId)}).click();
}

async function importJson(page, payload) {
  await page.locator("#json-mode").click();
  await page.locator("#json-editor").fill(JSON.stringify(payload));
  await page.locator("#form-mode").click();
}

test("protected shell, dynamic values, invalid types, numbers, focus, and narrow layout work in Chromium", async ({page}) => {
  await page.setViewportSize({width: 375, height: 900});
  page.on("dialog", (dialog) => dialog.accept());
  await openLab(page);
  await expect(page.locator("#workspace")).toBeHidden();
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await expect(page.locator("#atom-navigation button")).toHaveCount(11);
  await expect(page.locator("#workspace")).toBeVisible();

  await page.getByRole("button", {name: /A05/}).click();
  await page.locator("#fill-example").click();
  const integer = page.getByLabel("max_questions");
  await integer.fill("2.9");
  await expect(page.locator("#validation-errors")).toContainText("целым числом");
  await integer.fill("3");
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

  await page.locator("#json-mode").click();
  await page.locator("#json-editor").fill('{"issues":null,"context":"x","target_audience":"y"}');
  await page.locator("#form-mode").click();
  await expect(page.locator("#validation-errors")).toContainText("issues");

  await page.getByRole("button", {name: /A06/}).click();
  await page.locator("#fill-example").click();
  await page.getByRole("button", {name: "Добавить ключ"}).first().click();
  const type = page.getByLabel(/Тип значения.*key_1/);
  await expect(type).toBeFocused();
  await type.selectOption("string");
  await expect(page.getByRole("textbox", {name: "Значение «key_1»", exact: true})).toBeVisible();
});

test("unrestricted strings preserve line breaks through form edits", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {notes: "first\nsecond"}, objective: "pilot"});

  const notes = page.getByRole("textbox", {name: "Значение «notes»", exact: true});
  await expect(notes).toHaveJSProperty("tagName", "TEXTAREA");
  await expect(notes).toHaveValue("first\nsecond");
  await notes.fill("first\nsecond!");
  await page.locator("#json-mode").click();

  await expect(page.locator("#json-editor")).toHaveValue(/first\\nsecond!/);
});

test("JSON numbers that cannot round-trip are rejected without replacing the accepted draft", async ({page}) => {
  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#json-mode").click();
  const unsafeJson = '{"context":{"id":9007199254740993},"objective":"pilot"}';
  await page.locator("#json-editor").fill(unsafeJson);

  await expect(page.locator("#json-error")).toContainText("точност");
  await expect(page.locator("#json-editor")).toHaveValue(unsafeJson);
  await page.locator("#form-mode").click();
  await expect(page.locator("#json-panel")).toBeVisible();
});

test("omitting a container clears invalid descendant input errors", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {}, objective: "pilot", constraints: {length: 900}});

  await page.getByLabel("length").fill("2.9");
  await expect(page.locator("#validation-errors")).toContainText("целым числом");
  await page.getByRole("button", {name: "Не передавать «constraints»"}).click();
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await page.locator("#json-mode").click();

  await expect(page.locator("#json-panel")).toBeVisible();
  await expect(page.locator("#json-editor")).not.toHaveValue(/constraints/);
});

test("literal dotted and bracketed keys have identities distinct from nested paths", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {
    context: {"a.b": 1, a: {b: 2}, "items[0]": 3, items: [4]},
    objective: "pilot",
  });

  const idsAreUnique = await page.locator("#input-editor [id]").evaluateAll((nodes) => {
    const ids = nodes.map((node) => node.id);
    return ids.length === new Set(ids).size;
  });
  expect(idsAreUnique).toBe(true);

  await page.getByLabel("Значение «a.b»", {exact: true}).fill("");
  await page.getByLabel("Значение «b»", {exact: true}).fill("3");
  await page.getByLabel("Значение «items[0]»", {exact: true}).fill("");
  await page.getByLabel("Элемент 1", {exact: true}).fill("5");
  await expect(page.locator("#validation-errors li")).toHaveCount(2);
  await page.locator("#json-mode").click();

  await expect(page.locator("#input-editor")).toBeVisible();
});

test("renaming a dynamic key rebases its recoverable input error", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {amount: 1}, objective: "pilot"});

  await page.getByLabel("Значение «amount»", {exact: true}).fill("");
  await expect(page.locator("#validation-errors")).toContainText("context.amount");
  const key = page.getByLabel("Ключ context.amount", {exact: true});
  await key.fill("total");
  await key.press("Tab");

  await expect(page.locator("#validation-errors")).toContainText("context.total");
  await expect(page.locator("#validation-errors")).not.toContainText("context.amount");
  await page.getByLabel("Значение «total»", {exact: true}).fill("2");
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await page.locator("#json-mode").click();

  await expect(page.locator("#json-panel")).toBeVisible();
  await expect(page.locator("#json-editor")).toHaveValue(/"total": 2/);
});

test("duplicate dynamic-key rename restores the key shown by the accepted draft", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {a: 1, b: 2}, objective: "pilot"});

  const key = page.getByLabel("Ключ context.b", {exact: true});
  await key.fill("a");
  await key.press("Tab");

  await expect(key).toHaveValue("b");
  expect(await page.locator("input.dynamic-key").evaluateAll(
    (nodes) => nodes.map((node) => node.value),
  )).toEqual(["a", "b"]);
});

test("collection validation links focus to its add-item recovery control", async ({page}) => {
  await unlockAtom(page, "A11");
  await importJson(page, {
    subject_text: "Пилот",
    reference_text: "Эталон",
    categories: [],
    criteria: [{id: "scope", description: "Границы"}],
  });
  const addCategory = page.locator('[data-path="categories"]')
    .getByRole("button", {name: "Добавить элемент"});

  await page.getByRole("button", {name: /^categories:/}).click();

  await expect(addCategory).toBeFocused();
});

test("recovering a schema-invalid scalar clears its ARIA error state", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {}, objective: 42});

  const recovery = page.getByLabel("objective, JSON-значение", {exact: true});
  await expect(recovery).toHaveAttribute("aria-invalid", "true");
  await recovery.fill('"pilot"');
  await recovery.press("Tab");

  const objective = page.getByLabel("objective", {exact: true});
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await expect(objective).not.toHaveAttribute("aria-invalid", "true");
  await expect(objective).not.toHaveAttribute("aria-describedby", /.+/);
});

test("correcting a control clears validation-owned ARIA attributes", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {}, objective: "pilot", constraints: {length: 900}});

  const length = page.getByLabel("length");
  await length.fill("2.9");
  await expect(length).toHaveAttribute("aria-invalid", "true");
  await length.fill("3");

  await expect(page.locator("#validation-errors")).toBeEmpty();
  await expect(length).not.toHaveAttribute("aria-invalid", "true");
  await expect(length).not.toHaveAttribute("aria-describedby", /.+/);
});

test("adding a compound field focuses its first rendered descendant control", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {}, objective: "pilot"});

  await page.getByRole("button", {name: "Добавить поле «constraints»"}).click();

  await expect(page.getByRole("button", {name: "Добавить поле «tone»"})).toBeFocused();
});

test("adding a compound array item focuses its first rendered descendant control", async ({page}) => {
  await unlockAtom(page, "A05");
  await importJson(page, {issues: [], context: "x", target_audience: "y"});

  await page.getByRole("button", {name: "Добавить элемент"}).click();

  await expect(page.getByRole("button", {name: "Добавить поле «category»"})).toBeFocused();
});
