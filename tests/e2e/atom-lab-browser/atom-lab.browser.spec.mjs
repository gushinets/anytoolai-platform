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

function expectedAtomContract(atom) {
  const {action_type, base_action_config_id, prompt_ref, schema_refs, input_schema, output_schema} = atom;
  return {action_type, base_action_config_id, prompt_ref, schema_refs, input_schema, output_schema};
}

function snapshotAtomContract(atom) {
  return {
    atom_id: atom.atom_id,
    action: {type: atom.action_type, config_id: atom.base_action_config_id},
    prompt: {ref: atom.prompt_ref},
    schemas: {
      input: {ref: atom.schema_refs.input.schema_ref, version: atom.schema_refs.input.version, content: atom.input_schema},
      output: {ref: atom.schema_refs.output.schema_ref, version: atom.schema_refs.output.version, content: atom.output_schema},
    },
  };
}

const MODEL_CATALOG = {
  items: [
    {model_id: "gpt-supported", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: true, allowed_reasoning_efforts: ["low", "high"], provenance: {}},
    {model_id: "gpt-no-reasoning", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}},
    {model_id: "gpt-unknown", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: true, allowed_reasoning_efforts: null, provenance: {}},
    {model_id: "gpt-unknown-compatibility", compatibility: "unknown", reason: "litellm_compatibility_incomplete", reasoning_supported: null, allowed_reasoning_efforts: null, provenance: {}},
    {model_id: "gpt-unsupported", compatibility: "unsupported", reason: "override_unsupported", reasoning_supported: null, allowed_reasoning_efforts: null, provenance: {}},
  ],
  snapshot_id: "catalog-snapshot-1",
  last_success_at: "2026-09-19T10:00:00Z",
  stale: true,
  refresh_status: "current",
  error: null,
};

function historyDetail({
  runId = "run-library",
  input = A06.example_input,
  prompt = "Промпт запуска",
  reasoningEffort = "high",
} = {}) {
  return {
    run_id: runId,
    status: "succeeded",
    snapshot: {
      atom_id: "A06",
      scenario: {id: "lab.a06", version: 1},
      workflow: {id: "lab.a06", version: 1, step_id: "run", definition: {}},
      action: {type: A06.action_type, definition_version: 1, definition: {}, config_id: A06.base_action_config_id, config_schema_version: 1, config_definition: {}},
      prompt: {ref: A06.prompt_ref, version: 1, base: A06.prompt, content: prompt},
      schemas: {
        input: {ref: A06.schema_refs.input.schema_ref, version: 1, content: A06.input_schema},
        output: {ref: A06.schema_refs.output.schema_ref, version: 1, content: A06.output_schema},
      },
      input,
      provider: {policy_ref: "policy", policy: {}, model_id: "openai/gpt-supported", reasoning_effort: reasoningEffort, capability_snapshot_id: "models-1", capability_provenance: {}},
      preset: {id: null, version: null},
      execution_definition_hash: "hash",
    },
    runtime_ids: {scenario_session_id: "session-library", job_id: "job-library", action_run_id: "action-library", artifact_id: "artifact-library"},
    result: {summary: "Готово"},
    diagnostics: {
      error_code: null, duration_ms: 900, requested_model_id: "openai/gpt-supported",
      requested_reasoning_effort: reasoningEffort, response_model_id: "gpt-supported",
      validation_attempts: 2, transport_attempts: 1, physical_calls: 1,
      succeeded_first_attempt: false, provider_calls: [], provider_calls_truncated: false,
      debug_artifacts: [], debug_artifacts_truncated: false,
    },
    created_at: "2026-09-23T08:00:00Z",
    started_at: "2026-09-23T08:00:01Z",
    finished_at: "2026-09-23T08:00:02Z",
  };
}

async function editPreset(page) {
  if (await page.locator("#presets-panel").isHidden()) await page.locator("#presets-button").click();
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
  if (await page.locator("#preset-editor-form").isVisible()) return;
  await page.locator(await page.locator("#edit-preset").isVisible() ? "#edit-preset" : "#new-preset").click();
}

async function showWorkbench(page) {
  if (await page.locator("#request-response").isHidden()) await page.locator("#workbench-button").click();
}

async function openNewPresetFromExample(page) {
  await showWorkbench(page);
  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await editPreset(page);
}

async function submitNewPresetFromExample(page, name) {
  await openNewPresetFromExample(page);
  await page.locator("#preset-name").fill(name);
  await editPreset(page);
  await page.locator("#save-preset").click();
}

async function openLab(page, {models = () => MODEL_CATALOG, accessRequired = true} = {}) {
  await page.route("http://atom-lab.test/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/v1/atom-lab/atoms") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(catalog())});
      return;
    }
    if (pathname === "/v1/atom-lab/models") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(await models())});
      return;
    }
    if (pathname.startsWith("/v1/")) {
      await route.fallback();
      return;
    }
    const file = pathname === "/atom-lab/" ? "index.html" : pathname.split("/").at(-1);
    const contentType = file.endsWith(".css") ? "text/css" : file.endsWith(".mjs") ? "text/javascript" : "text/html";
    let body = await readFile(new URL(file, STATIC_ROOT), "utf8");
    if (file === "index.html" && !accessRequired) {
      body = body.replace('id="access-panel"', 'id="access-panel" data-auto-open="true" hidden');
    }
    await route.fulfill({contentType, body, headers: file === "index.html"
      ? {"Content-Security-Policy": "frame-ancestors 'none'"} : {}});
  });
  await page.goto("http://atom-lab.test/atom-lab/");
}

async function unlockAtom(page, atomId, options) {
  await openLab(page, options);
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await chooseAtom(page, atomId);
}

async function chooseAtom(page, atomId) {
  await expect(page.locator("#workspace")).toBeVisible();
  const picker = page.locator("#atom-picker");
  if (await picker.isVisible() && await picker.getAttribute("aria-expanded") === "false") await picker.click();
  await page.locator("#atom-navigation").getByRole("button", {name: new RegExp(atomId)}).click();
}

async function importJson(page, payload) {
  await showWorkbench(page);
  await page.locator("#json-mode").click();
  await page.locator("#json-editor").fill(JSON.stringify(payload));
  await page.locator("#form-mode").click();
}

test("preset and history libraries stay inert before access is unlocked", async ({page}) => {
  let protectedReads = 0;
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname === "/v1/atom-lab/presets" || pathname === "/v1/atom-lab/runs") protectedReads += 1;
  });
  await openLab(page);

  await expect(page.locator("#presets-button")).toBeDisabled();
  await expect(page.locator("#history-button")).toBeDisabled();
  await page.locator("#presets-button").dispatchEvent("click");
  await page.locator("#history-button").dispatchEvent("click");

  await expect(page.locator("#presets-panel")).toBeHidden();
  await expect(page.locator("#history-panel")).toBeHidden();
  expect(protectedReads).toBe(0);
});

for (const origin of ["http://untrusted.test", "http://atom-lab.test"]) {
  test(`the no-code shell rejects framing by ${origin}`, async ({page}) => {
    await openLab(page, {accessRequired: false});
    await expect(page.locator("#atom-navigation button")).toHaveCount(11);
    let protectedRequests = 0;
    page.on("request", request => {
      if (new URL(request.url()).pathname.startsWith("/v1/atom-lab/")) protectedRequests += 1;
    });
    await page.route(`${origin}/frame`, route => route.fulfill({
      contentType: "text/html",
      body: '<iframe style="opacity:0.01;width:1200px;height:900px" src="http://atom-lab.test/atom-lab/"></iframe>',
    }));
    const refused = page.waitForEvent("console", message => message.text().includes("frame-ancestors"));
    await page.goto(`${origin}/frame`);
    await refused;
    await expect(page.frameLocator("iframe").locator("#workspace")).toHaveCount(0);
    expect(protectedRequests).toBe(0);
  });
}

test("protected shell, dynamic values, invalid types, numbers, focus, and narrow layout work in Chromium", async ({page}) => {
  await page.setViewportSize({width: 375, height: 900});
  page.on("dialog", (dialog) => dialog.accept());
  await openLab(page);
  await expect(page.locator("#workspace")).toBeHidden();
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await expect(page.locator("#atom-navigation button")).toHaveCount(11);
  await expect(page.locator("#atom-count")).toHaveText("11");
  await expect(page.locator("#status")).toBeHidden();
  await expect(page.locator("#workspace")).toBeVisible();

  await chooseAtom(page, "A05");
  await page.locator("#fill-example").click();
  const integer = page.getByLabel("Максимум вопросов", {exact: true});
  await integer.fill("2.9");
  await expect(page.locator("#validation-errors")).toContainText("целым числом");
  await integer.fill("3");
  await expect.poll(() => page.evaluate(() => ({
    documentWidth: document.documentElement.scrollWidth,
    overflowingElements: [...document.querySelectorAll("body *")]
      .map((element) => {
        const rect = element.getBoundingClientRect();
        return {
          selector: `${element.tagName.toLowerCase()}#${element.id}.${element.className}`,
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          text: element.textContent?.trim().slice(0, 80),
        };
      })
      .filter(({left, right}) => left < 0 || right > window.innerWidth),
    viewportWidth: window.innerWidth,
  }))).toEqual({documentWidth: 375, overflowingElements: [], viewportWidth: 375});

  await page.locator("#json-mode").click();
  await page.locator("#json-editor").fill('{"issues":null,"context":"x","target_audience":"y"}');
  await page.locator("#form-mode").click();
  await expect(page.locator("#validation-errors")).toContainText("issues");

  await chooseAtom(page, "A06");
  await page.getByRole("textbox", {name: "Цель", exact: true}).fill("Пилот");
  const emptyObject = page.getByRole("button", {name: "Передать пустой объект «Контекст»"});
  await page.locator("#validation-errors").getByRole("button", {name: /^context:/}).click();
  await expect(emptyObject).toBeFocused();
  await emptyObject.click();
  await expect(page.getByRole("button", {name: "Добавить ключ"})).toBeFocused();
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await page.locator("#fill-example").click();
  await page.getByRole("button", {name: "Добавить ключ"}).first().click();
  const type = page.getByLabel(/Тип значения.*key_1/);
  await expect(type).toBeFocused();
  await type.selectOption("string");
  await expect(page.getByRole("textbox", {name: "Значение «key_1»", exact: true})).toBeVisible();
});

test("compact extraction controls stay aligned and preserve false versus omitted flags", async ({page}) => {
  const extraction = {
    ...catalog()[0],
    input_schema: await schema("extract_input.schema.json"),
    example_input: {
      source_text: "Срок — 20 ноября 2026 года. Бюджет — 120000 рублей.",
      fields: [
        {name: "deadline", type: "date", description: "Срок завершения проекта.", required: false},
        {name: "budget", type: "number", description: "Бюджет проекта в рублях.", required: true},
      ],
      strict: false,
    },
  };
  await openLab(page);
  await page.route("http://atom-lab.test/v1/atom-lab/atoms", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify(catalog().map((atom) => atom.atom_id === "A01" ? extraction : atom)),
  }));
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  const source = page.getByRole("textbox", {name: "Исходный текст"});
  await expect(source).toHaveValue("");
  await page.locator("#json-mode").click();
  expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual({});
  await page.locator("#form-mode").click();
  await source.fill("Тест");
  await source.fill("");
  await page.getByRole("button", {name: "Добавить элемент", exact: true}).click();
  await expect(page.getByLabel("Обязательное поле", {exact: true})).toHaveValue("");
  await page.getByLabel("Обязательное поле", {exact: true}).selectOption("false");
  await page.locator("#json-mode").click();
  expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual({source_text: "", fields: [{required: false}]});
  await page.locator("#form-mode").click();
  page.once("dialog", dialog => dialog.accept());
  await page.locator("#fill-example").click();
  const firstRow = page.locator("details.array-item").first();
  if (await firstRow.getAttribute("open") === null) await firstRow.locator("summary").click();

  for (const width of [1440, 390]) {
    await page.setViewportSize({width, height: 900});
    const alignment = await page.getByLabel("Тип", {exact: true}).first().evaluate((select) => {
      const control = select.getBoundingClientRect();
      const label = select.labels[0].getBoundingClientRect();
      return {beside: label.right <= control.left, sameRow: label.top < control.bottom && label.bottom > control.top};
    });
    expect(alignment).toEqual({beside: true, sameRow: true});
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
  }
  const required = page.getByLabel("Обязательное поле", {exact: true}).first();
  await required.selectOption("true");
  await expect(required).toHaveValue("true");
  await page.getByLabel("Тип", {exact: true}).first().selectOption("string");
  await page.getByLabel("Требовать все обязательные поля", {exact: true}).check();
  await expect(page.getByLabel("Требовать все обязательные поля", {exact: true})).toHaveAccessibleDescription(/отмеченные как обязательные/);
  await page.getByLabel("Требовать все обязательные поля", {exact: true}).uncheck();
  await page.locator("#json-mode").click();
  const payload = JSON.parse(await page.locator("#json-editor").inputValue());
  expect(payload.strict).toBe(false);
  expect(payload.fields[0]).toMatchObject({required: true, type: "string"});
  await page.locator("#form-mode").click();
  await page.getByRole("button", {name: "Не передавать «Требовать все обязательные поля»", exact: true}).click();
  await page.locator("#json-mode").click();
  expect(JSON.parse(await page.locator("#json-editor").inputValue())).not.toHaveProperty("strict");
});

test("data-flow passport shows long contracts and discloses exact versions and full schemas", async ({page}) => {
  const longKey = "optional_" + "contract_field_".repeat(8) + "name";
  const outputSchema = await schema("extract_output.schema.json");
  outputSchema.properties[longKey] = {type: "string"};
  const extraction = {
    ...catalog()[0],
    input_schema: await schema("extract_input.schema.json"),
    output_schema: outputSchema,
    schema_refs: {input: {schema_ref: "contract.input", version: 2}, output: {schema_ref: "contract.output", version: 3}},
  };
  await openLab(page);
  await page.route("http://atom-lab.test/v1/atom-lab/atoms", (route) => route.fulfill({
    contentType: "application/json",
    body: JSON.stringify(catalog().map((atom) => atom.atom_id === "A01" ? extraction : atom)),
  }));
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await expect(page.locator("#input-contract-fields .contract-field-list-required code")).toHaveText(["source_text", "fields"]);
  await expect(page.locator("#input-contract-fields")).toContainText("strict опционально");
  await expect(page.locator("#output-contract-fields .contract-field-list-required code")).toHaveText(["values", "missing_fields"]);
  await expect(page.locator("#output-contract-fields")).toContainText("confidence опционально");
  await expect(page.locator("#input-schema-ref")).toHaveText("contract.input");
  await expect(page.locator("#output-schema-version")).toHaveText("Версия 3");
  await expect(page.locator("#input-contract-fields")).toBeVisible();
  const longField = page.locator("#output-contract-fields code").filter({hasText: longKey});
  await expect(longField).toBeVisible();
  await expect(page.locator("#input-schema-ref")).toBeHidden();
  await expect(page.locator("#output-schema-version")).toBeHidden();
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({width, height: 900});
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    expect(await longField.evaluate(field => {
      const box = field.getBoundingClientRect();
      const panel = field.closest(".contract-part").getBoundingClientRect();
      return box.left >= panel.left && box.right <= panel.right;
    })).toBe(true);
    for (const direction of ["input", "output"]) {
      const fieldTops = await page.locator(`#${direction}-contract-fields .contract-field-list-required code`)
        .evaluateAll((fields) => fields.map((field) => field.getBoundingClientRect().top));
      expect(Math.max(...fieldTops) - Math.min(...fieldTops)).toBeLessThan(1);
    }
  }
  await page.getByText("Схемы и версии", {exact: true}).click();
  await page.getByText("JSON Schema входа", {exact: true}).click();
  await page.getByText("JSON Schema выхода", {exact: true}).click();
  await expect(page.locator("#input-schema")).toHaveText(JSON.stringify(extraction.input_schema, null, 2));
  await expect(page.locator("#output-schema")).toHaveText(JSON.stringify(extraction.output_schema, null, 2));
  const picker = page.locator("#atom-picker");
  await expect(page.locator("#atom-navigation")).toBeHidden();
  await picker.click();
  await page.locator("#atom-navigation").getByRole("button", {name: /A06/}).click();
  await expect(picker).toHaveAttribute("aria-expanded", "false");
  await expect(picker).toContainText("A06");
  await expect(picker).toBeFocused();
  await expect(page.locator("#input-schema-ref")).toHaveText(A06.schema_refs.input.schema_ref);
  await expect(page.locator("#output-contract-fields")).toHaveText("См. полную JSON Schema.");
});

test("selecting an atom with Enter keeps the keyboard in the catalog", async ({page}) => {
  await unlockAtom(page, "A01");
  const fields = page.getByRole("group", {name: "Найденные проблемы", exact: true});
  await expect(fields.getByRole("button", {name: "Добавить элемент"})).toHaveAccessibleDescription(/Обязательное поле/);
  const navigation = page.locator("#atom-navigation");
  const nextAtom = navigation.getByRole("button", {name: /A02/});
  await nextAtom.press("Enter");
  await expect(nextAtom).toHaveAttribute("aria-current", "true");
  await expect(nextAtom).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(navigation.getByRole("button", {name: /A03/})).toBeFocused();
  await page.locator("#fill-example").click();
  const dialogs = [];
  page.on("dialog", dialog => { dialogs.push(dialog.message()); return dialog.dismiss(); });
  await nextAtom.press("Enter");
  await expect(page.locator("#draft-state")).toContainText("несохранённые");
  expect(dialogs).toEqual([]);
});

test("request and response workspace keeps one launch action and keyboard-accessible editor views", async ({page}) => {
  await page.setViewportSize({width: 1280, height: 720});
  await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06/prompts", route => route.fulfill({
    contentType: "application/json", body: JSON.stringify([
      {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null},
    ]),
  }));
  await unlockAtom(page, "A06");
  await expect(page.locator("#request-title")).toHaveText("Запрос");
  await expect(page.getByRole("textbox", {name: "Цель", exact: true})).toHaveAttribute("aria-required", "true");
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await expect(page.locator("#launch-readiness")).toContainText("Проверьте");
  const positions = await page.evaluate(() => ({
    launch: document.querySelector(".run-controls").getBoundingClientRect().top,
    input: document.querySelector("#input-panel").getBoundingClientRect().bottom,
    request: document.querySelector(".editor-card").getBoundingClientRect().toJSON(),
    response: document.querySelector(".result-card").getBoundingClientRect().toJSON(),
  }));
  expect(positions.launch).toBeGreaterThan(positions.input);
  await expect(page.locator("#input-editor").getByRole("button", {name: "Добавить ключ", exact: true})).toBeInViewport({ratio: 1});
  expect(positions.request.right).toBeLessThan(positions.response.left);
  expect(positions.request.top).toBe(positions.response.top);
  await expect(page.locator("#prompt-editor")).toHaveCount(1);
  await expect(page.getByRole("button", {name: "Запустить атом", exact: true})).toHaveCount(1);
  await expect(page.getByRole("button", {name: "Пробный запуск", exact: true})).toHaveCount(0);
  await expect(page.locator(".run-controls #run-prompt-ref")).toHaveCount(0);

  await page.locator("#input-tab").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#prompt-tab")).toBeFocused();
  await expect(page.locator("#prompt-panel")).toBeVisible();
  await expect(page.locator("#run-prompt-ref")).toHaveText(A06.prompt_ref);
  await page.keyboard.press("Home");
  await expect(page.locator("#input-tab")).toBeFocused();
  await expect(page.locator("#input-panel")).toBeVisible();
  await page.locator("#run-button").click();
  await expect(page.locator("#validation-errors")).toContainText("Обязательное поле");
  await expect(page.getByRole("button", {name: "Передать пустой объект «Контекст»"})).toBeFocused();
  await page.locator("#fill-example").click();
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await expect(page.locator("#launch-readiness")).toHaveText("Черновик готов к запуску");
  for (const width of [390, 320]) {
    await page.setViewportSize({width, height: 1000});
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    const ordering = await page.evaluate(() => ({
      request: document.querySelector(".editor-card").getBoundingClientRect().bottom,
      response: document.querySelector(".result-card").getBoundingClientRect().top,
    }));
    expect(ordering.request).toBeLessThan(ordering.response);
  }
});

test("object array summaries preserve edits and reveal invalid or newly added controls", async ({page}) => {
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  const rows = page.locator("details.array-item");
  await expect(rows.first()).not.toHaveAttribute("open");
  await rows.first().locator("summary").click();
  await page.getByLabel("Серьёзность", {exact: true}).selectOption("low");
  await page.locator("#json-mode").click();
  const payload = JSON.parse(await page.locator("#json-editor").inputValue());
  expect(payload.issues[0].severity).toBe("low");
  payload.issues[0].severity = "invalid";
  await page.locator("#json-editor").fill(JSON.stringify(payload));
  await page.locator("#form-mode").click();
  await expect(rows.first()).toHaveAttribute("open");
  await rows.first().locator("summary").click();
  await page.locator("#validation-errors").getByRole("button", {name: /issues\[0\]\.severity/}).click();
  await expect(rows.first()).toHaveAttribute("open");
  await expect(page.getByLabel("Серьёзность", {exact: true})).toBeFocused();
  await page.getByLabel("Серьёзность", {exact: true}).selectOption("high");
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await rows.first().locator("summary").click();
  await page.getByRole("button", {name: "Добавить элемент", exact: true}).click();
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toHaveAttribute("open");
  await expect(rows.nth(1).getByLabel("Категория", {exact: true})).toBeFocused();
  await page.getByRole("button", {name: "Удалить элемент 2", exact: true}).click();
  await expect(rows).toHaveCount(1);
  await expect(page.getByLabel("Категория", {exact: true})).toBeFocused();
});

for (const state of ["replacement-get-before", "replacement-get-after", "replacement-refresh-failed", "replacement-read-failed", "replacement-unloaded", "replacement-source-pending", "replacement-name", "replacement-text", "replacement-source", "owner-name", "owner-name-whitespace", "owner-text", "owner-source", "other-atom", "new-catalog", "new-catalog-cancelled", "owner-unchanged"]) {
  test(`a confirmed prompt save synchronizes the library for ${state}`, async ({page}) => {
    const product = {ref: "product.a06.v1", name: "Продуктовый", prompt: "Текст продукта", group: "product", source_ref: null, source_run_id: null};
    let reads = 0;
    let saved;
    let payload;
    let completeSave;
    let completeRead;
    let writes = 0;
    const saveGate = new Promise(resolve => { completeSave = resolve; });
    const readGate = new Promise(resolve => { completeRead = resolve; });
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/*/prompts", async route => {
      const atom = catalog().find(item => route.request().url().includes(`/atoms/${item.atom_id}/`));
      if (route.request().method() === "POST") {
        writes += 1;
        payload = route.request().postDataJSON();
        await saveGate;
        saved = {ref: "lab.confirmed", group: "lab", ...payload};
        await route.fulfill({status: 201, json: saved});
        return;
      }
      const options = [{ref: atom.prompt_ref, name: "Платформенный", prompt: atom.prompt, group: "platform", source_ref: null, source_run_id: null}];
      if (atom.atom_id === "A06") {
        reads += 1;
        options.push(product);
        if (saved) options.push(saved);
        if ((reads === 2 && state === "replacement-read-failed")
          || (reads === 3 && state === "replacement-refresh-failed")) {
          await route.fulfill({status: 503, json: {error: {code: "prompts_unavailable", message: "Библиотека временно недоступна."}}});
          return;
        }
        if (reads === 2 && ["replacement-get-after", "replacement-refresh-failed"].includes(state)) await readGate;
        if (reads >= 2 && state === "replacement-source-pending") await readGate;
      }
      await route.fulfill({json: options});
    });
    if (state === "replacement-source-pending") {
      const detail = historyDetail();
      detail.snapshot.prompt.source_ref = product.ref;
      await page.route("http://atom-lab.test/v1/atom-lab/runs**", route => route.fulfill({json:
        new URL(route.request().url()).pathname === "/v1/atom-lab/runs" ? {items: [{
          run_id: detail.run_id, atom_id: "A06", status: "succeeded", created_at: detail.created_at,
          model_id: "openai/gpt-supported", preset_id: null, preset_version: null,
          started_at: detail.started_at, finished_at: detail.finished_at,
        }], next_cursor: null} : detail,
      }));
    }
    await unlockAtom(page, "A06");
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#save-prompt")).toBeEnabled();
    await page.locator("#prompt-editor").fill("Сохраняемый текст");
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Подтверждённый промпт");
    const posted = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/A06/prompts"));
    await page.locator("#save-prompt").click();
    await posted;
    if (state === "replacement-source-pending") {
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      page.once("dialog", dialog => dialog.accept());
      await page.locator("#restore-history").click();
      await showWorkbench(page);
      await page.locator("#prompt-tab").click();
      await expect.poll(() => reads).toBe(2);
    } else if (state.startsWith("replacement") || state === "other-atom") {
      if (state === "replacement-unloaded") await page.locator("#input-tab").click();
      page.once("dialog", dialog => dialog.accept());
      await page.getByRole("button", {name: /A05/}).click();
      if (state !== "other-atom") {
        const read = state === "replacement-unloaded" ? null
          : page.waitForRequest(request => request.method() === "GET" && request.url().endsWith("/A06/prompts"));
        await page.getByRole("button", {name: /A06/}).click();
        if (read) await read;
      }
    }
    if (state.startsWith("new-catalog")) {
      page.once("dialog", dialog => state === "new-catalog-cancelled" ? dialog.dismiss() : dialog.accept());
      await page.locator("#access-form").dispatchEvent("submit");
      await expect(page.locator("#atom-title")).toContainText(state === "new-catalog-cancelled" ? "A06" : "A01");
      if (state !== "new-catalog-cancelled") await page.getByRole("button", {name: /A06/}).click();
    }
    if (state === "replacement-read-failed") await expect(page.locator("#retry-prompts")).toBeVisible();
    else if (!["replacement-get-after", "replacement-refresh-failed", "replacement-source-pending"].includes(state)) await expect(page.locator("#prompt-load-status")).toBeEmpty();
    if (state.endsWith("source")) {
      if (state.startsWith("owner")) page.once("dialog", dialog => dialog.accept());
      await page.locator("#prompt-select").selectOption(product.ref);
      await page.locator("#prompt-editor").fill(payload.prompt);
    }
    if (state.endsWith("text")) await page.locator("#prompt-editor").fill("Новая правка во время сохранения");
    const editedName = state === "owner-name-whitespace" ? ` ${payload.name} ` : "Новое название";
    if (state.includes("name")) {
      if (state.startsWith("replacement")) await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill(editedName);
    }
    const currentText = await page.locator("#prompt-editor").inputValue();
    const currentRef = await page.locator("#run-prompt-ref").textContent();
    const accepted = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/A06/prompts"));
    completeSave();
    await (await accepted).finished();
    if (state === "replacement-source-pending") {
      await expect.poll(() => reads).toBe(3);
      await expect(page.locator('#prompt-select option[value="lab.confirmed"]')).toHaveCount(1);
      await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill("Ожидает источник");
      await expect(page.locator("#save-prompt")).toBeDisabled();
      await page.locator("#save-prompt-form").dispatchEvent("submit");
      expect(writes).toBe(1);
      completeRead();
      await expect(page.locator("#prompt-load-status")).toBeEmpty();
    }
    if (["replacement-refresh-failed", "replacement-read-failed"].includes(state)) {
      await expect(page.locator("#retry-prompts")).toBeVisible();
      await expect(page.locator('#prompt-select option[value="lab.confirmed"]')).toHaveCount(1);
      const previousReads = reads;
      await page.locator("#retry-prompts").click();
      await expect.poll(() => reads).toBe(previousReads + 1);
      await expect(page.locator("#prompt-load-status")).toBeEmpty();
      await expect(page.locator("#retry-prompts")).toBeHidden();
      await expect(page.locator("#save-prompt")).toBeEnabled();
    }
    if (["replacement-get-after", "replacement-refresh-failed"].includes(state)) {
      await expect(page.locator('#prompt-select option[value="lab.confirmed"]')).toHaveCount(1);
      const staleRead = page.waitForResponse(response => response.request().method() === "GET" && response.url().endsWith("/A06/prompts"));
      completeRead();
      await (await staleRead).finished();
    }
    if (state === "owner-unchanged") {
      await expect(page.locator("#save-prompt-status")).toContainText("Сохранён");
      await expect(page.locator("#run-prompt-ref")).toHaveText("lab.confirmed");
      await expect(page.locator("#prompt-select")).toBeFocused();
      await expect(page.locator("#save-prompt-name")).toBeEmpty();
      await expect(page.locator("#save-prompt-panel")).not.toHaveAttribute("open");
    } else {
      await expect(page.locator("#prompt-editor")).toHaveValue(currentText);
      await expect(page.locator("#run-prompt-ref")).toHaveText(currentRef);
      if (state.startsWith("owner")) {
        await expect(page.locator("#save-prompt")).toBeEnabled();
        await expect(page.locator("#save-prompt-panel")).toHaveAttribute("open");
        await expect(page.locator("#save-prompt-name")).toHaveValue(state.includes("name") ? editedName : payload.name);
      }
      if (state.includes("name")) await expect(page.locator("#save-prompt-name")).toBeFocused();
    }
    await page.locator("#input-tab").click();
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-load-status")).toBeEmpty();
    if (state === "replacement-unloaded") expect(reads).toBe(1);
    const differentScope = state === "other-atom" || state.startsWith("new-catalog");
    await expect(page.locator('#prompt-select option[value="lab.confirmed"]')).toHaveCount(differentScope ? 0 : 1);
    if (differentScope) return;
    await page.locator("#save-prompt-panel").evaluate(panel => { panel.open = true; });
    await expect(page.locator("#save-prompt")).toBeEnabled();
    await expect(page.locator("#prompt-editor")).toHaveValue(currentText);
    if (state !== "owner-unchanged") {
      if (state.endsWith("text") || state.endsWith("source") || state.startsWith("owner-name") || state === "replacement-source-pending") page.once("dialog", dialog => dialog.accept());
      await page.locator("#prompt-select").selectOption("lab.confirmed");
    }
    await expect(page.locator("#prompt-editor")).toHaveValue(payload.prompt);
    await expect(page.locator("#prompt-select")).toHaveValue("lab.confirmed");
  });
}

for (const firstCompletion of ["previous", "current"]) {
  test(`prompt saves preserve the current editable form when ${firstCompletion} completes first`, async ({page}) => {
    const releases = [];
    const writes = [];
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/*/prompts", async route => {
      const atom = route.request().url().includes("/A06/") ? A06 : A05;
      if (route.request().method() === "GET") {
        await route.fulfill({json: [{
          ref: atom.prompt_ref, name: "Платформенный", prompt: atom.prompt,
          group: "platform", source_ref: null, source_run_id: null,
        }]});
        return;
      }
      const payload = route.request().postDataJSON();
      const index = writes.push(payload) - 1;
      await new Promise(resolve => { releases[index] = resolve; });
      await route.fulfill({status: 201, json: {ref: `lab.saved.${index}`, group: "lab", ...payload}});
    });
    await unlockAtom(page, "A06");
    for (const name of ["Предыдущее название", "Текущее название"]) {
      await page.locator("#prompt-tab").click();
      await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill(name);
      await page.locator("#save-prompt").click();
      await expect.poll(() => writes.length).toBe(name === "Предыдущее название" ? 1 : 2);
      if (writes.length === 1) {
        await page.locator("#input-tab").click();
        await page.getByRole("button", {name: /A05/}).click();
        await page.getByRole("button", {name: /A06/}).click();
      }
    }
    await page.locator("#save-prompt-name").fill("Новое текущее название");
    const order = firstCompletion === "previous" ? [0, 1] : [1, 0];
    for (const index of order) {
      releases[index]();
      await expect(page.locator(`#prompt-select option[value="lab.saved.${index}"]`)).toHaveCount(1);
      await expect(page.locator("#save-prompt-name")).toHaveValue("Новое текущее название");
      await expect(page.locator("#save-prompt-name")).toBeFocused();
      if (index === 0 && firstCompletion === "previous") await expect(page.locator("#save-prompt")).toBeDisabled();
    }
    await expect(page.locator("#save-prompt")).toBeEnabled();
    await expect(page.locator("#save-prompt-panel")).toHaveAttribute("open");
    await expect(page.locator("#prompt-select")).toHaveValue(A06.prompt_ref);
    await expect(page.locator("#prompt-editor")).toHaveValue(A06.prompt);
    expect(writes.map(payload => payload.name)).toEqual(["Предыдущее название", "Текущее название"]);
  });
}

for (const outcome of ["rejected", "unavailable", "malformed", "indeterminate"]) {
  test(`a ${outcome} prompt write preserves the current draft without a confirmed option`, async ({page}) => {
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06/prompts", async route => {
      if (route.request().method() === "GET") await route.fulfill({json: [{
        ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null,
      }]});
      else if (outcome === "rejected") await route.fulfill({status: 422, json: {error: {
        code: "prompt_invalid", message: "Промпт не прошёл проверку.",
      }}});
      else if (outcome === "unavailable") await route.fulfill({status: 503, json: {error: {
        code: "lab_unavailable", message: "Промпт Atom Lab не может быть сохранён.",
      }}});
      else if (outcome === "malformed") await route.fulfill({status: 201, json: {}});
      else await route.abort("failed");
    });
    await unlockAtom(page, "A06");
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#save-prompt")).toBeEnabled();
    await page.locator("#prompt-editor").fill("Несохранённый текст");
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Не подтверждён");
    await page.locator("#save-prompt").click();
    await expect(page.locator("#save-prompt-status")).toContainText(outcome === "rejected"
      ? "Промпт не прошёл проверку" : "подтверждение не получено");
    await expect(page.locator("#save-prompt")).toBeEnabled();
    await expect(page.locator("#prompt-editor")).toHaveValue("Несохранённый текст");
    await expect(page.locator("#prompt-select")).toHaveValue(A06.prompt_ref);
    await expect(page.locator("#prompt-select option")).toHaveCount(1);
    await expect(page.locator("#save-prompt-panel")).toHaveAttribute("open");
    await expect(page.locator("#save-prompt-name")).toHaveValue("Не подтверждён");
  });
}

for (const presetReadback of ["success", "unavailable"]) {
test(`the shared launch keeps its successful prompt trial after ${presetReadback} preset readback`, async ({page}) => {
  const product = {ref: "product.a06.v1", name: "Продуктовый", prompt: "Промпт продукта", group: "product", source_ref: null, source_run_id: null};
  let body;
  let savedBody;
  let presetBody;
  let posts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06/prompts", async route => {
    if (route.request().method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify([
        {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null}, product,
      ])});
    } else {
      savedBody = route.request().postDataJSON();
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        ref: "lab.saved.v1", group: "lab", ...savedBody,
      })});
    }
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
    posts += 1;
    body = route.request().postDataJSON();
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
      run_id: "run-workbench", scenario_session_id: "session-library", job_id: "job-library", status: "queued",
    })});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-workbench", async route => {
    const detail = historyDetail({runId: "run-workbench", input: body.input, prompt: body.prompt});
    detail.snapshot.prompt.source_ref = product.ref;
    await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/presets**", async route => {
    const {pathname} = new URL(route.request().url());
    if (route.request().method() === "POST") {
      presetBody = route.request().postDataJSON();
      await route.fulfill({json: {preset_id: "trial-preset", version: 1, created_at: "2026-11-06T08:00:00Z"}});
      return;
    }
    const version = {...presetBody, preset_id: "trial-preset", version: 1, created_at: "2026-11-06T08:00:00Z"};
    const summary = presetBody ? {
      preset_id: version.preset_id, name: version.name, description: version.description,
      atom_id: version.atom_id, created_at: version.created_at,
    } : null;
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({json: {items: summary ? [{...summary, latest_version: 1, updated_at: version.created_at}] : [], next_cursor: null}});
    } else if (presetReadback === "unavailable") await route.fulfill({status: 503, json: {}});
    else if (pathname.endsWith("/versions")) await route.fulfill({json: {items: [{...summary, version: 1}], next_cursor: null}});
    else await route.fulfill({json: version});
  });
  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#reasoning-effort").selectOption("high");
  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-select").selectOption(product.ref);
  await page.locator("#prompt-editor").fill("Отредактированный продуктовый промпт");
  await expect(page.locator("#prompt-tab-state")).toContainText("изменён");
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
  await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
  await expect(page.locator("#response-draft-warning")).toBeHidden();
  expect(body.prompt_source_ref).toBe(product.ref);
  const snapshot = await page.locator("#submitted-snapshot").textContent();
  const result = await page.locator("#result-json").textContent();
  await page.locator("#input-tab").click();
  await page.locator("#json-mode").click();
  await page.locator("#json-editor").fill(JSON.stringify({objective: body.input.objective, context: body.input.context}));
  await expect(page.locator("#response-draft-warning")).toBeHidden();
  await page.locator("#json-editor").fill("{");
  await expect(page.locator("#response-draft-warning")).toBeVisible();
  await page.locator("#json-editor").fill(JSON.stringify({...body.input, objective: "Другая цель"}));
  await expect(page.locator("#response-draft-warning")).toBeVisible();
  await expect(page.locator("#submitted-snapshot")).toHaveText(snapshot);
  await expect(page.locator("#result-json")).toHaveText(result);
  await page.locator("#json-editor").fill(JSON.stringify(body.input));
  await expect(page.locator("#response-draft-warning")).toBeHidden();
  await page.locator("#model-select").selectOption("gpt-no-reasoning");
  await expect(page.locator("#response-draft-warning")).toBeVisible();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");
  await expect(page.locator("#response-draft-warning")).toBeHidden();
  await page.locator("#presets-button").click();
  await editPreset(page);
  await page.locator("#preset-name").fill("Проверенный пресет");
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-state")).toContainText(presetReadback === "success"
    ? "Сохранена неизменяемая версия 1" : "Версия 1 сохранена");
  expect(presetBody.source_run_id).toBe("run-workbench");
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
  await page.locator("#reasoning-effort").selectOption("low");
  await expect(page.locator("#prompt-test-status")).toContainText("изменились");
  await page.locator("#reasoning-effort").selectOption("high");
  await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
  await page.locator("#save-prompt-panel summary").click();
  await page.locator("#save-prompt-name").fill("Успешный промпт");
  await page.locator("#save-prompt").click();
  await expect(page.locator("#save-prompt-status")).toContainText("Сохранён");
  expect(savedBody).toMatchObject({prompt: body.prompt, source_ref: product.ref, source_run_id: "run-workbench"});
  await expect(page.locator("#run-prompt-ref")).toHaveText("lab.saved.v1");
  await page.locator("#input-tab").click();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#response-draft-warning")).toBeVisible();
  await expect(page.locator("#result-json")).toHaveText(result);
  expect(posts).toBe(1);
});
}

for (const state of ["new", "version", "failed", "prompt", "version-prompt", "source", "input", "model", "reasoning", "other-atom", "subsequent-failed"]) {
  test(`a trial completing after preset readback respects the ${state} draft`, async ({page}) => {
    const product = {ref: "product.a06.v1", name: "Продуктовый", prompt: "Текст продукта", group: "product", source_ref: null, source_run_id: null};
    const versions = [];
    let body;
    const savedBodies = [];
    let posts = 0;
    let completeRun;
    const completion = new Promise(resolve => { completeRun = resolve; });
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06/prompts", async route => {
      if (route.request().method() === "GET") await route.fulfill({json: [
        {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null}, product,
      ]});
      else {
        const savedBody = route.request().postDataJSON();
        savedBodies.push(savedBody);
        await route.fulfill({json: {ref: `lab.delayed.v${savedBodies.length}`, group: "lab", ...savedBody}});
      }
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
      posts += 1;
      body = route.request().postDataJSON();
      await route.fulfill({status: 202, json: {
        run_id: posts === 1 ? "run-delayed-trial" : "run-subsequent-failed",
        scenario_session_id: "session-library", job_id: "job-library", status: "queued",
      }});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs/run-delayed-trial", async route => {
      await completion;
      const detail = historyDetail({runId: "run-delayed-trial", input: body.input, prompt: body.prompt});
      detail.snapshot.prompt.source_ref = body.prompt_source_ref;
      if (state === "failed") {
        detail.status = "failed";
        detail.result = null;
        detail.diagnostics.error_code = "output_validation_failed";
      }
      await route.fulfill({json: detail});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs/run-subsequent-failed", async route => {
      const detail = historyDetail({runId: "run-subsequent-failed", input: body.input, prompt: body.prompt});
      detail.status = "failed";
      detail.result = null;
      detail.diagnostics.error_code = "output_validation_failed";
      await route.fulfill({json: detail});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/presets**", async route => {
      const {pathname} = new URL(route.request().url());
      if (route.request().method() === "POST") {
        const version = versions.length + 1;
        versions.push({...route.request().postDataJSON(), preset_id: "delayed-trial-preset", version, created_at: "2026-11-07T08:00:00Z"});
        await route.fulfill({status: 201, json: {preset_id: "delayed-trial-preset", version, created_at: versions.at(-1).created_at}});
        return;
      }
      const version = versions.at(-1);
      const summary = version ? {
        preset_id: version.preset_id, name: version.name, description: version.description,
        atom_id: version.atom_id, created_at: version.created_at,
      } : null;
      if (pathname === "/v1/atom-lab/presets") await route.fulfill({json: {
        items: summary ? [{...summary, latest_version: version.version, updated_at: version.created_at}] : [], next_cursor: null,
      }});
      else if (pathname.endsWith("/versions")) await route.fulfill({json: {
        items: versions.map(item => ({...summary, version: item.version})), next_cursor: null,
      }});
      else await route.fulfill({json: version});
    });

    await unlockAtom(page, "A06");
    await page.locator("#fill-example").click();
    await page.locator("#reasoning-effort").selectOption("high");
    await page.locator("#prompt-tab").click();
    await page.locator("#prompt-select").selectOption(product.ref);
    await page.locator("#prompt-editor").fill("Промпт отложенного запуска");
    const newVersion = state.startsWith("version");
    if (newVersion) {
      await editPreset(page);
      await page.locator("#preset-name").fill("Проверка отложенного запуска");
      await page.locator("#save-preset").click();
      await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 1");
      await showWorkbench(page);
    }
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toHaveText("Ожидает запуска");
    await editPreset(page);
    await page.locator("#preset-name").fill("Проверка отложенного запуска");
    await page.locator("#save-preset").click();
    await expect(page.locator("#preset-state")).toContainText(`Сохранена неизменяемая версия ${newVersion ? 2 : 1}`);
    await showWorkbench(page);
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
    if (["prompt", "version-prompt", "subsequent-failed"].includes(state)) await page.locator("#prompt-editor").fill("Другой текст");
    if (state === "source") {
      await page.locator("#prompt-select").selectOption(A06.prompt_ref);
      await page.locator("#prompt-editor").fill(body.prompt);
    }
    if (state === "input") {
      await page.locator("#input-tab").click();
      await page.locator("#json-mode").click();
      await page.locator("#json-editor").fill(JSON.stringify({...body.input, objective: "Другая цель"}));
      await page.locator("#prompt-tab").click();
    }
    if (state === "model") await page.locator("#model-select").selectOption("gpt-no-reasoning");
    if (state === "reasoning") await page.locator("#reasoning-effort").selectOption("low");
    if (state === "other-atom") {
      page.once("dialog", dialog => dialog.accept());
      await page.getByRole("button", {name: /A05/}).click();
    }
    completeRun();
    await expect(page.locator("#run-state")).toHaveText(state === "failed" ? "Ошибка" : "Завершён успешно");
    if (state === "other-atom") {
      await expect(page.locator("#atom-title")).toContainText("A05");
      await expect(page.locator("#prompt-editor")).toHaveValue(A05.prompt);
      expect(posts).toBe(1);
      return;
    }
    const proven = state === "new" || state === "version";
    if (proven) await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    else await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
    if (proven) await expect(page.locator("#response-draft-warning")).toBeHidden();
    else if (state !== "failed") await expect(page.locator("#response-draft-warning")).toBeVisible();
    const submittedSnapshot = await page.locator("#submitted-snapshot").textContent();
    const result = await page.locator("#result-json").textContent();
    if (state === "subsequent-failed") {
      await page.locator("#run-button").click();
      await expect(page.locator("#run-state")).toHaveText("Ошибка");
    }
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Отложенный промпт");
    await page.locator("#save-prompt").click();
    await expect(page.locator("#save-prompt-status")).toContainText("Сохранён");
    expect(savedBodies[0].source_run_id).toBe(proven ? "run-delayed-trial" : null);
    if (!proven) {
      await page.locator("#prompt-select").selectOption(product.ref);
      await page.locator("#prompt-editor").fill(versions.at(-1).prompt);
      await page.locator("#input-tab").click();
      await page.locator("#json-mode").click();
      await page.locator("#json-editor").fill(JSON.stringify(versions.at(-1).example_input));
      await page.locator("#model-select").selectOption("gpt-supported");
      await page.locator("#reasoning-effort").selectOption("high");
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-test-status")).toContainText(state === "failed"
        ? "нет успешного пробного запуска" : "Ответ прошёл контракт");
      if (state !== "subsequent-failed") {
        await expect(page.locator("#response-draft-warning")).toBeHidden();
        await expect(page.locator("#submitted-snapshot")).toHaveText(submittedSnapshot);
        await expect(page.locator("#result-json")).toHaveText(result);
      }
      await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill("Возврат к проверенному тексту");
      await page.locator("#save-prompt").click();
      await expect(page.locator("#save-prompt-status")).toContainText("Сохранён");
      expect(savedBodies[1].source_run_id).toBe(state === "failed" ? null : "run-delayed-trial");
    }
    expect(posts).toBe(state === "subsequent-failed" ? 2 : 1);
  });
}

for (const completionOrder of ["before", "after"]) {
  test(`restored trial and async success remain independently usable when completion is ${completionOrder} restore`, async ({page}) => {
    const restored = historyDetail({runId: "run-adopted-trial", prompt: "Проверенный промпт из истории"});
    let submitted;
    let posts = 0;
    let detailReads = 0;
    const savedBodies = [];
    let releaseRun;
    const completion = new Promise(resolve => { releaseRun = resolve; });
    await page.route("http://atom-lab.test/v1/atom-lab/**", async route => {
      const {pathname} = new URL(route.request().url());
      if (pathname === "/v1/atom-lab/runs" && route.request().method() === "POST") {
        posts += 1;
        if (posts === 1) submitted = route.request().postDataJSON();
        await route.fulfill({status: 202, json: {run_id: posts === 1 ? "run-async-trial" : "run-later-failure", status: "queued",
          scenario_session_id: "session-library", job_id: "job-library"}});
      } else if (pathname === "/v1/atom-lab/runs/run-later-failure") {
        await route.fulfill({json: {...restored, run_id: "run-later-failure", status: "failed", result: null,
          diagnostics: {...restored.diagnostics, error_code: "output_validation_failed"}}});
      } else if (pathname === "/v1/atom-lab/runs/run-async-trial") {
        detailReads += 1;
        await completion;
        await route.fulfill({json: historyDetail({runId: "run-async-trial", input: submitted.input, prompt: submitted.prompt})});
      } else if (pathname === "/v1/atom-lab/runs") await route.fulfill({json: {items: [{
        run_id: restored.run_id, status: restored.status, atom_id: "A06", model_id: restored.snapshot.provider.model_id,
        preset_id: null, preset_version: null, created_at: restored.created_at,
        started_at: restored.started_at, finished_at: restored.finished_at,
      }], next_cursor: null}});
      else if (pathname.endsWith(restored.run_id)) await route.fulfill({json: restored});
      else if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
        if (route.request().method() === "POST") {
          savedBodies.push(route.request().postDataJSON());
          await route.fulfill({status: 422, json: {error: {code: "prompt_invalid", message: "Test rejection", field_errors: []}}});
        } else await route.fulfill({json: [{ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt,
          group: "platform", source_ref: null, source_run_id: null}]});
      } else await route.fallback();
    });
    await unlockAtom(page, "A06");
    await page.locator("#fill-example").click();
    await page.locator("#reasoning-effort").selectOption("high");
    await page.locator("#prompt-tab").click();
    await page.locator("#prompt-editor").fill("Промпт асинхронного запуска");
    await page.locator("#run-button").click();
    await expect.poll(() => detailReads).toBe(1);
    if (completionOrder === "before") {
      releaseRun();
      await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
    }
    await page.locator("#history-button").click();
    await page.locator("#history-list .history-open").click();
    page.once("dialog", dialog => dialog.accept());
    await page.locator("#restore-history").click();
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    if (completionOrder === "after") {
      releaseRun();
      await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
    }
    const submittedSnapshot = await page.locator("#submitted-snapshot").textContent();
    const result = await page.locator("#result-json").textContent();
    for (const [prompt, runId] of [
      [restored.snapshot.prompt.content, restored.run_id],
      [submitted.prompt, "run-async-trial"],
      [restored.snapshot.prompt.content, restored.run_id],
    ]) {
      await page.locator("#prompt-editor").fill(prompt);
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      if (runId === restored.run_id) await expect(page.locator("#response-draft-warning")).toBeVisible();
      else await expect(page.locator("#response-draft-warning")).toBeHidden();
      if (await page.locator("#save-prompt-panel").getAttribute("open") === null) await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill("Подтверждённый текст");
      const count = savedBodies.length + 1;
      await page.locator("#save-prompt").click();
      await expect.poll(() => savedBodies.length).toBe(count);
      await expect(page.locator("#save-prompt-status")).toContainText("Test rejection");
      expect(savedBodies.at(-1)).toMatchObject({prompt, source_run_id: runId});
      await expect(page.locator("#submitted-snapshot")).toHaveText(submittedSnapshot);
      await expect(page.locator("#result-json")).toHaveText(result);
    }
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toHaveText("Ошибка");
    await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    await page.locator("#save-prompt-name").fill("Успех до ошибки");
    await page.locator("#save-prompt").click();
    await expect.poll(() => savedBodies.length).toBe(4);
    await expect(page.locator("#save-prompt-status")).toContainText("Test rejection");
    expect(savedBodies.at(-1).source_run_id).toBe(restored.run_id);
    page.once("dialog", dialog => dialog.accept());
    await page.getByRole("button", {name: /A05/}).click();
    await page.getByRole("button", {name: /A06/}).click();
    await page.locator("#input-tab").click();
    await page.locator("#fill-example").click();
    await page.locator("#prompt-tab").click();
    for (const prompt of [submitted.prompt, restored.snapshot.prompt.content]) {
      await page.locator("#prompt-editor").fill(prompt);
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    }
    expect(posts).toBe(2);
    expect(detailReads).toBe(1);
  });
}

for (const library of ["history", "presets"]) {
  test(`a delayed prompt rejection keeps the ${library} section open until explicit error navigation`, async ({page}) => {
    let rejectRun;
    const gate = new Promise(resolve => { rejectRun = resolve; });
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
      if (route.request().method() === "GET") {
        await route.fulfill({json: {items: [], next_cursor: null}});
        return;
      }
      await gate;
      await route.fulfill({status: 413, json: {error: {
        code: "payload_too_large", message: "Слишком большой промпт",
        field_errors: [{path: "prompt", message: "Сократите промпт"}],
      }}});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/presets", route => route.fulfill({json: {items: [], next_cursor: null}}));
    await unlockAtom(page, "A06");
    await page.locator("#fill-example").click();
    const submitted = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/runs"));
    await page.locator("#run-button").click();
    await submitted;
    await page.locator(`#${library}-button`).click();
    rejectRun();
    await expect(page.locator("#run-state")).toContainText("payload_too_large");
    await expect(page.locator(`#${library}-panel`)).toBeVisible();
    await expect(page.locator("#request-response")).toBeHidden();
    await showWorkbench(page);
    await page.locator("#validation-errors button").click();
    await expect(page.locator("#prompt-panel")).toBeVisible();
    await expect(page.locator("#prompt-editor")).toBeFocused();
  });
}

for (const historicalState of ["succeeded", "retired-model", "failed", "incompatible", "adapted-schema", "adapted-action", "adapted-prompt", "new-catalog", "new-catalog-cancelled"]) {
  test(`restored ${historicalState} history keeps only a matching successful prompt trial`, async ({page}) => {
    const detail = historyDetail({runId: "run-trial-restore"});
    detail.snapshot.prompt.source_ref = "product.a06.v1";
    if (historicalState === "retired-model") detail.snapshot.provider.model_id = "openai/gpt-retired";
    if (historicalState === "failed") {
      detail.status = "failed";
      detail.result = null;
    }
    if (historicalState === "incompatible") detail.snapshot.schemas.input.version = 99;
    let savedBody;
    let runWrites = 0;
    await page.route("http://atom-lab.test/v1/atom-lab/**", async route => {
      const {pathname} = new URL(route.request().url());
      if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
        if (route.request().method() === "POST") {
          savedBody = route.request().postDataJSON();
          if (historicalState === "new-catalog-cancelled") await route.fulfill({status: 422, json: {
            error: {code: "prompt_invalid", message: "Test rejection", field_errors: []},
          }});
          else await route.fulfill({json: {ref: "lab.restored", group: "lab", ...savedBody}});
        } else await route.fulfill({json: [
          {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null},
          {ref: detail.snapshot.prompt.source_ref, name: "Продуктовый", prompt: "Текущий продуктовый текст", group: "product", source_ref: null, source_run_id: null},
        ]});
      } else if (pathname === "/v1/atom-lab/runs") {
        if (route.request().method() === "POST") runWrites += 1;
        await route.fulfill({json: {items: [{
          run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: detail.snapshot.provider.model_id,
          preset_id: null, preset_version: null, created_at: detail.created_at,
          started_at: detail.started_at, finished_at: detail.finished_at,
        }], next_cursor: null}});
      } else if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) await route.fulfill({json: detail});
      else await route.fallback();
    });
    await unlockAtom(page, "A06");
    await page.locator("#history-button").click();
    await page.locator("#history-list .history-open").click();
    await page.locator("#restore-history").click();
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-select")).toHaveValue(detail.snapshot.prompt.source_ref);
    if (historicalState.startsWith("adapted-")) {
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      if (historicalState === "adapted-schema") detail.snapshot.schemas.input.version = 99;
      if (historicalState === "adapted-action") detail.snapshot.action.config_id = "retired.action";
      if (historicalState === "adapted-prompt") detail.snapshot.prompt.ref = "retired.prompt";
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      await expect(page.locator("#restore-history")).toHaveText("Адаптировать к текущему контракту");
      page.once("dialog", dialog => dialog.accept());
      await page.locator("#restore-history").click();
      await page.locator("#prompt-tab").click();
    }
    if (historicalState.startsWith("new-catalog")) {
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      page.once("dialog", dialog => historicalState === "new-catalog" ? dialog.accept() : dialog.dismiss());
      await page.locator("#access-form").dispatchEvent("submit");
      if (historicalState === "new-catalog") {
        await expect(page.locator("#atom-title")).toContainText("A01");
        await page.getByRole("button", {name: /A06/}).click();
        await page.locator("#input-tab").click();
        await importJson(page, detail.snapshot.input);
        await page.locator("#reasoning-effort").selectOption("high");
        await page.locator("#prompt-tab").click();
        await page.locator("#prompt-select").selectOption(detail.snapshot.prompt.source_ref);
        await page.locator("#prompt-editor").fill(detail.snapshot.prompt.content);
      } else {
        await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
        await expect(page.locator("#atom-title")).toContainText("A06");
      }
    }
    if (historicalState === "retired-model") {
      await expect(page.locator("#model-select")).toHaveValue("gpt-retired");
      await expect(page.locator("#run-button")).toBeDisabled();
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      await page.locator("#prompt-editor").fill("Правка текста");
      await expect(page.locator("#prompt-test-status")).toContainText("изменились");
      await page.locator("#prompt-editor").fill(detail.snapshot.prompt.content);
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    }
    if (historicalState === "succeeded") {
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      await page.locator("#prompt-editor").fill("Правка текста");
      await expect(page.locator("#prompt-test-status")).toContainText("изменились");
      await page.locator("#prompt-editor").fill(detail.snapshot.prompt.content);
      await page.locator("#model-select").selectOption("gpt-no-reasoning");
      await expect(page.locator("#prompt-test-status")).toContainText("изменились");
      await page.locator("#model-select").selectOption("gpt-supported");
      await page.locator("#reasoning-effort").selectOption("low");
      await expect(page.locator("#prompt-test-status")).toContainText("изменились");
      await page.locator("#reasoning-effort").selectOption("high");
      await page.locator("#input-tab").click();
      await page.locator("#json-mode").click();
      await page.locator("#json-editor").fill(JSON.stringify({...detail.snapshot.input, objective: "Другая цель"}));
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-test-status")).toContainText("изменились");
      await page.locator("#input-tab").click();
      await page.locator("#json-editor").fill(JSON.stringify(detail.snapshot.input));
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      page.once("dialog", dialog => dialog.accept());
      await page.locator("#prompt-select").selectOption(A06.prompt_ref);
      await page.locator("#prompt-editor").fill(detail.snapshot.prompt.content);
      await expect(page.locator("#prompt-test-status")).toContainText("изменились");
      page.once("dialog", dialog => dialog.accept());
      await page.locator("#prompt-select").selectOption(detail.snapshot.prompt.source_ref);
      await page.locator("#prompt-editor").fill(detail.snapshot.prompt.content);
      await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    } else if (historicalState !== "retired-model") await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Из истории");
    await page.locator("#save-prompt").click();
    await expect(page.locator("#save-prompt-status")).toContainText(historicalState === "new-catalog-cancelled" ? "Test rejection" : "Сохранён");
    expect(savedBody.source_run_id).toBe(["succeeded", "retired-model"].includes(historicalState) ? detail.run_id : null);
    expect(savedBody.source_ref).toBe(detail.snapshot.prompt.source_ref);
    expect(runWrites).toBe(0);
  });
}

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

test("Form numbers that cannot round-trip are rejected before changing the draft", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  await unlockAtom(page, "A06");
  await importJson(page, {context: {id: 1}, objective: "pilot"});

  await page.getByLabel("Значение «id»", {exact: true}).fill("9007199254740993");
  await expect(page.locator("#validation-errors")).toContainText("точност");

  await page.getByRole("button", {name: /A11/}).click();
  await importJson(page, {
    subject_text: "Пилот",
    reference_text: "Эталон",
    categories: ["да", "нет"],
    criteria: [{id: "scope", description: "Границы", weight: 1}],
  });
  await page.locator("details.array-item").first().locator("summary").click();
  await page.getByLabel("Вес", {exact: true}).fill("0.1234567890123456789");
  await expect(page.locator("#validation-errors")).toContainText("точност");
});

test("omitting a container clears invalid descendant input errors", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {}, objective: "pilot", constraints: {length: 900}});

  await page.getByLabel("Длина", {exact: true}).fill("2.9");
  await expect(page.locator("#validation-errors")).toContainText("целым числом");
  await page.getByRole("button", {name: "Не передавать «Ограничения»"}).click();
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

  const recovery = page.getByLabel("Цель, JSON-значение", {exact: true});
  await expect(recovery).toHaveAttribute("aria-invalid", "true");
  await recovery.fill('"pilot"');
  await recovery.press("Tab");

  const objective = page.getByLabel("Цель", {exact: true});
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await expect(objective).not.toHaveAttribute("aria-invalid", "true");
  await expect(objective).not.toHaveAttribute("aria-describedby", /.+/);
});

test("correcting a control clears validation-owned ARIA attributes", async ({page}) => {
  await unlockAtom(page, "A06");
  await importJson(page, {context: {}, objective: "pilot", constraints: {length: 900}});

  const length = page.getByLabel("Длина", {exact: true});
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

  await page.getByRole("button", {name: "Добавить поле «Ограничения»"}).click();

  await expect(page.getByRole("button", {name: "Добавить поле «Тон»"})).toBeFocused();
});

test("adding a compound array item focuses its first rendered descendant control", async ({page}) => {
  await unlockAtom(page, "A05");
  await importJson(page, {issues: [], context: "x", target_audience: "y"});

  await page.getByRole("button", {name: "Добавить элемент"}).click();

  await expect(page.getByLabel("Категория", {exact: true})).toBeFocused();
});

test("the displayed run remains saveable after compatible refresh and is hidden after contract drift", async ({page}) => {
  const detail = historyDetail({runId: "run-result-preset", prompt: A06.prompt});
  detail.snapshot.prompt.source_ref = A06.prompt_ref;
  const created = {preset_id: "result-preset", version: 1, created_at: detail.finished_at};
  let currentAtom = A06;
  let savedBody;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const {pathname} = new URL(route.request().url());
    if (pathname === "/v1/atom-lab/runs" && route.request().method() === "POST") {
      if (currentAtom !== A06) return route.fulfill({status: 422, json: {error: {
        code: "contract_unavailable", message: currentAtom.prompt,
        field_errors: [{path: "expected_contract", message: "Перечитайте контракт."}],
      }, request_id: "contract-refresh"}});
      return route.fulfill({status: 202, json: {run_id: detail.run_id, status: "queued",
        scenario_session_id: detail.runtime_ids.scenario_session_id, job_id: detail.runtime_ids.job_id}});
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) return route.fulfill({json: detail});
    if (pathname === "/v1/atom-lab/atoms/A06") return route.fulfill({json: currentAtom});
    if (pathname === "/v1/atom-lab/atoms/A06/prompts") return route.fulfill({json: [{
      ref: currentAtom.prompt_ref, name: "Платформа", prompt: currentAtom.prompt, group: "platform",
      source_ref: null, source_run_id: null,
    }]});
    if (pathname === "/v1/atom-lab/presets") {
      if (route.request().method() !== "POST") return route.fulfill({json: {items: [], next_cursor: null}});
      savedBody = route.request().postDataJSON();
      return route.fulfill({status: 201, json: created});
    }
    if (pathname === "/v1/atom-lab/presets/result-preset/versions") {
      const {name, description, atom_id} = savedBody;
      return route.fulfill({json: {items: [{...created, name, description, atom_id}], next_cursor: null}});
    }
    if (pathname === "/v1/atom-lab/presets/result-preset/versions/1") {
      return route.fulfill({json: {...savedBody, ...created}});
    }
    return route.fallback();
  });
  await unlockAtom(page, "A06");
  const save = page.locator("#save-result-preset");
  await expect(save).toBeHidden();
  await page.locator("#fill-example").click();
  await page.locator("#reasoning-effort").selectOption("high");
  await page.locator("#run-button").click();
  await expect(save).toBeVisible();
  await page.getByRole("textbox", {name: "Цель", exact: true}).fill("Новая цель черновика");
  await expect(page.locator("#response-draft-warning")).toBeVisible();
  currentAtom = {...A06, prompt: "Обновлённый текст того же промпта"};
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText(currentAtom.prompt);
  await expect(page.locator("#run-button")).toBeEnabled();
  await expect(save).toBeVisible();
  await save.click();
  await expect(page.locator("#preset-name")).toBeFocused();
  await expect(page.locator("#preset-source")).toContainText(detail.run_id);
  await page.locator("#preset-name").fill("Из результата");
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 1");
  expect(savedBody).toMatchObject({source_run_id: detail.run_id, atom_id: "A06", example_input: A06.example_input,
    prompt: A06.prompt, model_id: "openai/gpt-supported", reasoning_effort: "high"});
  await page.locator("#close-presets").click();
  await expect(page.getByRole("textbox", {name: "Цель", exact: true})).toHaveValue("Новая цель черновика");
  currentAtom = {...A06, prompt_ref: "prompt.a06.v2", prompt: "Новая версия платформенного промпта"};
  await page.locator("#run-button").click();
  await expect(page.locator("#run-prompt-ref")).toHaveText(currentAtom.prompt_ref);
  await expect(save).toBeHidden();
  await expect(page.locator("#result-section")).toBeVisible();
});

test("checking a result preset source keeps focus and leaves the workbench usable", async ({page}) => {
  const detail = historyDetail({runId: "run-preset-check", prompt: A06.prompt});
  detail.snapshot.prompt.source_ref = A06.prompt_ref;
  const promptReads = [];
  const promptOptions = {json: [{
    ref: A06.prompt_ref, name: "Платформа", prompt: A06.prompt, group: "platform",
    source_ref: null, source_run_id: null,
  }]};
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs" && request.method() === "POST") {
      return route.fulfill({status: 202, json: {run_id: detail.run_id, status: "queued",
        scenario_session_id: detail.runtime_ids.scenario_session_id, job_id: detail.runtime_ids.job_id}});
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) return route.fulfill({json: detail});
    if (pathname === "/v1/atom-lab/runs" || pathname === "/v1/atom-lab/presets") {
      return route.fulfill({json: {items: [], next_cursor: null}});
    }
    if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
      const pending = Promise.withResolvers();
      promptReads.push(pending.resolve);
      return route.fulfill(await pending.promise);
    }
    return route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#reasoning-effort").selectOption("high");
  await page.locator("#run-button").click();
  const result = page.getByRole("region", {name: "Результат", exact: true});
  const save = result.getByRole("button", {name: "Сохранить снимок как пресет"});
  const progress = result.getByRole("status");
  const objective = page.getByRole("textbox", {name: "Цель", exact: true});
  await expect(save).toBeVisible();
  await save.press("Enter");
  await expect(save).toBeFocused();
  await expect(save).toBeDisabled();
  await expect(progress).toHaveText("Проверяем источник промпта…");
  await expect(progress).toBeVisible();
  await expect(objective).toBeEditable();
  await page.keyboard.press("Enter");
  await expect.poll(() => promptReads.length).toBe(1);
  promptReads[0]({status: 503, json: {error: {message: "Источник временно недоступен"}}});
  await expect(result.getByRole("alert")).toContainText("Источник временно недоступен");
  await expect(progress).toBeEmpty();
  await expect(save).toBeEnabled();
  await expect(save).toBeFocused();

  await save.press("Enter");
  await expect.poll(() => promptReads.length).toBe(2);
  await objective.fill("Новая цель черновика");
  await page.locator("#history-button").click();
  await showWorkbench(page);
  await expect(save).toBeEnabled();
  await expect(progress).toBeEmpty();
  const abandonedCheck = page.waitForResponse("**/atoms/A06/prompts");
  promptReads[1](promptOptions);
  await (await abandonedCheck).finished();
  await expect(page.locator("#presets-panel")).toBeHidden();
  await expect(objective).toHaveValue("Новая цель черновика");

  await save.press("Enter");
  await expect.poll(() => promptReads.length).toBe(3);
  promptReads[2](promptOptions);
  await expect(page.locator("#preset-name")).toBeFocused();
  await expect(page.locator("#preset-source")).toContainText(detail.run_id);
});

test("model capabilities, stale state, and refresh are explicit", async ({page}) => {
  let refreshRequests = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/models/refresh", async (route) => {
    refreshRequests += 1;
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({...MODEL_CATALOG, refresh_status: "pending"}),
    });
  });
  await unlockAtom(page, "A01", {models: () => refreshRequests === 0 ? MODEL_CATALOG : {
    ...MODEL_CATALOG,
    items: [...MODEL_CATALOG.items, {model_id: "gpt-new", compatibility: "compatible", reason: "confirmed_openai_text_gpt", reasoning_supported: false, allowed_reasoning_efforts: null, provenance: {}}],
    snapshot_id: "catalog-snapshot-2",
    stale: false,
    refresh_status: "current",
  }});

  await expect(page.locator("#model-catalog-warning")).toContainText("устарел");
  await expect(page.locator("#model-catalog-warning")).toContainText("2026-09-19T10:00:00Z");
  await expect(page.locator("#model-select option")).toHaveCount(5);
  await expect(page.locator('#model-select option[value="gpt-unknown-compatibility"]')).toBeDisabled();
  await expect(page.locator('#model-select option[value="gpt-unknown-compatibility"]')).toContainText("совместимость неизвестна");
  await expect(page.locator('#model-select option[value="gpt-unsupported"]')).toBeDisabled();
  await expect(page.locator('#model-select option[value="gpt-unsupported"]')).toContainText("не поддерживается");

  await page.locator("#model-select").selectOption("gpt-no-reasoning");
  await expect(page.locator("#reasoning-effort")).toBeDisabled();
  await expect(page.locator("#reasoning-help")).toContainText("нельзя задать");

  await page.locator("#model-select").selectOption("gpt-unknown");
  await expect(page.locator("#reasoning-effort")).toBeDisabled();
  await expect(page.locator("#reasoning-help")).toContainText("не подтвердил");

  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");

  await page.locator("#refresh-models").click();
  await expect.poll(() => refreshRequests).toBe(1);
  await expect(page.locator("#model-catalog-warning")).toContainText("обновление запрошено");
  await expect(page.locator('#model-select option[value="gpt-new"]')).toHaveCount(1);
  await expect(page.locator("#model-catalog-warning")).toBeEmpty();
  await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
  await expect(page.locator("#reasoning-effort")).toHaveValue("high");
});

test("catalog refresh requires explicit model reselection when the selected model disappears", async ({page}) => {
  let refreshed = false;
  await page.route("http://atom-lab.test/v1/atom-lab/models/refresh", async (route) => {
    refreshed = true;
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
      snapshot_id: "catalog-snapshot-removed-model",
      last_success_at: "2026-09-22T00:00:00Z",
      stale: false,
      refresh_status: "current",
      error: null,
    })});
  });
  await unlockAtom(page, "A05", {models: () => refreshed ? {
    ...MODEL_CATALOG,
    items: MODEL_CATALOG.items.filter(({model_id: modelId}) => modelId !== "gpt-supported"),
    stale: false,
  } : MODEL_CATALOG});
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");

  await page.locator("#refresh-models").click();

  await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
  await expect(page.locator('#model-select option[value="gpt-supported"]')).toBeDisabled();
  await expect(page.locator("#model-catalog-warning")).toContainText("Выберите модель заново");
  await expect(page.locator("#run-button")).toBeDisabled();

  await page.locator("#model-select").selectOption("gpt-no-reasoning");
  await expect(page.locator("#model-catalog-warning")).toBeEmpty();
  await expect(page.locator("#run-button")).toBeEnabled();
});

test("catalog refresh requires explicit effort reselection when the selected effort disappears", async ({page}) => {
  let refreshed = false;
  await page.route("http://atom-lab.test/v1/atom-lab/models/refresh", async (route) => {
    refreshed = true;
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
      snapshot_id: "catalog-snapshot-removed-effort",
      last_success_at: "2026-09-22T00:00:00Z",
      stale: false,
      refresh_status: "current",
      error: null,
    })});
  });
  await unlockAtom(page, "A05", {models: () => refreshed ? {
    ...MODEL_CATALOG,
    items: MODEL_CATALOG.items.map((item) => item.model_id === "gpt-supported"
      ? {...item, allowed_reasoning_efforts: ["low"]}
      : item),
    stale: false,
  } : MODEL_CATALOG});
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");

  await page.locator("#refresh-models").click();

  await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
  await expect(page.locator("#reasoning-effort")).toHaveValue("high");
  await expect(page.locator('#reasoning-effort option[value="high"]')).toBeDisabled();
  await expect(page.locator("#reasoning-help")).toContainText("Выберите уровень заново");
  await expect(page.locator("#run-button")).toBeDisabled();

  await page.locator("#reasoning-effort").selectOption("low");
  await expect(page.locator("#reasoning-help")).not.toContainText("Выберите уровень заново");
  await expect(page.locator("#run-button")).toBeEnabled();
});

for (const reasoningSupported of [false, null]) {
  const mode = reasoningSupported === false ? "unsupported" : "unknown";
  test(`catalog refresh allows explicit no-effort recovery when reasoning becomes ${mode}`, async ({page}) => {
    let refreshed = false;
    await page.route("http://atom-lab.test/v1/atom-lab/models/refresh", async (route) => {
      refreshed = true;
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        snapshot_id: `catalog-snapshot-reasoning-${mode}`,
        last_success_at: "2026-09-22T00:00:00Z",
        stale: false,
        refresh_status: "current",
        error: null,
      })});
    });
    await unlockAtom(page, "A05", {models: () => refreshed ? {
      ...MODEL_CATALOG,
      items: MODEL_CATALOG.items.map((item) => item.model_id === "gpt-supported"
        ? {...item, reasoning_supported: reasoningSupported, allowed_reasoning_efforts: null}
        : item),
      stale: false,
    } : MODEL_CATALOG});
    await page.locator("#fill-example").click();
    await page.locator("#model-select").selectOption("gpt-supported");
    await page.locator("#reasoning-effort").selectOption("high");

    await page.locator("#refresh-models").click();

    await expect(page.locator("#reasoning-effort")).toBeEnabled();
    await expect(page.locator("#reasoning-effort")).toHaveValue("high");
    await expect(page.locator("#run-button")).toBeDisabled();

    await page.locator("#reasoning-effort").selectOption("");
    await expect(page.locator("#reasoning-effort")).toBeDisabled();
    await expect(page.locator("#run-button")).toBeEnabled();
  });
}

test("one accepted submission survives draft edits and renders safe result diagnostics", async ({page}) => {
  let posts = 0;
  let reads = 0;
  const submittedBodies = [];
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    posts += 1;
    submittedBodies.push(route.request().postDataJSON());
    await new Promise((resolve) => setTimeout(resolve, 80));
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-1", scenario_session_id: "session-1", job_id: "job-1", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-1", async (route) => {
    reads += 1;
    const terminal = reads > 1;
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-1",
      status: terminal ? "succeeded" : "running",
      snapshot: {
        atom_id: "A05",
        scenario: {id: "scenario-kernel-demo", version: 1},
        workflow: {id: "workflow-kernel-demo", version: 1, step_id: "main", definition: {}},
        action: {type: A05.action_type, definition_version: 1, definition: {}, config_id: A05.base_action_config_id, config_schema_version: 1, config_definition: {}},
        prompt: {ref: "prompt.a05", version: 1, base: "Базовый промпт A05", content: "Базовый промпт A05"},
        schemas: snapshotAtomContract(A05).schemas,
        input: A05.example_input,
        provider: {policy_ref: "policy.default", policy: {}, model_id: "openai/gpt-supported", reasoning_effort: "high", capability_snapshot_id: "snapshot-1", capability_provenance: {}},
        preset: {id: null, version: null},
        execution_definition_hash: "execution-hash-1",
      },
      runtime_ids: {scenario_session_id: null, job_id: null, action_run_id: terminal ? "action-1" : null, artifact_id: terminal ? "artifact-1" : null},
      result: terminal ? {summary: "<img id=unsafe src=x onerror=alert(1)>", score: 0, accepted: false} : null,
      diagnostics: {error_code: null, duration_ms: terminal ? 1250 : null, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: "high", response_model_id: terminal ? "gpt-confirmed" : null, validation_attempts: terminal ? 2 : 0, transport_attempts: terminal ? 3 : 0, physical_calls: terminal ? 3 : 0, succeeded_first_attempt: false, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: terminal ? "2026-09-20T10:00:01Z" : null,
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");

  await page.locator("#run-button").dblclick();
  await expect.poll(() => posts).toBe(1);
  await page.getByLabel("Контекст").fill("Изменённый после запуска черновик");

  await expect(page.locator("#run-state")).toContainText("Завершён");
  await expect(page.locator("#run-status")).toHaveAttribute("data-tone", "success");
  await expect(page.locator("#launch-outcome")).toHaveAttribute("data-tone", "success");
  await expect(page.locator("#launch-outcome-text")).toHaveText("Завершён успешно");
  await page.getByRole("button", {name: "К ответу"}).click();
  await expect(page.getByRole("heading", {name: "Ответ", exact: true})).toBeFocused();
  await expect(page.locator("#run-status-help")).toContainText("проверку контракта");
  await expect(page.locator("#run-metadata .metadata-group")).toHaveCount(2);
  await expect(page.locator("#submitted-snapshot")).toContainText("Оценка");
  await expect(page.locator("#submitted-snapshot")).not.toContainText("Изменённый после запуска");
  await expect(page.locator("#submitted-snapshot")).not.toContainText("execution-hash-1");
  await expect(page.locator("#run-metadata")).toContainText("Запрошенная модель");
  await expect(page.locator("#run-metadata")).toContainText("Модель в ответе");
  await expect(page.locator("#run-metadata")).toContainText("1250 мс");
  await expect(page.locator("#result-readable")).toContainText("<img id=unsafe");
  await expect(page.locator("#unsafe")).toHaveCount(0);
  await expect(page.locator("#run-diagnostics")).toContainText("artifact-1");
  await expect(page.locator("#run-diagnostics")).toContainText("session-1");
  await expect(page.locator("#run-diagnostics")).toContainText("job-1");
  expect(submittedBodies).toEqual([{
    atom_id: "A05",
    input: A05.example_input,
    prompt: A05.prompt,
    prompt_source_ref: A05.prompt_ref,
    model_id: "openai/gpt-supported",
    reasoning_effort: "high",
    preset_ref: null,
    expected_contract: expectedAtomContract(A05),
  }]);
});

test("a rejected next submission never replaces the previously accepted run card", async ({page}) => {
  let posts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    posts += 1;
    if (posts === 1) {
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-a", scenario_session_id: "session-a", job_id: "job-a", status: "queued"})});
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({error: {code: "lab_invalid_request", message: "Run B rejected.", field_errors: []}, request_id: "request-b"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-a", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-a", status: "succeeded",
      snapshot: {...snapshotAtomContract(A05), input: A05.example_input, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-a", job_id: "job-a", action_run_id: "action-a", artifact_id: "artifact-a"},
      result: {questions: ["Результат A"]},
      diagnostics: {error_code: null, duration_ms: 800, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: "gpt-confirmed", validation_attempts: 1, transport_attempts: 1, physical_calls: 1, succeeded_first_attempt: true, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("Завершён");
  await expect(page.locator("#submitted-snapshot")).toContainText(A05.prompt);
  await expect(page.locator("#run-diagnostics")).toContainText("artifact-a");

  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-editor").fill("Непринятый промпт B");
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("Отправка запуска");
  await expect(page.locator("#submitted-snapshot")).toContainText(A05.prompt);
  await expect(page.locator("#submitted-snapshot")).not.toContainText("Непринятый промпт B");
  await expect(page.locator("#run-diagnostics")).toContainText("artifact-a");
  await expect(page.locator("#result-readable")).toContainText("Результат A");

  await expect(page.locator("#run-state")).toContainText("lab_invalid_request");
  await expect(page.locator("#run-status")).toHaveAttribute("data-tone", "error");
  await expect(page.locator("#run-status-help")).toContainText("данные предыдущего принятого запуска run-a");
  await expect(page.locator("#submitted-snapshot")).toContainText(A05.prompt);
  await expect(page.locator("#run-diagnostics")).toContainText("artifact-a");
});

for (const outcome of ["success", "invalid", "diagnostics"]) {
  for (const rejection of ["quota", "validation", "network"]) {
    test(`retained ${outcome} data identifies its accepted run after an identical ${rejection} submission`, async ({page}) => {
      const sourceRunId = "atom_lab_run_01730885400000000000_0000000001_0123456789abcdef0123456789abcdef";
      const bodies = [];
      let rejectSubmission;
      const rejected = new Promise(resolve => { rejectSubmission = resolve; });
      let finishNextRun;
      const nextRun = new Promise(resolve => { finishNextRun = resolve; });
      await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
        bodies.push(route.request().postDataJSON());
        if (bodies.length === 2) {
          await rejected;
          if (rejection === "network") await route.abort("connectionfailed");
          else await route.fulfill({status: rejection === "quota" ? 429 : 422, json: {
            error: {code: rejection === "quota" ? "quota_exhausted" : "lab_invalid_request", message: "Run B rejected.", field_errors: []},
            request_id: "request-b",
          }});
          return;
        }
        const suffix = bodies.length === 1 ? "source" : "next";
        await route.fulfill({status: 202, json: {
          run_id: suffix === "source" ? sourceRunId : "run-next", scenario_session_id: `session-${suffix}`, job_id: `job-${suffix}`, status: "queued",
        }});
      });
      await page.route(`http://atom-lab.test/v1/atom-lab/runs/${sourceRunId}`, async route => {
        const detail = historyDetail({runId: sourceRunId, prompt: A06.prompt, reasoningEffort: null});
        detail.runtime_ids = {scenario_session_id: "session-source", job_id: "job-source", action_run_id: "action-source", artifact_id: outcome === "success" ? "artifact-source" : null};
        detail.diagnostics.physical_calls = 3;
        if (outcome !== "success") {
          detail.status = "failed";
          detail.result = null;
          detail.diagnostics.error_code = outcome === "invalid" ? "structured_output_validation_failed" : "provider_unavailable";
          detail.diagnostics.debug_artifacts = outcome === "invalid" ? [{
            artifact_id: "debug-source", error_code: detail.diagnostics.error_code,
            raw_output_text: "<invalid>Ответ запуска A</invalid>", truncated: true, redacted: true,
          }] : [];
        }
        await route.fulfill({json: detail});
      });
      await page.route("http://atom-lab.test/v1/atom-lab/runs/run-next", async route => {
        await nextRun;
        const detail = historyDetail({runId: "run-next", prompt: A06.prompt, reasoningEffort: null});
        detail.runtime_ids = {scenario_session_id: "session-next", job_id: "job-next", action_run_id: "action-next", artifact_id: "artifact-next"};
        detail.result = {summary: "Новый результат C"};
        await route.fulfill({json: detail});
      });
      await unlockAtom(page, "A06");
      await page.locator("#fill-example").click();
      await page.locator("#run-button").click();
      await expect(page.locator("#run-button")).toBeEnabled();
      await expect(page.locator("#run-state")).toContainText(outcome === "success" ? "Завершён успешно" : "Ошибка");
      await expect(page.locator("#run-status-help")).toContainText(`данные принятого запуска ${sourceRunId}`);
      await expect(page.locator("#run-status-help")).not.toContainText("предыдущего");
      await expect(page.locator("#result-section"))[outcome === "success" ? "toBeVisible" : "toBeHidden"]();
      await expect(page.locator("#invalid-response"))[outcome === "invalid" ? "toBeVisible" : "toBeHidden"]();
      if (outcome === "invalid") {
        await expect(page.locator("#invalid-response-note")).toHaveText("Сырой ответ обрезан. Содержимое ответа скрыто полностью или частично.");
        await expect(page.locator("#invalid-response-raw")).toBeHidden();
      }
      await expect(page.locator("#run-metadata-section")).toBeVisible();
      await expect(page.locator("#run-metadata dl > div").filter({hasText: "Вызовов провайдера"})).toHaveText("Вызовов провайдера3");
      const retained = new Map();
      for (const id of ["submitted-snapshot", "run-diagnostics", "run-metadata", "result-json", "invalid-response-raw"]) {
        retained.set(id, await page.locator(`#${id}`).textContent());
      }
      await expect(page.locator("#submitted-snapshot")).toBeHidden();
      await expect(page.locator("#response-draft-warning")).toBeHidden();

      await page.locator("#run-button").click();
      await expect(page.locator("#run-state")).toHaveText("Отправка запуска…");
      await expect(page.locator("#run-status-help")).toContainText(`данные предыдущего принятого запуска ${sourceRunId}`);
      rejectSubmission();
      if (rejection === "network") await expect(page.locator("#retry-submit")).toBeVisible();
      else await expect(page.locator("#run-state")).toContainText(rejection === "quota" ? "quota_exhausted" : "lab_invalid_request");
      expect(bodies).toHaveLength(2);
      expect(bodies[1]).toEqual(bodies[0]);
      for (const [id, text] of retained) await expect(page.locator(`#${id}`)).toHaveText(text);
      await expect(page.locator("#run-metadata-section")).toBeVisible();
      await expect(page.locator("#result-section"))[outcome === "success" ? "toBeVisible" : "toBeHidden"]();
      await expect(page.locator("#invalid-response"))[outcome === "invalid" ? "toBeVisible" : "toBeHidden"]();
      await expect(page.locator("#run-status-help")).toBeVisible();
      await expect(page.locator("#run-status-help")).toContainText(`данные предыдущего принятого запуска ${sourceRunId}`);
      await expect(page.locator("#response-draft-warning")).toBeHidden();
      if (outcome === "invalid" && rejection === "quota") {
        for (const width of [1280, 320]) {
          await page.setViewportSize({width, height: 1000});
          expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
          expect(await page.locator("#run-status-help").evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
        }
        await page.locator(".result-card").screenshot({path: test.info().outputPath("invalid-quota-320.png")});
      }
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#run-prompt-ref")).toHaveText(A06.prompt_ref);
      await page.locator("#prompt-editor").fill("Изменённый после отклонения черновик");
      await expect(page.locator("#response-draft-warning")).toBeVisible();
      await page.locator("#prompt-editor").fill(A06.prompt);
      await expect(page.locator("#response-draft-warning")).toBeHidden();
      await expect(page.locator("#run-status-help")).toContainText(`данные предыдущего принятого запуска ${sourceRunId}`);

      await page.locator(rejection === "network" ? "#retry-submit" : "#run-button").click();
      await expect(page.locator("#run-state")).toHaveText("Ожидает запуска");
      await expect(page.locator("#run-status-help")).toContainText("данные принятого запуска run-next");
      await expect(page.locator("#run-status-help")).not.toContainText("предыдущего");
      await expect(page.locator("#run-diagnostics")).toContainText("session-next");
      await expect(page.locator("#run-diagnostics")).not.toContainText(sourceRunId);
      await expect(page.locator("#result-section")).toBeHidden();
      await expect(page.locator("#invalid-response")).toBeHidden();
      finishNextRun();
      await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
      await expect(page.locator("#result-readable")).toContainText("Новый результат C");
      await expect(page.locator("#run-diagnostics")).toContainText("artifact-next");
      await expect(page.locator("#run-status-help")).toContainText("данные принятого запуска run-next");
      await expect(page.locator("#run-status-help")).not.toContainText("предыдущего");
      await expect(page.locator("#response-draft-warning")).toBeHidden();
      expect(bodies).toHaveLength(3);
      expect(bodies[2]).toEqual(bodies[0]);
    });
  }
}

test("accepted runtime IDs are visible before the protected detail read returns", async ({page}) => {
  let releaseDetail;
  const detailBlocked = new Promise((resolve) => { releaseDetail = resolve; });
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-accepted", scenario_session_id: "session-accepted", job_id: "job-accepted", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-accepted", async (route) => {
    await detailBlocked;
    await route.abort("connectionfailed");
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#run-diagnostics")).toContainText("run-accepted", {timeout: 1_000});
  await expect(page.locator("#run-diagnostics")).toContainText("session-accepted");
  await expect(page.locator("#run-diagnostics")).toContainText("job-accepted");
  releaseDetail();
});

test("network submission retry reuses the idempotency key and polling reconnects without another POST", async ({page}) => {
  const keys = [];
  const bodies = [];
  let reads = 0;
  let modelAvailable = true;
  await page.route("http://atom-lab.test/v1/atom-lab/models/refresh", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({...MODEL_CATALOG, refresh_status: "pending"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    bodies.push(route.request().postDataJSON());
    if (keys.length === 1) {
      await route.abort("connectionfailed");
      return;
    }
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-recovery", scenario_session_id: "session-recovery", job_id: "job-recovery", status: "succeeded"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-recovery", async (route) => {
    reads += 1;
    if (reads === 1) {
      await route.abort("connectionfailed");
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-recovery", status: "succeeded",
      snapshot: {...snapshotAtomContract(A05), input: A05.example_input, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-recovery", job_id: "job-recovery", action_run_id: "action-recovery", artifact_id: "artifact-recovery"},
      result: {questions: ["Когда срок?"]},
      diagnostics: {error_code: null, duration_ms: 900, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 1, transport_attempts: 1, physical_calls: 1, succeeded_first_attempt: true, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05", {models: () => modelAvailable
    ? MODEL_CATALOG
    : {...MODEL_CATALOG, items: MODEL_CATALOG.items.filter(({model_id: modelId}) => modelId !== "gpt-supported"), stale: false, refresh_status: "current"}});
  await page.locator("#fill-example").click();

  await page.locator("#run-button").click();
  await expect(page.locator("#retry-submit")).toBeVisible();
  await expect(page.locator("#run-state")).toContainText("Черновик сохранён");
  await expect(page.locator("#run-button")).toBeDisabled();
  await page.getByLabel("Контекст").fill("");
  modelAvailable = false;
  await page.locator("#refresh-models").click();
  await expect(page.locator('#model-select option[value="gpt-supported"]')).toBeDisabled();
  await page.locator("#retry-submit").click();
  await expect(page.locator("#run-button")).toBeDisabled();
  await expect(page.locator("#run-state")).toContainText("Переподключение… Запуск принят; текущее состояние временно неизвестно.");
  await expect(page.locator("#run-status")).toHaveAttribute("data-tone", "warning");
  await expect(page.locator("#launch-outcome-text")).toContainText("состояние временно неизвестно");
  await expect(page.locator("#run-button")).toBeDisabled();
  await expect(page.locator("#run-state")).toContainText("Завершён");
  await expect(page.locator("#run-button")).toBeDisabled();
  await page.locator("#model-select").selectOption("gpt-no-reasoning");
  await expect(page.locator("#run-button")).toBeEnabled();

  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(bodies[1]).toEqual(bodies[0]);
  expect(reads).toBe(2);
});

test("a delayed accepted run never attaches its source id to a newly selected draft", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  let runBody = null;
  let presetBody = null;
  const detail = historyDetail({runId: "run-delayed-owner"});
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs" && request.method() === "POST") {
      runBody = request.postDataJSON();
      await new Promise((resolve) => setTimeout(resolve, 250));
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        run_id: detail.run_id,
        scenario_session_id: detail.runtime_ids.scenario_session_id,
        job_id: detail.runtime_ids.job_id,
        status: detail.status,
      })});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "POST") {
      presetBody = request.postDataJSON();
      await route.abort("connectionfailed");
      return;
    }
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#run-diagnostics")).toContainText(detail.run_id);

  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await editPreset(page);
  await page.locator("#preset-name").fill("A05 после чужого запуска");
  await page.locator("#save-preset").click();
  await expect.poll(() => presetBody).not.toBeNull();

  expect(runBody.atom_id).toBe("A06");
  expect(presetBody.atom_id).toBe("A05");
  expect(presetBody.source_run_id).toBeNull();
});

test("an idempotent run retry keeps its original draft ownership after navigation", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  const runBodies = [];
  let presetBody = null;
  const detail = historyDetail({runId: "run-retry-owner"});
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs" && request.method() === "POST") {
      runBodies.push(request.postDataJSON());
      if (runBodies.length === 1) {
        await route.abort("connectionfailed");
        return;
      }
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        run_id: detail.run_id,
        scenario_session_id: detail.runtime_ids.scenario_session_id,
        job_id: detail.runtime_ids.job_id,
        status: detail.status,
      })});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "POST") {
      presetBody = request.postDataJSON();
      await route.abort("connectionfailed");
      return;
    }
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();
  await expect(page.locator("#retry-submit")).toBeVisible();
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await page.locator("#retry-submit").click();
  await expect(page.locator("#run-diagnostics")).toContainText(detail.run_id);

  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await editPreset(page);
  await page.locator("#preset-name").fill("A05 после retry чужого запуска");
  await page.locator("#save-preset").click();
  await expect.poll(() => presetBody).not.toBeNull();

  expect(runBodies).toHaveLength(2);
  expect(runBodies[1]).toEqual(runBodies[0]);
  expect(runBodies[0].atom_id).toBe("A06");
  expect(presetBody.atom_id).toBe("A05");
  expect(presetBody.source_run_id).toBeNull();
});

test("retryable HTTP submission responses preserve the frozen replay", async ({page}) => {
  const keys = [];
  const bodies = [];
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    bodies.push(route.request().postDataJSON());
    if (keys.length === 1) {
      await route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({
        error: {code: "provider_unavailable", message: "Admission outcome unknown.", field_errors: []},
        request_id: "request-retryable",
      })});
      return;
    }
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-http-recovery", scenario_session_id: "session-http-recovery", job_id: "job-http-recovery", status: "succeeded"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-http-recovery", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-http-recovery", status: "succeeded",
      snapshot: snapshotAtomContract(A05),
      runtime_ids: {scenario_session_id: "session-http-recovery", job_id: "job-http-recovery", action_run_id: "action-http-recovery", artifact_id: "artifact-http-recovery"},
      result: {questions: ["Recovered"]},
      diagnostics: {error_code: null, duration_ms: 500, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 1, transport_attempts: 1, physical_calls: 1, succeeded_first_attempt: true, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#retry-submit")).toBeVisible();
  await expect(page.locator("#run-state")).toContainText("Результат отправки неизвестен");
  await expect(page.locator("#run-button")).toBeDisabled();
  await page.locator("#retry-submit").click();
  await expect(page.locator("#run-state")).toContainText("Завершён");

  expect(keys).toHaveLength(2);
  expect(keys[1]).toBe(keys[0]);
  expect(bodies[1]).toEqual(bodies[0]);
});

test("client validation blocks admission and the corrected draft can be submitted", async ({page}) => {
  let posts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    posts += 1;
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-valid", scenario_session_id: "session-valid", job_id: "job-valid", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-valid", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-valid", status: "failed",
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-valid", job_id: "job-valid", action_run_id: null, artifact_id: null}, result: null,
      diagnostics: {error_code: "provider_unavailable", duration_ms: 20, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 2, physical_calls: 2, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");

  await page.locator("#run-button").click();
  await expect(page.locator("#validation-errors")).toContainText("Обязательное поле");
  expect(posts).toBe(0);
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#run-state")).toContainText("Ошибка");
  await expect(page.locator("#run-status")).toHaveAttribute("data-tone", "error");
  await expect(page.locator("#run-status-help")).toContainText("provider_unavailable");
  await expect(page.locator("#run-diagnostics")).toContainText("provider_unavailable");
  expect(posts).toBe(1);
});

test("final invalid output is diagnostics, never a successful result", async ({page}) => {
  const frozenOutput = {type: "object", properties: {frozen: {type: "string"}}};
  const rawOutput = JSON.stringify({frozen: "<script id=bad>boom()</script>"});
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-invalid", scenario_session_id: "session-invalid", job_id: "job-invalid", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-invalid", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-invalid", status: "failed",
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: "low",
        schemas: {output: {content: frozenOutput}}},
      runtime_ids: {scenario_session_id: "session-invalid", job_id: "job-invalid", action_run_id: "action-invalid", artifact_id: null}, result: null,
      diagnostics: {error_code: "structured_output_validation_failed", duration_ms: 500, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: "low", response_model_id: null, validation_attempts: 2, transport_attempts: 2, physical_calls: 2, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [{artifact_id: "debug-1", error_code: "structured_output_validation_failed", raw_output_text: rawOutput, truncated: false, redacted: true}], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("low");
  await page.locator("#run-button").click();

  await expect(page.locator("#invalid-response")).toBeVisible();
  await expect(page.locator("#invalid-response-title")).toHaveText("Ответ не прошёл проверку по контракту атома");
  await expect(page.locator("#run-status")).toHaveAttribute("data-tone", "error");
  await expect(page.locator("#show-response")).toBeFocused();
  await expect(page.locator("#invalid-response-raw")).toBeHidden();
  await page.getByRole("button", {name: "Открыть диагностику"}).click();
  await expect(page.locator("#run-diagnostics-summary")).toBeFocused();
  await expect(page.locator("#run-diagnostics")).toContainText("structured_output_validation_failed");
  await page.getByRole("button", {name: "К схеме выхода"}).click();
  await expect(page.locator("#run-diagnostic-schema summary")).toBeFocused();
  expect(JSON.parse(await page.locator("#run-diagnostic-schema-json").textContent())).toEqual(frozenOutput);
  await page.getByRole("button", {name: "К сырому ответу"}).click();
  await expect(page.locator("#invalid-response-sample summary")).toBeFocused();
  await expect(page.locator("#invalid-response-note")).toHaveText("Содержимое ответа скрыто полностью или частично.");
  await expect(page.locator("#invalid-response-raw")).toHaveText(rawOutput);
  await expect(page.locator("#result-section")).toBeHidden();
  await expect(page.locator("#bad")).toHaveCount(0);
  await page.setViewportSize({width: 320, height: 844});
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  expect(await page.locator("#run-metadata dl > div").evaluateAll(rows => rows.every(row => {
    const [label, value] = row.children;
    return label.getBoundingClientRect().bottom <= value.getBoundingClientRect().top;
  }))).toBe(true);
});

test("admission rejection keeps the draft, hides transport retry, and a new launch gets a new key", async ({page}) => {
  const keys = [];
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    if (keys.length === 1) {
      await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({error: {code: "model_not_allowed", message: "Модель больше недоступна.", field_errors: [{path: "model_id", message: "Недоступно"}]}, request_id: "request-1"})});
      return;
    }
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-new", scenario_session_id: "session-new", job_id: "job-new", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-new", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-new", status: "failed", snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-new", job_id: "job-new", action_run_id: null, artifact_id: null}, result: null,
      diagnostics: {error_code: "provider_unavailable", duration_ms: 1, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 1, physical_calls: 1, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: null, finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();

  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("model_not_allowed");
  await expect(page.locator("#retry-submit")).toBeHidden();
  await expect(page.getByLabel("Контекст")).toHaveValue("Оценка");
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("Ошибка");

  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe(keys[1]);
});

for (const replay of [false, true]) {
  test(`default platform run source stays frozen across publication${replay ? " and idempotent retry" : ""}`, async ({page}) => {
    page.on("dialog", dialog => dialog.accept());
    const fresh = {...A06, prompt_ref: "prompt.a06.v2", prompt: "Опубликованная платформа v2"};
    let published = false;
    const submissions = [];
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06**", async route => {
      const atom = published ? fresh : A06;
      await route.fulfill({json: new URL(route.request().url()).pathname.endsWith("/prompts") ? [{
        ref: atom.prompt_ref, name: "Платформа", prompt: atom.prompt, group: "platform", source_ref: null, source_run_id: null,
      }] : atom});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
      const payload = route.request().postDataJSON();
      submissions.push({payload, key: route.request().headers()["idempotency-key"]});
      if (replay && submissions.length === 1) {
        await route.abort("connectionfailed");
      } else if (payload.prompt_source_ref === A06.prompt_ref) {
        await route.fulfill({status: 422, json: {error: {
          code: "prompt_source_invalid", message: "Старая основа недоступна.",
          field_errors: [{path: "prompt_source_ref", message: "Старая основа недоступна."}],
        }, request_id: "published-platform"}});
      } else {
        await route.fulfill({status: 422, json: {error: {
          code: "input_invalid", message: "Контроль следующего запуска.", field_errors: [],
        }, request_id: "next-platform"}});
      }
    });
    await unlockAtom(page, "A06");
    await page.locator("#fill-example").click();
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#save-prompt")).toBeEnabled();
    await page.locator("#prompt-editor").fill("Правка опубликованного v1");
    published = true;
    await page.locator("#run-button").click();
    if (replay) {
      await expect(page.locator("#retry-submit")).toBeVisible();
      await page.locator("#prompt-editor").fill("Новая правка во время повтора");
      await page.locator("#retry-submit").click();
      expect(submissions[1]).toEqual(submissions[0]);
    }
    await expect(page.locator("#run-state")).toContainText("prompt_source_invalid");
    await expect(page.locator("#prompt-select")).toHaveValue(fresh.prompt_ref);
    await expect(page.locator("#prompt-editor")).toHaveValue(replay ? "Новая правка во время повтора" : "Правка опубликованного v1");
    await expect(page.locator("#run-button")).toBeEnabled();
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toContainText("Контроль следующего запуска");
    expect(submissions[0].payload.prompt_source_ref).toBe(A06.prompt_ref);
    expect(submissions.at(-1).payload.prompt_source_ref).toBeUndefined();
    expect(submissions.at(-1).key).not.toBe(submissions[0].key);
  });
}

for (const source of ["platform", "product"]) {
  for (const changedBase of [false, true]) {
    test(`late trial completion keeps submitted ${source} atom identity with ${changedBase ? "a new" : "the same"} base`, async ({page}) => {
      let published = false;
      let submitted;
      const submissions = [];
      let saved;
      let completeRun;
      const completion = new Promise(resolve => { completeRun = resolve; });
      const fresh = {...A06, prompt_ref: "prompt.a06.v2"};
      const product = {ref: "product.a06.v1", name: "Продукт", prompt: "Текст продукта", group: "product", source_ref: null, source_run_id: null};
      const atom = () => published && changedBase ? fresh : A06;
      await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06**", async route => {
        if (route.request().method() === "POST") {
          saved = route.request().postDataJSON();
          await route.fulfill({json: {...product, ...saved, ref: "lab.late-trial", group: "lab"}});
        } else await route.fulfill({json: new URL(route.request().url()).pathname.endsWith("/prompts") ? [{
          ref: atom().prompt_ref, name: "Платформа", prompt: atom().prompt, group: "platform", source_ref: null, source_run_id: null,
        }, product] : atom()});
      });
      await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
        submitted = route.request().postDataJSON();
        submissions.push(submitted);
        const runId = submissions.length === 1 ? "run-old-base" : "run-current-base";
        await route.fulfill({status: 202, json: {run_id: runId, scenario_session_id: "session-library", job_id: "job-library", status: "queued"}});
      });
      await page.route("http://atom-lab.test/v1/atom-lab/runs/run-*-base", async route => {
        await completion;
        const runId = new URL(route.request().url()).pathname.split("/").at(-1);
        const detail = historyDetail({runId, input: submitted.input, prompt: submitted.prompt});
        detail.snapshot.prompt.ref = submitted.expected_contract.prompt_ref;
        detail.snapshot.prompt.source_ref = submitted.prompt_source_ref;
        await route.fulfill({json: detail});
      });
      await unlockAtom(page, "A06");
      await page.locator("#fill-example").click();
      await page.locator("#reasoning-effort").selectOption("high");
      if (source === "product") {
        await page.locator("#prompt-tab").click();
        await page.locator("#prompt-select").selectOption(product.ref);
        await page.locator("#prompt-editor").fill("Проверяемый текст продукта");
      }
      await page.locator("#run-button").click();
      await expect(page.locator("#run-state")).toHaveText("Ожидает запуска");
      published = true;
      if (source === "product") await page.locator("#retry-prompts").dispatchEvent("click");
      else await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-load-status")).toBeEmpty();
      await expect(page.locator("#prompt-select")).toHaveValue(source === "product" ? product.ref : atom().prompt_ref);
      if (source === "product") {
        await expect(page.locator("#prompt-editor")).toHaveValue(submitted.prompt);
        await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
        await expect(page.locator("#reasoning-effort")).toHaveValue("high");
      }
      completeRun();
      await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
      await expect(page.locator("#response-draft-warning"))[changedBase ? "toBeVisible" : "toBeHidden"]();
      expect(JSON.parse(await page.locator("#submitted-snapshot").textContent())).toEqual({
        atom_id: submitted.atom_id, input: submitted.input, prompt: submitted.prompt,
        prompt_source_ref: submitted.prompt_source_ref, model_id: submitted.model_id,
        reasoning_effort: submitted.reasoning_effort,
      });
      await expect(page.locator("#result-json")).toHaveText(JSON.stringify({summary: "Готово"}, null, 2));
      await expect(page.locator("#run-diagnostics")).toContainText("run-old-base");
      if (changedBase) await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
      else await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill("Проверка позднего ответа");
      await page.locator("#save-prompt").click();
      await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
      expect(saved.source_ref).toBe(source === "product" ? product.ref : atom().prompt_ref);
      expect(saved.source_run_id).toBe(changedBase ? null : "run-old-base");
      expect(submitted.prompt_source_ref).toBe(source === "product" ? product.ref : A06.prompt_ref);
      await page.locator("#run-button").click();
      await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
      await expect(page.locator("#run-diagnostics")).toContainText("run-current-base");
      await expect(page.locator("#response-draft-warning")).toBeHidden();
      expect(submissions[1].expected_contract).toEqual(expectedAtomContract(atom()));
      expect(submissions[1].input).toEqual(submissions[0].input);
    });
  }
}

async function prepareRejectedSourceWrite(page, kind, {historyAtom = "A05"} = {}) {
  page.on("dialog", dialog => dialog.accept());
  const platform = {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null};
  const product = {ref: "product.a06.v1", name: "Продуктовый v1", prompt: "Текст продукта v1", group: "product", source_ref: null, source_run_id: null};
  const replacement = {...product, ref: "product.a06.v2", name: "Продуктовый v2", prompt: "Текст продукта v2"};
  const detail = historyDetail({runId: "run-write-source", prompt: "Исторический ручной текст"});
  detail.snapshot.prompt.source_ref = product.ref;
  const originalDetail = structuredClone(detail);
  let stored = {
    preset_id: "preset-write-source", version: 1, created_at: detail.created_at,
    name: "Исходный пресет", description: "Описание", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: "Ручной текст пресета", prompt_ref: A06.prompt_ref, prompt_source_ref: product.ref,
    example_input: A06.example_input, fixed_fields: [], model_id: "openai/gpt-supported",
    reasoning_effort: "high", source_run_id: detail.run_id,
  };
  const originalVersion = structuredClone(stored);
  const summary = () => ({...stored, latest_version: stored.version, updated_at: stored.created_at});
  const state = {
    reads: 0, writes: [], refreshStatus: 200, rejectionCode: kind === "prompt" ? "prompt_invalid" : "preset_contract_invalid",
    rejectionField: kind === "prompt" ? "source_ref" : "prompt_source_ref",
    writeGate: Promise.resolve(), refreshGate: Promise.resolve(),
    authoritativeAtom: A06, atomReads: 0, atomStatus: 200, atomGate: Promise.resolve(), malformedOptions: false, optionsOverride: null,
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async route => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (request.method() === "POST") {
      const payload = request.postDataJSON();
      state.writes.push({pathname, payload});
      await state.writeGate;
      if (state.writes.length === 1) {
        await route.fulfill({status: 422, json: {error: {
          code: state.rejectionCode, message: "Источник сохранения отклонён.",
          field_errors: [{path: state.rejectionField, message: "Источник больше недоступен."}],
        }, request_id: "write-source-rejection"}});
      } else if (pathname.endsWith("/prompts")) {
        await route.fulfill({json: {...product, ref: "lab.saved-source", group: "lab", ...payload}});
      } else {
        const {base_version: baseVersion, ...configuration} = payload;
        if (payload.source_run_id !== null) expect(payload).toMatchObject({
          source_run_id: detail.run_id, atom_id: originalVersion.atom_id,
          base_action_config_id: originalVersion.base_action_config_id,
          schema_refs: originalVersion.schema_refs, prompt_ref: originalVersion.prompt_ref,
        });
        stored = {...configuration, preset_id: stored.preset_id, version: (baseVersion ?? 0) + 1, created_at: stored.created_at};
        await route.fulfill({status: 201, json: {preset_id: stored.preset_id, version: stored.version, created_at: stored.created_at}});
      }
      return;
    }
    if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
      const read = ++state.reads;
      if (read > 1) await state.refreshGate;
      if (read > 1 && state.refreshStatus !== 200) {
        await route.fulfill({status: state.refreshStatus, json: {error: {code: "prompts_unavailable", message: "Источники временно недоступны."}}});
      } else await route.fulfill({json: state.optionsOverride ?? [
        ...(state.malformedOptions ? [] : [{...platform, ref: read === 1 ? A06.prompt_ref : state.authoritativeAtom.prompt_ref}]),
        state.writes.length === 0 ? product : replacement,
      ]});
      return;
    }
    if (pathname === "/v1/atom-lab/atoms/A06") {
      state.atomReads += 1;
      await state.atomGate;
      await route.fulfill({status: state.atomStatus, json: state.atomStatus === 200
        ? state.authoritativeAtom : {error: {code: "atom_lab_catalog_unavailable", message: "Атом временно недоступен."}}});
      return;
    }
    if (pathname.endsWith("/prompts")) {
      const atom = catalog().find(item => pathname.includes(`/${item.atom_id}/`));
      await route.fulfill({json: [{...platform, ref: atom.prompt_ref, prompt: atom.prompt}, {...product, ref: "product.a05.v1"}]});
      return;
    }
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({json: {items: kind === "version" || state.writes.length > 1 ? [summary()] : [], next_cursor: null}});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
      await route.fulfill({json: {items: [{...summary(), version: stored.version}], next_cursor: null}});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/${stored.version}`) {
      await route.fulfill({json: stored});
      return;
    }
    if (pathname === "/v1/atom-lab/runs") {
      await route.fulfill({json: {items: [{
        run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: stored.model_id,
        preset_id: null, preset_version: null, created_at: detail.created_at,
        started_at: detail.started_at, finished_at: detail.finished_at,
      }], next_cursor: null}});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({json: detail});
      return;
    }
    await route.fallback();
  });
  await unlockAtom(page, kind === "history" ? historyAtom : "A06");
  await page.locator("#fill-example").click();
  if (kind === "version") {
    await page.locator("#presets-button").click();
    await page.locator("#preset-list button").click();
    await page.locator("#edit-preset").click();
    await expect.poll(() => state.reads).toBe(1);
  } else {
    await page.locator("#prompt-tab").click();
    await page.locator("#prompt-select").selectOption(kind === "history" && historyAtom === "A05" ? "product.a05.v1" : product.ref);
    await page.locator("#prompt-editor").fill("Ручной текст владельца");
    if (kind === "history") {
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      await page.locator("#save-history-preset").click();
    } else if (kind === "preset") await editPreset(page);
  }
  const name = page.locator(kind === "prompt" ? "#save-prompt-name" : "#preset-name");
  if (kind === "prompt") await page.locator("#save-prompt-panel summary").click();
  await name.fill("  Имя владельца  ");
  const save = page.locator(kind === "prompt" ? "#save-prompt" : "#save-preset");
  const error = page.locator(kind === "prompt" ? "#save-prompt-status" : "#preset-error");
  return {state, product, replacement, detail, originalDetail, originalVersion, save, name, error};
}

for (const change of ["base", "schema", "config"]) {
  test(`pinned run admission recovers a still-valid product source after ${change} drift`, async ({page}) => {
    const {state, product} = await prepareRejectedSourceWrite(page, "prompt");
    const fresh = structuredClone(A06);
    if (change === "base") fresh.prompt_ref = "prompt.a06.v2";
    if (change === "schema") fresh.schema_refs.input.version = 2;
    if (change === "config") fresh.base_action_config_id = "config.a06.v2";
    state.authoritativeAtom = fresh;
    state.optionsOverride = [{...product, ref: fresh.prompt_ref, group: "platform"}, product];
    const submissions = [];
    await page.route("**/v1/atom-lab/runs", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      submissions.push({body: route.request().postDataJSON(), key: route.request().headers()["idempotency-key"]});
      await route.fulfill({status: 409, json: {error: {
        code: "contract_unavailable", message: "Контракт изменился.",
        field_errors: [{path: "expected_contract", message: "Проверьте контракт."}],
      }, request_id: "contract-pin"}});
    });
    await page.locator("#reasoning-effort").selectOption("high");
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toContainText("contract_unavailable");
    await expect.poll(() => state.atomReads).toBe(1);
    await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
    await expect(page.locator("#save-prompt-name")).toHaveValue("  Имя владельца  ");
    await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
    await expect(page.locator("#reasoning-effort")).toHaveValue("high");
    expect(submissions[0].body.expected_contract).toEqual({
      action_type: A06.action_type, base_action_config_id: A06.base_action_config_id,
      prompt_ref: A06.prompt_ref, schema_refs: A06.schema_refs,
      input_schema: A06.input_schema, output_schema: A06.output_schema,
    });
    expect(submissions[0].body.prompt_source_ref).toBe(product.ref);
    await expect(page.locator("#retry-submit")).toBeHidden();
    await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
    if (change !== "base") {
      await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
      await expect(page.locator("#run-button")).toBeDisabled();
      state.authoritativeAtom = A06;
      await page.locator("#retry-prompts").click();
      await expect.poll(() => state.atomReads).toBe(2);
    }
    await expect(page.locator("#run-button")).toBeEnabled();
    await page.locator("#run-button").click();
    await expect.poll(() => submissions.length).toBe(2);
    expect(submissions[1].key).not.toBe(submissions[0].key);
    expect(submissions[1].body.expected_contract.prompt_ref).toBe(change === "base" ? fresh.prompt_ref : A06.prompt_ref);
    expect(submissions[1].body.input).toEqual(A06.example_input);
  });
}

for (const rejection of ["contract", "source"]) {
  for (const change of ["platform", "manual"]) {
    test(`pending ${rejection} rejection respects a later ${change} source choice`, async ({page}) => {
      const {state, product} = await prepareRejectedSourceWrite(page, "prompt");
      state.authoritativeAtom = {...A06, schema_refs: {...A06.schema_refs,
        input: {...A06.schema_refs.input, version: 2}}};
      state.optionsOverride = [{...product, ref: A06.prompt_ref, group: "platform", prompt: A06.prompt}, product];
      let releasePost;
      const gate = new Promise(resolve => { releasePost = resolve; });
      const submissions = [];
      await page.route("**/v1/atom-lab/runs", async route => {
        if (route.request().method() !== "POST") return route.fallback();
        submissions.push(route.request().postDataJSON());
        await gate;
        await route.fulfill({status: rejection === "contract" ? 409 : 422, json: {error: {
          code: rejection === "contract" ? "contract_unavailable" : "prompt_source_invalid",
          message: "Отказ от отправленного запроса.", field_errors: [{
            path: rejection === "contract" ? "expected_contract" : "prompt_source_ref",
            message: "Отправленное значение устарело.",
          }],
        }, request_id: "changed-source"}});
      });
      await page.locator("#reasoning-effort").selectOption("high");
      await page.locator("#run-button").click();
      await expect.poll(() => submissions.length).toBe(1);
      await page.locator("#prompt-select").selectOption(A06.prompt_ref);
      const text = change === "manual" ? "Новый ручной текст после отправки" : A06.prompt;
      if (change === "manual") await page.locator("#prompt-editor").fill(text);
      releasePost();
      await expect(page.locator("#run-state")).toContainText(rejection === "contract" ? "contract_unavailable" : "prompt_source_invalid");
      if (rejection === "contract") {
        await expect.poll(() => state.atomReads).toBe(1);
        await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
        await expect(page.locator("#run-button")).toBeDisabled();
        await expect(page.locator("#save-prompt")).toBeDisabled();
        await page.locator("#run-button").dispatchEvent("click");
        await page.locator("#save-prompt").dispatchEvent("click");
        expect(submissions).toHaveLength(1);
        expect(state.writes).toHaveLength(0);
      } else {
        await expect(page.locator("#run-button")).toBeEnabled();
        await expect(page.locator("#save-prompt")).toBeEnabled();
        expect(state.atomReads).toBe(0);
        expect(state.reads).toBe(1);
      }
      await expect(page.locator("#prompt-select")).toHaveValue(A06.prompt_ref);
      await expect(page.locator("#prompt-editor")).toHaveValue(text);
      await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
      await expect(page.locator("#reasoning-effort")).toHaveValue("high");
      await expect(page.locator("#save-prompt-name")).toHaveValue("  Имя владельца  ");
      expect(submissions[0]).toMatchObject({prompt_source_ref: product.ref,
        prompt: "Ручной текст владельца", input: A06.example_input,
        expected_contract: expectedAtomContract(A06)});
    });
  }
}

for (const change of ["replacement-editor", "catalog", "new-base"]) {
  test(`pending contract rejection leaves a later ${change} authority usable`, async ({page}) => {
    const {state, product, save} = await prepareRejectedSourceWrite(page, "prompt");
    let releasePost;
    const gate = new Promise(resolve => { releasePost = resolve; });
    let posted = false;
    await page.route("**/v1/atom-lab/runs", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      posted = true;
      await gate;
      await route.fulfill({status: 409, json: {error: {code: "contract_unavailable",
        message: "Старый контракт отклонён.", field_errors: [{path: "expected_contract", message: "Старый контракт."}]},
      request_id: "replaced-contract"}});
    });
    await page.locator("#run-button").click();
    await expect.poll(() => posted).toBe(true);
    if (change === "new-base") {
      state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2", prompt: "Актуальная платформа"};
      state.optionsOverride = [{...product, ref: state.authoritativeAtom.prompt_ref, group: "platform",
        prompt: state.authoritativeAtom.prompt}, product];
      await save.click();
      await expect.poll(() => state.atomReads).toBe(1);
      await expect(save).toBeEnabled();
      await expect(page.locator("#prompt-select option[value='prompt.a06.v2']")).toHaveCount(1);
    } else {
      if (change === "catalog") {
        const reloaded = page.waitForResponse("**/v1/atom-lab/models");
        await page.locator("#access-form").dispatchEvent("submit");
        await reloaded;
      } else await page.getByRole("button", {name: /A05/}).click();
      await page.getByRole("button", {name: /A06/}).click();
      await page.locator("#input-tab").click();
      await page.locator("#fill-example").click();
      await page.locator("#prompt-tab").click();
      await page.locator("#prompt-editor").fill("Новый редактор");
    }
    await editPreset(page);
    await page.locator("#preset-name").fill("Открытая библиотека");
    const reads = state.atomReads;
    releasePost();
    await expect(page.locator("#run-state")).toContainText("contract_unavailable");
    await expect(page.locator("#presets-panel")).toBeVisible();
    await expect(page.locator("#preset-name")).toHaveValue("Открытая библиотека");
    await expect(page.locator("#save-preset")).toBeEnabled();
    await showWorkbench(page);
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#retry-prompts")).toBeHidden();
    await expect(page.locator("#prompt-editor")).toHaveValue(change === "new-base" ? "Ручной текст владельца" : "Новый редактор");
    expect(state.atomReads).toBe(reads);
  });
}

for (const source of ["removed", "stable", "detached"]) {
  test(`peer contract Retry updates the ${source} source reset baseline through Run and Save`, async ({page}) => {
    const {state, save, product, detail} = await prepareRejectedSourceWrite(page, "history", {historyAtom: "A06"});
    if (source === "detached") {
      detail.snapshot.prompt.source_ref = "retired.product.source";
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      await page.locator("#restore-history").click();
      await showWorkbench(page);
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-origin")).toContainText("Исторический источник недоступен");
      await page.locator("#prompt-editor").fill("Ручной текст владельца");
      await page.locator("#history-button").click();
      await page.locator("#save-history-preset").click();
    }
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2", base_action_config_id: "config.a06.v2"};
    state.optionsOverride = [{...product, ref: "prompt.a06.v2", group: "platform"}, product];
    await save.click();
    await expect(page.locator("#preset-error")).toContainText("Контракт атома изменился");
    await showWorkbench(page);
    await expect(page.locator("#run-button")).toBeDisabled();
    state.authoritativeAtom = structuredClone(A06);
    state.optionsOverride = [{...product, ref: A06.prompt_ref, group: "platform", prompt: A06.prompt},
      ...(source === "removed" ? [] : [product])];
    await page.locator("#presets-button").click();
    await page.getByRole("button", {name: "Повторить загрузку источника", exact: true}).click();
    await expect(save).toBeEnabled();
    await showWorkbench(page);
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
    await expect(page.locator("#prompt-select")).toHaveValue(source === "stable" ? product.ref : A06.prompt_ref);
    if (source !== "stable") await expect(page.locator("#prompt-origin")).toContainText("Исторический источник недоступен");
    await page.locator("#reset-prompt").click();
    const resetText = source === "stable" ? product.prompt : A06.prompt;
    await expect(page.locator("#prompt-editor")).toHaveValue(resetText);
    let submitted;
    const runId = `run-peer-reset-${source}`;
    await page.route("**/v1/atom-lab/runs", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      submitted = route.request().postDataJSON();
      await route.fulfill({status: 202, json: {run_id: runId, scenario_session_id: "session-library", job_id: "job-library", status: "queued"}});
    });
    await page.route(`**/v1/atom-lab/runs/${runId}`, async route => {
      const completed = historyDetail({runId, input: submitted.input, prompt: submitted.prompt,
        reasoningEffort: submitted.reasoning_effort});
      completed.snapshot.prompt.source_ref = submitted.prompt_source_ref ?? null;
      await route.fulfill({json: completed});
    });
    await page.locator("#run-button").click();
    await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    expect(submitted.prompt).toBe(resetText);
    expect(submitted.input).toEqual(A06.example_input);
    expect(submitted.prompt_source_ref).toBe(source === "stable" ? product.ref : undefined);
    const saved = [];
    await page.route("**/v1/atom-lab/atoms/A06/prompts", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      const body = route.request().postDataJSON();
      saved.push(body);
      await route.fulfill({status: 201, json: {...product, ...body, group: "lab", ref: "lab.peer-reset"}});
    });
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Проверенный сброс");
    await page.locator("#save-prompt").click();
    await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
    expect(saved).toEqual([{name: "Проверенный сброс", prompt: resetText,
      source_ref: source === "stable" ? product.ref : A06.prompt_ref, source_run_id: runId}]);
  });
}

for (const otherOwner of [false, true]) {
  test(`known shared contract failure blocks legacy history without a source${otherOwner ? " beside another atom" : ""}`, async ({page}) => {
    const {state, save, detail, product} = await prepareRejectedSourceWrite(page, "prompt");
    delete detail.snapshot.prompt.source_ref;
    const original = structuredClone(detail);
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2", base_action_config_id: "config.a06.v2"};
    state.optionsOverride = [{...product, ref: "prompt.a06.v2", group: "platform"}, product];
    await save.click();
    await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
    if (otherOwner) {
      await page.getByRole("button", {name: /A05/}).click();
      await page.locator("#prompt-editor").fill("Другой ручной черновик");
    }
    await page.locator("#history-button").click();
    await page.locator("#history-list .history-open").click();
    await page.locator("#save-history-preset").click();
    await expect.poll(() => state.atomReads).toBe(2);
    await expect(page.locator("#history-error")).toContainText("Контракт атома изменился");
    await expect(page.locator("#presets-panel")).toBeHidden();
    expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(original);
    expect(state.writes).toHaveLength(1);
    state.authoritativeAtom = A06;
    state.optionsOverride = [{...product, ref: A06.prompt_ref, group: "platform"}, product];
    await page.locator("#save-history-preset").click();
    await expect.poll(() => state.atomReads).toBe(3);
    await expect(page.locator("#save-preset")).toBeEnabled();
    await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
    await showWorkbench(page);
    await expect(page.locator("#prompt-editor")).toHaveValue(otherOwner ? "Другой ручной черновик" : "Ручной текст владельца");
    if (otherOwner) await expect(page.locator("#atom-title")).toContainText("A05");
  });
}

test("a forced contract recheck preserves an intentionally detached history source", async ({page}) => {
  const {state, detail} = await prepareRejectedSourceWrite(page, "prompt");
  detail.snapshot.prompt.source_ref = "retired.product.source";
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#restore-history").click();
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await expect(page.locator("#prompt-origin")).toContainText("Исторический источник недоступен");
  const submissions = [];
  await page.route("**/v1/atom-lab/runs", async route => {
    if (route.request().method() !== "POST") return route.fallback();
    submissions.push(route.request().postDataJSON());
    await route.fulfill({status: 409, json: {error: {
      code: "contract_unavailable", message: "Повторите проверку контракта.",
      field_errors: [{path: "expected_contract", message: "Проверьте контракт."}],
    }, request_id: "detached-pin"}});
  });
  await page.locator("#run-button").click();
  await expect.poll(() => state.atomReads).toBe(1);
  await expect(page.locator("#run-button")).toBeEnabled();
  await page.locator("#run-button").click();
  await expect.poll(() => submissions.length).toBe(2);
  expect(submissions.map(body => body.prompt_source_ref)).toEqual([undefined, undefined]);
  expect(submissions[1].prompt).toBe(detail.snapshot.prompt.content);
});

for (const change of ["base", "schema-version", "schema-content", "config", "action"]) {
test(`a successful run snapshot with changed ${change} cannot confirm the displayed contract`, async ({page}) => {
  const {state, product} = await prepareRejectedSourceWrite(page, "prompt");
  let submitted;
  await page.route("**/v1/atom-lab/runs", async route => {
    if (route.request().method() !== "POST") return route.fallback();
    submitted = route.request().postDataJSON();
    await route.fulfill({status: 202, json: {run_id: "run-mismatched-base", scenario_session_id: "session-library", job_id: "job-library", status: "queued"}});
  });
  await page.route("**/v1/atom-lab/runs/run-mismatched-base", async route => {
    const detail = historyDetail({runId: "run-mismatched-base", input: submitted.input, prompt: submitted.prompt});
    detail.snapshot.prompt.source_ref = product.ref;
    if (change === "base") detail.snapshot.prompt.ref = "prompt.a06.v2";
    if (change === "schema-version") detail.snapshot.schemas.input.version = 2;
    if (change === "schema-content") detail.snapshot.schemas.input.content = {type: "object"};
    if (change === "config") detail.snapshot.action.config_id = "config.a06.v2";
    if (change === "action") detail.snapshot.action.type = "other.action";
    await route.fulfill({json: detail});
  });
  await page.locator("#reasoning-effort").selectOption("high");
  await page.locator("#run-button").click();
  await expect(page.locator("#result-section")).toBeVisible();
  await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
  await page.locator("#save-prompt").click();
  await expect.poll(() => state.writes.length).toBe(1);
  expect(state.writes[0].payload.source_run_id).toBeNull();
});
}

for (const changedOwner of [false, true]) {
  test(`definite prompt proof rejection allows an explicit untested save${changedOwner ? " without touching a new owner" : ""}`, async ({page}) => {
    const {state, detail, product} = await prepareRejectedSourceWrite(page, "prompt");
    detail.snapshot.prompt.content = "Ручной текст владельца";
    await page.locator("#history-button").click();
    await page.locator("#history-list .history-open").click();
    await page.locator("#restore-history").click();
    await showWorkbench(page);
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Текст после проверки");
    state.rejectionField = "source_run_id";
    let release;
    state.writeGate = new Promise(resolve => { release = resolve; });
    await page.locator("#save-prompt").click();
    await expect.poll(() => state.writes.length).toBe(1);
    if (changedOwner) {
      await page.getByRole("button", {name: /A05/}).click();
      await page.locator("#prompt-editor").fill("Сохранённый другой редактор");
    }
    release();
    if (changedOwner) {
      await expect(page.locator("#prompt-editor")).toHaveValue("Сохранённый другой редактор");
      await expect(page.locator("#save-prompt-status")).not.toContainText("Источник сохранения отклонён");
    } else {
      await expect(page.locator("#save-prompt-status")).toContainText("без подтверждения");
      await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
      await page.locator("#save-prompt").click();
      await expect.poll(() => state.writes.length).toBe(2);
      expect(state.writes[1].payload).toMatchObject({source_run_id: null, source_ref: product.ref, prompt: detail.snapshot.prompt.content});
    }
    expect(state.writes[0].payload.source_run_id).toBe(detail.run_id);
  });
}

for (const kind of ["prompt", "preset", "version", "history"]) {
  for (const refreshFails of [false, true]) {
    test(`${kind} source recovery accepts an authoritative new base${refreshFails ? " after atom 503 and Retry" : ""}`, async ({page}) => {
      const {state, save, name, error, detail, originalDetail} = await prepareRejectedSourceWrite(page, kind);
      if (kind === "prompt" || kind === "preset") {
        await showWorkbench(page);
        await page.locator("#prompt-tab").click();
        await page.locator("#prompt-select").selectOption(A06.prompt_ref);
        await page.locator("#prompt-editor").fill("Ручной текст для новой основы");
        if (kind === "preset") await editPreset(page);
      }
      state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2", prompt: "Новая платформа"};
      state.atomStatus = refreshFails ? 503 : 200;
      let releaseAtom;
      state.atomGate = new Promise(resolve => { releaseAtom = resolve; });
      await save.click();
      await expect(error).toContainText("Источник сохранения отклонён");
      await expect.poll(() => state.atomReads).toBe(1);
      await name.fill("Имя во время проверки");
      const retainedPrompt = kind === "history" ? detail.snapshot.prompt.content : "Ручной текст во время проверки";
      const retainedInput = kind === "history" ? detail.snapshot.input : {...A06.example_input, objective: "Правка во время проверки"};
      if (kind !== "history") {
        await showWorkbench(page);
        await page.locator("#prompt-tab").click();
        await page.locator("#prompt-editor").fill(retainedPrompt);
        await page.locator("#input-tab").click();
        await importJson(page, retainedInput);
        await page.locator("#prompt-tab").click();
      }
      releaseAtom();
      if (refreshFails) {
        const loadError = kind === "history" ? error : page.locator("#prompt-load-status");
        if (kind !== "history") { await showWorkbench(page); await page.locator("#prompt-tab").click(); }
        await expect(loadError).toContainText("Атом временно недоступен");
        await expect(save).toBeDisabled();
        if (kind === "preset" || kind === "version") await editPreset(page);
        await name.fill("Имя после отказа");
        state.atomStatus = 200;
        if (kind === "preset" || kind === "version") { await showWorkbench(page); await page.locator("#prompt-tab").click(); }
        await (kind === "history" ? page.getByRole("button", {name: "Повторить загрузку источника", exact: true}) : page.locator("#retry-prompts")).click();
      }
      if (kind !== "history") {
        await showWorkbench(page);
        await page.locator("#prompt-tab").click();
        await expect(page.locator("#prompt-select")).toHaveValue("prompt.a06.v2");
        await expect(page.locator("#prompt-select option[value='prompt.a06']")).toHaveCount(0);
        await expect(page.locator("#prompt-editor")).toHaveValue(retainedPrompt);
        await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
        await expect(page.locator("#reasoning-effort")).toHaveValue(kind === "version" ? "high" : "");
        if (kind !== "prompt") await editPreset(page);
      } else {
        await expect(page.locator("#preset-config-metadata")).toContainText("prompt.a06.v2");
        await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
      }
      await expect(name).toHaveValue(refreshFails ? "Имя после отказа" : "Имя во время проверки");
      await expect(save).toBeEnabled();
      await save.click();
      await expect.poll(() => state.writes.length).toBe(2);
      const recovered = state.writes[1].payload;
      expect(recovered.prompt).toBe(retainedPrompt);
      expect(recovered[kind === "prompt" ? "source_ref" : "prompt_source_ref"]).toBe(kind === "prompt" ? "prompt.a06.v2" : null);
      if (kind !== "prompt") {
        expect(recovered.prompt_ref).toBe("prompt.a06.v2");
        expect(recovered.example_input).toEqual(retainedInput);
        expect(recovered.source_run_id).toBeNull();
        await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия");
      } else await expect(error).toContainText("Сохранён промпт");
      if (kind === "history") {
        await showWorkbench(page);
        await expect(page.locator("#atom-title")).toContainText("A05");
        await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
        await expect(page.locator("#prompt-select")).toHaveValue("product.a05.v1");
        await page.locator("#history-button").click();
        await page.locator("#history-list .history-open").click();
        expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(originalDetail);
      }
      expect(state.atomReads).toBe(refreshFails ? 2 : 1);
    });
  }
}

test("source recovery rejects a list without its authoritative platform base", async ({page}) => {
  const {state, save, name} = await prepareRejectedSourceWrite(page, "prompt");
  state.malformedOptions = true;
  await save.click();
  await expect(page.locator("#prompt-load-status")).toContainText("Список промптов вернул некорректный ответ");
  await expect(save).toBeDisabled();
  await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
  await expect(name).toHaveValue("  Имя владельца  ");
  expect(state.writes).toHaveLength(1);
});

for (const kind of ["preset", "version"]) {
  test(`${kind} base-only rejection preserves a still-valid product source`, async ({page}) => {
    const {state, product, save, name} = await prepareRejectedSourceWrite(page, kind);
    state.rejectionField = "prompt_ref";
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
    state.optionsOverride = [{...product, ref: "prompt.a06.v2", group: "platform"}, product];
    await save.click();
    await expect.poll(() => state.atomReads).toBe(1);
    await expect(save).toBeEnabled();
    await expect(name).toHaveValue("  Имя владельца  ");
    await expect(page.locator("#preset-config-metadata")).toContainText(product.ref);
    await save.click();
    await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия");
    expect(state.writes[1].payload).toMatchObject({
      prompt_ref: "prompt.a06.v2", prompt_source_ref: product.ref,
      prompt: kind === "version" ? "Ручной текст пресета" : "Ручной текст владельца",
      example_input: A06.example_input,
    });
  });
}

for (const failure of ["none", "atom-503", "contract"]) {
  test(`first prompt load recovers base drift with ${failure}`, async ({page}) => {
    let atomReads = 0;
    let atomStatus = failure === "atom-503" ? 503 : 200;
    let savedBody;
    let releaseAtom;
    const atomGate = new Promise(resolve => { releaseAtom = resolve; });
    const fresh = structuredClone({...A06, prompt_ref: "prompt.a06.v2"});
    if (failure === "contract") fresh.schema_refs.input.version += 1;
    const platform = {ref: fresh.prompt_ref, name: "Свежая платформа", prompt: fresh.prompt, group: "platform", source_ref: null, source_run_id: null};
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06**", async route => {
      if (route.request().method() === "POST") {
        savedBody = route.request().postDataJSON();
        await route.fulfill({json: {...platform, ...savedBody, group: "lab", ref: "lab.first-load"}});
      } else if (new URL(route.request().url()).pathname.endsWith("/prompts")) {
        await route.fulfill({json: [platform]});
      } else {
        atomReads += 1;
        await atomGate;
        await route.fulfill({status: atomStatus, json: atomStatus === 200 ? fresh : {error: {code: "atom_lab_catalog_unavailable", message: "Атом временно недоступен."}}});
      }
    });
    await unlockAtom(page, "A06");
    await importJson(page, A06.example_input);
    await page.locator("#prompt-tab").click();
    await expect.poll(() => atomReads).toBe(1);
    await page.locator("#prompt-editor").fill("Черновик до первого списка");
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Имя до первого списка");
    releaseAtom();
    if (failure !== "none") {
      await expect(page.locator("#prompt-load-status")).toContainText(failure === "contract" ? "Контракт атома изменился" : "Атом временно недоступен");
      await expect(page.locator("#save-prompt")).toBeDisabled();
      await expect(page.locator("#run-button")).toBeDisabled();
      if (failure === "atom-503") {
        atomStatus = 200;
        await page.locator("#retry-prompts").click();
      }
    }
    await expect(page.locator("#prompt-editor")).toHaveValue("Черновик до первого списка");
    await expect(page.locator("#save-prompt-name")).toHaveValue("Имя до первого списка");
    if (failure !== "contract") {
      await expect(page.locator("#prompt-select")).toHaveValue(fresh.prompt_ref);
      await page.locator("#save-prompt").click();
      await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
      expect(savedBody).toMatchObject({prompt: "Черновик до первого списка", source_ref: fresh.prompt_ref, source_run_id: null});
    }
    await page.locator("#input-tab").click();
    await page.locator("#json-mode").click();
    expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual(A06.example_input);
  });
}

test("a direct history source read blocks a newly incompatible base without rewriting the snapshot", async ({page}) => {
  const {state, detail, originalDetail, product} = await prepareRejectedSourceWrite(page, "prompt");
  state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
  state.optionsOverride = [{...product, ref: "prompt.a06.v2", group: "platform"}, product];
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#save-history-preset").click();
  await expect.poll(() => state.atomReads).toBe(1);
  await expect(page.locator("#history-error")).toContainText("Основа промпта изменилась");
  await expect(page.locator("#presets-panel")).toBeHidden();
  expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(originalDetail);
  await expect(page.locator("#history-prompt")).toHaveText(detail.snapshot.prompt.content);
  await showWorkbench(page);
  await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
  expect(state.writes).toHaveLength(0);
});

for (const change of ["input-ref", "input-content", "output", "config", "action", "malformed-atom", "wrong-atom", "claimed-platform"]) {
  test(`base source recovery preserves the draft after ${change}`, async ({page}) => {
    const {state, save, name} = await prepareRejectedSourceWrite(page, "prompt");
    const atom = structuredClone({...A06, prompt_ref: "prompt.a06.v2"});
    if (change === "input-ref") atom.schema_refs.input.version += 1;
    if (change === "input-content") atom.input_schema.properties.context = {type: "string"};
    if (change === "output") atom.schema_refs.output.version += 1;
    if (change === "config") atom.base_action_config_id = "config.a06.v2";
    if (change === "action") atom.action_type = "kernel.other_action";
    if (change === "malformed-atom") atom.schema_refs = null;
    if (change === "wrong-atom") atom.atom_id = "A05";
    state.authoritativeAtom = atom;
    if (change === "claimed-platform") state.optionsOverride = [{
      ref: "pretend.platform", name: "Подмена", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null,
    }];
    await save.click();
    await expect(page.locator("#prompt-load-status")).toContainText(change.includes("atom")
      ? "Атом вернул некорректный ответ" : change === "claimed-platform"
        ? "Список промптов вернул некорректный ответ" : "Контракт атома изменился");
    await expect(save).toBeDisabled();
    await page.locator("#prompt-select").evaluate((picker, ref) => {
      picker.value = ref;
      picker.dispatchEvent(new Event("change", {bubbles: true}));
    }, A06.prompt_ref);
    await expect(page.locator("#prompt-select")).toHaveValue("product.a06.v1");
    await expect(page.locator("#prompt-select")).toBeDisabled();
    await expect(page.locator("#retry-prompts")).toBeVisible();
    await expect(page.locator("#run-button")).toBeDisabled();
    await page.locator("#run-button").dispatchEvent("click");
    await save.dispatchEvent("click");
    await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
    await expect(name).toHaveValue("  Имя владельца  ");
    await page.locator("#input-tab").click();
    await page.locator("#json-mode").click();
    expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual(A06.example_input);
    await expect(page.locator("#input-schema-version")).toHaveText("Версия 1");
    expect(state.writes).toHaveLength(1);
  });
}

for (const change of ["schema", "action", "config"]) {
  test(`contract lock survives cached selection and stale lists after ${change}, then compatible Retry recovers`, async ({page}) => {
    const {state, product, save, name} = await prepareRejectedSourceWrite(page, "prompt");
    const fresh = structuredClone({...A06, prompt_ref: "prompt.a06.v2"});
    const incompatible = structuredClone(fresh);
    if (change === "schema") incompatible.schema_refs.input.version += 1;
    if (change === "action") incompatible.action_type = "kernel.changed_action";
    if (change === "config") incompatible.base_action_config_id = "config.a06.v2";
    state.authoritativeAtom = incompatible;
    await save.click();
    await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
    await expect(page.locator("#prompt-select")).toBeDisabled();
    const cached = [{...product, ref: A06.prompt_ref, group: "platform", prompt: A06.prompt}, product];
    state.optionsOverride = cached;
    await page.locator("#retry-prompts").click();
    await expect.poll(() => state.atomReads).toBe(2);
    await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
    state.atomStatus = 503;
    await page.locator("#retry-prompts").click();
    await expect.poll(() => state.atomReads).toBe(3);
    await expect(page.locator("#prompt-load-status")).toContainText("Атом временно недоступен");
    state.optionsOverride = [{}];
    await page.locator("#retry-prompts").click();
    await expect(page.locator("#prompt-load-status")).toContainText("Список промптов вернул некорректный ответ");
    await expect(page.locator("#run-button")).toBeDisabled();
    await expect(save).toBeDisabled();
    await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
    await expect(name).toHaveValue("  Имя владельца  ");
    expect(state.writes).toHaveLength(1);

    state.atomStatus = 200;
    state.authoritativeAtom = fresh;
    state.optionsOverride = [{...product, ref: fresh.prompt_ref, group: "platform", prompt: fresh.prompt}, product];
    let release;
    state.atomGate = new Promise(resolve => { release = resolve; });
    await page.locator("#retry-prompts").click();
    await expect.poll(() => state.atomReads).toBe(4);
    await page.locator("#prompt-select").evaluate((picker, ref) => {
      picker.value = ref;
      picker.dispatchEvent(new Event("change", {bubbles: true}));
    }, A06.prompt_ref);
    await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
    await expect(save).toBeDisabled();
    release();
    await expect(page.locator("#prompt-select")).toBeEnabled();
    await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#prompt-load-status")).toBeEmpty();
    await expect(page.locator("#retry-prompts")).toBeHidden();
    await expect(save).toBeEnabled();
    await save.click();
    await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
    expect(state.writes[1].payload).toMatchObject({prompt: "Ручной текст владельца", source_ref: product.ref, source_run_id: null});
  });
}

for (const staleCompatible of [false, true]) {
  test(`contract lock ignores a stale ${staleCompatible ? "compatible" : "incompatible"} authoritative Retry response`, async ({page}) => {
    const {state, save, product} = await prepareRejectedSourceWrite(page, "prompt");
    const fresh = {...A06, prompt_ref: "prompt.a06.v2"};
    const incompatible = {...fresh, base_action_config_id: "config.a06.v2"};
    state.authoritativeAtom = fresh;
    state.optionsOverride = [{...product, ref: fresh.prompt_ref, group: "platform"}, product];
    let releaseStale;
    const staleGate = new Promise(resolve => { releaseStale = resolve; });
    const replies = [incompatible, staleCompatible ? fresh : incompatible, staleCompatible ? incompatible : fresh, fresh];
    let reads = 0;
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06", async route => {
      const index = reads++;
      if (index === 1) await staleGate;
      await route.fulfill({json: replies[index]});
    });
    await save.click();
    await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
    await page.locator("#retry-prompts").click();
    await expect.poll(() => reads).toBe(2);
    await page.locator("#retry-prompts").dispatchEvent("click");
    await expect.poll(() => reads).toBe(3);
    if (staleCompatible) await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
    else await expect(save).toBeEnabled();
    const staleResponse = page.waitForResponse("**/v1/atom-lab/atoms/A06");
    releaseStale();
    await (await staleResponse).finished();
    await page.locator("#prompt-editor").fill("Правка после старого ответа");
    if (staleCompatible) {
      await expect(page.locator("#prompt-select")).toBeDisabled();
      await expect(page.locator("#run-button")).toBeDisabled();
      await expect(page.locator("#retry-prompts")).toBeVisible();
      await page.locator("#retry-prompts").click();
    }
    await expect(page.locator("#prompt-select")).toBeEnabled();
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#prompt-load-status")).toBeEmpty();
    await save.click();
    await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
    expect(state.writes[1].payload).toMatchObject({prompt: "Правка после старого ответа", source_ref: product.ref, source_run_id: null});
  });
}

test("ordinary retired source selection still recovers after a source-list read fails", async ({page}) => {
  const {state, save} = await prepareRejectedSourceWrite(page, "prompt");
  state.refreshStatus = 503;
  await save.click();
  await expect(page.locator("#prompt-load-status")).toContainText("Источники временно недоступны");
  await expect(page.locator("#prompt-select")).toBeEnabled();
  await expect(page.locator("#run-button")).toBeDisabled();
  await page.locator("#prompt-select").selectOption(A06.prompt_ref);
  await expect(page.locator("#run-button")).toBeEnabled();
  await expect(page.locator("#prompt-load-status")).toBeEmpty();
  await expect(page.locator("#retry-prompts")).toBeHidden();
  await page.locator("#prompt-editor").fill("Явно выбранная платформа");
  await save.click();
  await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
  expect(state.writes[1].payload).toMatchObject({prompt: "Явно выбранная платформа", source_ref: A06.prompt_ref});
  expect(state.atomReads).toBe(0);
});

for (const phase of ["write", "atom"]) {
  for (const change of ["source", "editor", "catalog"]) {
    test(`base source recovery fences ${change} during ${phase}`, async ({page}) => {
      const {state, save} = await prepareRejectedSourceWrite(page, "prompt");
      state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
      let release;
      const gate = new Promise(resolve => { release = resolve; });
      if (phase === "write") state.writeGate = gate;
      else state.atomGate = gate;
      await save.click();
      await expect.poll(() => phase === "write" ? state.writes.length : state.atomReads).toBe(1);
      if (change === "source") await page.locator("#prompt-select").selectOption(A06.prompt_ref);
      if (change === "editor") {
        await page.getByRole("button", {name: /A05/}).click();
        await page.locator("#prompt-select").selectOption("product.a05.v1");
      }
      await page.locator("#prompt-editor").fill("Поздний ручной текст");
      if (change === "catalog") {
        page.removeAllListeners("dialog");
        page.on("dialog", dialog => dialog.dismiss());
        const reloaded = page.waitForResponse("**/v1/atom-lab/models");
        await page.locator("#access-form").dispatchEvent("submit");
        await reloaded;
      }
      const completed = page.waitForResponse(response => phase === "write"
        ? response.request().method() === "POST" : response.url().endsWith("/atoms/A06"));
      release();
      await (await completed).finished();
      await expect(page.locator("#prompt-editor")).toHaveValue("Поздний ручной текст");
      await expect(page.locator("#prompt-select option[value='prompt.a06.v2']")).toHaveCount(0);
      await expect(page.locator("#prompt-select")).toHaveValue(change === "source" ? A06.prompt_ref : change === "editor" ? "product.a05.v1" : "product.a06.v1");
      expect(state.atomReads).toBe(phase === "write" ? 0 : 1);
      expect(state.writes).toHaveLength(1);
    });
  }
}

test("base recovery keeps both a history snapshot and dirty A06 editor usable", async ({page}) => {
  const {state, save, detail} = await prepareRejectedSourceWrite(page, "history", {historyAtom: "A06"});
  state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
  await save.click();
  await expect(save).toBeEnabled();
  await expect(page.locator("#preset-config-metadata")).toContainText("prompt.a06.v2");
  await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
  await showWorkbench(page);
  await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
  await expect(page.locator("#prompt-select")).toHaveValue("prompt.a06.v2");
  await page.locator("#save-prompt-panel summary").click();
  await page.locator("#save-prompt-name").fill("Другой живой владелец");
  await page.locator("#save-prompt").click();
  await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
  expect(state.writes[1].pathname).toBe("/v1/atom-lab/atoms/A06/prompts");
  expect(state.writes[1].payload).toMatchObject({prompt: "Ручной текст владельца", source_ref: "prompt.a06.v2", source_run_id: null});
  await editPreset(page);
  await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
  await save.click();
  await expect.poll(() => state.writes.length).toBe(3);
  expect(state.writes[2].payload).toMatchObject({prompt_ref: "prompt.a06.v2", prompt: detail.snapshot.prompt.content, source_run_id: null});
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия");
});

for (const discoveryOwner of ["history", "editor"]) {
  for (const recovery of ["unchanged", "new-base"]) {
    test(`shared contract failure from ${discoveryOwner} locks both owners until ${recovery} authoritative Retry`, async ({page}) => {
      const {state, save, product, detail, originalDetail, name} = await prepareRejectedSourceWrite(page, "history", {historyAtom: "A06"});
      let runs = 0;
      await page.route("**/v1/atom-lab/runs", async route => {
        if (route.request().method() !== "POST") return route.fallback();
        runs += 1;
        await route.fulfill({status: 422, json: {error: {code: "input_invalid", message: "Unexpected run"}}});
      });
      await expect(page.locator("#preset-source")).toContainText(`сохранённый запуск ${detail.run_id}`);
      const fresh = {...A06, prompt_ref: "prompt.a06.v2"};
      state.authoritativeAtom = {...fresh, schema_refs: {...A06.schema_refs, input: {...A06.schema_refs.input, version: 2}}};
      state.optionsOverride = [{...product, ref: fresh.prompt_ref, group: "platform"}, product];
      state.rejectionField = "prompt_ref";
      if (discoveryOwner === "history") await save.click();
      else {
        state.rejectionCode = "prompt_invalid";
        state.rejectionField = "source_ref";
        await showWorkbench(page);
        await page.locator("#save-prompt-panel summary").click();
        await page.locator("#save-prompt-name").fill("Имя промпта второго владельца");
        await page.locator("#save-prompt").click();
      }
      await expect.poll(() => state.atomReads).toBe(1);
      await showWorkbench(page);
      await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
      await expect(page.locator("#retry-prompts")).toBeVisible();
      await expect(page.locator("#prompt-select")).toBeDisabled();
      await expect(page.locator("#run-button")).toBeDisabled();
      if (await page.locator("#save-prompt").isHidden()) await page.locator("#save-prompt-panel summary").click();
      await expect(page.locator("#save-prompt")).toBeDisabled();
      await page.locator("#run-button").dispatchEvent("click");
      await page.locator("#save-prompt").dispatchEvent("click");
      await page.locator("#prompt-select").evaluate((picker, ref) => {
        picker.value = ref;
        picker.dispatchEvent(new Event("change", {bubbles: true}));
      }, A06.prompt_ref);
      await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
      await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
      await page.locator("#presets-button").click();
      await expect(page.locator("#preset-error")).toContainText("Контракт атома изменился");
      const historyRetry = page.getByRole("button", {name: "Повторить загрузку источника", exact: true});
      await expect(historyRetry).toBeVisible();
      await expect(save).toBeDisabled();
      await save.dispatchEvent("click");
      await expect(name).toHaveValue("  Имя владельца  ");
      await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
      expect(JSON.parse(await page.locator("#preset-input-json").textContent())).toEqual(detail.snapshot.input);
      expect(state.writes).toHaveLength(1);
      expect(runs).toBe(0);

      // Even an old cached options list must recheck the locked authoritative contract.
      state.optionsOverride = [{...product, ref: A06.prompt_ref, group: "platform", prompt: A06.prompt}, product];
      await historyRetry.click();
      await expect.poll(() => state.atomReads).toBe(2);
      await expect(page.locator("#preset-error")).toContainText("Контракт атома изменился");
      await expect(save).toBeDisabled();
      await showWorkbench(page);
      await expect(page.locator("#run-button")).toBeDisabled();
      state.authoritativeAtom = recovery === "unchanged" ? structuredClone(A06) : fresh;
      state.optionsOverride = [{...product, ref: state.authoritativeAtom.prompt_ref, group: "platform", prompt: state.authoritativeAtom.prompt}, product];
      await page.locator("#retry-prompts").click();
      await expect.poll(() => state.atomReads).toBe(3);
      await expect(page.locator("#run-button")).toBeEnabled();
      await expect(page.locator("#prompt-select")).toBeEnabled();
      await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
      await expect(page.locator("#prompt-load-status")).toBeEmpty();
      await expect(page.locator("#retry-prompts")).toBeHidden();
      await page.locator("#presets-button").click();
      await expect(page.locator("#preset-error")).toBeEmpty();
      await expect(save).toBeEnabled();
      await expect(name).toHaveValue("  Имя владельца  ");
      if (recovery === "unchanged") await expect(page.locator("#preset-source")).toContainText(`сохранённый запуск ${detail.run_id}`);
      else {
        await expect(page.locator("#preset-source")).toHaveText("Источник: настройки из истории. Привязка к сохранённому запуску снята после смены основы промпта. Настройки и вход не связаны с текущим черновиком.");
        await expect(page.locator("#preset-source")).not.toContainText("null");
        await expect(page.locator("#preset-source")).not.toContainText(detail.run_id);
      }
      await save.click();
      await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия");
      expect(state.writes[1].payload).toMatchObject({
        prompt_ref: recovery === "unchanged" ? A06.prompt_ref : fresh.prompt_ref,
        prompt_source_ref: product.ref, source_run_id: recovery === "unchanged" ? detail.run_id : null,
        prompt: detail.snapshot.prompt.content, example_input: detail.snapshot.input,
      });
      expect(detail).toEqual(originalDetail);
    });
  }
}

for (const staleCompatible of [false, true]) {
  test(`shared contract checks ignore an older ${staleCompatible ? "compatible" : "incompatible"} response from the other owner`, async ({page}) => {
    const {state, save, product} = await prepareRejectedSourceWrite(page, "history", {historyAtom: "A06"});
    const incompatible = {...A06, prompt_ref: "prompt.a06.v2", base_action_config_id: "config.a06.v2"};
    state.optionsOverride = [{...product, ref: "prompt.a06.v2", group: "platform"}, product];
    state.rejectionField = "prompt_ref";
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    const replies = [incompatible, staleCompatible ? A06 : incompatible, staleCompatible ? incompatible : A06, A06];
    let reads = 0;
    await page.route("**/v1/atom-lab/atoms/A06", async route => {
      const index = reads++;
      if (index === 1) await gate;
      await route.fulfill({json: replies[index]});
    });
    await save.click();
    await expect(page.locator("#preset-error")).toContainText("Контракт атома изменился");
    state.optionsOverride = [{...product, ref: A06.prompt_ref, group: "platform", prompt: A06.prompt}, product];
    await showWorkbench(page);
    await page.locator("#retry-prompts").click();
    await expect.poll(() => reads).toBe(2);
    await page.locator("#presets-button").click();
    await page.getByRole("button", {name: "Повторить загрузку источника", exact: true}).click();
    await expect.poll(() => reads).toBe(3);
    await expect(save)[staleCompatible ? "toBeDisabled" : "toBeEnabled"]();
    const completed = page.waitForResponse("**/v1/atom-lab/atoms/A06");
    release();
    await (await completed).finished();
    await showWorkbench(page);
    await expect(page.locator("#run-button"))[staleCompatible ? "toBeDisabled" : "toBeEnabled"]();
    await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
    if (staleCompatible) {
      await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
      await page.locator("#retry-prompts").click();
      await expect.poll(() => reads).toBe(4);
    }
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#prompt-load-status")).toBeEmpty();
    await page.locator("#presets-button").click();
    await expect(page.locator("#preset-error")).toBeEmpty();
    await expect(save).toBeEnabled();
    expect(state.writes).toHaveLength(1);
  });
}

test("shared contract ignores an invalidated peer options read before it can supersede a current authority check", async ({page}) => {
  const {state, save, product} = await prepareRejectedSourceWrite(page, "history", {historyAtom: "A06"});
  const fresh = {...A06, prompt_ref: "prompt.a06.v2"};
  state.authoritativeAtom = {...fresh, base_action_config_id: "config.a06.v2"};
  const options = [{...product, ref: fresh.prompt_ref, group: "platform"}, product];
  state.optionsOverride = options;
  state.rejectionField = "prompt_ref";
  let releaseOptions;
  let waiting = false;
  const optionsGate = new Promise(resolve => { releaseOptions = resolve; });
  await page.route("**/v1/atom-lab/atoms/A06/prompts", async route => {
    if (waiting) return route.fallback();
    waiting = true;
    await optionsGate;
    await route.fulfill({json: options});
  });
  await showWorkbench(page);
  await page.locator("#retry-prompts").dispatchEvent("click");
  await expect.poll(() => waiting).toBe(true);
  await page.locator("#presets-button").click();
  await save.click();
  await expect(page.locator("#preset-error")).toContainText("Контракт атома изменился");
  state.authoritativeAtom = fresh;
  let releaseAtom;
  state.atomGate = new Promise(resolve => { releaseAtom = resolve; });
  await page.getByRole("button", {name: "Повторить загрузку источника", exact: true}).click();
  await expect.poll(() => state.atomReads).toBe(2);
  const oldOptions = page.waitForResponse("**/v1/atom-lab/atoms/A06/prompts");
  releaseOptions();
  await (await oldOptions).finished();
  await expect(save).toBeDisabled();
  expect(state.atomReads).toBe(2);
  releaseAtom();
  await expect(save).toBeEnabled();
  await expect(page.locator("#preset-error")).toBeEmpty();
  await showWorkbench(page);
  await expect(page.locator("#run-button")).toBeEnabled();
  await expect(page.locator("#prompt-load-status")).toBeEmpty();
  expect(state.writes).toHaveLength(1);
});

test("shared contract direct history Retry clears both owners only after compatible authority", async ({page}) => {
  const {state, save, product, detail, originalDetail} = await prepareRejectedSourceWrite(page, "history", {historyAtom: "A06"});
  const fresh = {...A06, prompt_ref: "prompt.a06.v2"};
  state.authoritativeAtom = {...fresh, base_action_config_id: "config.a06.v2"};
  state.optionsOverride = [{...product, ref: fresh.prompt_ref, group: "platform"}, product];
  await save.click();
  await expect(page.locator("#preset-error")).toContainText("Контракт атома изменился");
  state.authoritativeAtom = structuredClone(A06);
  state.optionsOverride = [{...product, ref: A06.prompt_ref, group: "platform", prompt: A06.prompt}, product];
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#save-history-preset").click();
  await expect.poll(() => state.atomReads).toBe(2);
  await expect(save).toBeEnabled();
  await expect(page.locator("#preset-source")).toContainText(`сохранённый запуск ${detail.run_id}`);
  await expect(page.locator("#preset-error")).toBeEmpty();
  await showWorkbench(page);
  await expect(page.locator("#run-button")).toBeEnabled();
  await expect(page.locator("#prompt-select")).toBeEnabled();
  await expect(page.locator("#prompt-load-status")).toBeEmpty();
  expect(detail).toEqual(originalDetail);
  expect(state.writes).toHaveLength(1);
});

test("shared contract failure leaves another atom usable and survives recreating its old editor", async ({page}) => {
  const {state, save, product} = await prepareRejectedSourceWrite(page, "history");
  const fresh = {...A06, prompt_ref: "prompt.a06.v2"};
  state.authoritativeAtom = {...fresh, base_action_config_id: "config.a06.v2"};
  state.optionsOverride = [{...product, ref: fresh.prompt_ref, group: "platform"}, product];
  state.rejectionField = "prompt_ref";
  await save.click();
  await expect(page.locator("#preset-error")).toContainText("Контракт атома изменился");
  await showWorkbench(page);
  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#prompt-select")).toBeEnabled();
  await expect(page.locator("#run-button")).toBeEnabled();
  await expect(page.locator("#prompt-load-status")).toBeEmpty();
  await page.locator("#input-tab").click();
  await page.getByRole("button", {name: /A06/}).click();
  await page.locator("#fill-example").click();
  await expect(page.locator("#run-button")).toBeDisabled();
  await page.locator("#run-button").dispatchEvent("click");
  expect(state.writes).toHaveLength(1);
  await page.locator("#prompt-tab").click();
  await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
  await expect(page.locator("#retry-prompts")).toBeVisible();
  await expect(page.locator("#prompt-select")).toBeDisabled();
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#prompt-select")).toBeEnabled();
});

for (const ownerAtom of ["A05", "A06"]) {
  for (const stale of ["none", "editor", "catalog"]) {
    test(`shared contract direct history failure protects ${ownerAtom} with ${stale} owner replacement`, async ({page}) => {
      const {state, product, detail, originalDetail} = await prepareRejectedSourceWrite(page, "prompt");
      if (ownerAtom === "A05") {
        await page.getByRole("button", {name: /A05/}).click();
        await page.locator("#input-tab").click();
        await page.locator("#fill-example").click();
        await page.locator("#prompt-tab").click();
        await page.locator("#prompt-select").selectOption("product.a05.v1");
        await page.locator("#prompt-editor").fill("Другой атом");
      }
      state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2", base_action_config_id: "config.a06.v2"};
      state.optionsOverride = [{...product, ref: "prompt.a06.v2", group: "platform"}, product];
      let release;
      state.atomGate = new Promise(resolve => { release = resolve; });
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      await page.locator("#save-history-preset").click();
      await expect.poll(() => state.atomReads).toBe(1);
      if (stale !== "none") {
        await showWorkbench(page);
        await page.locator("#input-tab").click();
        if (stale === "editor") await page.getByRole("button", {name: new RegExp(ownerAtom)}).click();
        else {
          const reloaded = page.waitForResponse("**/v1/atom-lab/models");
          await page.locator("#access-form").dispatchEvent("submit");
          await reloaded;
          await page.getByRole("button", {name: new RegExp(ownerAtom)}).click();
        }
        await page.locator("#fill-example").click();
      }
      const completed = page.waitForResponse("**/v1/atom-lab/atoms/A06");
      release();
      await (await completed).finished();
      if (stale === "none") {
        await expect(page.locator("#history-error")).toContainText("Контракт атома изменился");
        expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(originalDetail);
        await expect(page.locator("#history-prompt")).toHaveText(detail.snapshot.prompt.content);
      }
      await showWorkbench(page);
      await expect(page.locator("#run-button"))[ownerAtom === "A06" && stale === "none" ? "toBeDisabled" : "toBeEnabled"]();
      if (ownerAtom === "A06" && stale === "none") {
        await expect(page.locator("#prompt-load-status")).toContainText("Контракт атома изменился");
        await expect(page.locator("#retry-prompts")).toBeVisible();
        await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
      }
      expect(state.writes).toHaveLength(0);
    });
  }
}

test("a new authoritative base invalidates the old exact successful trial", async ({page}) => {
  const {state, detail} = await prepareRejectedSourceWrite(page, "prompt");
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#restore-history").click();
  await page.locator("#prompt-tab").click();
  await expect(page.locator("#prompt-test-status")).toContainText("Пробный запуск завершён");
  await page.locator("#save-prompt-panel summary").click();
  await page.locator("#save-prompt-name").fill("Текст с прежним испытанием");
  state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
  await page.locator("#save-prompt").click();
  await expect(page.locator("#prompt-select")).toHaveValue("prompt.a06.v2");
  await expect(page.locator("#prompt-editor")).toHaveValue(detail.snapshot.prompt.content);
  await expect(page.locator("#prompt-test-status")).not.toContainText("Пробный запуск завершён");
  await page.locator("#save-prompt").click();
  await expect(page.locator("#save-prompt-status")).toContainText("Сохранён промпт");
  expect(state.writes[0].payload.source_run_id).toBe(detail.run_id);
  expect(state.writes[1].payload.source_run_id).toBeNull();
});

for (const historyAtom of ["A05", "A06"]) {
  test(`changed history preset base clears its source run without borrowing the ${historyAtom} editor run`, async ({page}) => {
    const {state, save, detail, originalDetail} = await prepareRejectedSourceWrite(page, "history", {historyAtom});
    await expect(page.locator("#preset-source")).toContainText(`сохранённый запуск ${detail.run_id}`);
    let runBody;
    await page.route("**/v1/atom-lab/runs", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      runBody = route.request().postDataJSON();
      await route.fulfill({status: 202, json: {
        run_id: "run-foreign-editor", scenario_session_id: "session-library", job_id: "job-library", status: "queued",
      }});
    });
    const foreign = historyDetail({runId: "run-foreign-editor", prompt: "Ручной текст владельца", reasoningEffort: null});
    Object.assign(foreign.snapshot, snapshotAtomContract(historyAtom === "A05" ? A05 : A06));
    await page.route("**/v1/atom-lab/runs/run-foreign-editor", route => route.fulfill({json: foreign}));
    await showWorkbench(page);
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
    expect(runBody.atom_id).toBe(historyAtom);
    await page.locator("#presets-button").click();
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
    await save.click();
    await expect(page.locator("#preset-config-metadata")).toContainText("prompt.a06.v2");
    await expect(page.locator("#preset-source")).toHaveText("Источник: настройки из истории. Привязка к сохранённому запуску снята после смены основы промпта. Настройки и вход не связаны с текущим черновиком.");
    await expect(save).toBeEnabled();
    await save.click();
    await expect.poll(() => state.writes.length).toBe(2);
    expect(state.writes[1].payload).toMatchObject({prompt_ref: "prompt.a06.v2", source_run_id: null});
    await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия");
    expect(detail).toEqual(originalDetail);
  });
}

for (const presetAtom of ["A05", "A06"]) {
  test(`base refresh rechecks the immutable ${presetAtom} preset card against its own atom`, async ({page}) => {
    const {state, originalVersion, product} = await prepareRejectedSourceWrite(page, "version");
    await page.locator("#cancel-preset").click();
    const viewed = presetAtom === "A06" ? originalVersion : {...originalVersion,
      atom_id: "A05", base_action_config_id: A05.base_action_config_id, schema_refs: A05.schema_refs,
      prompt_ref: A05.prompt_ref, prompt_source_ref: null, example_input: A05.example_input,
    };
    if (presetAtom === "A05") {
      await page.route(`**/v1/atom-lab/presets/${originalVersion.preset_id}/versions/1`, route => route.fulfill({json: viewed}));
      await page.locator("#preset-list button").click();
    }
    await showWorkbench(page);
    await page.locator("#prompt-tab").click();
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
    state.optionsOverride = [
      {...product, group: "platform", ref: state.authoritativeAtom.prompt_ref}, product,
    ];
    state.rejectionCode = "prompt_invalid";
    state.rejectionField = "source_ref";
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Обновить основу");
    await page.locator("#save-prompt").click();
    await expect.poll(() => state.atomReads).toBe(1);
    await showWorkbench(page);
    await page.locator("#presets-button").click();
    if (presetAtom === "A05") {
      await expect(page.locator("#apply-preset")).toBeEnabled();
      await expect(page.locator("#adapt-preset")).toBeHidden();
      expect(JSON.parse(await page.locator("#preset-readonly").textContent())).toEqual(viewed);
      return;
    }
    await expect(page.locator("#apply-preset")).toBeDisabled();
    await expect(page.locator("#edit-preset")).toBeDisabled();
    await expect(page.locator("#adapt-preset")).toBeVisible();
    expect(JSON.parse(await page.locator("#preset-readonly").textContent())).toEqual(originalVersion);
    await page.locator("#apply-preset").dispatchEvent("click");
    await page.locator("#edit-preset").dispatchEvent("click");
    await expect(page.locator("#presets-panel")).toBeVisible();
    await expect(page.locator("#preset-editor-form")).toBeHidden();
    await page.locator("#adapt-preset").click();
    await expect(page.locator("#preset-editor-form")).toBeVisible();
    await expect(page.locator("#preset-config-metadata")).toContainText(product.ref);
    await expect(page.locator("#preset-prompt")).toHaveText(originalVersion.prompt);
    await page.locator("#save-preset").click();
    await expect.poll(() => state.writes.length).toBe(2);
    expect(state.writes[1].payload).toMatchObject({prompt_ref: "prompt.a06.v2", source_run_id: null, prompt_source_ref: product.ref});
    await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия");
  });
}

for (const first of ["atom", "preset"]) {
  test(`preset read and base refresh keep the immutable version guarded when ${first} returns first`, async ({page}) => {
    const {state, originalVersion, product} = await prepareRejectedSourceWrite(page, "version");
    await page.locator("#cancel-preset").click();
    await showWorkbench(page);
    await page.locator("#prompt-tab").click();
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
    state.optionsOverride = [{...product, ref: state.authoritativeAtom.prompt_ref, group: "platform"}, product];
    state.rejectionCode = "prompt_invalid";
    state.rejectionField = "source_ref";
    let releaseAtom;
    state.atomGate = new Promise(resolve => { releaseAtom = resolve; });
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Проверить основу");
    await page.locator("#save-prompt").click();
    await expect.poll(() => state.atomReads).toBe(1);
    await page.locator("#presets-button").click();
    let releasePreset;
    const presetGate = new Promise(resolve => { releasePreset = resolve; });
    let readingPreset = false;
    const versionUrl = `**/v1/atom-lab/presets/${originalVersion.preset_id}/versions/1`;
    await page.route(versionUrl, async route => {
      readingPreset = true;
      await presetGate;
      await route.fulfill({json: originalVersion});
    });
    await page.locator("#preset-list button").click();
    await expect.poll(() => readingPreset).toBe(true);
    await page.locator("#apply-preset").dispatchEvent("click");
    await page.locator("#edit-preset").dispatchEvent("click");
    const atomRead = page.waitForResponse("**/v1/atom-lab/atoms/A06");
    const presetRead = page.waitForResponse(versionUrl);
    if (first === "atom") {
      releaseAtom();
      await (await atomRead).finished();
      releasePreset();
    } else {
      releasePreset();
      await (await presetRead).finished();
      releaseAtom();
    }
    await atomRead;
    await presetRead;
    await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
    await expect(page.locator("#apply-preset")).toBeDisabled();
    await expect(page.locator("#adapt-preset")).toBeVisible();
    expect(JSON.parse(await page.locator("#preset-readonly").textContent())).toEqual(originalVersion);
    expect(state.writes).toHaveLength(1);
  });
}

for (const proof of ["restored", "completed"]) {
  test(`unchanged authoritative Retry keeps preset binding and the ${proof} exact trial`, async ({page}) => {
    const {state, detail, product, originalVersion} = await prepareRejectedSourceWrite(page, "prompt");
    detail.snapshot.preset = {id: originalVersion.preset_id, version: originalVersion.version};
    await page.locator("#history-button").click();
    await page.locator("#history-list .history-open").click();
    await page.locator("#restore-history").click();
    let runBody;
    await page.route("**/v1/atom-lab/runs", async route => {
      if (route.request().method() !== "POST") return route.fallback();
      runBody = route.request().postDataJSON();
      await route.fulfill({status: 202, json: {
        run_id: "run-unchanged-base", scenario_session_id: "session-library", job_id: "job-library", status: "queued",
      }});
    });
    const completed = structuredClone({...detail, run_id: "run-unchanged-base"});
    await page.route("**/v1/atom-lab/runs/run-unchanged-base", route => route.fulfill({json: completed}));
    if (proof === "completed") {
      await page.locator("#run-button").click();
      await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
      // Replace the restored owner so this assertion can only use completed proof.
      detail.run_id = "run-other-proof";
      detail.snapshot.prompt.content = "Другой восстановленный текст";
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      await page.locator("#restore-history").click();
      await page.locator("#prompt-tab").click();
      await page.locator("#prompt-editor").fill(completed.snapshot.prompt.content);
    }
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-test-status")).toContainText("Пробный запуск завершён");
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.temporary"};
    state.atomStatus = 503;
    if (!(await page.locator("#save-prompt").isVisible())) await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Неизменная основа");
    await page.locator("#save-prompt").click();
    await expect(page.locator("#prompt-load-status")).toContainText("Атом временно недоступен");
    state.authoritativeAtom = structuredClone(A06);
    state.optionsOverride = [{...product, ref: A06.prompt_ref, group: "platform", prompt: A06.prompt}, product];
    state.atomStatus = 200;
    await page.locator("#retry-prompts").click();
    await expect.poll(() => state.atomReads).toBe(2);
    await expect(page.locator("#prompt-load-status")).toHaveText("");
    await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
    await expect(page.locator("#prompt-test-status")).toContainText("Пробный запуск завершён");
    await page.locator("#save-prompt").click();
    await expect.poll(() => state.writes.length).toBe(2);
    expect(state.writes[1].payload.source_run_id).toBe(proof === "completed" ? completed.run_id : detail.run_id);
    await page.locator("#run-button").click();
    await expect.poll(() => runBody?.preset_ref).toEqual({preset_id: originalVersion.preset_id, version: 1});
  });
}

for (const change of ["new-preset", "editor", "catalog", "hidden-panel"]) {
  test(`history base recovery fences a later ${change} during its atom read`, async ({page}) => {
    const {state, save, detail} = await prepareRejectedSourceWrite(page, "history");
    state.authoritativeAtom = {...A06, prompt_ref: "prompt.a06.v2"};
    let releaseAtom;
    state.atomGate = new Promise(resolve => { releaseAtom = resolve; });
    await save.click();
    await expect.poll(() => state.atomReads).toBe(1);
    if (change === "new-preset") {
      await page.locator("#new-preset").click();
      await page.locator("#preset-name").fill("Новый владелец");
    } else {
      await showWorkbench(page);
      if (change === "editor") await page.getByRole("button", {name: /A11/}).click();
      if (change === "catalog") {
        const reloaded = page.waitForResponse("**/v1/atom-lab/models");
        await page.locator("#access-form").dispatchEvent("submit");
        await reloaded;
      }
    }
    const completed = page.waitForResponse("**/v1/atom-lab/atoms/A06");
    releaseAtom();
    await (await completed).finished();
    if (change === "new-preset") {
      await expect(page.locator("#preset-name")).toHaveValue("Новый владелец");
      await expect(page.locator("#preset-config-metadata")).toContainText("product.a05.v1");
      await expect(page.locator("#preset-prompt")).toHaveText("Ручной текст владельца");
    } else if (change === "hidden-panel") {
      await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
      await expect(page.locator("#prompt-select")).toHaveValue("product.a05.v1");
      await page.locator("#presets-button").click();
      await expect(page.locator("#preset-config-metadata")).toContainText("prompt.a06.v2");
      await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
      await expect(save).toBeEnabled();
    } else {
      await expect(page.locator("#presets-panel")).toBeHidden();
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-select option[value='prompt.a06.v2']")).toHaveCount(0);
    }
    expect(state.writes).toHaveLength(1);
  });
}

for (const kind of ["prompt", "preset", "version", "history"]) {
  for (const refreshFails of [false, true]) {
    test(`${kind} source write rejection refreshes its owner${refreshFails ? " after 503 and Retry" : ""}`, async ({page}) => {
      const fixture = await prepareRejectedSourceWrite(page, kind);
      const {state, product, replacement, detail, originalDetail, save, name, error} = fixture;
      let releaseRefresh;
      state.refreshGate = new Promise(resolve => { releaseRefresh = resolve; });
      state.refreshStatus = refreshFails ? 503 : 200;
      await save.click();
      await expect(error).toContainText("Источник сохранения отклонён");
      await expect.poll(() => state.reads).toBe(2);
      await expect(save).toBeDisabled();
      await name.fill("Изменённое имя во время проверки");
      if (kind !== "history") {
        await showWorkbench(page);
        await page.locator("#prompt-tab").click();
        await page.locator("#prompt-editor").fill("Ручной текст после отказа");
        await page.locator("#input-tab").click();
        await importJson(page, {...A06.example_input, objective: "Ручной вход после отказа"});
        await page.locator("#prompt-tab").click();
        await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
      }
      releaseRefresh();
      const retry = kind === "history"
        ? page.getByRole("button", {name: "Повторить загрузку источника", exact: true})
        : page.locator("#retry-prompts");
      if (refreshFails) {
        await expect(kind === "history" ? error : page.locator("#prompt-load-status")).toContainText("Источники временно недоступны");
        await expect(retry).toBeVisible();
        await expect(save).toBeDisabled();
        if (kind === "history") await expect(page.locator("#preset-config-metadata")).toContainText(product.ref);
        else await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
        await save.dispatchEvent("click");
        expect(state.writes).toHaveLength(1);
        state.refreshStatus = 200;
        if (kind === "history") {
          await showWorkbench(page);
          await expect(page.locator("#prompt-select")).toHaveValue("product.a05.v1");
          await page.locator("#presets-button").click();
        }
        await retry.click();
      }
      if (kind === "history") {
        await expect(page.locator("#preset-state")).toContainText("Исторический источник недоступен");
        await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
        await expect(page.locator("#preset-config-metadata")).not.toContainText(product.ref);
      } else {
        await expect(page.locator("#prompt-select")).toHaveValue(A06.prompt_ref);
        await expect(page.locator("#prompt-select option")).toContainText(["Платформенный", replacement.name]);
        await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст после отказа");
        if (kind !== "prompt") await editPreset(page);
      }
      await expect(name).toHaveValue("Изменённое имя во время проверки");
      await expect(save).toBeEnabled();
      expect(state.reads).toBe(refreshFails ? 3 : 2);
      await save.click();
      await expect.poll(() => state.writes.length).toBe(2);
      const recovered = state.writes[1].payload;
      expect(state.writes[0].payload[kind === "prompt" ? "source_ref" : "prompt_source_ref"]).toBe(product.ref);
      expect(recovered[kind === "prompt" ? "source_ref" : "prompt_source_ref"]).toBe(kind === "prompt" ? A06.prompt_ref : null);
      expect(recovered.name).toBe("Изменённое имя во время проверки");
      expect(recovered.prompt).toBe(kind === "history" ? detail.snapshot.prompt.content : "Ручной текст после отказа");
      if (kind !== "prompt") {
        expect(recovered.example_input).toEqual(kind === "history" ? detail.snapshot.input : {...A06.example_input, objective: "Ручной вход после отказа"});
        expect(recovered.source_run_id).toBe(kind === "preset" ? null : detail.run_id);
        await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия");
      } else await expect(error).toContainText("Сохранён промпт");
      if (kind === "history") {
        await showWorkbench(page);
        await expect(page.locator("#atom-title")).toContainText("A05");
        await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
        await expect(page.locator("#prompt-select")).toHaveValue("product.a05.v1");
        await page.locator("#history-button").click();
        await page.locator("#history-list .history-open").click();
        expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(originalDetail);
      }
    });
  }
}

for (const phase of ["write", "refresh"]) {
  for (const change of ["source", "editor", "catalog", "text-and-name", "closed-panel"]) {
    test(`prompt source write recovery fences a later ${change} during ${phase}`, async ({page}) => {
      const {state, save, name, product} = await prepareRejectedSourceWrite(page, "prompt");
      let release;
      const gate = new Promise(resolve => { release = resolve; });
      if (phase === "write") state.writeGate = gate;
      else state.refreshGate = gate;
      await save.click();
      await expect.poll(() => phase === "write" ? state.writes.length : state.reads).toBe(phase === "write" ? 1 : 2);
      if (change === "source") await page.locator("#prompt-select").selectOption(A06.prompt_ref);
      if (change === "editor") {
        await page.getByRole("button", {name: /A05/}).click();
        await page.locator("#prompt-select").selectOption("product.a05.v1");
      }
      await page.locator("#prompt-editor").fill("Правки после отправки");
      if (change === "text-and-name") await name.fill("Позднее ручное имя");
      if (change === "closed-panel") await page.locator("#save-prompt-panel summary").click();
      if (change === "catalog") {
        page.removeAllListeners("dialog");
        page.on("dialog", dialog => dialog.dismiss());
        const reloaded = page.waitForResponse("**/v1/atom-lab/models");
        await page.locator("#access-form").dispatchEvent("submit");
        await reloaded;
      }
      const completed = page.waitForResponse(response => phase === "write"
        ? response.request().method() === "POST"
        : response.url().endsWith("/atoms/A06/prompts"));
      release();
      await (await completed).finished();
      const shouldRecover = change === "text-and-name" || change === "closed-panel";
      if (shouldRecover) await expect(page.locator("#prompt-select")).toHaveValue(A06.prompt_ref);
      else await expect(page.locator("#prompt-select")).toHaveValue(change === "source" ? A06.prompt_ref : change === "editor" ? "product.a05.v1" : product.ref);
      await expect(page.locator("#prompt-editor")).toHaveValue("Правки после отправки");
      await expect(page.locator("#retry-prompts")).toBeHidden();
      if (change === "source" || change === "editor") await expect(page.locator("#prompt-load-status")).toBeEmpty();
      if (change === "text-and-name") await expect(name).toHaveValue("Позднее ручное имя");
      if (change === "closed-panel") await expect(page.locator("#save-prompt-panel")).not.toHaveAttribute("open", "");
      expect(state.reads).toBe(phase === "refresh" || shouldRecover ? 2 : 1);
      expect(state.writes).toHaveLength(1);
    });
  }
}

for (const phase of ["write", "refresh"]) {
  for (const change of phase === "write" ? ["closed-panel", "catalog"] : ["closed-panel", "new-preset", "editor", "catalog"]) {
    test(`history source write recovery preserves a later ${change} during ${phase}`, async ({page}) => {
      const {state, save, product} = await prepareRejectedSourceWrite(page, "history");
      let release;
      const gate = new Promise(resolve => { release = resolve; });
      if (phase === "write") state.writeGate = gate;
      else state.refreshGate = gate;
      await save.click();
      await expect.poll(() => phase === "write" ? state.writes.length : state.reads).toBe(phase === "write" ? 1 : 2);
      await showWorkbench(page);
      if (change === "new-preset") {
        await page.locator("#presets-button").click();
        await page.locator("#new-preset").click();
        await page.locator("#preset-name").fill("Другой владелец");
      }
      if (change === "editor") await page.getByRole("button", {name: /A06/}).click();
      if (change === "catalog") {
        const reloaded = page.waitForResponse("**/v1/atom-lab/models");
        await page.locator("#access-form").dispatchEvent("submit");
        await reloaded;
      }
      const completed = page.waitForResponse(response => phase === "write"
        ? response.request().method() === "POST"
        : response.url().endsWith("/atoms/A06/prompts"));
      release();
      await (await completed).finished();
      if (change === "new-preset") {
        await expect(page.locator("#preset-name")).toHaveValue("Другой владелец");
        await expect(page.locator("#preset-prompt")).toHaveText("Ручной текст владельца");
        await expect(page.locator("#preset-config-metadata")).toContainText("product.a05.v1");
        await expect(page.locator("#preset-state")).not.toContainText("источник недоступен");
      } else {
        await expect(page.locator("#presets-panel")).toBeHidden();
        if (change !== "catalog") await expect(page.locator("#atom-title")).toContainText(change === "editor" ? "A06" : "A05");
        if (change === "closed-panel") {
          await expect(page.locator("#prompt-editor")).toHaveValue("Ручной текст владельца");
          await expect(page.locator("#prompt-select")).toHaveValue("product.a05.v1");
        }
      }
      await expect(page.locator("#prompt-load-status")).toBeEmpty();
      await expect(page.locator("#retry-prompts")).toBeHidden();
      expect(state.writes).toHaveLength(1);
      expect(state.writes[0].payload.prompt_source_ref).toBe(product.ref);
    });
  }
}

for (const kind of ["prompt", "preset", "version", "history"]) {
  for (const mismatch of ["code", "field"]) {
    test(`${kind} source write recovery ignores a different rejection ${mismatch}`, async ({page}) => {
      const {state, save, error} = await prepareRejectedSourceWrite(page, kind);
      if (mismatch === "code") state.rejectionCode = "input_invalid";
      else state.rejectionField = "prompt";
      await save.click();
      await expect(error).toContainText("Источник сохранения отклонён");
      await expect(save).toBeEnabled();
      expect(state.reads).toBe(1);
      expect(state.writes).toHaveLength(1);
      await expect(page.locator("#retry-prompts")).toBeHidden();
      await expect(page.getByRole("button", {name: "Повторить загрузку источника", exact: true})).toHaveCount(0);
    });
  }
}

for (const refreshFails of [false, true]) {
  test(`a rejected prompt source refreshes without losing edits${refreshFails ? " after a failed read and Retry" : ""}`, async ({page}) => {
    page.on("dialog", dialog => dialog.accept());
    const platform = {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null};
    const product = {ref: "product.a06.v1", name: "Продуктовый v1", prompt: "Текст продукта v1", group: "product", source_ref: null, source_run_id: null};
    const replacement = {...product, ref: "product.a06.v2", name: "Продуктовый v2", prompt: "Текст продукта v2"};
    let reads = 0;
    let releaseRefresh;
    const refreshGate = new Promise(resolve => { releaseRefresh = resolve; });
    const submissions = [];
    const keys = [];
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06/prompts", async route => {
      reads += 1;
      const read = reads;
      if (read === 2) await refreshGate;
      if (read === 2 && refreshFails) {
        await route.fulfill({status: 503, json: {error: {code: "prompts_unavailable", message: "Библиотека временно недоступна."}}});
      } else await route.fulfill({json: [platform, read === 1 ? product : replacement]});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
      submissions.push(route.request().postDataJSON());
      keys.push(route.request().headers()["idempotency-key"]);
      await route.fulfill({status: 422, json: {error: {
        code: submissions.length === 1 ? "prompt_source_invalid" : "input_invalid",
        message: "Запуск не принят.",
        field_errors: [{path: submissions.length === 1 ? "prompt_source_ref" : "input", message: "Источник больше недоступен."}],
      }, request_id: "source-rejected"}});
    });
    await unlockAtom(page, "A06");
    await page.locator("#fill-example").click();
    await page.locator("#prompt-tab").click();
    await page.locator("#prompt-select").selectOption(product.ref);
    await page.locator("#prompt-editor").fill("Ручной текст до отказа");
    await page.locator("#input-tab").click();
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toContainText("prompt_source_invalid");
    await expect.poll(() => reads).toBe(2);
    await expect(page.locator("#prompt-panel")).toBeVisible();
    await expect(page.locator("#prompt-select")).toHaveAttribute("aria-invalid", "true");
    await expect(page.locator("#validation-errors")).toContainText("prompt_source_ref: Источник больше недоступен.");
    await expect(page.locator("#run-button")).toBeDisabled();
    await expect(page.locator("#reset-prompt")).toBeDisabled();
    await expect(page.locator("#save-prompt")).toBeDisabled();
    await expect(page.locator("#retry-submit")).toBeHidden();
    const editedPrompt = "Ручной текст после отказа — сохранить полностью";
    await page.locator("#prompt-editor").fill(editedPrompt);
    await page.locator("#input-tab").click();
    const input = {...A06.example_input, objective: "Правка во время обновления источников"};
    await importJson(page, input);
    await page.getByRole("button", {name: "prompt_source_ref: Источник больше недоступен.", exact: true}).click();
    await expect(page.locator("#prompt-select")).toBeFocused();
    releaseRefresh();
    if (refreshFails) {
      await expect(page.locator("#prompt-load-status")).toContainText("Библиотека временно недоступна");
      await expect(page.locator("#retry-prompts")).toBeVisible();
      await expect(page.locator("#prompt-select")).toHaveValue(product.ref);
      await expect(page.locator("#prompt-editor")).toHaveValue(editedPrompt);
      await expect(page.locator("#run-button")).toBeDisabled();
      await page.locator("#run-button").dispatchEvent("click");
      expect(submissions).toHaveLength(1);
      await page.locator("#retry-prompts").click();
    }
    await expect(page.locator("#prompt-select")).toHaveValue(A06.prompt_ref);
    await expect(page.locator("#prompt-select option")).toHaveText([platform.name, replacement.name]);
    await expect(page.locator("#prompt-origin")).toContainText("источник недоступен");
    await expect(page.locator("#prompt-editor")).toHaveValue(editedPrompt);
    await expect(page.locator("#validation-errors")).not.toContainText("prompt_source_ref");
    await expect(page.locator("#prompt-select")).not.toHaveAttribute("aria-invalid", "true");
    await expect(page.locator("#retry-prompts")).toBeHidden();
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#prompt-test-status")).toContainText("нет успешного пробного запуска");
    await page.locator("#run-button").click();
    await expect.poll(() => submissions.length).toBe(2);
    expect(submissions[0].prompt_source_ref).toBe(product.ref);
    expect(submissions[1].prompt_source_ref).toBeUndefined();
    expect(submissions[1].prompt).toBe(editedPrompt);
    expect(submissions[1].input).toEqual(input);
    expect(keys[1]).not.toBe(keys[0]);
    expect(reads).toBe(refreshFails ? 3 : 2);
    await page.locator("#prompt-select").selectOption(replacement.ref);
    await expect(page.locator("#prompt-editor")).toHaveValue(replacement.prompt);
  });
}

for (const change of ["source", "replacement-editor", "catalog"]) {
  test(`a delayed rejected prompt source leaves a changed ${change} untouched`, async ({page}) => {
    let cancelSwitch = false;
    page.on("dialog", dialog => cancelSwitch ? dialog.dismiss() : dialog.accept());
    const product = {ref: "product.a06.v1", name: "Продуктовый v1", prompt: "Текст продукта v1", group: "product", source_ref: null, source_run_id: null};
    const other = {...product, ref: "product.a06.v2", name: "Продуктовый v2", prompt: "Текст продукта v2"};
    let reads = 0;
    let releaseRejection;
    const rejection = new Promise(resolve => { releaseRejection = resolve; });
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06/prompts", async route => {
      reads += 1;
      await route.fulfill({json: [
        {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null}, product, other,
      ]});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
      await rejection;
      await route.fulfill({status: 422, json: {error: {
        code: "prompt_source_invalid", message: "Источник больше недоступен.",
        field_errors: [{path: "prompt_source_ref", message: "Устаревший источник."}],
      }, request_id: "late-source-rejection"}});
    });
    await unlockAtom(page, "A06");
    await page.locator("#fill-example").click();
    await page.locator("#prompt-tab").click();
    await page.locator("#prompt-select").selectOption(product.ref);
    const posted = page.waitForRequest(request => request.method() === "POST" && request.url().endsWith("/runs"));
    await page.locator("#run-button").click();
    await posted;
    if (change === "source") await page.locator("#prompt-select").selectOption(other.ref);
    if (change === "replacement-editor") {
      await page.getByRole("button", {name: /A05/}).click();
      await page.getByRole("button", {name: /A06/}).click();
      await page.locator("#input-tab").click();
      await page.locator("#fill-example").click();
      await page.locator("#prompt-tab").click();
      await page.locator("#prompt-select").selectOption(product.ref);
    }
    const currentText = "Правки текущего редактора";
    await page.locator("#prompt-editor").fill(currentText);
    if (change === "catalog") {
      cancelSwitch = true;
      const reloaded = page.waitForResponse("**/v1/atom-lab/models");
      await page.locator("#access-form").dispatchEvent("submit");
      await reloaded;
    }
    const readsBeforeRejection = reads;
    const rejected = page.waitForResponse(response => response.request().method() === "POST" && response.url().endsWith("/runs"));
    releaseRejection();
    await (await rejected).finished();
    await expect(page.locator("#run-state")).toContainText("prompt_source_invalid");
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#prompt-editor")).toHaveValue(currentText);
    await expect(page.locator("#prompt-select")).toHaveValue(change === "source" ? other.ref : product.ref);
    await expect(page.locator("#validation-errors")).not.toContainText("Устаревший источник");
    await expect(page.locator("#retry-prompts")).toBeHidden();
    expect(reads).toBe(readsBeforeRejection);
    await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
  });
}

for (const change of ["source", "editor"]) {
  test(`a rejected source refresh preserves a later ${change} selection`, async ({page}) => {
    page.on("dialog", dialog => dialog.accept());
    const platform = {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null};
    const product = {ref: "product.a06.v1", name: "Продуктовый v1", prompt: "Текст продукта v1", group: "product", source_ref: null, source_run_id: null};
    const replacement = {...product, ref: "product.a06.v2", name: "Продуктовый v2", prompt: "Текст продукта v2"};
    let reads = 0;
    let releaseRefresh;
    const refresh = new Promise(resolve => { releaseRefresh = resolve; });
    await page.route("http://atom-lab.test/v1/atom-lab/atoms/A06/prompts", async route => {
      const read = ++reads;
      if (read === 2) await refresh;
      await route.fulfill({json: [platform, read === 1 ? product : replacement]});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs", route => route.fulfill({status: 422, json: {error: {
      code: "prompt_source_invalid", message: "Источник больше недоступен.",
      field_errors: [{path: "prompt_source_ref", message: "Устаревший источник."}],
    }, request_id: "source-refresh"}}));
    await unlockAtom(page, "A06");
    await page.locator("#fill-example").click();
    await page.locator("#prompt-tab").click();
    await page.locator("#prompt-select").selectOption(product.ref);
    await page.locator("#run-button").click();
    await expect.poll(() => reads).toBe(2);
    if (change === "editor") {
      await page.getByRole("button", {name: /A05/}).click();
      await page.getByRole("button", {name: /A06/}).click();
    }
    const selectedRef = change === "source" ? platform.ref : replacement.ref;
    await page.locator("#prompt-select").selectOption(selectedRef);
    const text = "Правки после начала обновления";
    await page.locator("#prompt-editor").fill(text);
    const refreshed = page.waitForResponse("**/atoms/A06/prompts");
    releaseRefresh();
    await (await refreshed).finished();
    await expect(page.locator("#run-button")).toBeEnabled();
    await expect(page.locator("#prompt-editor")).toHaveValue(text);
    await expect(page.locator("#prompt-select")).toHaveValue(selectedRef);
    await expect(page.locator("#prompt-origin")).not.toContainText("недоступен");
    await expect(page.locator("#validation-errors")).not.toContainText("Устаревший источник");
    await expect(page.locator("#retry-prompts")).toBeHidden();
    expect(reads).toBe(change === "source" ? 2 : 3);
  });
}

test("prompt admission errors stay visible and identify the prompt editor", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({
      error: {
        code: "input_invalid",
        message: "Prompt validation failed.",
        field_errors: [{path: "prompt", message: "Prompt must not be blank."}],
      },
      request_id: "request-prompt-error",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-editor").fill("");
  await page.locator("#run-button").click();

  await expect(page.locator("#prompt-panel")).toBeVisible();
  await expect(page.locator("#validation-errors")).toContainText("Prompt must not be blank.");
  await expect(page.locator("#prompt-editor")).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#prompt-editor")).toHaveAttribute("aria-describedby", /.+/);

  await page.locator("#prompt-editor").fill("Corrected prompt");
  await expect(page.locator("#validation-errors")).not.toContainText("Prompt must not be blank.");
  await expect(page.locator("#prompt-editor")).not.toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#prompt-editor")).not.toHaveAttribute("aria-describedby", /.+/);
});

test("input admission errors retire when the input draft changes", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({
      error: {
        code: "input_invalid",
        message: "Input validation failed.",
        field_errors: [{path: "input", message: "Submitted input is no longer accepted."}],
      },
      request_id: "request-input-error",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#validation-errors")).toContainText("Submitted input is no longer accepted.");
  await page.getByLabel("Контекст").fill("Исправленная оценка");
  await expect(page.locator("#validation-errors")).not.toContainText("Submitted input is no longer accepted.");
});

test("corrected accepted submission clears authoritative admission field errors", async ({page}) => {
  let submissions = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    submissions += 1;
    if (submissions > 1) {
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        run_id: "run-corrected", scenario_session_id: "session-corrected", job_id: "job-corrected", status: "queued",
      })});
      return;
    }
    await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({
      error: {
        code: "reasoning_not_allowed",
        message: "Reasoning is no longer allowed.",
        field_errors: [
          {path: "input", message: "Server input validation failed."},
          {path: "reasoning_effort", message: "Selected reasoning is unavailable."},
        ],
      },
      request_id: "request-field-errors",
    })});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-corrected", async (route) => {
    await route.fulfill({status: 404, contentType: "application/json", body: JSON.stringify({
      error: {code: "lab_resource_not_found", message: "Запуск ещё не виден.", field_errors: []},
      request_id: "request-corrected",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");
  await page.locator("#run-button").click();

  await expect(page.locator("#run-state")).toContainText("reasoning_not_allowed");
  await expect(page.locator("#validation-errors")).toContainText("Server input validation failed.");
  await expect(page.locator("#validation-errors")).toContainText("Selected reasoning is unavailable.");
  await expect(page.locator("#reasoning-effort")).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#retry-submit")).toBeHidden();

  await page.locator("#reasoning-effort").selectOption("low");
  await expect(page.locator("#validation-errors")).not.toContainText("Selected reasoning is unavailable.");
  await expect(page.locator("#reasoning-effort")).not.toHaveAttribute("aria-invalid", "true");
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("lab_resource_not_found");
  await expect(page.locator("#validation-errors")).not.toContainText("Selected reasoning is unavailable.");
  await expect(page.locator("#validation-errors")).not.toContainText("Server input validation failed.");
  await expect(page.locator("#reasoning-effort")).not.toHaveAttribute("aria-invalid", "true");
  expect(submissions).toBe(2);
});

test("atom navigation clears validation-owned ARIA state from global model controls", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({
      error: {
        code: "reasoning_not_allowed",
        message: "The selected configuration is no longer allowed.",
        field_errors: [
          {path: "model_id", message: "Selected model is unavailable."},
          {path: "reasoning_effort", message: "Selected reasoning is unavailable."},
        ],
      },
      request_id: "request-navigation-errors",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");
  await page.locator("#run-button").click();

  await expect(page.locator("#model-select")).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#reasoning-effort")).toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#model-select")).toHaveAttribute("aria-describedby", /.+/);
  await expect(page.locator("#reasoning-effort")).toHaveAttribute("aria-describedby", /.+/);

  await page.getByRole("button", {name: /A06/}).click();

  await expect(page.locator("#validation-errors")).not.toContainText("Selected model is unavailable.");
  await expect(page.locator("#validation-errors")).not.toContainText("Selected reasoning is unavailable.");
  await expect(page.locator("#model-select")).not.toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#reasoning-effort")).not.toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#model-select")).not.toHaveAttribute("aria-describedby", /.+/);
  await expect(page.locator("#reasoning-effort")).toHaveAttribute("aria-describedby", "reasoning-help");
});

test("delayed admission errors do not invalidate a newer draft selection", async ({page}) => {
  let releaseRejection;
  let markRequestStarted;
  const requestStarted = new Promise((resolve) => { markRequestStarted = resolve; });
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    markRequestStarted();
    await new Promise((resolve) => { releaseRejection = resolve; });
    await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({
      error: {
        code: "reasoning_not_allowed",
        message: "Reasoning is no longer allowed.",
        field_errors: [{path: "reasoning_effort", message: "Submitted reasoning is unavailable."}],
      },
      request_id: "request-delayed-rejection",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");

  const submission = page.locator("#run-button").click();
  await requestStarted;
  await page.locator("#reasoning-effort").selectOption("low");
  releaseRejection();
  await submission;

  await expect(page.locator("#run-state")).toContainText("reasoning_not_allowed");
  await expect(page.locator("#validation-errors")).not.toContainText("Submitted reasoning is unavailable.");
  await expect(page.locator("#reasoning-effort")).not.toHaveAttribute("aria-invalid", "true");
  await expect(page.locator("#reasoning-effort")).toHaveValue("low");
});

test("succeeded run without a result fails closed as an invalid API response", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
      run_id: "run-empty-success", scenario_session_id: "session-empty-success", job_id: "job-empty-success", status: "queued",
    })});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-empty-success", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-empty-success", status: "succeeded",
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-empty-success", job_id: "job-empty-success", action_run_id: "action-empty-success", artifact_id: null},
      result: null,
      diagnostics: {error_code: null, duration_ms: 1, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: "openai/gpt-supported", validation_attempts: 1, transport_attempts: 1, physical_calls: 1, succeeded_first_attempt: true, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-22T00:00:00Z", started_at: "2026-09-22T00:00:00Z", finished_at: "2026-09-22T00:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#run-state")).toContainText("Некорректный ответ API");
  await expect(page.locator("#retry-read")).toBeVisible();
  await expect(page.locator("#result-section")).toBeHidden();
  await expect(page.locator("#run-button")).toBeDisabled();
});

test("malformed successful run detail fails closed without automatic reconnect", async ({page}) => {
  let reads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
      run_id: "run-malformed-detail", scenario_session_id: "session-malformed-detail", job_id: "job-malformed-detail", status: "running",
    })});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-malformed-detail", async (route) => {
    reads += 1;
    await route.fulfill({status: 200, contentType: "text/html", body: "<not-json>"});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#run-state")).toContainText("Некорректный ответ API");
  await expect(page.locator("#retry-read")).toBeVisible();
  await new Promise((resolve) => setTimeout(resolve, 500));
  expect(reads).toBe(1);
});

for (const mismatch of [
  {
    label: "requested model",
    submittedEffort: null,
    requestedModelId: "openai/gpt-other",
    requestedEffort: null,
  },
  {
    label: "requested reasoning effort",
    submittedEffort: "low",
    requestedModelId: "openai/gpt-supported",
    requestedEffort: "high",
  },
]) {
  test(`run detail with conflicting ${mismatch.label} fails closed`, async ({page}) => {
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        run_id: "run-conflict", scenario_session_id: "session-conflict", job_id: "job-conflict", status: "running",
      })});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs/run-conflict", async (route) => {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        run_id: "run-conflict", status: "running",
        snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: mismatch.submittedEffort},
        runtime_ids: {scenario_session_id: "session-conflict", job_id: "job-conflict", action_run_id: "action-conflict", artifact_id: null},
        result: null,
        diagnostics: {error_code: null, duration_ms: null, requested_model_id: mismatch.requestedModelId, requested_reasoning_effort: mismatch.requestedEffort, response_model_id: null, validation_attempts: 0, transport_attempts: 0, physical_calls: 0, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
        created_at: "2026-09-22T00:00:00Z", started_at: "2026-09-22T00:00:00Z", finished_at: null,
      })});
    });
    await unlockAtom(page, "A05");
    await page.locator("#fill-example").click();
    if (mismatch.submittedEffort) {
      await page.locator("#model-select").selectOption("gpt-supported");
      await page.locator("#reasoning-effort").selectOption(mismatch.submittedEffort);
    }
    await page.locator("#run-button").click();

    await expect(page.locator("#run-state")).toContainText("Некорректный ответ API");
    await expect(page.locator("#retry-read")).toBeVisible();
    await expect(page.locator("#run-metadata")).toHaveText("");
    await expect(page.locator("#submitted-snapshot")).toContainText("openai/gpt-supported");
    await expect(page.locator("#run-button")).toBeDisabled();
  });
}

test("run detail with conflicting accepted runtime identity fails closed", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
      run_id: "run-identity", scenario_session_id: "session-a", job_id: "job-a", status: "running",
    })});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-identity", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-identity", status: "running",
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-b", job_id: "job-b", action_run_id: "action-b", artifact_id: null},
      result: null,
      diagnostics: {error_code: null, duration_ms: null, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 0, physical_calls: 0, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-22T00:00:00Z", started_at: "2026-09-22T00:00:00Z", finished_at: null,
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#run-state")).toContainText("Некорректный ответ API");
  await expect(page.locator("#retry-read")).toBeVisible();
  await expect(page.locator("#run-metadata")).toHaveText("");
  await expect(page.locator("#run-diagnostics")).toContainText('"scenario_session_id": "session-a"');
  await expect(page.locator("#run-diagnostics")).toContainText('"job_id": "job-a"');
  await expect(page.locator("#run-diagnostics")).not.toContainText("session-b");
  await expect(page.locator("#run-diagnostics")).not.toContainText("job-b");
});

for (const key of ["action_run_id", "artifact_id"]) {
  test(`run detail enforces fill-once ${key}`, async ({page}) => {
    let reads = 0;
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        run_id: `run-fill-once-${key}`, scenario_session_id: "session-fill-once", job_id: "job-fill-once", status: "running",
      })});
    });
    await page.route(`http://atom-lab.test/v1/atom-lab/runs/run-fill-once-${key}`, async (route) => {
      reads += 1;
      const runtimeIds = {
        scenario_session_id: "session-fill-once",
        job_id: "job-fill-once",
        action_run_id: key === "action_run_id" ? `action-${reads === 1 ? "a" : "b"}` : "action-stable",
        artifact_id: key === "artifact_id" ? `artifact-${reads === 1 ? "a" : "b"}` : null,
      };
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        run_id: `run-fill-once-${key}`, status: "running",
        snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
        runtime_ids: runtimeIds,
        result: null,
        diagnostics: {error_code: null, duration_ms: null, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 0, physical_calls: 0, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
        created_at: "2026-09-22T00:00:00Z", started_at: "2026-09-22T00:00:00Z", finished_at: null,
      })});
    });
    await unlockAtom(page, "A05");
    await page.locator("#fill-example").click();
    await page.locator("#run-button").click();

    const acceptedId = key === "action_run_id" ? "action-a" : "artifact-a";
    const conflictingId = key === "action_run_id" ? "action-b" : "artifact-b";
    await expect(page.locator("#run-diagnostics")).toContainText(acceptedId);
    await expect(page.locator("#run-state")).toContainText("Некорректный ответ API");
    await expect(page.locator("#retry-read")).toBeVisible();
    await expect(page.locator("#run-diagnostics")).toContainText(acceptedId);
    await expect(page.locator("#run-diagnostics")).not.toContainText(conflictingId);
    expect(reads).toBe(2);
  });
}

for (const status of [422, 429]) {
  test(`malformed ${status} admission rejection releases the frozen submission`, async ({page}) => {
    let submissions = 0;
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
      submissions += 1;
      await route.fulfill({status, contentType: "text/html", body: "<not-json>"});
    });
    await unlockAtom(page, "A05");
    await page.locator("#fill-example").click();
    await page.locator("#run-button").click();

    await expect(page.locator("#run-state")).toContainText("request_failed");
    await expect(page.locator("#retry-submit")).toBeHidden();
    await expect(page.locator("#run-button")).toBeEnabled();
    await page.locator("#run-button").click();
    await expect.poll(() => submissions).toBe(2);
  });
}

test("malformed accepted response keeps the same submission available for safe replay", async ({page}) => {
  const keys = [];
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify(
      keys.length === 1
        ? {status: "queued"}
        : {run_id: "run-shape", scenario_session_id: "session-shape", job_id: "job-shape", status: "queued"},
    )});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-shape", async (route) => {
    await route.fulfill({status: 404, contentType: "application/json", body: JSON.stringify({error: {code: "lab_resource_not_found", message: "Не найдено.", field_errors: []}, request_id: "request-shape"})});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();

  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("Некорректный ответ");
  await expect(page.locator("#retry-submit")).toBeVisible();
  await page.locator("#retry-submit").click();

  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test("permanent protected poll error stops automatic polling and offers reread", async ({page}) => {
  let reads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-gone", scenario_session_id: "session-gone", job_id: "job-gone", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-gone", async (route) => {
    reads += 1;
    await route.fulfill({status: 404, contentType: "application/json", body: JSON.stringify({error: {code: "lab_resource_not_found", message: "Запуск не найден.", field_errors: []}, request_id: "request-gone"})});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#run-state")).toContainText("lab_resource_not_found");
  await expect(page.locator("#retry-read")).toBeVisible();
  await page.waitForTimeout(600);
  expect(reads).toBe(1);
});

test("an accepted nonterminal run blocks overlapping launch until it reaches terminal state", async ({page}) => {
  let posts = 0;
  let reads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/models/refresh", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({...MODEL_CATALOG, refresh_status: "pending"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    posts += 1;
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-serial", scenario_session_id: "session-serial", job_id: "job-serial", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-serial", async (route) => {
    reads += 1;
    await new Promise((resolve) => setTimeout(resolve, 350));
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-serial", status: reads === 1 ? "running" : "failed", snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-serial", job_id: "job-serial", action_run_id: null, artifact_id: null}, result: null,
      diagnostics: {error_code: reads === 1 ? null : "provider_unavailable", duration_ms: null, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 0, transport_attempts: 0, physical_calls: 0, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: null, finished_at: null,
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#run-button")).toBeDisabled();
  await page.locator("#refresh-models").click();
  await page.waitForTimeout(400);
  await expect(page.locator("#run-button")).toBeDisabled();
  expect(posts).toBe(1);
  await expect(page.locator("#run-state")).toContainText("Ошибка");
  await expect(page.locator("#run-button")).toBeEnabled();
});

test("preset browsing preserves an unrelated dirty draft until explicit application", async ({page}) => {
  const stored = {
    name: "Сравнение пилота", description: "Сохранённая конфигурация", atom_id: "A11",
    base_action_config_id: A11.base_action_config_id, schema_refs: A11.schema_refs,
    prompt: "Сохранённый промпт", prompt_ref: A11.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: ["categories"],
    example_input: A11.example_input, source_run_id: null,
    preset_id: "preset-browse", version: 1, created_at: "2026-11-06T08:00:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/presets**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const summary = {preset_id: stored.preset_id, name: stored.name, description: stored.description,
      atom_id: stored.atom_id, created_at: stored.created_at};
    const body = pathname.endsWith("/versions/1") ? stored : pathname.endsWith("/versions")
      ? {items: [{...summary, version: 1}], next_cursor: null}
      : {items: [{...summary, latest_version: 1, updated_at: stored.created_at}], next_cursor: null};
    await route.fulfill({contentType: "application/json", body: JSON.stringify(body)});
  });
  let discard = false;
  let confirmations = 0;
  page.on("dialog", (dialog) => { confirmations += 1; return discard ? dialog.accept() : dialog.dismiss(); });
  await unlockAtom(page, "A05");
  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-editor").fill("Несохранённый промпт A05");
  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-editor-form")).toBeHidden();
  await expect(page.locator("#preset-empty")).toBeVisible();
  await page.locator("#preset-list button").click();
  await expect(page.locator("#preset-selected-name")).toHaveText(stored.name);
  await expect(page.locator("#preset-editor-form")).toBeHidden();
  await expect(page.locator("#preset-config-metadata")).toContainText("high");
  await expect(page.locator("#preset-input-fields [data-fixed=true]")).toHaveText("categories · закреплено");
  await page.setViewportSize({width: 320, height: 900});
  await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  await page.evaluate(() => { document.documentElement.style.fontSize = ""; });
  await page.setViewportSize({width: 1280, height: 720});
  await expect(page.locator("#atom-sidebar")).toBeHidden();
  await expect(page.locator("#request-response")).toBeHidden();
  expect(JSON.parse(await page.locator("#preset-readonly").textContent())).toEqual(stored);
  expect(confirmations).toBe(0);
  await page.locator("#apply-preset").click();
  await expect(page.locator("#presets-panel")).toBeVisible();
  await expect(page.locator("#prompt-editor")).toHaveValue("Несохранённый промпт A05");
  discard = true;
  await page.locator("#apply-preset").click();
  await expect(page.locator("#presets-panel")).toBeHidden();
  await expect(page.locator("#atom-title")).toContainText("A11");
  await expect(page.locator("#prompt-editor")).toHaveValue(stored.prompt);
  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-editor-form")).toBeVisible();
  await expect(page.locator("#preset-editor-title")).toHaveText("Новая версия на основе v1");
  await page.locator("#cancel-preset").click();
  await expect(page.locator("#preset-editor-form")).toBeHidden();
  expect(JSON.parse(await page.locator("#preset-readonly").textContent())).toEqual(stored);
});

for (const settingsOnly of [false, true, null]) {
  test(`reopening v1 after cancelling ${settingsOnly === null ? "run provenance" : settingsOnly ? "model, reasoning and origin" : "input and prompt"} edits protects and restores the saved settings`, async ({page}) => {
    const stored = {
      name: "Повторное открытие", description: "Неизменяемая версия", atom_id: "A06",
      base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
      prompt: A06.prompt, prompt_ref: A06.prompt_ref, prompt_source_ref: "product.a06.v1",
      model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: ["context"],
      example_input: A06.example_input, source_run_id: settingsOnly === false ? "run-unknown" : null,
      preset_id: "preset-reopen", version: 1, created_at: "2026-11-06T08:00:00Z",
    };
    let runBody;
    await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
      const request = route.request();
      const {pathname} = new URL(request.url());
      if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
        await route.fulfill({json: [
          {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null},
          {ref: stored.prompt_source_ref, name: "Продуктовый", prompt: stored.prompt, group: "product", source_ref: null, source_run_id: null},
        ]});
      } else if (pathname.startsWith("/v1/atom-lab/presets")) {
        expect(request.method()).toBe("GET");
        const summary = {preset_id: stored.preset_id, name: stored.name, description: stored.description,
          atom_id: stored.atom_id, created_at: stored.created_at};
        await route.fulfill({json: pathname.endsWith("/versions/1") ? stored : {
          items: [pathname.endsWith("/versions") ? {...summary, version: 1}
            : {...summary, latest_version: 1, updated_at: stored.created_at}], next_cursor: null,
        }});
      } else if (pathname === "/v1/atom-lab/runs") {
        runBody = request.postDataJSON();
        await route.fulfill({status: 202, json: {
          run_id: "run-reopen", scenario_session_id: "session-library", job_id: "job-library", status: "queued",
        }});
      } else if (pathname === "/v1/atom-lab/runs/run-reopen") {
        const detail = historyDetail({runId: "run-reopen", prompt: stored.prompt});
        detail.snapshot.prompt.source_ref = stored.prompt_source_ref;
        detail.snapshot.preset = {id: stored.preset_id, version: 1};
        await route.fulfill({json: detail});
      } else await route.fallback();
    });
    let discard = false;
    let confirmations = 0;
    page.on("dialog", dialog => { confirmations += 1; return discard ? dialog.accept() : dialog.dismiss(); });
    await unlockAtom(page, "A06");
    await page.locator("#presets-button").click();
    await page.locator("#preset-list button").click();
    await page.locator("#apply-preset").click();
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-select")).toHaveValue(stored.prompt_source_ref);
    await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
    if (settingsOnly !== null) await expect(page.locator("#preset-config-metadata")).toContainText(stored.prompt_source_ref);
    const editedInput = settingsOnly !== false ? stored.example_input : {...stored.example_input, objective: "Новая цель"};
    const editedPrompt = settingsOnly !== false ? stored.prompt : "Несохранённый промпт";
    if (settingsOnly === null) {
      await page.locator("#run-button").click();
      await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
    } else if (settingsOnly) {
      await page.locator("#prompt-select").selectOption(A06.prompt_ref);
      await page.locator("#model-select").selectOption("gpt-no-reasoning");
    } else {
      await page.locator("#input-tab").click();
      await importJson(page, editedInput);
      await page.locator("#prompt-tab").click();
      await page.locator("#prompt-editor").fill(editedPrompt);
    }
    await page.locator("#input-tab").click();
    await page.locator("#json-mode").click();
    await page.locator("#presets-button").click();
    await expect(page.locator("#preset-editor-form")).toBeVisible();
    await expect(page.locator("#preset-state")).toContainText("Есть несохранённый черновик");
    expect(JSON.parse(await page.locator("#preset-input-json").textContent())).toEqual(editedInput);
    await expect(page.locator("#preset-prompt")).toHaveText(editedPrompt);
    expect(confirmations).toBe(0);
    discard = true;
    await page.locator("#cancel-preset").click();
    await expect(page.locator("#preset-editor-form")).toBeHidden();
    expect(confirmations).toBe(1);
    expect(JSON.parse(await page.locator("#preset-readonly").textContent())).toEqual(stored);
    discard = false;
    await page.locator("#apply-preset").click();
    expect(confirmations).toBe(2);
    await expect(page.locator("#presets-panel")).toBeVisible();
    await expect(page.locator("#prompt-editor")).toHaveValue(editedPrompt);
    expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual(editedInput);
    await expect(page.locator("#model-select")).toHaveValue(settingsOnly === true ? "gpt-no-reasoning" : "gpt-supported");
    await expect(page.locator("#reasoning-effort")).toHaveValue(settingsOnly === true ? "" : "high");
    await expect(page.locator("#prompt-select")).toHaveValue(settingsOnly === true ? A06.prompt_ref : stored.prompt_source_ref);
    discard = true;
    await page.locator("#apply-preset").click();
    expect(confirmations).toBe(3);
    await expect(page.locator("#presets-panel")).toBeHidden();
    await expect(page.locator("#prompt-editor")).toHaveValue(stored.prompt);
    await expect(page.locator("#prompt-select")).toHaveValue(stored.prompt_source_ref);
    await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
    await expect(page.locator("#reasoning-effort")).toHaveValue(stored.reasoning_effort);
    await page.locator("#input-tab").click();
    await page.locator("#json-mode").click();
    expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual(stored.example_input);
    if (settingsOnly === null) {
      await page.locator("#presets-button").click();
      await expect(page.locator("#preset-state")).not.toContainText("Есть несохранённый черновик");
      await showWorkbench(page);
    }
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toHaveText("Завершён успешно");
    expect(runBody).toEqual({
      atom_id: stored.atom_id, input: stored.example_input, prompt: stored.prompt,
      prompt_source_ref: stored.prompt_source_ref, model_id: stored.model_id,
      reasoning_effort: stored.reasoning_effort, preset_ref: {preset_id: stored.preset_id, version: 1},
      expected_contract: expectedAtomContract(A06),
    });
  });
}

test("full length preset names and descriptions wrap on desktop and mobile", async ({page}, testInfo) => {
  const longName = "Я".repeat(256);
  const longDescription = "О".repeat(4096);
  const items = [
    {preset_id: "long-name", name: longName, description: "Полное длинное имя без пробелов"},
    {preset_id: "long-description", name: "Полное описание без пробелов", description: longDescription},
  ].map(item => ({...item, atom_id: "A06", latest_version: 1, created_at: "2026-09-23T08:00:00Z", updated_at: "2026-09-23T08:00:00Z"}));
  await page.route("http://atom-lab.test/v1/atom-lab/presets", route => route.fulfill({json: {items, next_cursor: null}}));
  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-list button")).toHaveCount(2);
  for (const width of [1440, 360]) {
    await page.setViewportSize({width, height: 900});
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    await expect(page.locator('[data-preset-id="long-name"]')).toContainText(longName);
    await expect(page.locator('[data-preset-id="long-description"] small').last()).toHaveText(longDescription);
    expect(await page.locator("#preset-list button").evaluateAll(buttons => buttons.every(button => button.scrollWidth <= button.clientWidth))).toBe(true);
  }
  await page.screenshot({path: testInfo.outputPath("long-presets-360.png")});
});

test("a failed history detail stays collapsed and retries from its date button", async ({page}, testInfo) => {
  await page.setViewportSize({width: 360, height: 900});
  const detail = historyDetail();
  let reads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs**", async route => {
    if (new URL(route.request().url()).pathname.endsWith("/runs")) {
      await route.fulfill({json: {items: [{
        run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: "openai/gpt-supported",
        preset_id: null, preset_version: null, created_at: detail.created_at,
        started_at: detail.started_at, finished_at: detail.finished_at,
      }], next_cursor: null}});
    } else {
      reads += 1;
      await route.fulfill(reads === 1
        ? {status: 503, json: {error: {code: "history_unavailable", message: "Подробности временно недоступны."}}}
        : {json: detail});
    }
  });
  await unlockAtom(page, "A06");
  await page.locator("#history-button").click();
  const date = page.locator(`[data-run-id="${detail.run_id}"]`);
  await date.click();
  await expect(page.locator("#history-error")).toContainText("Подробности временно недоступны");
  await expect(date).toHaveAttribute("aria-current", "true");
  await expect(date).toHaveAttribute("aria-expanded", "false");
  await expect(date).toBeEnabled();
  await expect(page.locator("#history-record")).toBeHidden();
  await expect(page.locator("#history-list > tr")).toHaveCount(1);
  await expect(page.locator("#history-list .history-expanded")).toHaveCount(0);
  await expect(page.locator("#history-error")).toContainText("кнопкой даты");
  await page.screenshot({path: testInfo.outputPath("history-read-failed-360.png")});
  await date.click();
  await expect(page.locator("#history-record")).toBeVisible();
  await expect(date).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#history-list > tr")).toHaveCount(2);
  await expect(page.locator("#history-list .history-expanded")).toHaveCount(1);
  await expect(page.locator("#history-error")).toHaveText("");
  await expect(page.locator("#history-result-readable")).toContainText("Готово");
  await expect(page.locator("#restore-history")).toBeEnabled();
  expect(reads).toBe(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(360);
  await page.screenshot({path: testInfo.outputPath("history-read-retried-360.png")});
});

test("history table reveals result, request and diagnostics with complete JSON and keyboard tabs", async ({page}) => {
  const detail = historyDetail();
  detail.result = {text: "Готово", values: {deadline: "30 сентября", budget: 120000}, missing_fields: []};
  const older = {...historyDetail({runId: "run-older-page"}), created_at: "2026-09-22T08:00:00Z"};
  let posts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs**", async (route) => {
    if (route.request().method() === "POST") posts += 1;
    const url = new URL(route.request().url());
    const selected = url.searchParams.has("cursor") || url.pathname.endsWith(older.run_id) ? older : detail;
    const body = url.pathname.endsWith("/runs") ? {items: [{
      run_id: selected.run_id, status: selected.status, atom_id: "A06", model_id: "openai/gpt-supported",
      preset_id: null, preset_version: null, created_at: selected.created_at,
      started_at: selected.started_at, finished_at: selected.finished_at,
    }], next_cursor: url.searchParams.has("cursor") ? null : "older"} : selected;
    await route.fulfill({contentType: "application/json", body: JSON.stringify(body)});
  });
  await unlockAtom(page, "A05");
  await page.locator("#history-button").click();
  await expect(page.locator(".history-table th")).toHaveText(["Создан", "Атом", "Статус", "Модель"]);
  await expect(page.locator("#history-list .status-badge")).toHaveText("Успешно");
  await expect(page.locator(".history-open")).toHaveAccessibleName(/Подробности запуска.*A06.*Успешно/);
  await expect(page.locator("#history-record")).toBeHidden();
  await page.locator(".history-open").click();
  await expect(page.locator("#history-record")).toBeVisible();
  await expect(page.locator("#history-result-readable")).toContainText("Готово");
  await expect(page.locator("#history-result-readable")).toContainText("Пропусков нет");
  await expect(page.locator("#history-result-readable dl dl dd")).toHaveText(["30 сентября", "120000"]);
  expect(JSON.parse(await page.locator("#history-result-json").textContent())).toEqual(detail.result);
  expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(detail);
  await page.locator("#history-result-tab").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#history-request-tab")).toBeFocused();
  expect(JSON.parse(await page.locator("#history-snapshot").textContent())).toEqual(detail.snapshot);
  await page.keyboard.press("End");
  await expect(page.locator("#history-diagnostics-panel")).toBeVisible();
  expect(JSON.parse(await page.locator("#history-diagnostics-json").textContent())).toEqual(detail.diagnostics);
  for (const width of [390, 320]) {
    await page.setViewportSize({width, height: 900});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
  await page.locator("#collapse-history").click();
  await expect(page.locator(".history-open")).toBeFocused();
  await expect(page.locator("#history-record")).toBeHidden();
  await page.locator("#load-more-history").click();
  await page.locator('[data-run-id="run-older-page"]').click();
  await expect(page.locator("#history-detail")).toContainText(older.run_id);
  await page.locator("#presets-button").click();
  await page.locator("#history-button").click();
  await expect(page.locator("#history-record")).toBeHidden();
  await page.locator("#load-more-history").click();
  await expect(page.locator("#history-record")).toBeVisible();
  expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(older);
  await page.getByRole("button", {name: "В лабораторию"}).press("Enter");
  await expect(page.getByRole("button", {name: "Лаборатория", exact: true})).toBeFocused();
  expect(posts).toBe(0);
});

test("empty preset library validates the draft before opening the editor", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", (route) => route.fulfill({
    contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null}),
  }));
  await page.route("http://atom-lab.test/v1/atom-lab/runs", (route) => route.fulfill({
    contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null}),
  }));
  await unlockAtom(page, "A05");
  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-list-state")).toContainText("Сохранённых пресетов пока нет");
  await expect(page.locator("#preset-empty")).toBeHidden();
  await expect(page.locator("#preset-editor-form")).toBeHidden();
  await page.locator("#new-preset").click();
  await expect(page.locator("#preset-editor-form")).toBeHidden();
  await expect(page.locator("#input-editor [aria-invalid='true']").first()).toBeFocused();
  await page.locator("#history-button").click();
  await expect(page.locator("#status")).toBeEmpty();
  await page.locator("#workbench-button").click();
  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await page.locator("#new-preset").click();
  await expect(page.locator("#preset-editor-form")).toBeVisible();
  await expect(page.locator("#preset-name")).toBeFocused();
  await expect(page.locator("#preset-source")).toContainText("текущий черновик A05");
  await page.locator("#cancel-preset").click();
  await expect(page.locator("#new-preset")).toBeFocused();
  await page.locator("#history-button").click();
  await expect(page.locator("#history-list-state")).toContainText("Запусков пока нет");
  await expect(page.locator(".history-table")).toBeHidden();
  await expect(page.locator("#history-record")).toBeHidden();
});

test("a failed history run without raw text still links to its schema and can open a preset draft", async ({page}) => {
  const detail = historyDetail();
  detail.status = "failed";
  detail.result = null;
  detail.diagnostics.error_code = "structured_output_validation_failed";
  detail.diagnostics.debug_artifacts = [{
    artifact_id: "debug-without-sample", error_code: detail.diagnostics.error_code,
    raw_output_text: null, truncated: false, redacted: false,
  }];
  await page.route("http://atom-lab.test/v1/atom-lab/runs**", route => {
    if (route.request().url().endsWith(`/runs/${detail.run_id}`)) return route.fulfill({json: detail});
    return route.fulfill({json: {items: [{
      run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: "openai/gpt-supported",
      preset_id: null, preset_version: null, created_at: detail.created_at,
      started_at: detail.started_at, finished_at: detail.finished_at,
    }], next_cursor: null}});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/presets", route => route.fulfill({
    status: 503, json: {error: {code: "atom_lab_unavailable", message: "Сбой чтения списка"}},
  }));
  await unlockAtom(page, "A06");
  await page.locator("#history-button").click();
  await page.locator(".history-open").click();
  await expect(page.locator("#history-contract-message")).toHaveText("Ответ модели не прошёл проверку по контракту атома. Сырой ответ недоступен.");
  await page.locator("#show-history-diagnostics").click();
  await expect(page.locator("#history-diagnostic-raw-link")).toBeHidden();
  await expect(page.locator("#history-raw-sample")).toBeHidden();
  await page.locator("#history-diagnostic-schema-link").click();
  await expect(page.locator("#history-diagnostic-schema summary")).toBeFocused();
  expect(JSON.parse(await page.locator("#history-diagnostic-schema-json").textContent())).toEqual(detail.snapshot.schemas.output.content);

  await page.locator("#save-history-preset").click();
  await expect(page.locator("#preset-list-state")).toContainText("Сбой чтения списка");
  await expect(page.locator("#preset-error")).toBeEmpty();
  await expect(page.locator("#preset-name")).toBeFocused();
  await expect(page.locator("#save-preset")).toBeEnabled();
});

async function presetHistoryJourney(page, promptGroup) {
  page.on("dialog", (dialog) => dialog.accept());
  const versions = [];
  const presetWrites = [];
  let presetListReads = 0;
  let runPosts = 0;
  const detail = historyDetail();
  const promptOrigin = {
    ref: `${promptGroup}.a06.v1`, name: "Исходный промпт", prompt: "Промпт источника",
    group: promptGroup, source_ref: promptGroup === "lab" ? "product.a06.v1" : null,
    source_run_id: null,
  };

  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    const method = request.method();
    expect(request.headers()["x-atom-lab-access-code"]).toBe("secret");
    if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify([
        {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null},
        promptOrigin,
      ])});
      return;
    }
    if (pathname === "/v1/atom-lab/runs" && method === "POST") {
      runPosts += 1;
      expect(request.postDataJSON().prompt_source_ref).toBe(promptOrigin.ref);
      detail.snapshot.input = request.postDataJSON().input;
      detail.snapshot.prompt.content = request.postDataJSON().prompt;
      detail.snapshot.prompt.source_ref = request.postDataJSON().prompt_source_ref;
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        run_id: detail.run_id, scenario_session_id: "session-library", job_id: "job-library", status: "succeeded",
      })});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    if (pathname === "/v1/atom-lab/runs" && method === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        run_id: detail.run_id, status: "succeeded", atom_id: "A06", model_id: "openai/gpt-supported",
        preset_id: null, preset_version: null, created_at: detail.created_at,
        started_at: detail.started_at, finished_at: detail.finished_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && method === "GET") {
      presetListReads += 1;
      if (presetListReads === 1) await new Promise((resolve) => setTimeout(resolve, 150));
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        items: versions.length === 0 ? [] : [{
          preset_id: "preset-library", latest_version: versions.length,
          name: versions.at(-1).name, description: versions.at(-1).description, atom_id: "A06",
          created_at: "2026-09-23T08:01:00Z", updated_at: `2026-09-23T08:0${versions.length}:00Z`,
        }],
        next_cursor: null,
      })});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && method === "POST") {
      const body = request.postDataJSON();
      presetWrites.push(body);
      versions.push({...body, preset_id: "preset-library", version: 1, created_at: "2026-09-23T08:01:00Z"});
      await new Promise((resolve) => setTimeout(resolve, 150));
      await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({preset_id: "preset-library", version: 1, created_at: versions[0].created_at})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets/preset-library/versions" && method === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [...versions].reverse().map((item) => ({
        preset_id: item.preset_id, version: item.version, name: item.name,
        description: item.description, atom_id: item.atom_id, created_at: item.created_at,
      })), next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets/preset-library/versions" && method === "POST") {
      const body = request.postDataJSON();
      presetWrites.push(body);
      const version = versions.length + 1;
      versions.push({...body, preset_id: "preset-library", version, created_at: `2026-09-23T08:0${version}:00Z`});
      await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({preset_id: "preset-library", version, created_at: versions.at(-1).created_at})});
      return;
    }
    const exportMatch = pathname.match(/^\/v1\/atom-lab\/presets\/preset-library\/versions\/(\d+)\/export$/);
    if (exportMatch) {
      const version = Number(exportMatch[1]);
      const stored = versions[version - 1];
      const configuration = Object.fromEntries(Object.entries(stored).filter(
        ([key]) => !["preset_id", "version", "created_at", "base_version"].includes(key),
      ));
      await route.fulfill({contentType: "application/json", body: JSON.stringify({format_version: 1, preset_id: stored.preset_id, version, configuration})});
      return;
    }
    const versionMatch = pathname.match(/^\/v1\/atom-lab\/presets\/preset-library\/versions\/(\d+)$/);
    if (versionMatch) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(versions[Number(versionMatch[1]) - 1])});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await showWorkbench(page);
  await page.locator("#fill-example").click();
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-select").selectOption(promptOrigin.ref);
  await showWorkbench(page);
  await page.locator("#prompt-editor").fill("Промпт версии один");
  await page.locator("#reasoning-effort").selectOption("high");
  await showWorkbench(page);
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("Завершён");

  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-name")).toBeDisabled();
  await expect(page.locator("#preset-state")).toHaveText("Загрузка пресетов…");
  await editPreset(page);
  await expect(page.locator("#preset-name")).toBeEnabled();
  await page.locator("#preset-name").fill("Рабочий пресет");
  await editPreset(page);
  await page.locator("#preset-description").fill("Проверка версий");
  await page.locator("#fixed-fields").getByLabel("context").check();
  await editPreset(page);
  await page.locator("#save-preset").dblclick();
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "true");
  expect(await page.locator("#workspace").evaluate((node) => node.inert)).toBe(true);
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 1");
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#preset-error")).toHaveText("");
  expect(presetWrites).toHaveLength(1);
  expect(presetWrites[0].prompt_source_ref).toBe(promptOrigin.ref);

  await page.locator("#close-presets").click();
  await showWorkbench(page);
  await expect(page.locator("#prompt-select")).toHaveValue(promptOrigin.ref);
  await expect(page.locator("#run-prompt-ref")).toHaveText(promptOrigin.ref);
  await page.locator("#prompt-editor").fill("Промпт версии два");
  await page.locator("#presets-button").click();
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 2");
  await page.locator("#preset-version-select").selectOption("1");
  await expect(page.locator("#preset-prompt")).toHaveText("Промпт версии один");
  await expect(page.locator("#prompt-editor")).toHaveValue("Промпт версии два");
  await page.locator("#export-preset").click();
  await expect(page.locator("#preset-export")).toContainText('"version": 1');
  expect(JSON.parse(await page.locator("#preset-export").textContent()).configuration.prompt_source_ref).toBe(promptOrigin.ref);
  await expect(page.locator("#preset-export-download")).toHaveAttribute("download", "atom-lab-preset-library-v1.json");
  await page.locator("#preset-version-select").selectOption("2");
  await expect(page.locator("#prompt-editor")).toHaveValue("Промпт версии два");
  await expect(page.locator("#preset-export")).toBeHidden();
  await expect(page.locator("#preset-export-download")).toBeHidden();

  expect(versions).toHaveLength(2);
  expect(versions[0].prompt).toBe("Промпт версии один");
  expect(versions[1].prompt).toBe("Промпт версии два");
  expect(presetWrites[0].source_run_id).toBe(detail.run_id);
  expect(versions.every(version => version.prompt_source_ref === promptOrigin.ref)).toBe(true);

  await page.locator("#close-presets").click();
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#restore-history").click();
  await expect(page.locator("#input-editor textarea").first()).toBeFocused();
  await page.locator("#presets-button").click();
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новый");
  await expect(page.locator("#preset-version-select option")).toHaveCount(0);

  await page.reload();
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await expect(page.locator("#history-detail")).toContainText('"validation_attempts": 2');
  await page.locator("#restore-history").click();
  await expect(page.locator("#prompt-editor")).toHaveValue("Промпт версии один");
  await page.locator("#prompt-tab").click();
  await expect(page.locator("#prompt-select")).toHaveValue(promptOrigin.ref);
  await expect(page.locator("#run-prompt-ref")).toHaveText(promptOrigin.ref);
  await expect(page.locator("#draft-state")).toContainText("несохранённые");
  await expect(page.locator("#run-state")).toContainText("Запуск ещё не создан");
  expect(runPosts).toBe(1);
  expect(detail.diagnostics.physical_calls).toBe(1);
  await page.locator("#run-button").click();
  await expect.poll(() => runPosts).toBe(2);
  await expect(page.locator("#run-state")).toContainText("Завершён");

  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();
  await page.locator("#apply-preset").click();
  await page.locator("#prompt-tab").click();
  await expect(page.locator("#prompt-select")).toHaveValue(promptOrigin.ref);
  await page.locator("#run-button").click();
  await expect.poll(() => runPosts).toBe(3);
}

for (const promptGroup of ["product", "lab"]) {
  test(`run, immutable preset versions, export, reload, and history restore preserve ${promptGroup} origin`, async ({page}) => {
    await presetHistoryJourney(page, promptGroup);
  });
}

test("preset conflict disables stale recovery when the latest-version read fails", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  const stored = {
    name: "Конкурентный пресет", description: "Исходная версия", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: "Сохранённый промпт", prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: ["context"],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-conflict", version: 1, created_at: "2026-09-23T09:00:00Z",
  };
  let listReads = 0;
  let versionReads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      listReads += 1;
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, latest_version: listReads === 1 ? 1 : 2, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: "2026-09-23T09:01:00Z",
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions` && request.method() === "GET") {
      versionReads += 1;
      if (versionReads > 2) {
        await route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({
          error: {code: "temporary_failure", message: "Версии недоступны.", field_errors: []},
          request_id: "request-latest-failed",
        })});
        return;
      }
      const version = versionReads === 1 ? 1 : 2;
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, version, name: stored.name, description: stored.description,
        atom_id: stored.atom_id, created_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/2`) {
      await route.fulfill({status: 404, contentType: "application/json", body: JSON.stringify({error: {code: "preset_not_found", message: "Нет версии.", field_errors: []}, request_id: "request-2"})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions` && request.method() === "POST") {
      await route.fulfill({status: 409, contentType: "application/json", body: JSON.stringify({
        error: {code: "preset_version_conflict", message: "Уже есть новая версия.", field_errors: []},
        request_id: "request-conflict",
      })});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();
  await expect(page.locator("#preset-state")).toContainText("Открыта сохранённая версия");
  await editPreset(page);
  await page.locator("#preset-name").fill("Мой локальный черновик");
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await showWorkbench(page);
  await page.locator("#prompt-editor").fill("Локальный промпт не потерять");
  await editPreset(page);
  await page.locator("#save-preset").click();

  await expect(page.locator("#preset-conflict")).toBeVisible();
  await expect(page.locator("#preset-error")).toContainText("Значения черновика сохранены");
  await expect(page.locator("#preset-name")).toHaveValue("Мой локальный черновик");
  await expect(page.locator("#prompt-editor")).toHaveValue("Локальный промпт не потерять");
  await expect(page.locator("#open-latest-preset")).toBeVisible();
  await expect(page.locator("#open-latest-preset")).toBeEnabled();
  await expect(page.locator("#save-as-new-preset")).toBeVisible();
  expect(listReads).toBe(2);

  await page.locator("#open-latest-preset").click();
  await expect(page.locator("#open-latest-preset")).toBeDisabled();
  await expect(page.locator("#preset-error")).toContainText("Не удалось получить актуальную версию: Версии недоступны");
  await expect(page.locator("#preset-name")).toHaveValue("Мой локальный черновик");
  await expect(page.locator("#prompt-editor")).toHaveValue("Локальный промпт не потерять");

  await showWorkbench(page);
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#preset-name")).toHaveValue("");
  await expect(page.locator("#preset-version-select option")).toHaveCount(0);
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новый");
});

test("preset conflict opens the directly resolved latest version from a later library page", async ({page}) => {
  const stored = {
    name: "Конкурентный пресет", description: "Исходная версия", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: "Сохранённый промпт", prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: ["context"],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-later-page", version: 1, created_at: "2026-09-23T09:10:00Z",
  };
  const latest = {
    ...stored, name: "Актуальная серверная версия", prompt: "Серверный промпт",
    version: 2, created_at: "2026-09-23T09:11:00Z",
  };
  const newest = {
    ...latest, name: "Самая новая серверная версия", prompt: "Самый новый промпт",
    version: 3, created_at: "2026-09-23T09:12:00Z",
  };
  const saved = {
    ...newest, name: "Сохранённая поздняя версия",
    version: 4, created_at: "2026-09-23T09:13:00Z",
  };
  let listReads = 0;
  let versionReads = 0;
  let versionPosts = 0;
  let savedCommitted = false;
  let confirmations = 0;
  page.on("dialog", async (dialog) => {
    confirmations += 1;
    await dialog.accept();
  });
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const {pathname} = url;
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      listReads += 1;
      const onLaterPage = url.searchParams.get("cursor") === "older-page";
      const items = onLaterPage ? [{
        preset_id: stored.preset_id, latest_version: 1, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: stored.created_at,
      }] : [{
        preset_id: "preset-first-page", latest_version: 1, name: "Первый пресет",
        description: "Первая страница", atom_id: "A06",
        created_at: "2026-09-23T09:12:00Z", updated_at: "2026-09-23T09:12:00Z",
      }];
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        items, next_cursor: onLaterPage ? null : "older-page",
      })});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions` && request.method() === "GET") {
      versionReads += 1;
      const visible = savedCommitted
        ? saved
        : versionReads === 1 ? stored : versionReads === 2 ? latest : newest;
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: visible.preset_id, version: visible.version, name: visible.name,
        description: visible.description, atom_id: visible.atom_id, created_at: visible.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/2`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(latest)});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/3`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(newest)});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/4`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(saved)});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions` && request.method() === "POST") {
      versionPosts += 1;
      if (versionPosts > 1) {
        savedCommitted = true;
        await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({
          preset_id: stored.preset_id, version: saved.version, created_at: saved.created_at,
        })});
        return;
      }
      await route.fulfill({status: 409, contentType: "application/json", body: JSON.stringify({
        error: {code: "preset_version_conflict", message: "Уже есть новая версия.", field_errors: []},
        request_id: "request-direct-latest",
      })});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#load-more-presets").click();
  await page.getByRole("button", {name: /Конкурентный пресет/}).click();
  await editPreset(page);
  await page.locator("#preset-name").fill("Локальный конфликтующий draft");
  await editPreset(page);
  await page.locator("#save-preset").click();

  await expect(page.locator("#open-latest-preset")).toBeEnabled();
  expect(listReads).toBe(2);
  await page.locator("#open-latest-preset").click();
  await expect(page.locator("#preset-version-select")).toHaveValue("3");
  await expect(page.locator("#preset-name")).toHaveValue(newest.name);
  await expect(page.locator("#preset-prompt")).toHaveText(newest.prompt);
  await expect(page.getByRole("button", {name: /Самая новая серверная версия/})).toContainText("v3");
  expect(confirmations).toBe(1);
  expect(listReads).toBe(2);

  await editPreset(page);
  await page.locator("#preset-name").fill(saved.name);
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 4");
  await expect(page.getByRole("button", {name: new RegExp(saved.name)})).toContainText("v4");
  await expect(page.getByRole("button", {name: new RegExp(saved.name)})).toHaveAttribute("aria-current", "true");
  expect(listReads).toBe(2);
});

test("preset selection commits atomically across stale responses and failed reads", async ({page}) => {
  const stored = (id, name) => ({
    name, description: `${name} description`, atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: `${name} prompt`, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: ["context"],
    example_input: A06.example_input, source_run_id: null,
    preset_id: id, version: 1, created_at: "2026-09-23T09:15:00Z",
  });
  const presets = [stored("preset-a", "Preset A"), stored("preset-b", "Preset B"), stored("preset-c", "Preset C")];
  let savePath = null;
  let versionPageReads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname, searchParams} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: presets.map((item) => ({
        preset_id: item.preset_id, latest_version: 1, name: item.name, description: item.description,
        atom_id: item.atom_id, created_at: item.created_at, updated_at: item.created_at,
      })), next_cursor: null})});
      return;
    }
    const match = pathname.match(/^\/v1\/atom-lab\/presets\/(preset-[abc])\/versions(?:\/(\d+))?$/);
    if (match && request.method() === "GET") {
      const item = presets.find((candidate) => candidate.preset_id === match[1]);
      if (item.preset_id === "preset-b" && searchParams.get("cursor") === "more-b") {
        versionPageReads += 1;
        await new Promise((resolve) => setTimeout(resolve, 200));
        await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
          preset_id: item.preset_id, version: 2, name: item.name, description: item.description,
          atom_id: item.atom_id, created_at: "2026-09-23T09:16:00Z",
        }], next_cursor: null})});
        return;
      }
      if (item.preset_id === "preset-c") {
        await route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({
          error: {code: "temporary_failure", message: "Версия временно недоступна.", field_errors: []},
          request_id: "request-c",
        })});
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, item.preset_id === "preset-a" ? 200 : 20));
      const body = match[2] ? item : {items: [{
        preset_id: item.preset_id, version: 1, name: item.name, description: item.description,
        atom_id: item.atom_id, created_at: item.created_at,
      }], next_cursor: item.preset_id === "preset-b" ? "more-b" : null};
      await route.fulfill({contentType: "application/json", body: JSON.stringify(body)});
      return;
    }
    if (match && request.method() === "POST") {
      savePath = pathname;
      await route.abort();
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  const presetButtons = page.locator("#preset-list button");
  await presetButtons.nth(0).click();
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "true");
  expect(await page.locator("#workspace").evaluate((node) => node.inert)).toBe(true);
  await presetButtons.nth(1).dispatchEvent("click");
  await expect(page.locator("#preset-name")).toHaveValue("Preset B");
  await page.waitForTimeout(250);
  await expect(page.locator("#preset-name")).toHaveValue("Preset B");
  await expect(presetButtons.nth(1)).toHaveAttribute("aria-current", "true");

  await page.locator("#load-more-versions").dispatchEvent("click");
  await page.locator("#load-more-versions").dispatchEvent("click");
  await expect.poll(() => versionPageReads).toBe(1);
  await presetButtons.nth(2).click();
  await expect(page.locator("#preset-error")).toContainText("Версия временно недоступна");
  await expect(page.locator("#preset-name")).toHaveValue("Preset B");
  await expect(presetButtons.nth(1)).toHaveAttribute("aria-current", "true");
  await page.waitForTimeout(250);
  await expect(page.locator("#preset-version-select option")).toHaveCount(1);
  await editPreset(page);
  await page.locator("#preset-name").fill("Preset B edited");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect.poll(() => savePath).toBe("/v1/atom-lab/presets/preset-b/versions");
});

test("preset identity opens the fresh latest version while explicit version selection stays exact", async ({page}) => {
  const stale = {
    name: "Устаревшая версия", description: "v1", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: "Промпт v1", prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-fresh-latest", version: 1, created_at: "2026-09-24T06:10:00Z",
  };
  const latest = {
    ...stale, name: "Свежая версия", description: "v2", prompt: "Промпт v2",
    version: 2, created_at: "2026-09-24T06:11:00Z",
  };
  const detailReads = [];
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stale.preset_id, latest_version: stale.version, name: stale.name,
        description: stale.description, atom_id: stale.atom_id,
        created_at: stale.created_at, updated_at: stale.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stale.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [
        {preset_id: latest.preset_id, version: latest.version, name: latest.name, description: latest.description, atom_id: latest.atom_id, created_at: latest.created_at},
        {preset_id: stale.preset_id, version: stale.version, name: stale.name, description: stale.description, atom_id: stale.atom_id, created_at: stale.created_at},
      ], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stale.preset_id}/versions/1`) {
      detailReads.push(1);
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stale)});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stale.preset_id}/versions/2`) {
      detailReads.push(2);
      await route.fulfill({contentType: "application/json", body: JSON.stringify(latest)});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();
  await expect(page.locator("#preset-name")).toHaveValue(latest.name);
  await expect(page.locator("#preset-version-select")).toHaveValue("2");
  await expect(page.getByRole("button", {name: /Свежая версия/})).toContainText("v2");
  expect(detailReads).toEqual([2]);

  await page.locator("#preset-version-select").selectOption("1");
  await expect(page.locator("#preset-name")).toHaveValue(stale.name);
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  expect(detailReads).toEqual([2, 1]);
});

test("reset prompt warns only when the open preset already has unsaved changes", async ({page}) => {
  const stored = {
    name: "Preset with custom prompt", description: "Reset guard", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: "Сохранённый пользовательский промпт", prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-reset-guard", version: 1, created_at: "2026-09-24T08:00:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const {pathname} = new URL(route.request().url());
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, latest_version: 1, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, version: 1, name: stored.name, description: stored.description,
        atom_id: stored.atom_id, created_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
      return;
    }
    await route.fallback();
  });

  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    dialog.accept();
  });
  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();

  await showWorkbench(page);
  await page.locator("#reset-prompt").click();
  await expect(page.locator("#prompt-editor")).toHaveValue(A06.prompt);
  expect(dialogs).toBe(0);

  await showWorkbench(page);
  await page.locator("#prompt-editor").fill("Ещё одно несохранённое изменение");
  await showWorkbench(page);
  await page.locator("#reset-prompt").click();
  await expect(page.locator("#prompt-editor")).toHaveValue(A06.prompt);
  expect(dialogs).toBe(1);
});

test("opening presets replaces unavailable model placeholders and restores the catalog warning", async ({page}) => {
  let refreshed = false;
  const stored = (presetId, name, modelId, createdAt) => ({
    name, description: "Model selection state", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: modelId, reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: presetId, version: 1, created_at: createdAt,
  });
  const unavailable = stored("preset-missing-model", "Missing model", "openai/gpt-retired", "2026-09-24T08:10:00Z");
  const available = stored("preset-current-model", "Current model", "openai/gpt-supported", "2026-09-24T08:09:00Z");
  const presets = [unavailable, available];
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/models/refresh" && request.method() === "POST") {
      refreshed = true;
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        ...MODEL_CATALOG,
        stale: false,
        refresh_status: "current",
      })});
      return;
    }
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: presets.map((item) => ({
        preset_id: item.preset_id, latest_version: 1, name: item.name,
        description: item.description, atom_id: item.atom_id,
        created_at: item.created_at, updated_at: item.created_at,
      })), next_cursor: null})});
      return;
    }
    const matched = presets.find((item) => pathname.startsWith(`/v1/atom-lab/presets/${item.preset_id}/versions`));
    if (matched && pathname.endsWith("/versions")) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: matched.preset_id, version: 1, name: matched.name,
        description: matched.description, atom_id: matched.atom_id, created_at: matched.created_at,
      }], next_cursor: null})});
      return;
    }
    if (matched && pathname.endsWith("/versions/1")) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(matched)});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06", {models: () => refreshed ? {
    ...MODEL_CATALOG,
    stale: false,
    refresh_status: "current",
  } : MODEL_CATALOG});
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Missing model/}).click();
  await editPreset(page);
  await expect(page.locator("#model-select option", {hasText: "gpt-retired — недоступна"})).toHaveCount(1);
  await expect(page.locator("#model-catalog-warning")).toContainText("Сохранённая модель недоступна");

  await page.getByRole("button", {name: /Missing model/}).click();
  await editPreset(page);
  await expect(page.locator("#model-select option", {hasText: "gpt-retired — недоступна"})).toHaveCount(1);

  await showWorkbench(page);
  await page.locator("#refresh-models").click();
  await expect.poll(() => refreshed).toBe(true);
  await expect(page.locator('#model-select option[value="gpt-retired"]')).toHaveCount(1);
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Current model/}).click();
  await editPreset(page);
  await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
  await expect(page.locator('#model-select option[value="gpt-retired"]')).toHaveCount(0);
  await expect(page.locator("#model-catalog-warning")).toBeEmpty();
});

test("reopening presets refreshes shared identities without dropping loaded later pages", async ({page}) => {
  const summary = (presetId, name, createdAt) => ({
    preset_id: presetId,
    latest_version: 1,
    name,
    description: `${name} description`,
    atom_id: "A06",
    created_at: createdAt,
    updated_at: createdAt,
  });
  const first = summary("preset-first", "Первый пресет", "2026-09-24T09:00:00Z");
  const later = summary("preset-later", "Пресет с поздней страницы", "2026-09-24T08:00:00Z");
  const shared = summary("preset-shared-new", "Новый командный пресет", "2026-09-24T10:00:00Z");
  let firstPageReads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/presets**", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("cursor") === "older-page") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        items: [later], next_cursor: null,
      })});
      return;
    }
    firstPageReads += 1;
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      items: firstPageReads === 1 ? [first] : [shared, first],
      next_cursor: "older-page",
    })});
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#load-more-presets").click();
  await expect(page.locator("#preset-list button")).toHaveCount(2);
  await page.locator("#close-presets").click();

  await page.locator("#presets-button").click();

  await expect(page.getByRole("button", {name: /Новый командный пресет/})).toBeVisible();
  await expect(page.getByRole("button", {name: /Первый пресет/})).toBeVisible();
  await expect(page.getByRole("button", {name: /Пресет с поздней страницы/})).toBeVisible();
  await expect(page.locator("#preset-list button")).toHaveCount(3);
  await expect(page.locator("#load-more-presets")).toBeHidden();
  expect(firstPageReads).toBe(2);
});

test("reopening presets resets pagination when the refreshed first page has no overlap", async ({page}) => {
  const summary = (presetId, name, createdAt) => ({
    preset_id: presetId,
    latest_version: 1,
    name,
    description: `${name} description`,
    atom_id: "A06",
    created_at: createdAt,
    updated_at: createdAt,
  });
  const oldFirst = summary("preset-old-first", "Старый первый", "2026-09-24T08:00:00Z");
  const oldLater = summary("preset-old-later", "Старый поздний", "2026-09-24T07:00:00Z");
  const newFirst = summary("preset-new-first", "Новый первый", "2026-09-24T12:00:00Z");
  const newSecond = summary("preset-new-second", "Новый второй", "2026-09-24T11:00:00Z");
  const newLater = summary("preset-new-later", "Новый со следующей страницы", "2026-09-24T10:00:00Z");
  let firstPageReads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/presets**", async (route) => {
    const cursor = new URL(route.request().url()).searchParams.get("cursor");
    if (cursor === "old-page") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        items: [oldLater], next_cursor: null,
      })});
      return;
    }
    if (cursor === "new-page") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        items: [newLater], next_cursor: null,
      })});
      return;
    }
    firstPageReads += 1;
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      items: firstPageReads === 1 ? [oldFirst] : [newFirst, newSecond],
      next_cursor: firstPageReads === 1 ? "old-page" : "new-page",
    })});
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#load-more-presets").click();
  await expect(page.locator("#preset-list button")).toHaveCount(2);
  await page.locator("#close-presets").click();

  await page.locator("#presets-button").click();

  await expect(page.getByRole("button", {name: /Новый первый/})).toBeVisible();
  await expect(page.getByRole("button", {name: /Новый второй/})).toBeVisible();
  await expect(page.getByRole("button", {name: /Старый первый/})).toHaveCount(0);
  await expect(page.getByRole("button", {name: /Старый поздний/})).toHaveCount(0);
  await expect(page.locator("#load-more-presets")).toBeVisible();

  await page.locator("#load-more-presets").click();
  await expect(page.getByRole("button", {name: /Новый со следующей страницы/})).toBeVisible();
  await expect(page.locator("#preset-list button")).toHaveCount(3);
  await expect(page.locator("#load-more-presets")).toBeHidden();
});

test("stalled preset reads release the locked workspace at the browser deadline", async ({page}) => {
  const stored = {
    name: "Deadline preset", description: "Read timeout", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-deadline", version: 1, created_at: "2026-09-23T09:30:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
      preset_id: stored.preset_id, latest_version: 1, name: stored.name,
      description: stored.description, atom_id: stored.atom_id,
      created_at: stored.created_at, updated_at: stored.created_at,
    }], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.clock.install();
  await page.evaluate(() => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (url, options = {}) => {
      if (String(url).includes("/presets/preset-deadline/versions")) {
        return new Promise((resolve, reject) => {
          options.signal.addEventListener("abort", () => reject(new DOMException("Timed out", "AbortError")));
        });
      }
      return originalFetch(url, options);
    };
  });

  await page.locator("#preset-list button").click();
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "true");
  await page.clock.fastForward(30_000);
  await expect(page.locator("#preset-error")).toContainText("Время ожидания ответа истекло");
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
  expect(await page.locator("#workspace").evaluate((node) => node.inert)).toBe(false);
});

test("stalled preset writes report an ambiguous outcome and block blind duplicate saves", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await openNewPresetFromExample(page);
  await page.locator("#preset-name").fill("Неизвестный результат");
  await page.clock.install();
  await page.evaluate(() => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (url, options = {}) => {
      if (String(url).endsWith("/v1/atom-lab/presets") && options.method === "POST") {
        return new Promise((resolve, reject) => {
          options.signal.addEventListener("abort", () => reject(new DOMException("Timed out", "AbortError")));
        });
      }
      return originalFetch(url, options);
    };
  });

  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "true");
  await page.clock.fastForward(30_000);
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#save-preset")).toBeDisabled();
  await expect(page.locator("#save-as-new-preset")).toBeDisabled();
  await expect(page.locator("#new-preset")).toBeDisabled();
  await page.locator("#new-preset").dispatchEvent("click");
  await expect(page.locator("#preset-name")).toHaveValue("Неизвестный результат");
  await expect(page.locator("#save-preset")).toBeDisabled();
});

test("transport loss after a committed preset write blocks blind duplicate saves", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await openNewPresetFromExample(page);
  await page.locator("#preset-name").fill("Потерянный ответ");
  await page.evaluate(() => {
    const originalFetch = globalThis.fetch;
    globalThis.__presetTransportState = {committed: false, posts: 0};
    globalThis.fetch = (url, options = {}) => {
      if (String(url).endsWith("/v1/atom-lab/presets") && options.method === "POST") {
        globalThis.__presetTransportState.posts += 1;
        globalThis.__presetTransportState.committed = true;
        return Promise.reject(new TypeError("Failed to fetch after commit"));
      }
      return originalFetch(url, options);
    };
  });

  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await expect(page.locator("#save-preset")).toBeDisabled();
  await expect(page.locator("#save-as-new-preset")).toBeDisabled();
  await expect.poll(() => page.evaluate(() => globalThis.__presetTransportState)).toEqual({
    committed: true,
    posts: 1,
  });
});

test("ambiguous preset create stays blocked after reopening and opening another identity", async ({page}) => {
  const stored = {
    name: "Другой пресет", description: "Не связан с неизвестным create", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-unrelated", version: 1, created_at: "2026-09-24T09:30:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, latest_version: 1, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, version: 1, name: stored.name, description: stored.description,
        atom_id: stored.atom_id, created_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1/export`) {
      const configuration = Object.fromEntries(Object.entries(stored).filter(
        ([key]) => !["preset_id", "version", "created_at"].includes(key),
      ));
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        format_version: 1,
        preset_id: stored.preset_id,
        version: stored.version,
        configuration,
      })});
      return;
    }
    await route.fallback();
  });

  page.on("dialog", (dialog) => dialog.accept());
  await unlockAtom(page, "A06");
  await openNewPresetFromExample(page);
  await page.locator("#preset-name").fill("Create с неизвестным результатом");
  await page.evaluate(() => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = (url, options = {}) => {
      if (String(url).endsWith("/v1/atom-lab/presets") && options.method === "POST") {
        return Promise.reject(new TypeError("Response lost after create"));
      }
      return originalFetch(url, options);
    };
  });

  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await page.locator("#close-presets").click();
  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await page.getByRole("button", {name: /Другой пресет/}).click();

  await expect(page.locator("#preset-name")).toHaveValue(stored.name);
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await expect(page.locator("#new-preset")).toBeDisabled();
  await expect(page.locator("#save-preset")).toBeDisabled();
  await expect(page.locator("#save-as-new-preset")).toBeDisabled();
  await page.locator("#export-preset").click();
  await expect(page.locator("#preset-export")).toContainText(`"preset_id": "${stored.preset_id}"`);
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
});

test("ambiguous version write with no new server version unlocks retry and keeps the draft", async ({page}) => {
  const first = {
    name: "Пресет для recovery", description: "До обновления", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-update-no-commit", version: 1, created_at: "2026-09-25T07:00:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id,
        created_at: first.created_at, updated_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      await route.abort("connectionreset");
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id, created_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(first)});
      return;
    }
    await route.fallback();
  });

  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    dialog.accept();
  });
  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет для recovery/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Локальный черновик");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");

  await page.getByRole("button", {name: /Пресет для recovery/}).click();

  expect(dialogs).toBe(0);
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator("#preset-description")).toHaveValue("Локальный черновик");
  await expect(page.locator("#preset-error")).toContainText("можно повторить Save");
  await expect(page.locator("#save-preset")).toBeEnabled();
});

test("ambiguous version recovery opens the preset normally after its owner session is replaced", async ({page}) => {
  const first = {
    name: "Пресет после смены session", description: "Сохранённое описание", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-replaced-session", version: 1, created_at: "2026-09-25T07:05:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id,
        created_at: first.created_at, updated_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      await route.abort("connectionreset");
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id, created_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(first)});
      return;
    }
    await route.fallback();
  });

  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    dialog.accept();
  });
  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет после смены session/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Неизвестно сохранённый draft");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");

  await showWorkbench(page);
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет после смены session/}).click();

  await editPreset(page);
  expect(dialogs).toBe(1);
  await expect(page.locator("#atom-title")).toContainText("A06");
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator("#preset-description")).toHaveValue("Сохранённое описание");
  await expect(page.locator("#preset-error")).toHaveText("");
  await expect(page.locator("#save-preset")).toBeEnabled();
});

test("history preset draft does not inherit ambiguous recovery ownership", async ({page}) => {
  const first = {
    name: "Исходный recovery preset", description: "Сохранённое описание", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-history-replacement", version: 1, created_at: "2026-09-25T07:06:00Z",
  };
  const detail = historyDetail({runId: "run-replaces-preset-draft"});
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: "openai/gpt-supported",
        preset_id: null, preset_version: null, created_at: detail.created_at,
        started_at: detail.started_at, finished_at: detail.finished_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id,
        created_at: first.created_at, updated_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      await route.abort("connectionreset");
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id, created_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(first)});
      return;
    }
    await route.fallback();
  });

  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    dialog.accept();
  });
  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Исходный recovery preset/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Неизвестно сохранённый исходный draft");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");

  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#save-history-preset").click();
  await expect(page.locator("#preset-name")).toHaveValue(`Запуск ${detail.run_id}`);
  expect(dialogs).toBe(1);

  await page.getByRole("button", {name: /Исходный recovery preset/}).click();

  expect(dialogs).toBe(2);
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator("#preset-name")).toHaveValue(first.name);
  await expect(page.locator("#preset-description")).toHaveValue(first.description);
  await expect(page.locator("#preset-error")).toHaveText("");
});

test("history-derived ambiguous recovery does not preserve a replaced owner session", async ({page}) => {
  const detail = historyDetail({runId: "run-history-recovery"});
  let savedBody = null;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: "openai/gpt-supported",
        preset_id: null, preset_version: null, created_at: detail.created_at,
        started_at: detail.started_at, finished_at: detail.finished_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "POST") {
      savedBody = request.postDataJSON();
      await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({
        preset_id: "history-recovery-preset", version: 1, created_at: "2026-09-25T07:07:00Z",
      })});
      return;
    }
    if (pathname === "/v1/atom-lab/presets") {
      const items = savedBody ? [{
        preset_id: "history-recovery-preset", latest_version: 1, name: savedBody.name,
        description: savedBody.description, atom_id: savedBody.atom_id,
        created_at: "2026-09-25T07:07:00Z", updated_at: "2026-09-25T07:07:00Z",
      }] : [];
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items, next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets/history-recovery-preset/versions"
      && request.method() === "POST") {
      await route.abort("connectionreset");
      return;
    }
    if (pathname === "/v1/atom-lab/presets/history-recovery-preset/versions") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: "history-recovery-preset", version: 1, name: savedBody.name,
        description: savedBody.description, atom_id: savedBody.atom_id,
        created_at: "2026-09-25T07:07:00Z",
      }], next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets/history-recovery-preset/versions/1") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        ...savedBody, preset_id: "history-recovery-preset", version: 1,
        created_at: "2026-09-25T07:07:00Z",
      })});
      return;
    }
    await route.fallback();
  });

  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    dialog.accept();
  });
  await unlockAtom(page, "A05");
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#save-history-preset").click();
  await editPreset(page);
  await page.locator("#preset-name").fill("History recovery preset");
  await editPreset(page);
  await page.locator("#preset-description").fill("Сохранённая history версия");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-version-select")).toHaveValue("1");

  await editPreset(page);
  await page.locator("#preset-description").fill("Неизвестно сохранённое history обновление");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await showWorkbench(page);
  await page.getByRole("button", {name: /A11/}).click();
  await expect(page.locator("#atom-title")).toContainText("A11");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /History recovery preset/}).click();

  await editPreset(page);
  expect(dialogs).toBe(1);
  await expect(page.locator("#atom-title")).toContainText("A06");
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator("#preset-description")).toHaveValue("Сохранённая history версия");
  await expect(page.locator("#preset-error")).toHaveText("");
});

test("successful preset readback materializes its version outside the latest page", async ({page}) => {
  const first = {
    name: "Пресет successful readback", description: "До обновления", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-success-readback", version: 1, created_at: "2026-09-25T07:00:00Z",
  };
  const competingVersion = (version) => ({
    ...first,
    description: `Конкурентная версия ${version}`,
    version,
    created_at: `2026-09-25T07:${String(version).padStart(2, "0")}:00Z`,
  });
  const newerVersions = Array.from({length: 20}, (_, index) => competingVersion(22 - index));
  const versionWriteBodies = [];
  let savedVersion = null;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname, searchParams} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id,
        created_at: first.created_at, updated_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      const body = request.postDataJSON();
      versionWriteBodies.push(body);
      if (versionWriteBodies.length === 1) {
        savedVersion = {
          ...body, preset_id: first.preset_id, version: 2, created_at: "2026-09-25T07:02:00Z",
        };
        delete savedVersion.base_version;
        await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({
          preset_id: first.preset_id, version: 2, created_at: savedVersion.created_at,
        })});
      } else {
        await route.fulfill({status: 409, contentType: "application/json", body: JSON.stringify({
          error: {code: "preset_version_conflict", message: "Конкурентное обновление", field_errors: []},
        })});
      }
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      const loadingOlder = searchParams.get("cursor") === "older";
      const items = savedVersion
        ? (loadingOlder ? [savedVersion, first] : newerVersions)
        : [first];
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: items.map((item) => ({
        preset_id: item.preset_id, version: item.version, name: item.name,
        description: item.description, atom_id: item.atom_id, created_at: item.created_at,
      })), next_cursor: savedVersion && !loadingOlder ? "older" : null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions/2/export`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        format_version: 1,
        preset_id: first.preset_id,
        version: 2,
        configuration: Object.fromEntries(Object.entries(savedVersion).filter(
          ([key]) => !["preset_id", "version", "created_at"].includes(key),
        )),
      })});
      return;
    }
    const requestedVersion = Number(pathname.split("/").at(-1));
    if (Number.isInteger(requestedVersion)) {
      const version = requestedVersion === 1
        ? first
        : requestedVersion === 2
          ? savedVersion
          : competingVersion(requestedVersion);
      await route.fulfill({contentType: "application/json", body: JSON.stringify(version)});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет successful readback/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Успешно сохранённая v2");
  await editPreset(page);
  await page.locator("#save-preset").click();

  await expect(page.locator("#preset-version-select")).toHaveValue("2");
  await expect(page.locator('#preset-version-select option[value="2"]')).toHaveCount(1);
  await expect(page.getByRole("button", {name: /Пресет successful readback/})).toContainText("v22");
  await page.locator("#export-preset").click();
  await expect(page.locator("#preset-export")).toContainText('"version": 2');
  await page.locator("#load-more-versions").click();
  await expect(page.locator('#preset-version-select option[value="1"]')).toHaveCount(1);
  await expect(page.locator("#preset-version-select")).toHaveValue("2");
  await expect(page.locator('#preset-version-select option[value="2"]')).toHaveCount(1);
  await editPreset(page);
  await page.locator("#preset-description").fill("Следующий черновик");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect.poll(() => versionWriteBodies).toHaveLength(2);
  expect(versionWriteBodies[1].base_version).toBe(2);
});

test("ambiguous recovery keeps its base selected when the expected-version read fails", async ({page}) => {
  const first = {
    name: "Пресет recovery read failure", description: "До обновления", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-recovery-read-failure", version: 1, created_at: "2026-09-25T07:00:00Z",
  };
  const competingVersion = (version) => ({
    ...first,
    description: `Конкурентная версия ${version}`,
    version,
    created_at: `2026-09-25T08:${String(version).padStart(2, "0")}:00Z`,
  });
  const latestVersions = Array.from({length: 20}, (_, index) => competingVersion(22 - index));
  let ambiguousWrite = false;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: 1, name: first.name,
        description: first.description, atom_id: first.atom_id,
        created_at: first.created_at, updated_at: first.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      ambiguousWrite = true;
      await route.abort("connectionreset");
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      const items = ambiguousWrite ? latestVersions : [first];
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: items.map((item) => ({
        preset_id: item.preset_id, version: item.version, name: item.name,
        description: item.description, atom_id: item.atom_id, created_at: item.created_at,
      })), next_cursor: ambiguousWrite ? "older" : null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions/1/export`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        format_version: 1,
        preset_id: first.preset_id,
        version: 1,
        configuration: Object.fromEntries(Object.entries(first).filter(
          ([key]) => !["preset_id", "version", "created_at"].includes(key),
        )),
      })});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions/2`) {
      await route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({
        error: {code: "temporary_failure", message: "Ожидаемая версия временно недоступна.", field_errors: []},
        request_id: "request-expected-version-failed",
      })});
      return;
    }
    const requestedVersion = Number(pathname.split("/").at(-1));
    if (Number.isInteger(requestedVersion)) {
      const version = requestedVersion === 1 ? first : competingVersion(requestedVersion);
      await route.fulfill({contentType: "application/json", body: JSON.stringify(version)});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет recovery read failure/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Локальный черновик после неизвестного Save");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");

  await page.getByRole("button", {name: /Пресет recovery read failure/}).click();

  await expect(page.locator("#preset-error")).toContainText("Ожидаемая версия временно недоступна");
  await expect(page.locator('#preset-version-select option[value="1"]')).toHaveCount(1);
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator("#preset-description")).toHaveValue("Локальный черновик после неизвестного Save");
  await page.locator("#export-preset").click();
  await expect(page.locator("#preset-export")).toContainText('"version": 1');
});

test("exact committed recovery refreshes the editor draft version", async ({page}) => {
  const first = {
    name: "Пресет draft state", description: "До обновления", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-draft-state", version: 1, created_at: "2026-09-25T07:00:00Z",
  };
  let committed = null;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      const latest = committed ?? first;
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: latest.version, name: latest.name,
        description: latest.description, atom_id: latest.atom_id,
        created_at: first.created_at, updated_at: latest.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      committed = {
        ...request.postDataJSON(), preset_id: first.preset_id, version: 2,
        created_at: "2026-09-25T07:02:00Z",
      };
      delete committed.base_version;
      await route.abort("connectionreset");
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      const items = committed ? [committed, first] : [first];
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: items.map((item) => ({
        preset_id: item.preset_id, version: item.version, name: item.name,
        description: item.description, atom_id: item.atom_id, created_at: item.created_at,
      })), next_cursor: null})});
      return;
    }
    const requestedVersion = Number(pathname.split("/").at(-1));
    if (Number.isInteger(requestedVersion)) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(
        requestedVersion === 2 ? committed : first,
      )});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет draft state/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Сохранённая v2");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");

  await page.getByRole("button", {name: /Пресет draft state/}).click();

  await expect(page.locator("#preset-version-select")).toHaveValue("2");
  await expect(page.locator("#draft-state")).toHaveText("Открыта сохранённая версия 2.");
});

test("ambiguous version write reconciles an exact committed version without discarding the draft", async ({page}) => {
  const first = {
    name: "Пресет exact recovery", description: "До обновления", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-update-exact", version: 1, created_at: "2026-09-25T07:10:00Z",
  };
  const competingVersion = (version) => ({
    ...first,
    description: `Конкурентная версия ${version}`,
    version,
    created_at: `2026-09-25T07:${String(version + 10).padStart(2, "0")}:00Z`,
  });
  const newerVersions = Array.from({length: 20}, (_, index) => competingVersion(30 - index));
  let committed = null;
  const versionWriteBodies = [];
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname, searchParams} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      const latest = committed ? newerVersions[0] : first;
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: latest.version, name: latest.name,
        description: latest.description, atom_id: latest.atom_id,
        created_at: first.created_at, updated_at: latest.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      const body = request.postDataJSON();
      versionWriteBodies.push(body);
      committed = {
        ...body,
        schema_refs: {output: body.schema_refs.output, input: body.schema_refs.input},
        example_input: {objective: body.example_input.objective, context: body.example_input.context},
        preset_id: first.preset_id,
        version: 2,
        created_at: "2026-09-25T07:11:00Z",
      };
      delete committed.base_version;
      await route.abort("connectionreset");
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      const loadingOlder = searchParams.get("cursor") === "older";
      const olderVersions = Array.from({length: 10}, (_, index) => {
        const version = 10 - index;
        if (version === 2) return committed;
        return version === 1 ? first : competingVersion(version);
      });
      const items = committed ? (loadingOlder ? olderVersions : newerVersions) : [first];
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: items.map((item) => ({
        preset_id: item.preset_id, version: item.version, name: item.name,
        description: item.description, atom_id: item.atom_id, created_at: item.created_at,
      })), next_cursor: committed && !loadingOlder ? "older" : null})});
      return;
    }
    const requestedVersion = Number(pathname.split("/").at(-1));
    const version = requestedVersion === 2
      ? committed
      : requestedVersion === 1
        ? first
        : competingVersion(requestedVersion);
    if (pathname.endsWith(`/presets/${first.preset_id}/versions/${version?.version}`)) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(version)});
      return;
    }
    await route.fallback();
  });

  let dialogs = 0;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    dialog.accept();
  });
  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет exact recovery/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Exact committed draft");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");

  await editPreset(page);
  await page.locator("#preset-name").fill("Локальное имя после ошибки");
  await editPreset(page);
  await page.locator("#preset-description").fill("Поздний локальный черновик");
  await importJson(page, {...A06.example_input, objective: "Поздняя локальная цель"});
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await showWorkbench(page);
  await page.locator("#prompt-editor").fill("Поздний локальный промпт");

  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет exact recovery/}).click();

  expect(dialogs).toBe(0);
  await expect(page.locator("#preset-version-select")).toHaveValue("2");
  await expect(page.locator('#preset-version-select option[value="2"]')).toHaveCount(1);
  await expect(page.locator("#preset-name")).toHaveValue("Локальное имя после ошибки");
  await expect(page.locator("#preset-description")).toHaveValue("Поздний локальный черновик");
  await expect(page.locator("#prompt-editor")).toHaveValue("Поздний локальный промпт");
  await showWorkbench(page);
  await page.locator("#input-tab").click();
  await showWorkbench(page);
  await page.locator("#json-mode").click();
  await expect(page.locator("#json-editor")).toHaveValue(/Поздняя локальная цель/);
  await expect(page.locator("#preset-state")).toContainText("несохранённый черновик");
  await expect(page.locator("#preset-error")).toHaveText("");
  await expect(page.locator("#save-preset")).toBeEnabled();
  await page.locator("#presets-button").click();
  await page.locator("#load-more-versions").click();
  await expect(page.locator("#preset-version-select")).toHaveValue("2");
  await expect(page.locator('#preset-version-select option[value="2"]')).toHaveCount(1);
  await expect.poll(() => page.locator("#preset-version-select option").evaluateAll(
    (options) => options.map((option) => option.value),
  )).toEqual(Array.from({length: 30}, (_, index) => String(30 - index)));
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect.poll(() => versionWriteBodies).toHaveLength(2);
  expect(versionWriteBodies[1].base_version).toBe(2);
});

test("ambiguous version write surfaces a concurrent conflict without discarding the draft", async ({page}) => {
  const first = {
    name: "Пресет conflict recovery", description: "До обновления", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-update-conflict", version: 1, created_at: "2026-09-25T07:20:00Z",
  };
  const competingVersion = (version) => ({
    ...first,
    description: `Конкурентная версия ${version}`,
    version,
    created_at: `2026-09-25T08:${String(version).padStart(2, "0")}:00Z`,
  });
  const latestVersions = Array.from({length: 20}, (_, index) => competingVersion(22 - index));
  let conflictExists = false;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname, searchParams} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets") {
      const latest = conflictExists ? latestVersions[0] : first;
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: first.preset_id, latest_version: latest.version, name: latest.name,
        description: latest.description, atom_id: latest.atom_id,
        created_at: first.created_at, updated_at: latest.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`
      && request.method() === "POST") {
      conflictExists = true;
      await route.abort("connectionreset");
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions`) {
      const loadingOlder = searchParams.get("cursor") === "older";
      const items = conflictExists ? (loadingOlder ? [competingVersion(2), first] : latestVersions) : [first];
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: items.map((item) => ({
        preset_id: item.preset_id, version: item.version, name: item.name,
        description: item.description, atom_id: item.atom_id, created_at: item.created_at,
      })), next_cursor: conflictExists && !loadingOlder ? "older" : null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${first.preset_id}/versions/1/export`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        format_version: 1,
        preset_id: first.preset_id,
        version: 1,
        configuration: Object.fromEntries(Object.entries(first).filter(
          ([key]) => !["preset_id", "version", "created_at"].includes(key),
        )),
      })});
      return;
    }
    const requestedVersion = Number(pathname.split("/").at(-1));
    if (Number.isInteger(requestedVersion)) {
      const version = requestedVersion === 1 ? first : competingVersion(requestedVersion);
      await route.fulfill({contentType: "application/json", body: JSON.stringify(version)});
      return;
    }
    await route.fallback();
  });

  let dialogs = 0;
  let acceptDialogs = false;
  page.on("dialog", (dialog) => {
    dialogs += 1;
    if (acceptDialogs) dialog.accept();
    else dialog.dismiss();
  });
  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.getByRole("button", {name: /Пресет conflict recovery/}).click();
  await editPreset(page);
  await page.locator("#preset-description").fill("Локальный конфликтующий draft");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");

  await page.getByRole("button", {name: /Пресет conflict recovery/}).click();

  expect(dialogs).toBe(0);
  await expect(page.locator("#preset-error")).toContainText("Конфликт сохранения");
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator('#preset-version-select option[value="1"]')).toHaveCount(1);
  await expect(page.locator("#preset-description")).toHaveValue("Локальный конфликтующий draft");
  await expect(page.locator("#open-latest-preset")).toBeEnabled();

  await page.locator("#load-more-versions").click();
  await expect(page.locator('#preset-version-select option[value="2"]')).toHaveCount(1);
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator('#preset-version-select option[value="1"]')).toHaveCount(1);
  await page.locator("#export-preset").click();
  await expect(page.locator("#preset-export")).toContainText('"version": 1');

  await page.locator("#open-latest-preset").click();
  expect(dialogs).toBe(1);
  await expect(page.locator("#preset-version-select")).toHaveValue("1");
  await expect(page.locator("#preset-description")).toHaveValue("Локальный конфликтующий draft");

  acceptDialogs = true;
  await page.locator("#open-latest-preset").click();
  expect(dialogs).toBe(2);
  await expect(page.locator("#preset-version-select")).toHaveValue("22");
  await expect(page.locator("#preset-description")).toHaveValue("Конкурентная версия 22");
});

test("gateway failure after a committed preset write blocks blind duplicate saves", async ({page}) => {
  let committed = false;
  let posts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    if (route.request().method() === "POST") {
      posts += 1;
      committed = true;
      await route.fulfill({status: 502, contentType: "application/json", body: JSON.stringify({
        error: {
          code: "atom_lab_catalog_unavailable",
          message: "Bad Gateway after an uncertain upstream outcome.",
          field_errors: [],
        },
        request_id: "request-gateway-1",
      })});
      return;
    }
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await submitNewPresetFromExample(page, "Commit за gateway");

  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await expect(page.locator("#save-preset")).toBeDisabled();
  await expect(page.locator("#save-as-new-preset")).toBeDisabled();
  expect({committed, posts}).toEqual({committed: true, posts: 1});
});

test("structured pre-write preset failure keeps the draft retryable", async ({page}) => {
  let posts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    if (route.request().method() === "POST") {
      posts += 1;
      await route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({
        error: {
          code: "atom_lab_catalog_unavailable",
          message: "Каталог Atom Lab недоступен.",
          field_errors: [],
        },
        request_id: `request-pre-write-${posts}`,
      })});
      return;
    }
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await submitNewPresetFromExample(page, "Retryable pre-write draft");

  await expect(page.locator("#preset-error")).toContainText("Каталог Atom Lab недоступен");
  await expect(page.locator("#preset-name")).toHaveValue("Retryable pre-write draft");
  await expect(page.locator("#save-preset")).toBeEnabled();
  await expect(page.locator("#new-preset")).toBeEnabled();
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect.poll(() => posts).toBe(2);
});

for (const responseCase of [
  {
    name: "malformed successful preset response", presetName: "Повреждённый ответ", body: "{",
  },
  {
    name: "invalid successful preset response", presetName: "Неполный успешный ответ",
    body: JSON.stringify({preset_id: "preset-committed-with-invalid-envelope", version: 1}),
  },
  {
    name: "new preset response with a non-initial version", presetName: "Неверная первая версия",
    body: JSON.stringify({
      preset_id: "preset-wrong-create-version",
      version: 2,
      created_at: "2026-09-24T12:00:00Z",
    }),
  },
]) {
  test(`${responseCase.name} blocks blind duplicate saves`, async ({page}) => {
    let posts = 0;
    await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
      if (route.request().method() === "POST") {
        posts += 1;
        await route.fulfill({status: 201, contentType: "application/json", body: responseCase.body});
        return;
      }
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
    });

    await unlockAtom(page, "A06");
    await submitNewPresetFromExample(page, responseCase.presetName);

    await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
    await expect(page.locator("#save-preset")).toBeDisabled();
    await expect(page.locator("#save-as-new-preset")).toBeDisabled();
    expect(posts).toBe(1);
  });
}

for (const responseCase of [
  {name: "another identity", presetId: "preset-other", version: 2},
  {name: "a non-consecutive version", presetId: "preset-update-contract", version: 3},
]) {
  test(`preset version response for ${responseCase.name} blocks blind duplicate saves`, async ({page}) => {
    const stored = {
      name: "Версия до обновления", description: "Проверка write receipt", atom_id: "A06",
      base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
      prompt: A06.prompt, prompt_ref: A06.prompt_ref,
      model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
      example_input: A06.example_input, source_run_id: null,
      preset_id: "preset-update-contract", version: 1, created_at: "2026-09-24T11:00:00Z",
    };
    let posts = 0;
    await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
      const request = route.request();
      const {pathname} = new URL(request.url());
      if (pathname === "/v1/atom-lab/presets") {
        await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
          preset_id: stored.preset_id, latest_version: 1, name: stored.name,
          description: stored.description, atom_id: stored.atom_id,
          created_at: stored.created_at, updated_at: stored.created_at,
        }], next_cursor: null})});
        return;
      }
      if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions` && request.method() === "POST") {
        posts += 1;
        await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({
          preset_id: responseCase.presetId,
          version: responseCase.version,
          created_at: "2026-09-24T12:00:00Z",
        })});
        return;
      }
      if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
        await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
          preset_id: stored.preset_id, version: 1, name: stored.name, description: stored.description,
          atom_id: stored.atom_id, created_at: stored.created_at,
        }], next_cursor: null})});
        return;
      }
      if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
        await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
        return;
      }
      await route.fallback();
    });

    await unlockAtom(page, "A06");
    await page.locator("#presets-button").click();
    await page.locator("#preset-list button").click();
    await editPreset(page);
    await page.locator("#preset-description").fill(`Изменение: ${responseCase.name}`);
    await editPreset(page);
    await page.locator("#save-preset").click();

    await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
    await expect(page.locator("#save-preset")).toBeDisabled();
    await expect(page.locator("#save-as-new-preset")).toBeDisabled();
    expect(posts).toBe(1);
  });
}

test("preset save exposes backend field errors without losing the draft", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({status: 422, contentType: "application/json", body: JSON.stringify({
        error: {
          code: "preset_contract_invalid",
          message: "Конфигурация пресета не соответствует контракту атома.",
          field_errors: [
            {path: "name", message: "Имя не может состоять только из пробелов."},
            {path: "fixed_fields.0", message: "Значение отсутствует в example_input."},
            {path: "prompt", message: "Укажите текст промпта."},
          ],
        },
        request_id: "request-preset-fields",
      })});
      return;
    }
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await openNewPresetFromExample(page);
  await page.locator("#preset-name").fill("   ");
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-editor").fill("   ");
  await editPreset(page);
  await page.locator("#save-preset").click();

  await expect(page.locator("#presets-panel")).toBeVisible();
  await expect(page.locator("#preset-error")).toBeVisible();
  await expect(page.locator("#preset-error")).toContainText("name: Имя не может состоять только из пробелов.");
  await expect(page.locator("#preset-error")).toContainText("fixed_fields.0: Значение отсутствует в example_input.");
  await expect(page.locator("#preset-error")).toContainText("prompt: Укажите текст промпта.");
  await expect(page.locator("#preset-name")).toHaveValue("   ");
  await expect(page.locator("#save-preset")).toBeEnabled();
  await showWorkbench(page);
  await expect(page.locator("#prompt-editor")).toBeVisible();
  await expect(page.locator("#prompt-editor")).toHaveValue("   ");
});

for (const [path, compatible] of [["preset", false], ["history", false], ["preset", true], ["history", true]]) {
  for (const available of [false, true]) {
    test(`${path} ${compatible ? "compatible restore" : "adaptation"} ${available ? "retains an available" : "detaches an obsolete"} ${compatible ? "product" : "Lab"} prompt origin after checking current options`, async ({page}) => {
      page.on("dialog", (dialog) => dialog.accept());
      const promptSourceRef = compatible ? "product.prompt.v1" : "atom_lab_prompt_historical";
      const stored = {
        name: "Исторический пресет", description: "Старый контракт", atom_id: "A06",
        base_action_config_id: !compatible && available ? "config.a06.retired" : A06.base_action_config_id,
        schema_refs: A06.schema_refs, prompt: "Исторический текст промпта", prompt_ref: A06.prompt_ref,
        prompt_source_ref: promptSourceRef, model_id: "openai/gpt-supported", reasoning_effort: "high",
        fixed_fields: ["context"], example_input: A06.example_input, source_run_id: null,
        preset_id: "preset-historical-origin", version: 1, created_at: "2026-09-23T09:30:00Z",
      };
      const detail = historyDetail({runId: "run-historical-origin", prompt: stored.prompt});
      detail.snapshot.action.config_id = stored.base_action_config_id;
      detail.snapshot.prompt.source_ref = promptSourceRef;
      const currentAtom = compatible || available ? A06 : {
        ...A06, schema_refs: {
          input: {...A06.schema_refs.input, version: 2},
          output: {...A06.schema_refs.output, version: 2},
        },
      };
      const summary = {
        preset_id: stored.preset_id, latest_version: 1, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: stored.created_at,
      };
      let promptReads = 0;
      let releasePrompts;
      const promptGate = new Promise((resolve) => { releasePrompts = resolve; });
      let runBody = null;
      let presetBody = null;
      await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
        const request = route.request();
        const {pathname} = new URL(request.url());
        if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
          promptReads += 1;
          await promptGate;
          if (!available && promptReads === 1) {
            await route.fulfill(path === "preset"
              ? {status: 503, json: {error: {code: "prompts_unavailable", message: "Не удалось проверить источник"}}}
              : {json: []});
          } else {
            await route.fulfill({json: [
              {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null},
              ...(available ? [{ref: promptSourceRef, name: "Сохранённый", prompt: stored.prompt, group: compatible ? "product" : "lab", source_ref: A06.prompt_ref, source_run_id: null}] : []),
              ...(compatible && !available ? [{ref: "product.prompt.v2", name: "Новый продуктовый", prompt: "Новый текст v2", group: "product", source_ref: A06.prompt_ref, source_run_id: null}] : []),
            ]});
          }
          return;
        }
        if (pathname === "/v1/atom-lab/presets") {
          if (request.method() === "POST") {
            presetBody = request.postDataJSON();
            await route.abort();
          } else await route.fulfill({json: {items: [summary], next_cursor: null}});
          return;
        }
        if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
          if (request.method() === "POST") {
            presetBody = request.postDataJSON();
            await route.abort();
          } else await route.fulfill({json: {items: [{...summary, version: 1}], next_cursor: null}});
          return;
        }
        if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
          await route.fulfill({json: stored});
          return;
        }
        if (pathname === "/v1/atom-lab/runs") {
          if (request.method() === "POST") {
            runBody = request.postDataJSON();
            await route.abort();
          } else await route.fulfill({json: {items: [{
            run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: stored.model_id,
            preset_id: null, preset_version: null, created_at: detail.created_at,
            started_at: detail.started_at, finished_at: detail.finished_at,
          }], next_cursor: null}});
          return;
        }
        if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
          await route.fulfill({json: detail});
          return;
        }
        await route.fallback();
      });

      await openLab(page);
      await page.route("http://atom-lab.test/v1/atom-lab/atoms", (route) => route.fulfill({
        json: catalog().map((atom) => atom.atom_id === "A06" ? currentAtom : atom),
      }));
      await page.locator("#access-code").fill("secret");
      await page.locator("#access-form button").click();
      await page.getByRole("button", {name: /A06/}).click();
      if (available) {
        await page.locator("#prompt-tab").click();
        await expect.poll(() => promptReads).toBe(1);
      }
      await page.locator(`#${path === "preset" ? "presets" : "history"}-button`).click();
      await page.locator(path === "preset" ? "#preset-list button" : "#history-list .history-open").click();
      await page.locator(path === "preset" ? compatible ? "#apply-preset" : "#adapt-preset" : "#restore-history").click();
      await expect.poll(() => promptReads).toBe(available ? 2 : 1);
      await expect(page.locator("#prompt-editor")).toHaveValue(stored.prompt);
      await expect(page.locator("#run-button")).toBeDisabled();
      await editPreset(page);
      await expect(page.locator("#save-preset")).toBeDisabled();
      await expect(page.locator("#preset-state")).toContainText("Повторить загрузку можно во вкладке «Промпт»");
      await page.locator("#run-button").dispatchEvent("click");
      await page.locator("#save-preset").dispatchEvent("click");
      expect(runBody).toBeNull();
      expect(presetBody).toBeNull();
      await showWorkbench(page);
      await page.locator("#prompt-tab").click();
      const editedPrompt = `${stored.prompt}. Правка во время загрузки`;
      await page.locator("#prompt-editor").fill(editedPrompt);
      await expect(page.locator("#reset-prompt")).toBeDisabled();
      await page.locator("#reset-prompt").dispatchEvent("click");
      await expect(page.locator("#prompt-editor")).toHaveValue(editedPrompt);
      releasePrompts();
      if (!available) {
        await expect(page.locator("#retry-prompts")).toBeVisible();
        await expect(page.locator("#reset-prompt")).toBeDisabled();
        await expect(page.locator("#run-button")).toBeDisabled();
        await editPreset(page);
        await expect(page.locator("#save-preset")).toBeDisabled();
        await showWorkbench(page);
        await page.locator("#retry-prompts").click();
        await expect(page.locator("#prompt-origin")).toContainText("Исторический источник недоступен");
      } else await expect(page.locator("#prompt-select")).toHaveValue(promptSourceRef);
      await expect(page.locator("#prompt-editor")).toHaveValue(editedPrompt);
      await expect(page.locator("#reset-prompt")).toBeEnabled();
      await page.locator("#reset-prompt").click();
      await expect(page.locator("#prompt-editor")).toHaveValue(available ? stored.prompt : currentAtom.prompt);
      await expect(page.locator("#prompt-select")).toHaveValue(available ? promptSourceRef : currentAtom.prompt_ref);
      await page.locator("#prompt-editor").fill(editedPrompt);
      await expect(page.locator("#run-button")).toBeEnabled();
      await page.locator("#run-button").click();
      await expect.poll(() => runBody).not.toBeNull();
      expect(runBody.prompt).toBe(editedPrompt);
      expect(runBody.prompt_source_ref ?? null).toBe(available ? promptSourceRef : null);
      await editPreset(page);
      await page.locator("#preset-name").fill("Адаптированный пресет");
      await page.locator("#save-preset").click();
      await expect.poll(() => presetBody).not.toBeNull();
      expect(presetBody.prompt).toBe(editedPrompt);
      expect(presetBody.prompt_source_ref).toBe(available ? promptSourceRef : null);
      expect(presetBody.schema_refs).toEqual(currentAtom.schema_refs);
      await page.locator(`#${path === "preset" ? "presets" : "history"}-button`).click();
      await page.locator(path === "preset" ? "#preset-list button" : "#history-list .history-open").click();
      await expect.poll(async () => {
        const text = await page.locator(path === "preset" ? "#preset-readonly" : "#history-detail").textContent();
        return text ? JSON.parse(text) : null;
      }).toEqual(path === "preset" ? stored : detail);
    });
  }
}

for (const available of [false, true]) {
  test(`direct history preset ${available ? "preserves a valid" : "detaches a retired"} product origin without changing another atom's draft`, async ({page}) => {
    const confirmations = [];
    page.on("dialog", (dialog) => { confirmations.push(dialog.message()); return dialog.accept(); });
    const promptSourceRef = "product.prompt.v1";
    const detail = historyDetail({runId: "run-direct-preset", prompt: "Точный исторический текст"});
    detail.snapshot.prompt.source_ref = promptSourceRef;
    let promptReads = 0;
    const promptRequests = [];
    let releasePrompts;
    const promptGate = new Promise((resolve) => { releasePrompts = resolve; });
    let presetBody = null;
    await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
      const request = route.request();
      const {pathname} = new URL(request.url());
      if (pathname.endsWith("/prompts")) {
        promptRequests.push(pathname);
        if (pathname.includes("/A05/")) {
          await route.fulfill({json: [
            {ref: A05.prompt_ref, name: "Платформенный", prompt: A05.prompt, group: "platform", source_ref: null, source_run_id: null},
            {ref: "product.a05.v1", name: "Продуктовый A05", prompt: "Текст A05", group: "product", source_ref: A05.prompt_ref, source_run_id: null},
          ]});
          return;
        }
        promptReads += 1;
        await promptGate;
        if (promptReads === 2) {
          await route.fulfill({status: 503, json: {error: {code: "prompts_unavailable", message: "Источник временно недоступен"}}});
        } else if (promptReads === 3) {
          await route.fulfill({json: []});
        } else await route.fulfill({json: [
          {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null},
          ...(available ? [{ref: promptSourceRef, name: "Продуктовый", prompt: "Текущий текст", group: "product", source_ref: A06.prompt_ref, source_run_id: null}] : []),
          ...(!available ? [{ref: "product.prompt.v2", name: "Новый продуктовый", prompt: "Новый текст v2", group: "product", source_ref: A06.prompt_ref, source_run_id: null}] : []),
        ]});
        return;
      }
      if (pathname === "/v1/atom-lab/runs") {
        await route.fulfill({json: {items: [{
          run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: "openai/gpt-supported",
          preset_id: null, preset_version: null, created_at: detail.created_at,
          started_at: detail.started_at, finished_at: detail.finished_at,
        }], next_cursor: null}});
        return;
      }
      if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
        await route.fulfill({json: detail});
        return;
      }
      if (pathname === "/v1/atom-lab/presets") {
        if (request.method() === "POST") {
          presetBody = request.postDataJSON();
          await route.abort();
        } else await route.fulfill({json: {items: [], next_cursor: null}});
        return;
      }
      await route.fallback();
    });

    await unlockAtom(page, "A05");
    await page.locator("#fill-example").click();
    await page.locator("#prompt-tab").click();
    await page.locator("#prompt-select").selectOption("product.a05.v1");
    const currentPrompt = "Несохранённый промпт другого атома";
    await page.locator("#prompt-editor").fill(currentPrompt);
    await page.locator("#history-button").click();
    await page.locator("#history-list .history-open").click();
    await page.locator("#save-history-preset").click();
    await expect.poll(() => promptReads).toBe(1);
    expect(confirmations).toEqual([]);
    await expect(page.locator("#save-history-preset")).toBeDisabled();
    await expect(page.locator("#history-panel")).toBeVisible();
    expect(presetBody).toBeNull();
    await showWorkbench(page);
    const abandonedCheck = page.waitForResponse("**/atoms/A06/prompts");
    releasePrompts();
    await abandonedCheck;
    await expect(page.locator("#presets-panel")).toBeHidden();
    await expect(page.locator("#request-response")).toBeVisible();
    await page.locator("#history-button").click();
    await expect(page.locator("#save-history-preset")).toBeEnabled();
    await page.locator("#save-history-preset").click();
    await expect(page.locator("#history-error")).toContainText("Источник временно недоступен");
    await expect(page.locator("#save-history-preset")).toBeEnabled();
    await page.locator("#save-history-preset").click();
    await expect(page.locator("#history-error")).toContainText("Список промптов вернул некорректный ответ");
    await page.locator("#save-history-preset").click();
    await expect(page.locator("#presets-panel")).toBeVisible();
    await expect(page.locator("#preset-name")).toBeFocused();
    expect(confirmations).toEqual([]);
    await expect(page.locator("#preset-prompt")).toHaveText(detail.snapshot.prompt.content);
    if (!available) await expect(page.locator("#preset-state")).toContainText("Исторический источник недоступен");
    await page.locator("#preset-name").fill("Из истории другого атома");
    await page.locator("#save-preset").click();
    await expect.poll(() => presetBody).not.toBeNull();
    expect(presetBody.atom_id).toBe("A06");
    expect(presetBody.prompt).toBe(detail.snapshot.prompt.content);
    expect(presetBody.prompt_source_ref).toBe(available ? promptSourceRef : null);
    expect(presetBody.source_run_id).toBe(detail.run_id);
    expect(presetBody.example_input).toEqual(detail.snapshot.input);
    expect(promptRequests.filter((pathname) => pathname.includes("/A06/"))).toHaveLength(4);
    await showWorkbench(page);
    await expect(page.locator("#atom-title")).toContainText("A05");
    await expect(page.locator("#prompt-editor")).toHaveValue(currentPrompt);
    await expect(page.locator("#prompt-select")).toHaveValue("product.a05.v1");
    await page.locator("#input-tab").click();
    await page.locator("#json-mode").click();
    await expect(page.locator("#json-editor")).toHaveValue(JSON.stringify(A05.example_input, null, 2));
    await page.locator("#history-button").click();
    await page.locator("#history-list .history-open").click();
    expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(detail);
  });
}

test("historical preset provenance stays read-only until explicit adaptation", async ({page}) => {
  const stored = {
    name: "Исторический пресет", description: "Старый контракт", atom_id: "A06",
    base_action_config_id: "config.a06.retired", schema_refs: A06.schema_refs,
    prompt: "Исторический промпт", prompt_ref: "prompt.a06.retired",
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: ["context"],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-retired", version: 1, created_at: "2026-09-23T09:30:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, latest_version: 1, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, version: 1, name: stored.name, description: stored.description,
        atom_id: stored.atom_id, created_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  const originalPrompt = await page.locator("#prompt-editor").inputValue();
  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();

  await expect(page.locator("#preset-compatibility")).toBeVisible();
  await expect(page.locator("#preset-readonly")).toContainText("config.a06.retired");
  await expect(page.locator("#preset-readonly")).toContainText("prompt.a06.retired");
  await expect(page.locator("#preset-name")).toBeDisabled();
  await expect(page.locator("#save-preset")).toBeDisabled();
  await expect(page.locator("#prompt-editor")).toHaveValue(originalPrompt);

  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await showWorkbench(page);
  await page.locator("#prompt-editor").fill("Текущий несохранённый draft");
  await page.locator("#presets-button").click();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.locator("#adapt-preset").click();
  await expect(page.locator("#preset-compatibility")).toBeVisible();
  await expect(page.locator("#prompt-editor")).toHaveValue("Текущий несохранённый draft");
  page.once("dialog", (dialog) => dialog.accept());
  await page.locator("#adapt-preset").click();
  await expect(page.locator("#preset-compatibility")).toBeHidden();
  await expect(page.locator("#preset-name")).toBeEnabled();
  await expect(page.locator("#preset-name")).toHaveValue(stored.name);
  await expect(page.locator("#prompt-editor")).toHaveValue(stored.prompt);
  await expect(page.locator("#preset-state")).toContainText("Есть несохранённый черновик");
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новый");
});

test("successful preset write keeps its identity when readback fails", async ({page}) => {
  let created = false;
  let createPosts = 0;
  let versionPosts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: created ? [{
        preset_id: "preset-readback", latest_version: 1, name: "Readback preset",
        description: "Readback failure", atom_id: "A06",
        created_at: "2026-09-23T09:45:00Z", updated_at: "2026-09-23T09:45:00Z",
      }] : [], next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "POST") {
      createPosts += 1;
      created = true;
      await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({
        preset_id: "preset-readback", version: 1, created_at: "2026-09-23T09:45:00Z",
      })});
      return;
    }
    if (pathname.startsWith("/v1/atom-lab/presets/preset-readback/versions") && request.method() === "GET") {
      await route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({
        error: {code: "temporary_failure", message: "Readback недоступен.", field_errors: []},
        request_id: "request-readback",
      })});
      return;
    }
    if (pathname === "/v1/atom-lab/presets/preset-readback/versions" && request.method() === "POST") {
      versionPosts += 1;
      await route.abort();
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await openNewPresetFromExample(page);
  await page.locator("#preset-name").fill("Readback preset");
  await editPreset(page);
  await page.locator("#preset-description").fill("Readback failure");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-state")).toContainText("повторное чтение не удалось");
  await expect(page.locator("#preset-error")).toContainText("Сохранение завершено");
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новую версию");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect.poll(() => versionPosts).toBe(1);
  expect(createPosts).toBe(1);
});

for (const existing of [false, true]) {
  test(`${existing ? "versioned" : "new"} preset save reveals the invalid editor and preserves the draft through correction`, async ({page}) => {
    const versions = existing ? [{
      preset_id: "preset-validation", version: 1, created_at: "2026-09-24T06:00:00Z",
      name: "Исходный пресет", description: "Сохранённая версия", atom_id: "A06",
      base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
      prompt: A06.prompt, prompt_ref: A06.prompt_ref, model_id: "openai/gpt-supported",
      reasoning_effort: "high", fixed_fields: [], example_input: A06.example_input,
      source_run_id: null,
    }] : [];
    const writes = [];
    await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
      const request = route.request();
      const {pathname} = new URL(request.url());
      if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
        const latest = versions.at(-1);
        await route.fulfill({contentType: "application/json", body: JSON.stringify({items: latest ? [{
          ...latest, latest_version: latest.version, updated_at: latest.created_at,
        }] : [], next_cursor: null})});
        return;
      }
      if (request.method() === "POST" && pathname.startsWith("/v1/atom-lab/presets")) {
        writes.push({pathname, body: request.postDataJSON()});
        const stored = {
          ...writes.at(-1).body, preset_id: "preset-validation", version: versions.length + 1,
          created_at: "2026-09-24T07:00:00Z",
        };
        versions.push(stored);
        await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify(stored)});
        return;
      }
      if (pathname === "/v1/atom-lab/presets/preset-validation/versions") {
        await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [...versions].reverse(), next_cursor: null})});
        return;
      }
      if (pathname.startsWith("/v1/atom-lab/presets/preset-validation/versions/")) {
        await route.fulfill({contentType: "application/json", body: JSON.stringify(versions[Number(pathname.split("/").at(-1)) - 1])});
        return;
      }
      await route.fallback();
    });

    await unlockAtom(page, "A06");
    await page.locator("#presets-button").click();
    if (existing) await page.locator("#preset-list button").click();
    else {
      await showWorkbench(page);
      await page.locator("#fill-example").click();
    }
    await editPreset(page);
    await page.locator("#preset-name").fill("Невалидный черновик");
    await page.locator("#preset-description").fill("Метаданные для исправления");
    await page.locator("#fixed-fields").getByLabel("Контекст (context)", {exact: true}).check();
    await showWorkbench(page);
    await page.locator("#json-mode").click();
    await page.locator("#json-editor").fill('{"context":');
    await editPreset(page);
    await page.locator("#save-preset").click();

    await expect(page.locator("#request-response")).toBeVisible();
    await expect(page.locator("#presets-panel")).toBeHidden();
    await expect(page.locator("#status")).toBeVisible();
    await expect(page.locator("#status")).toContainText("Исправьте входные данные");
    await expect(page.locator("#json-editor")).toBeVisible();
    await expect(page.locator("#json-editor")).toBeFocused();
    await expect(page.locator("#json-editor")).toHaveValue('{"context":');
    await expect(page.locator("#validation-errors")).toBeVisible();
    await page.locator("#validation-errors").getByRole("button", {name: /JSON/}).click();
    await expect(page.locator("#json-editor")).toBeFocused();
    expect(writes).toHaveLength(0);

    const corrected = {...A06.example_input, objective: "Исправленная цель"};
    await page.locator("#json-editor").fill(JSON.stringify(corrected));
    await expect(page.locator("#validation-errors")).toBeEmpty();
    await editPreset(page);
    await expect(page.locator("#preset-name")).toHaveValue("Невалидный черновик");
    await expect(page.locator("#preset-description")).toHaveValue("Метаданные для исправления");
    await expect(page.locator("#fixed-fields").getByLabel("Контекст (context)", {exact: true})).toBeChecked();
    if (existing) await expect(page.locator("#preset-version-select")).toHaveValue("1");
    await page.locator("#save-preset").click();
    await expect(page.locator("#preset-state")).toContainText(`Сохранена неизменяемая версия ${existing ? 2 : 1}`);
    expect(writes).toEqual([{
      pathname: existing ? "/v1/atom-lab/presets/preset-validation/versions" : "/v1/atom-lab/presets",
      body: expect.objectContaining({
        name: "Невалидный черновик", description: "Метаданные для исправления",
        example_input: corrected, fixed_fields: ["context"],
        ...(existing ? {base_version: 1} : {}),
      }),
    }]);

    await showWorkbench(page);
    await page.locator("#json-mode").click();
    await page.locator("#json-editor").fill("{}");
    await expect(page.locator("#validation-errors")).toBeVisible();
    await expect(page.locator("#validation-errors li")).toHaveCount(2);
    await expect(page.locator("#validation-errors")).toContainText("Обязательное поле");
  });
}

test("an untouched empty draft stays quiet but returning edited input to empty keeps validation visible", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  await unlockAtom(page, "A06");
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await page.locator("#json-mode").click();
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await page.locator("#json-editor").fill(JSON.stringify(A06.example_input));
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await page.locator("#json-editor").fill("{}");
  await expect(page.locator("#validation-errors li")).toHaveCount(2);
  await expect(page.locator("#validation-errors")).toContainText("context");
  await expect(page.locator("#validation-errors")).toContainText("objective");
  await page.locator("#validation-errors").getByRole("button", {name: /context/}).click();
  await expect(page.locator("#json-editor")).toBeFocused();
  await page.locator("#form-mode").click();
  await expect(page.locator("#validation-errors li")).toHaveCount(2);
  await page.locator("#fill-example").click();
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#validation-errors")).toBeEmpty();
});

test("creating a preset from the prompt tab reveals untouched required input", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", (route) => route.fulfill({
    contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null}),
  }));
  await unlockAtom(page, "A06");
  await page.locator("#prompt-tab").click();
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await editPreset(page);
  await expect(page.locator("#request-response")).toBeVisible();
  await expect(page.locator("#input-editor")).toBeVisible();
  await expect(page.locator("#validation-errors li")).toHaveCount(2);
  await expect(page.locator("#input-editor [aria-invalid='true']").first()).toBeFocused();
  await page.locator("#fill-example").click();
  await expect(page.locator("#validation-errors")).toBeEmpty();
  await editPreset(page);
  await expect(page.locator("#preset-name")).toBeFocused();
  await expect(page.locator("#preset-name")).toHaveValue("");
});

test("fixed fields are selectable only while their values exist in the preset input", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await openNewPresetFromExample(page);
  await expect(page.locator("#fixed-fields").getByLabel("context")).toBeEnabled();
  await expect(page.locator("#fixed-fields").getByLabel("audience")).toBeDisabled();

  await showWorkbench(page);
  await page.locator("#json-mode").click();
  await showWorkbench(page);
  await page.locator("#json-editor").fill(JSON.stringify({...A06.example_input, audience: "Команда"}));
  await expect(page.locator("#fixed-fields").getByLabel("audience")).toBeEnabled();
  await editPreset(page);
  await page.locator("#fixed-fields").getByLabel("audience").check();
  await page.locator("#close-presets").click();
  await showWorkbench(page);
  await page.locator("#json-editor").fill(JSON.stringify(A06.example_input));
  await page.locator("#presets-button").click();
  await expect(page.locator("#fixed-fields").getByLabel("audience")).toBeDisabled();
  await expect(page.locator("#fixed-fields").getByLabel("audience")).not.toBeChecked();
  await expect(page.locator("#preset-state")).not.toHaveText("Загрузка пресетов…");
});

test("fill example protects preset-only fixed-field changes", async ({page}) => {
  const stored = {
    name: "Preset-only draft", description: "Dirty fixed field", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: {...A06.example_input, audience: "Команда"}, source_run_id: null,
    preset_id: "preset-fixed-dirty", version: 1, created_at: "2026-09-24T06:00:00Z",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, latest_version: stored.version, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, version: stored.version, name: stored.name,
        description: stored.description, atom_id: stored.atom_id, created_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
      return;
    }
    await route.fallback();
  });
  let confirmations = 0;
  page.on("dialog", async (dialog) => {
    confirmations += 1;
    await dialog.dismiss();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();
  await editPreset(page);
  await page.locator("#fixed-fields").getByLabel("audience").check();
  await expect(page.locator("#preset-state")).toContainText("Есть несохранённый черновик");

  await showWorkbench(page);
  await page.locator("#fill-example").click();

  expect(confirmations).toBe(1);
  await expect(page.locator("#fixed-fields").getByLabel("audience")).toBeChecked();
  await showWorkbench(page);
  await page.locator("#json-mode").click();
  await expect(page.locator("#json-editor")).toHaveValue(/"audience": "Команда"/);
});

test("accepted run immediately marks an open saved preset as a changed draft", async ({page}) => {
  const stored = {
    name: "Run provenance", description: "До запуска", atom_id: "A06",
    base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
    prompt: A06.prompt, prompt_ref: A06.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A06.example_input, source_run_id: null,
    preset_id: "preset-run-state", version: 1, created_at: "2026-09-23T09:50:00Z",
  };
  const detail = historyDetail({runId: "run-new-provenance", prompt: stored.prompt});
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, latest_version: 1, name: stored.name,
        description: stored.description, atom_id: stored.atom_id,
        created_at: stored.created_at, updated_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, version: 1, name: stored.name,
        description: stored.description, atom_id: stored.atom_id, created_at: stored.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(stored)});
      return;
    }
    if (pathname === "/v1/atom-lab/runs" && request.method() === "POST") {
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        run_id: detail.run_id, scenario_session_id: detail.runtime_ids.scenario_session_id,
        job_id: detail.runtime_ids.job_id, status: "succeeded",
      })});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();
  await editPreset(page);
  await expect(page.locator("#preset-state")).toContainText("Открыта сохранённая версия");
  await page.locator("#close-presets").click();
  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-state")).toContainText("Открыта сохранённая версия");
  await showWorkbench(page);
  await page.locator("#run-button").click();
  await expect(page.locator("#preset-state")).toContainText("Есть несохранённый черновик");
});

for (const draftState of ["clean", "dirty"]) {
  test(`cancelling a new preset preserves the ${draftState} editor binding until a committed save`, async ({page}) => {
    page.on("dialog", dialog => dialog.accept());
    const stored = {
      name: "Исходный пресет", description: "Версия 1", atom_id: "A06",
      base_action_config_id: A06.base_action_config_id, schema_refs: A06.schema_refs,
      prompt: A06.prompt, prompt_ref: A06.prompt_ref, prompt_source_ref: null,
      model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: ["context"],
      example_input: A06.example_input, source_run_id: "run-source-preset",
      preset_id: "preset-cancel-origin", version: 1, created_at: "2026-11-07T08:00:00Z",
    };
    const writes = [];
    const runBodies = [];
    let created = null;
    await page.route("http://atom-lab.test/v1/atom-lab/presets**", async route => {
      const {pathname} = new URL(route.request().url());
      if (route.request().method() === "POST") {
        writes.push(route.request().postDataJSON());
        created = {...writes.at(-1), preset_id: "preset-new-committed", version: 1, created_at: stored.created_at};
        await route.fulfill({status: 201, json: {preset_id: created.preset_id, version: 1, created_at: created.created_at}});
        return;
      }
      const version = pathname.includes("preset-new-committed") ? created : stored;
      const summary = item => ({
        preset_id: item.preset_id, name: item.name, description: item.description,
        atom_id: item.atom_id, created_at: item.created_at,
      });
      if (pathname === "/v1/atom-lab/presets") await route.fulfill({json: {
        items: [stored, ...(created ? [created] : [])].map(item => ({...summary(item), latest_version: 1, updated_at: item.created_at})),
        next_cursor: null,
      }});
      else if (pathname.endsWith("/versions")) await route.fulfill({json: {items: [{...summary(version), version: 1}], next_cursor: null}});
      else await route.fulfill({json: version});
    });
    await page.route("http://atom-lab.test/v1/atom-lab/runs", async route => {
      runBodies.push(route.request().postDataJSON());
      await route.fulfill({status: 422, json: {error: {code: "test_rejected", message: "Запуск не принят", field_errors: []}, request_id: "test-cancel"}});
    });
    await unlockAtom(page, "A06");
    await page.locator("#presets-button").click();
    await page.locator("#preset-list button").click();
    await page.locator("#apply-preset").click();
    const input = draftState === "dirty" ? {...stored.example_input, objective: "Изменённая цель"} : stored.example_input;
    if (draftState === "dirty") await importJson(page, input);
    const draftMessage = await page.locator("#draft-state").textContent();
    await page.locator("#presets-button").click();
    await page.locator("#new-preset").click();
    await page.locator("#cancel-preset").click();
    await showWorkbench(page);
    await expect(page.locator("#draft-state")).toHaveText(draftMessage);
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toContainText("test_rejected");
    const expectedBody = {
      atom_id: stored.atom_id, input, prompt: stored.prompt,
      prompt_source_ref: stored.prompt_ref,
      model_id: stored.model_id, reasoning_effort: stored.reasoning_effort,
      preset_ref: {preset_id: stored.preset_id, version: stored.version},
      expected_contract: expectedAtomContract(A06),
    };
    expect(runBodies).toEqual([expectedBody]);
    expect(writes).toEqual([]);

    await page.locator("#presets-button").click();
    await page.locator("#preset-list button").click();
    await editPreset(page);
    await expect(page.locator("#fixed-fields").getByLabel("context")).toBeChecked();
    await expect(page.locator("#preset-config-metadata")).toContainText(stored.source_run_id);
    if (draftState === "dirty") await expect(page.locator("#preset-input-json")).toContainText(input.objective);
    await page.locator("#new-preset").click();
    await page.locator("#preset-name").fill("Новый сохранённый пресет");
    await page.locator("#fixed-fields").getByLabel("context").check();
    await page.locator("#save-preset").click();
    await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 1");
    expect(writes).toHaveLength(1);
    expect(writes[0]).toMatchObject({example_input: input, source_run_id: stored.source_run_id, fixed_fields: ["context"]});
    await showWorkbench(page);
    await page.locator("#run-button").click();
    await expect(page.locator("#run-state")).toContainText("test_rejected");
    expect(runBodies).toEqual([expectedBody, {...expectedBody, preset_ref: {preset_id: created.preset_id, version: 1}}]);
  });
}

test("new preset metadata participates in discard protection and atom changes clear its association", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });
  await unlockAtom(page, "A06");
  await openNewPresetFromExample(page);
  await page.locator("#preset-name").fill("Несохранённый пресет");
  await editPreset(page);
  await page.locator("#preset-description").fill("Не потерять metadata");
  await page.locator("#fixed-fields").getByLabel("context").check();

  page.once("dialog", (dialog) => dialog.dismiss());
  await showWorkbench(page);
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A06");
  await expect(page.locator("#preset-name")).toHaveValue("Несохранённый пресет");

  page.once("dialog", (dialog) => dialog.accept());
  await showWorkbench(page);
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#preset-name")).toHaveValue("");
  await expect(page.locator("#preset-version-select option")).toHaveCount(0);
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новый");
  await expect(page.locator("#preset-state")).toHaveText("");

  await openNewPresetFromExample(page);
  await expect(page.locator("#preset-name")).toBeEnabled();
  await expect(page.locator("#fixed-fields").getByLabel("issues")).toBeVisible();
  await editPreset(page);
  await page.locator("#preset-name").fill("Новый после смены атома");
  page.once("dialog", (dialog) => dialog.dismiss());
  await showWorkbench(page);
  await page.getByRole("button", {name: /A06/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#preset-name")).toHaveValue("Новый после смены атома");
});

test("history list identifies presets that share the same version number", async ({page}) => {
  const runSummary = (runId, presetId, createdAt) => ({
    run_id: runId,
    status: "succeeded",
    atom_id: "A06",
    model_id: "openai/gpt-supported",
    preset_id: presetId,
    preset_version: 1,
    created_at: createdAt,
    started_at: createdAt,
    finished_at: createdAt,
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [
      runSummary("run-preset-a", "preset-a", "2026-09-25T06:00:00Z"),
      runSummary("run-preset-b", "preset-b", "2026-09-25T05:00:00Z"),
    ], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await page.locator("#history-button").click();

  const historyButtons = page.locator("#history-list .history-open");
  await expect(historyButtons).toHaveCount(2);
  const rows = page.locator("#history-list > tr[data-selected]");
  await expect(rows.nth(0)).toContainText("preset-a · v1");
  await expect(rows.nth(1)).toContainText("preset-b · v1");
});

test("open history model availability follows delayed catalog load and refresh", async ({page}) => {
  const detail = historyDetail({runId: "run-model-availability"});
  let releaseInitialModels;
  const initialModels = new Promise((resolve) => {
    releaseInitialModels = resolve;
  });
  let modelReads = 0;
  let refreshRequested = false;
  const withoutHistoryModel = {
    ...MODEL_CATALOG,
    items: MODEL_CATALOG.items.filter(({model_id: modelId}) => modelId !== "gpt-supported"),
    stale: false,
    refresh_status: "current",
  };
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        run_id: detail.run_id,
        status: detail.status,
        atom_id: detail.snapshot.atom_id,
        model_id: detail.snapshot.provider.model_id,
        preset_id: null,
        preset_version: null,
        created_at: detail.created_at,
        started_at: detail.started_at,
        finished_at: detail.finished_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    if (pathname === "/v1/atom-lab/models/refresh" && request.method() === "POST") {
      refreshRequested = true;
      await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({
        ...withoutHistoryModel,
        items: undefined,
      })});
      return;
    }
    await route.fallback();
  });

  await openLab(page, {models: () => {
    modelReads += 1;
    return modelReads === 1 ? initialModels : withoutHistoryModel;
  }});
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await expect(page.locator("#history-button")).toBeEnabled();
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await expect(page.locator("#history-warning")).toContainText("Историческая модель недоступна");

  releaseInitialModels(MODEL_CATALOG);
  await expect.poll(() => modelReads).toBe(1);
  await expect(page.locator("#history-warning")).toHaveText("");

  await showWorkbench(page);
  await page.locator("#refresh-models").click();
  await expect.poll(() => refreshRequested).toBe(true);
  await expect.poll(() => modelReads).toBe(2);
  await expect(page.locator("#history-warning")).toContainText("Историческая модель недоступна");
});

for (const direction of ["input", "output"]) {
  for (const change of ["unchanged", "required", "properties", "reordered", "missing", "malformed", "boolean-number", "version"]) {
    test(`history frozen schema ${direction} ${change} keeps only compatible trial proof`, async ({page}) => {
      page.on("dialog", dialog => dialog.accept());
      const input = {...A06.example_input, context: {nested: {active: false, budget: 0}}, audience: "Сохранённая аудитория"};
      const detail = structuredClone(historyDetail({input, prompt: "Ручной исторический текст"}));
      const current = structuredClone(A06);
      const compatible = change === "unchanged" || change === "reordered";
      const content = current[`${direction}_schema`];
      if (change === "required" || change === "properties") {
        content.properties = {...content.properties, new_field: {type: "string"}};
        if (change === "required") content.required = [...(content.required ?? []), "new_field"];
      } else if (change === "reordered") {
        current[`${direction}_schema`] = Object.fromEntries(Object.entries(content).reverse());
        if (content.properties) current[`${direction}_schema`].properties = Object.fromEntries(Object.entries(content.properties).reverse());
      } else if (change === "missing") delete detail.snapshot.schemas[direction].content;
      else if (change === "malformed") detail.snapshot.schemas[direction].content = [];
      else if (change === "boolean-number") {
        detail.snapshot.schemas[direction].content.$defs = {trial_constant: {const: true}};
        content.$defs = {trial_constant: {const: 1}};
      } else if (change === "version") current.schema_refs[direction].version += 1;
      const original = structuredClone(detail);
      const writes = [];
      let runPosts = 0;
      await page.route("http://atom-lab.test/v1/atom-lab/**", async route => {
        const request = route.request();
        const pathname = new URL(request.url()).pathname;
        if (pathname === "/v1/atom-lab/runs" && request.method() === "GET") {
          await route.fulfill({json: {items: [{run_id: detail.run_id, status: detail.status,
            atom_id: "A06", model_id: detail.snapshot.provider.model_id, preset_id: null, preset_version: null,
            created_at: detail.created_at, started_at: detail.started_at, finished_at: detail.finished_at}], next_cursor: null}});
        } else if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) await route.fulfill({json: detail});
        else if (pathname === "/v1/atom-lab/runs") {
          runPosts += 1;
          await route.abort();
        } else if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
          if (request.method() === "POST") {
            const body = request.postDataJSON();
            writes.push(body);
            await route.fulfill({status: 201, json: {ref: `saved.${writes.length}`, name: body.name,
              prompt: body.prompt, group: "lab", source_ref: body.source_ref, source_run_id: body.source_run_id}});
          } else await route.fulfill({json: [{ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt,
            group: "platform", source_ref: null, source_run_id: null}]});
        } else await route.fallback();
      });
      await openLab(page);
      await page.route("http://atom-lab.test/v1/atom-lab/atoms", route => route.fulfill({
        json: catalog().map(atom => atom.atom_id === "A06" ? current : atom),
      }));
      await page.locator("#access-code").fill("secret");
      await page.locator("#access-form button").click();
      await page.getByRole("button", {name: /A06/}).click();
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      await expect(page.locator("#restore-history")).toHaveText(compatible
        ? "Восстановить запрос в лаборатории" : "Адаптировать к текущему контракту");
      await expect(page.locator("#save-history-preset"))[compatible ? "toBeEnabled" : "toBeDisabled"]();
      await page.locator("#restore-history").click();
      await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
      await expect(page.locator("#reasoning-effort")).toHaveValue("high");
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-editor")).toHaveValue(detail.snapshot.prompt.content);
      if (compatible) await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      else await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
      await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill("Из снимка");
      await page.locator("#save-prompt").click();
      await expect.poll(() => writes.length).toBe(1);
      expect(writes[0]).toEqual({name: "Из снимка", prompt: detail.snapshot.prompt.content,
        source_ref: current.prompt_ref, source_run_id: compatible ? detail.run_id : null});
      await page.locator("#input-tab").click();
      await page.locator("#json-mode").click();
      expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual(input);
      const editedInput = {...input, audience: "Ручная правка после восстановления"};
      await page.locator("#json-editor").fill(JSON.stringify(editedInput));
      await page.locator("#reasoning-effort").selectOption("low");
      await page.locator("#prompt-tab").click();
      await page.locator("#prompt-editor").fill("Ручная правка промпта после восстановления");
      await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill("После ручной правки");
      await page.locator("#save-prompt").click();
      await expect.poll(() => writes.length).toBe(2);
      expect(writes[1].source_run_id).toBeNull();
      expect(writes[1].prompt).toBe("Ручная правка промпта после восстановления");
      await expect(page.locator("#model-select")).toHaveValue("gpt-supported");
      await expect(page.locator("#reasoning-effort")).toHaveValue("low");
      await page.locator("#input-tab").click();
      expect(JSON.parse(await page.locator("#json-editor").inputValue())).toEqual(editedInput);
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(original);
      expect(runPosts).toBe(0);
    });
  }
}

for (const followup of ["row", "unrelated-page", "fresh-status", "fresh-times"]) {
  test(`history detail newer than its list stays coherent through ${followup}`, async ({page}) => {
    const complete = historyDetail({runId: "run-newer-history-detail"});
    const pending = {...complete, status: "running", result: null, finished_at: null};
    const other = historyDetail({runId: "run-unrelated-page"});
    const changed = {...complete, finished_at: "2026-09-23T08:00:03Z"};
    if (followup === "fresh-status") {
      changed.status = "failed";
      changed.result = null;
      changed.finished_at = complete.finished_at;
    }
    let listReads = 0;
    let detailReads = 0;
    let promptBody;
    let runPosts = 0;
    const summary = detail => ({run_id: detail.run_id, status: detail.status, atom_id: "A06",
      model_id: detail.snapshot.provider.model_id, preset_id: null, preset_version: null,
      created_at: detail.created_at, started_at: detail.started_at, finished_at: detail.finished_at});
    await page.route("http://atom-lab.test/v1/atom-lab/**", async route => {
      const url = new URL(route.request().url());
      if (url.pathname === "/v1/atom-lab/runs" && route.request().method() === "GET") {
        listReads += 1;
        await route.fulfill({json: {items: [listReads === 1 ? pending : url.searchParams.has("cursor") ? other : changed].map(summary),
          next_cursor: listReads === 1 ? "older-page" : null}});
      } else if (url.pathname.endsWith(complete.run_id)) {
        detailReads += 1;
        if (detailReads > 1 && followup === "unrelated-page") await route.fulfill({status: 503, json: {}});
        else await route.fulfill({json: detailReads === 1 ? complete : changed});
      } else if (url.pathname === "/v1/atom-lab/runs") {
        runPosts += 1;
        await route.abort();
      } else if (url.pathname === "/v1/atom-lab/atoms/A06/prompts") {
        if (route.request().method() === "POST") {
          promptBody = route.request().postDataJSON();
          await route.fulfill({status: 422, json: {error: {code: "prompt_invalid", message: "Test rejection", field_errors: []}}});
        } else await route.fulfill({json: [{ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt,
          group: "platform", source_ref: null, source_run_id: null}]});
      } else await route.fallback();
    });
    await unlockAtom(page, "A06");
    await page.locator("#history-button").click();
    await page.locator(`[data-run-id="${complete.run_id}"]`).click();
    await expect(page.locator("#history-status-text")).toHaveText("Завершён успешно");
    if (followup === "unrelated-page") {
      await page.locator("#load-more-history").click();
      await expect(page.locator("#history-list .history-open")).toHaveCount(2);
    } else if (followup.startsWith("fresh-")) {
      await showWorkbench(page);
      await page.locator("#history-button").click();
      await expect.poll(() => detailReads).toBe(2);
    }
    await expect(page.locator("#restore-history")).toBeEnabled();
    await expect(page.locator("#save-history-preset")).toBeEnabled();
    await expect(page.locator("#history-record")).toBeVisible();
    await expect(page.locator("#history-error")).toHaveText("");
    const expected = followup.startsWith("fresh-") ? changed : complete;
    const selectedRow = page.locator("#history-list tr[data-selected='true']");
    await expect(selectedRow.locator(".status-badge")).toHaveText(expected.status === "succeeded" ? "Успешно" : "Ошибка");
    expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(expected);
    expect(detailReads).toBe(followup.startsWith("fresh-") ? 2 : 1);
    await page.locator("#restore-history").click();
    await page.locator("#prompt-tab").click();
    await expect(page.locator("#prompt-editor")).toHaveValue(expected.snapshot.prompt.content);
    await page.locator("#save-prompt-panel summary").click();
    await page.locator("#save-prompt-name").fill("Свежий снимок");
    await page.locator("#save-prompt").click();
    await expect.poll(() => promptBody).toBeTruthy();
    expect(promptBody.source_run_id).toBe(expected.status === "succeeded" ? complete.run_id : null);
    expect(runPosts).toBe(0);
  });
}

for (const initialStatus of ["queued", "running"]) {
  for (const finalStatus of ["succeeded", "failed"]) {
    test(`history refresh replaces ${initialStatus} detail with actual ${finalStatus} data and trial provenance`, async ({page}) => {
      const complete = historyDetail({runId: "run-refreshed-history", prompt: A06.prompt});
      complete.snapshot.prompt.source_ref = A06.prompt_ref;
      complete.status = finalStatus;
      if (finalStatus === "failed") {
        complete.result = null;
        complete.diagnostics.error_code = "worker_lease_lost";
      }
      const pending = {...complete, status: initialStatus, result: null, finished_at: null,
        started_at: initialStatus === "queued" ? null : complete.started_at,
        diagnostics: {...complete.diagnostics, error_code: null, response_model_id: null, physical_calls: 0}};
      let current = pending;
      let detailReads = 0;
      let promptBody = null;
      let runPosts = 0;
      await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
        const {pathname} = new URL(route.request().url());
        if (pathname === "/v1/atom-lab/runs" && route.request().method() === "GET") {
          await route.fulfill({json: {items: [{run_id: current.run_id, status: current.status, atom_id: "A06",
            model_id: current.snapshot.provider.model_id, preset_id: null, preset_version: null,
            created_at: current.created_at, started_at: current.started_at, finished_at: current.finished_at}], next_cursor: null}});
        } else if (pathname === `/v1/atom-lab/runs/${complete.run_id}`) {
          detailReads += 1;
          await route.fulfill({json: current});
        } else if (pathname === "/v1/atom-lab/runs") {
          runPosts += 1;
          await route.abort();
        } else if (pathname === "/v1/atom-lab/atoms/A06/prompts" && route.request().method() === "POST") {
          promptBody = route.request().postDataJSON();
          await route.fulfill({status: 422, json: {error: {code: "prompt_invalid", message: "Test rejection", field_errors: []}, request_id: "save-history"}});
        } else if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
          await route.fulfill({json: [{ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt,
            group: "platform", source_ref: null, source_run_id: null}]});
        } else await route.fallback();
      });
      await unlockAtom(page, "A06");
      await page.locator("#history-button").click();
      await page.locator("#history-list .history-open").click();
      await expect(page.locator("#history-status-text")).toHaveText(initialStatus === "queued" ? "Ожидает запуска" : "Выполняется");
      await showWorkbench(page);
      await page.locator("#prompt-tab").click();
      await page.locator("#prompt-editor").fill("Несохранённый текущий черновик");
      current = complete;
      await page.locator("#history-button").click();
      await expect(page.locator("#history-status-text")).toHaveText(finalStatus === "succeeded" ? "Завершён успешно" : "Ошибка");
      expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(complete);
      await showWorkbench(page);
      await expect(page.locator("#prompt-editor")).toHaveValue("Несохранённый текущий черновик");
      await page.locator("#history-button").click();
      expect(detailReads).toBe(2);
      page.once("dialog", dialog => dialog.accept());
      await page.locator("#restore-history").click();
      await page.locator("#prompt-tab").click();
      await expect(page.locator("#prompt-editor")).toHaveValue(complete.snapshot.prompt.content);
      if (finalStatus === "succeeded") await expect(page.locator("#prompt-test-status")).toContainText("Ответ прошёл контракт");
      else await expect(page.locator("#prompt-test-status")).not.toContainText("Ответ прошёл контракт");
      await page.locator("#save-prompt-panel summary").click();
      await page.locator("#save-prompt-name").fill("Из обновлённой истории");
      await page.locator("#save-prompt").click();
      await expect.poll(() => promptBody).not.toBeNull();
      expect(promptBody.source_run_id).toBe(finalStatus === "succeeded" ? complete.run_id : null);
      expect(runPosts).toBe(0);
    });
  }
}

for (const outcome of ["list-failure", "failure", "malformed", "superseded-success", "superseded-failure", "pagination", "append"]) {
  test(`history refresh fences stale actions and delayed reads after ${outcome}`, async ({page}) => {
    const complete = historyDetail({runId: "run-refresh-owner"});
    const other = historyDetail({runId: "run-refresh-other", prompt: "Последний выбранный запрос"});
    const pending = {...complete, status: "running", result: null, finished_at: null};
    let refreshed = false;
    let reads = 0;
    let releaseRead;
    const delayedRead = new Promise(resolve => { releaseRead = resolve; });
    const summary = detail => ({run_id: detail.run_id, status: detail.status, atom_id: "A06",
      model_id: detail.snapshot.provider.model_id, preset_id: null, preset_version: null,
      created_at: detail.created_at, started_at: detail.started_at, finished_at: detail.finished_at});
    await page.route("http://atom-lab.test/v1/atom-lab/runs**", async route => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith("/runs")) {
        if (outcome === "list-failure" && refreshed) {
          await route.fulfill({status: 503, json: {error: {code: "history_unavailable", message: "Список недоступен", field_errors: []}, request_id: "list-failed"}});
          return;
        }
        const paginated = outcome === "pagination" && refreshed && !url.searchParams.has("cursor");
        const appending = outcome === "append" && url.searchParams.has("cursor");
        await route.fulfill({json: {items: (paginated || appending ? [other] : [refreshed ? complete : pending, other]).map(summary),
          next_cursor: paginated || (outcome === "append" && !appending) ? "selected-page" : null}});
      } else if (url.pathname.endsWith(other.run_id)) await route.fulfill({json: other});
      else {
        reads += 1;
        if (reads === 2) await delayedRead;
        if (reads === 2 && outcome.includes("failure")) {
          await route.fulfill({status: 503, json: {error: {code: "history_unavailable", message: "Свежее чтение недоступно", field_errors: []}, request_id: "history-failed"}});
        } else await route.fulfill({json: reads === 1 ? pending : reads === 2 && outcome === "malformed" ? {} : complete});
      }
    });
    await unlockAtom(page, "A06");
    await page.locator("#history-button").click();
    await page.locator(`[data-run-id="${complete.run_id}"]`).click();
    await expect(page.locator("#history-status-text")).toHaveText("Выполняется");
    if (outcome !== "append") await showWorkbench(page);
    refreshed = true;
    await page.locator(outcome === "append" ? "#load-more-history" : "#history-button").click();
    if (outcome === "list-failure") {
      await expect(page.locator("#history-error")).toContainText("Список недоступен");
      await expect(page.locator("#history-record")).toBeHidden();
      await expect(page.locator(`[data-run-id="${complete.run_id}"]`)).toHaveAttribute("aria-expanded", "false");
      await expect(page.locator("#history-list .history-expanded")).toHaveCount(0);
      await expect(page.locator("#restore-history")).toBeDisabled();
      await expect(page.locator("#save-history-preset")).toBeDisabled();
      return;
    }
    if (outcome === "pagination") {
      await expect(page.locator("#restore-history")).toBeDisabled();
      await page.locator("#load-more-history").click();
    }
    await expect.poll(() => reads).toBe(2);
    await expect(page.locator("#history-record")).toBeHidden();
    await expect(page.locator("#restore-history")).toBeDisabled();
    await expect(page.locator("#save-history-preset")).toBeDisabled();
    await page.locator("#restore-history").dispatchEvent("click");
    await page.locator("#save-history-preset").dispatchEvent("click");
    await expect(page.locator("#history-panel")).toBeVisible();
    if (outcome.startsWith("superseded")) {
      await page.locator(`[data-run-id="${other.run_id}"]`).dispatchEvent("click");
      await expect(page.locator("#history-detail")).toContainText(other.snapshot.prompt.content);
    }
    const reply = page.waitForResponse(response => response.url().endsWith(complete.run_id));
    releaseRead();
    await (await reply).finished();
    if (outcome === "failure" || outcome === "malformed") {
      await expect(page.locator("#history-error")).toContainText(outcome === "failure" ? "Свежее чтение недоступно" : "некорректный ответ");
      await expect(page.locator("#restore-history")).toBeDisabled();
      await expect(page.locator("#save-history-preset")).toBeDisabled();
      await page.locator(`[data-run-id="${complete.run_id}"]`).click();
    }
    await expect(page.locator("#restore-history")).toBeEnabled();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
    expect(JSON.parse(await page.locator("#history-detail").textContent())).toEqual(outcome.startsWith("superseded") ? other : complete);
    await expect(page.locator("#history-error")).toHaveText("");
    await page.locator("#restore-history").click();
    await expect(page.locator("#prompt-editor")).toHaveValue(outcome.startsWith("superseded") ? other.snapshot.prompt.content : complete.snapshot.prompt.content);
  });
}

test("history detail keeps the last selected snapshot across out-of-order responses", async ({page}) => {
  const slow = historyDetail({runId: "run-history-slow", prompt: "Медленный snapshot"});
  const fast = historyDetail({runId: "run-history-fast", prompt: "Последний выбранный snapshot"});
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const {pathname} = new URL(route.request().url());
    if (pathname === "/v1/atom-lab/runs") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [slow, fast].map((item) => ({
        run_id: item.run_id, status: item.status, atom_id: item.snapshot.atom_id,
        model_id: item.snapshot.provider.model_id, preset_id: null, preset_version: null,
        created_at: item.created_at, started_at: item.started_at, finished_at: item.finished_at,
      })), next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${slow.run_id}` || pathname === `/v1/atom-lab/runs/${fast.run_id}`) {
      const detail = pathname.endsWith(slow.run_id) ? slow : fast;
      await new Promise((resolve) => setTimeout(resolve, detail === slow ? 200 : 20));
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#history-button").click();
  const historyButtons = page.locator("#history-list .history-open");
  await historyButtons.nth(0).click();
  await expect(page.locator("#restore-history")).toBeDisabled();
  await historyButtons.nth(1).dispatchEvent("click");
  await expect(page.locator("#history-detail")).toContainText("Последний выбранный snapshot");
  await page.waitForTimeout(250);
  await expect(page.locator("#history-detail")).toContainText("Последний выбранный snapshot");
  await expect(historyButtons.nth(1)).toHaveAttribute("aria-current", "true");
  await page.locator("#restore-history").click();
  await expect(page.locator("#prompt-editor")).toHaveValue("Последний выбранный snapshot");
});

test("history keeps running and crash-failed snapshots readable without silent migration", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  const failed = historyDetail({runId: "run-crash", prompt: "Старый промпт"});
  failed.status = "failed";
  failed.result = null;
  failed.runtime_ids.action_run_id = null;
  failed.runtime_ids.artifact_id = null;
  failed.diagnostics = {
    ...failed.diagnostics,
    error_code: "worker_lease_lost",
    response_model_id: null,
    validation_attempts: 0,
    physical_calls: 1,
    succeeded_first_attempt: null,
  };
  failed.snapshot.action.config_id = "config.a06.retired";
  failed.snapshot.prompt.ref = "prompt.a06.retired";
  failed.snapshot.preset = {id: "preset-retired", version: 1};
  failed.snapshot.provider.model_id = "openai/gpt-retired";
  let runPosts = 0;
  let adaptedRunBody = null;
  let adaptedPresetBody = null;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs" && request.method() === "POST") {
      runPosts += 1;
      adaptedRunBody = request.postDataJSON();
      await route.abort();
      return;
    }
    if (pathname === "/v1/atom-lab/runs") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [
        {run_id: "run-live", status: "running", atom_id: "A05", model_id: "openai/gpt-supported", preset_id: null, preset_version: null, created_at: "2026-09-23T10:01:00Z", started_at: "2026-09-23T10:01:01Z", finished_at: null},
        {run_id: failed.run_id, status: "failed", atom_id: "A06", model_id: "openai/gpt-retired", preset_id: null, preset_version: null, created_at: failed.created_at, started_at: failed.started_at, finished_at: failed.finished_at},
      ], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${failed.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(failed)});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "POST") {
      adaptedPresetBody = request.postDataJSON();
      await route.abort();
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#history-button").click();
  await expect(page.locator("#history-list .history-open")).toHaveCount(2);
  await page.locator("#history-list .history-open").nth(1).click();
  await expect(page.locator("#history-detail")).toContainText("worker_lease_lost");
  await expect(page.locator("#history-detail")).toContainText('"action_run_id": null');
  await expect(page.locator("#history-warning")).toContainText("только для чтения");
  await expect(page.locator("#restore-history")).toHaveText("Адаптировать к текущему контракту");
  await expect(page.locator("#save-history-preset")).toBeDisabled();

  await page.locator("#restore-history").click();
  await expect(page.locator("#prompt-editor")).toHaveValue("Старый промпт");
  await expect(page.locator("#model-catalog-warning")).toContainText("модель недоступна");
  await expect(page.locator("#run-button")).toBeDisabled();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("high");
  await showWorkbench(page);
  await page.locator("#run-button").click();
  await expect.poll(() => runPosts).toBe(1);
  expect(adaptedRunBody.preset_ref).toBeNull();
  await page.locator("#presets-button").click();
  await editPreset(page);
  await page.locator("#preset-name").fill("Адаптированный пресет");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect.poll(() => adaptedPresetBody).not.toBeNull();
  expect(adaptedPresetBody.source_run_id).toBeNull();
});

test("saving from history uses the selected snapshot instead of the unrelated editor draft", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  const detail = historyDetail({
    runId: "run-history-source",
    prompt: "Промпт выбранной истории",
    reasoningEffort: null,
  });
  detail.snapshot.prompt.source_ref = "product.history.a06.v1";
  const editorPreset = {
    name: "Текущий A05", description: "Связанный runtime draft", atom_id: "A05",
    base_action_config_id: A05.base_action_config_id, schema_refs: A05.schema_refs,
    prompt: A05.prompt, prompt_ref: A05.prompt_ref,
    model_id: "openai/gpt-supported", reasoning_effort: "high", fixed_fields: [],
    example_input: A05.example_input, source_run_id: null,
    preset_id: "preset-editor-a05", version: 1, created_at: "2026-09-23T10:55:00Z",
  };
  let savedBody = null;
  let runBody = null;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/runs" && request.method() === "POST") {
      runBody = request.postDataJSON();
      await route.abort();
      return;
    }
    if (pathname === "/v1/atom-lab/runs" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        run_id: detail.run_id, status: detail.status, atom_id: "A06", model_id: "openai/gpt-supported",
        preset_id: null, preset_version: null, created_at: detail.created_at,
        started_at: detail.started_at, finished_at: detail.finished_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/runs/${detail.run_id}`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(detail)});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "POST") {
      savedBody = request.postDataJSON();
      await route.fulfill({status: 201, contentType: "application/json", body: JSON.stringify({
        preset_id: "history-preset", version: 1, created_at: "2026-09-23T11:00:00Z",
      })});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: editorPreset.preset_id, latest_version: 1, name: editorPreset.name,
        description: editorPreset.description, atom_id: editorPreset.atom_id,
        created_at: editorPreset.created_at, updated_at: editorPreset.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${editorPreset.preset_id}/versions`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: editorPreset.preset_id, version: 1, name: editorPreset.name,
        description: editorPreset.description, atom_id: editorPreset.atom_id,
        created_at: editorPreset.created_at,
      }], next_cursor: null})});
      return;
    }
    if (pathname === `/v1/atom-lab/presets/${editorPreset.preset_id}/versions/1`) {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(editorPreset)});
      return;
    }
    if (pathname === "/v1/atom-lab/atoms/A06/prompts") {
      await route.fulfill({json: [
        {ref: A06.prompt_ref, name: "Платформенный", prompt: A06.prompt, group: "platform", source_ref: null, source_run_id: null},
        {ref: detail.snapshot.prompt.source_ref, name: "Из истории", prompt: detail.snapshot.prompt.content, group: "product", source_ref: A06.prompt_ref, source_run_id: null},
      ]});
      return;
    }
    if (pathname === "/v1/atom-lab/presets/history-preset/versions") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: "history-preset", version: 1, name: savedBody.name, description: savedBody.description,
        atom_id: savedBody.atom_id, created_at: "2026-09-23T11:00:00Z",
      }], next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets/history-preset/versions/1") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({
        ...savedBody, preset_id: "history-preset", version: 1, created_at: "2026-09-23T11:00:00Z",
      })});
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A05");
  await page.locator("#presets-button").click();
  await page.locator("#preset-list button").click();
  await editPreset(page);
  await page.locator("#close-presets").click();
  await page.locator("#history-button").click();
  await page.locator("#history-list .history-open").click();
  await page.locator("#save-history-preset").click();
  await expect(page.locator("#fixed-fields").getByLabel("objective")).toBeVisible();
  await page.locator("#close-presets").click();
  await showWorkbench(page);
  await page.locator("#prompt-tab").click();
  await showWorkbench(page);
  await page.locator("#prompt-editor").fill("Несохранённый A05 prompt");
  await page.locator("#presets-button").click();
  await editPreset(page);
  await page.locator("#preset-name").fill("Из выбранной истории");
  await editPreset(page);
  await page.locator("#preset-description").fill("Не из текущего A05 draft");
  await editPreset(page);
  await page.locator("#save-preset").click();
  await expect.poll(() => savedBody).not.toBeNull();
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 1");

  expect(savedBody.atom_id).toBe("A06");
  expect(savedBody.base_action_config_id).toBe(detail.snapshot.action.config_id);
  expect(savedBody.schema_refs).toEqual({
    input: {schema_ref: detail.snapshot.schemas.input.ref, version: detail.snapshot.schemas.input.version},
    output: {schema_ref: detail.snapshot.schemas.output.ref, version: detail.snapshot.schemas.output.version},
  });
  expect(savedBody.example_input).toEqual(detail.snapshot.input);
  expect(savedBody.prompt).toBe(detail.snapshot.prompt.content);
  expect(savedBody.prompt_ref).toBe(detail.snapshot.prompt.ref);
  expect(savedBody.prompt_source_ref).toBe(detail.snapshot.prompt.source_ref);
  expect(savedBody.model_id).toBe(detail.snapshot.provider.model_id);
  expect(savedBody.reasoning_effort).toBe(detail.snapshot.provider.reasoning_effort);
  expect(savedBody.source_run_id).toBe(detail.run_id);

  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#prompt-editor")).toHaveValue("Несохранённый A05 prompt");
  await page.locator("#close-presets").click();
  await showWorkbench(page);
  await page.locator("#run-button").click();
  await expect.poll(() => runBody).not.toBeNull();
  expect(runBody.atom_id).toBe("A05");
  expect(runBody.prompt).toBe("Несохранённый A05 prompt");
  expect(runBody.preset_ref).toEqual({preset_id: editorPreset.preset_id, version: 1});
});
