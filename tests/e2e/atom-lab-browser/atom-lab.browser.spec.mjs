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

async function openLab(page, {models = () => MODEL_CATALOG} = {}) {
  await page.route("http://atom-lab.test/**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/v1/atom-lab/atoms") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(catalog())});
      return;
    }
    if (pathname === "/v1/atom-lab/models") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify(models())});
      return;
    }
    if (pathname.startsWith("/v1/")) {
      await route.fallback();
      return;
    }
    const file = pathname === "/atom-lab/" ? "index.html" : pathname.split("/").at(-1);
    const contentType = file.endsWith(".css") ? "text/css" : file.endsWith(".mjs") ? "text/javascript" : "text/html";
    await route.fulfill({contentType, body: await readFile(new URL(file, STATIC_ROOT))});
  });
  await page.goto("http://atom-lab.test/atom-lab/");
}

async function unlockAtom(page, atomId, options) {
  await openLab(page, options);
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
  await page.getByLabel("weight", {exact: true}).fill("0.1234567890123456789");
  await expect(page.locator("#validation-errors")).toContainText("точност");
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
  await expect(page.locator("#model-select option")).toHaveCount(5);
  await expect(page.locator('#model-select option[value="gpt-unknown-compatibility"]')).toBeDisabled();
  await expect(page.locator('#model-select option[value="gpt-unknown-compatibility"]')).toContainText("совместимость неизвестна");
  await expect(page.locator('#model-select option[value="gpt-unsupported"]')).toBeDisabled();
  await expect(page.locator('#model-select option[value="gpt-unsupported"]')).toContainText("не поддерживается");

  await page.locator("#model-select").selectOption("gpt-no-reasoning");
  await expect(page.locator("#reasoning-effort")).toBeDisabled();
  await expect(page.locator("#reasoning-help")).toContainText("не поддерживает");

  await page.locator("#model-select").selectOption("gpt-unknown");
  await expect(page.locator("#reasoning-effort")).toBeDisabled();
  await expect(page.locator("#reasoning-help")).toContainText("неизвестны");

  await page.locator("#refresh-models").click();
  await expect.poll(() => refreshRequests).toBe(1);
  await expect(page.locator("#model-catalog-warning")).toContainText("обновление запрошено");
  await expect(page.locator('#model-select option[value="gpt-new"]')).toHaveCount(1);
  await expect(page.locator("#model-catalog-warning")).toBeEmpty();
});

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
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: "Базовый промпт A05", model_id: "openai/gpt-supported", reasoning_effort: "high"},
      runtime_ids: {scenario_session_id: "session-1", job_id: "job-1", action_run_id: terminal ? "action-1" : null, artifact_id: terminal ? "artifact-1" : null},
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
  await page.getByLabel("context").fill("Изменённый после запуска черновик");

  await expect(page.locator("#run-state")).toContainText("Завершён");
  await expect(page.locator("#submitted-snapshot")).toContainText("Оценка");
  await expect(page.locator("#submitted-snapshot")).not.toContainText("Изменённый после запуска");
  await expect(page.locator("#run-metadata")).toContainText("Запрошенная модель");
  await expect(page.locator("#run-metadata")).toContainText("Модель в ответе");
  await expect(page.locator("#run-metadata")).toContainText("1250 мс");
  await expect(page.locator("#result-readable")).toContainText("<img id=unsafe");
  await expect(page.locator("#unsafe")).toHaveCount(0);
  await expect(page.locator("#run-diagnostics")).toContainText("artifact-1");
  expect(submittedBodies).toEqual([{
    atom_id: "A05",
    input: A05.example_input,
    prompt: A05.prompt,
    model_id: "openai/gpt-supported",
    reasoning_effort: "high",
    preset_ref: null,
  }]);
});

test("network submission retry reuses the idempotency key and polling reconnects without another POST", async ({page}) => {
  const keys = [];
  let reads = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    keys.push(route.request().headers()["idempotency-key"]);
    if (keys.length === 1) {
      await route.abort("connectionfailed");
      return;
    }
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-recovery", scenario_session_id: "session-recovery", job_id: "job-recovery", status: "queued"})});
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
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
      runtime_ids: {scenario_session_id: "session-recovery", job_id: "job-recovery", action_run_id: "action-recovery", artifact_id: "artifact-recovery"},
      result: {questions: ["Когда срок?"]},
      diagnostics: {error_code: null, duration_ms: 900, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: null, response_model_id: null, validation_attempts: 1, transport_attempts: 1, physical_calls: 1, succeeded_first_attempt: true, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();

  await page.locator("#run-button").click();
  await expect(page.locator("#retry-submit")).toBeVisible();
  await expect(page.locator("#run-state")).toContainText("Черновик сохранён");
  await page.locator("#retry-submit").click();
  await expect(page.locator("#run-state")).toContainText("Переподключение");
  await expect(page.locator("#run-state")).toContainText("Завершён");

  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
  expect(reads).toBe(2);
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
  await expect(page.locator("#run-diagnostics")).toContainText("provider_unavailable");
  expect(posts).toBe(1);
});

test("final invalid output is diagnostics, never a successful result", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/runs", async (route) => {
    await route.fulfill({status: 202, contentType: "application/json", body: JSON.stringify({run_id: "run-invalid", scenario_session_id: "session-invalid", job_id: "job-invalid", status: "queued"})});
  });
  await page.route("http://atom-lab.test/v1/atom-lab/runs/run-invalid", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({
      run_id: "run-invalid", status: "failed",
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: "low"},
      runtime_ids: {scenario_session_id: "session-invalid", job_id: "job-invalid", action_run_id: "action-invalid", artifact_id: null}, result: null,
      diagnostics: {error_code: "structured_output_validation_failed", duration_ms: 500, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: "low", response_model_id: null, validation_attempts: 2, transport_attempts: 2, physical_calls: 2, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [{artifact_id: "debug-1", error_code: "structured_output_validation_failed", raw_output_text: "<script id=bad>boom()</script>", truncated: false, redacted: true}], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#run-button").click();

  await expect(page.locator("#invalid-response")).toBeVisible();
  await expect(page.locator("#invalid-response")).toContainText("structured_output_validation_failed");
  await expect(page.locator("#invalid-response-raw")).toContainText("<script id=bad>");
  await expect(page.locator("#result-section")).toBeHidden();
  await expect(page.locator("#bad")).toHaveCount(0);
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
  await expect(page.getByLabel("context")).toHaveValue("Оценка");
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("Ошибка");

  expect(keys).toHaveLength(2);
  expect(keys[0]).not.toBe(keys[1]);
});

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
