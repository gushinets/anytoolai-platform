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

function historyDetail({runId = "run-library", input = A06.example_input, prompt = "Промпт запуска"} = {}) {
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
      provider: {policy_ref: "policy", policy: {}, model_id: "openai/gpt-supported", reasoning_effort: "high", capability_snapshot_id: "models-1", capability_provenance: {}},
      preset: {id: null, version: null},
      execution_definition_hash: "hash",
    },
    runtime_ids: {scenario_session_id: "session-library", job_id: "job-library", action_run_id: "action-library", artifact_id: "artifact-library"},
    result: {summary: "Готово"},
    diagnostics: {
      error_code: null, duration_ms: 900, requested_model_id: "openai/gpt-supported",
      requested_reasoning_effort: "high", response_model_id: "gpt-supported",
      validation_attempts: 2, transport_attempts: 1, physical_calls: 1,
      succeeded_first_attempt: false, provider_calls: [], provider_calls_truncated: false,
      debug_artifacts: [], debug_artifacts_truncated: false,
    },
    created_at: "2026-09-23T08:00:00Z",
    started_at: "2026-09-23T08:00:01Z",
    finished_at: "2026-09-23T08:00:02Z",
  };
}

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
  await expect(page.locator("#model-catalog-warning")).toContainText("2026-09-19T10:00:00Z");
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
  await expect(page.locator("#reasoning-help")).toContainText("Выберите effort заново");
  await expect(page.locator("#run-button")).toBeDisabled();

  await page.locator("#reasoning-effort").selectOption("low");
  await expect(page.locator("#reasoning-help")).not.toContainText("Выберите effort заново");
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
        action: {type: "score_match", definition_version: 1, definition: {}, config_id: "config-a05", config_schema_version: 1, config_definition: {}},
        prompt: {ref: "prompt.a05", version: 1, base: "Базовый промпт A05", content: "Базовый промпт A05"},
        schemas: {input: {ref: "input.a05", version: 1, content: {}}, output: {ref: "output.a05", version: 1, content: {}}},
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
  await page.getByLabel("context").fill("Изменённый после запуска черновик");

  await expect(page.locator("#run-state")).toContainText("Завершён");
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
    model_id: "openai/gpt-supported",
    reasoning_effort: "high",
    preset_ref: null,
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
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: "Принятый промпт A", model_id: "openai/gpt-supported", reasoning_effort: null},
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
  await expect(page.locator("#submitted-snapshot")).toContainText(A05.prompt);
  await expect(page.locator("#run-diagnostics")).toContainText("artifact-a");
});

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
      snapshot: {atom_id: "A05", input: A05.example_input, prompt: A05.prompt, model_id: "openai/gpt-supported", reasoning_effort: null},
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
  await page.getByLabel("context").fill("");
  modelAvailable = false;
  await page.locator("#refresh-models").click();
  await expect(page.locator('#model-select option[value="gpt-supported"]')).toBeDisabled();
  await page.locator("#retry-submit").click();
  await expect(page.locator("#run-button")).toBeDisabled();
  await expect(page.locator("#run-state")).toContainText("Переподключение… Запуск принят; текущее состояние временно неизвестно.");
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
      snapshot: {atom_id: "A05"},
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
      diagnostics: {error_code: "structured_output_validation_failed", duration_ms: 500, requested_model_id: "openai/gpt-supported", requested_reasoning_effort: "low", response_model_id: null, validation_attempts: 2, transport_attempts: 2, physical_calls: 2, succeeded_first_attempt: null, provider_calls: [], provider_calls_truncated: false, debug_artifacts: [{artifact_id: "debug-1", error_code: "structured_output_validation_failed", raw_output_text: "<script id=bad>boom()</script>", truncated: true, redacted: true}], debug_artifacts_truncated: false},
      created_at: "2026-09-20T10:00:00Z", started_at: "2026-09-20T10:00:00Z", finished_at: "2026-09-20T10:00:01Z",
    })});
  });
  await unlockAtom(page, "A05");
  await page.locator("#fill-example").click();
  await page.locator("#model-select").selectOption("gpt-supported");
  await page.locator("#reasoning-effort").selectOption("low");
  await page.locator("#run-button").click();

  await expect(page.locator("#invalid-response")).toBeVisible();
  await expect(page.locator("#invalid-response")).toContainText("structured_output_validation_failed");
  await expect(page.locator("#invalid-response")).toContainText("Сырой ответ обрезан");
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
  await page.getByLabel("context").fill("Исправленная оценка");
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
  await expect(page.locator("#reasoning-effort")).not.toHaveAttribute("aria-describedby", /.+/);
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

test("run, immutable preset versions, export, reload, and history restore form one protected journey", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  const versions = [];
  const presetWrites = [];
  let presetListReads = 0;
  let runPosts = 0;
  const detail = historyDetail();

  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    const method = request.method();
    expect(request.headers()["x-atom-lab-access-code"]).toBe("secret");
    if (pathname === "/v1/atom-lab/runs" && method === "POST") {
      runPosts += 1;
      detail.snapshot.input = request.postDataJSON().input;
      detail.snapshot.prompt.content = request.postDataJSON().prompt;
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
  await page.locator("#fill-example").click();
  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-editor").fill("Промпт версии один");
  await page.locator("#reasoning-effort").selectOption("high");
  await page.locator("#run-button").click();
  await expect(page.locator("#run-state")).toContainText("Завершён");

  await page.locator("#presets-button").click();
  await expect(page.locator("#preset-name")).toBeDisabled();
  await expect(page.locator("#preset-state")).toHaveText("Загрузка пресетов…");
  await expect(page.locator("#preset-name")).toBeEnabled();
  await page.locator("#preset-name").fill("Рабочий пресет");
  await page.locator("#preset-description").fill("Проверка версий");
  await page.locator("#fixed-fields").getByLabel("context").check();
  await page.locator("#save-preset").dblclick();
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "true");
  expect(await page.locator("#workspace").evaluate((node) => node.inert)).toBe(true);
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 1");
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#preset-error")).toHaveText("");
  expect(presetWrites).toHaveLength(1);

  await page.locator("#close-presets").click();
  await page.locator("#prompt-editor").fill("Промпт версии два");
  await page.locator("#presets-button").click();
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-state")).toContainText("Сохранена неизменяемая версия 2");
  await page.locator("#preset-version-select").selectOption("1");
  await expect(page.locator("#prompt-editor")).toHaveValue("Промпт версии один");
  await page.locator("#export-preset").click();
  await expect(page.locator("#preset-export")).toContainText('"version": 1');
  await expect(page.locator("#preset-export-download")).toHaveAttribute("download", "atom-lab-preset-library-v1.json");
  await page.locator("#preset-version-select").selectOption("2");
  await expect(page.locator("#prompt-editor")).toHaveValue("Промпт версии два");
  await expect(page.locator("#preset-export")).toBeHidden();
  await expect(page.locator("#preset-export-download")).toBeHidden();

  expect(versions).toHaveLength(2);
  expect(versions[0].prompt).toBe("Промпт версии один");
  expect(versions[1].prompt).toBe("Промпт версии два");
  expect(presetWrites[0].source_run_id).toBe(detail.run_id);

  await page.locator("#close-presets").click();
  await page.locator("#history-button").click();
  await page.locator("#history-list button").click();
  await page.locator("#restore-history").click();
  await page.locator("#presets-button").click();
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новый");
  await expect(page.locator("#preset-version-select option")).toHaveCount(0);

  await page.reload();
  await page.locator("#access-code").fill("secret");
  await page.locator("#access-form button").click();
  await page.locator("#history-button").click();
  await page.locator("#history-list button").click();
  await expect(page.locator("#history-detail")).toContainText('"validation_attempts": 2');
  await page.locator("#restore-history").click();
  await expect(page.locator("#prompt-editor")).toHaveValue("Промпт версии один");
  await expect(page.locator("#draft-state")).toContainText("несохранённые");
  await expect(page.locator("#run-state")).toContainText("Запуск ещё не создан");
  expect(runPosts).toBe(1);
  expect(detail.diagnostics.physical_calls).toBe(1);
});

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
      if (versionReads > 1) {
        await route.fulfill({status: 503, contentType: "application/json", body: JSON.stringify({
          error: {code: "temporary_failure", message: "Версии недоступны.", field_errors: []},
          request_id: "request-latest-failed",
        })});
        return;
      }
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [{
        preset_id: stored.preset_id, version: 1, name: stored.name, description: stored.description,
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
  await page.locator("#preset-name").fill("Мой локальный черновик");
  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-editor").fill("Локальный промпт не потерять");
  await page.locator("#save-preset").click();

  await expect(page.locator("#preset-conflict")).toBeVisible();
  await expect(page.locator("#preset-error")).toContainText("Значения черновика сохранены");
  await expect(page.locator("#preset-name")).toHaveValue("Мой локальный черновик");
  await expect(page.locator("#prompt-editor")).toHaveValue("Локальный промпт не потерять");
  await expect(page.locator("#open-latest-preset")).toBeVisible();
  await expect(page.locator("#open-latest-preset")).toBeDisabled();
  await expect(page.locator("#preset-error")).toContainText("Не удалось получить актуальную версию");
  await expect(page.locator("#save-as-new-preset")).toBeVisible();
  expect(listReads).toBe(1);

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
  let listReads = 0;
  let versionReads = 0;
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
      const visible = versionReads === 1 ? stored : versionReads === 2 ? latest : newest;
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
    if (pathname === `/v1/atom-lab/presets/${stored.preset_id}/versions` && request.method() === "POST") {
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
  await page.locator("#preset-name").fill("Локальный конфликтующий draft");
  await page.locator("#save-preset").click();

  await expect(page.locator("#open-latest-preset")).toBeEnabled();
  expect(listReads).toBe(2);
  await page.locator("#open-latest-preset").click();
  await expect(page.locator("#preset-version-select")).toHaveValue("3");
  await expect(page.locator("#preset-name")).toHaveValue(newest.name);
  await expect(page.locator("#prompt-editor")).toHaveValue(newest.prompt);
  await expect(page.getByRole("button", {name: /Самая новая серверная версия/})).toContainText("v3");
  expect(confirmations).toBe(1);
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
  await page.locator("#preset-name").fill("Preset B edited");
  await page.locator("#save-preset").click();
  await expect.poll(() => savePath).toBe("/v1/atom-lab/presets/preset-b/versions");
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
  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
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

  await page.locator("#save-preset").click();
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "true");
  await page.clock.fastForward(30_000);
  await expect(page.locator("#preset-error")).toContainText("Не повторяйте Save");
  await expect(page.locator("#workspace")).toHaveAttribute("aria-busy", "false");
  await expect(page.locator("#save-preset")).toBeDisabled();
  await expect(page.locator("#save-as-new-preset")).toBeDisabled();
});

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

  await page.locator("#prompt-tab").click();
  await page.locator("#prompt-editor").fill("Текущий несохранённый draft");
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
  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await page.locator("#preset-name").fill("Readback preset");
  await page.locator("#preset-description").fill("Readback failure");
  await page.locator("#save-preset").click();
  await expect(page.locator("#preset-state")).toContainText("повторное чтение не удалось");
  await expect(page.locator("#preset-error")).toContainText("Сохранение завершено");
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новую версию");
  await page.locator("#save-preset").click();
  await expect.poll(() => versionPosts).toBe(1);
  expect(createPosts).toBe(1);
});

test("preset save rejects the visible invalid editor value instead of storing the last accepted payload", async ({page}) => {
  let presetPosts = 0;
  await page.route("http://atom-lab.test/v1/atom-lab/**", async (route) => {
    const request = route.request();
    const {pathname} = new URL(request.url());
    if (pathname === "/v1/atom-lab/presets" && request.method() === "GET") {
      await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
      return;
    }
    if (pathname === "/v1/atom-lab/presets" && request.method() === "POST") {
      presetPosts += 1;
      await route.abort();
      return;
    }
    await route.fallback();
  });

  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await page.locator("#preset-name").fill("Невалидный черновик");
  await page.locator("#json-mode").click();
  await page.locator("#json-editor").fill('{"context":');
  await page.locator("#save-preset").click();

  await expect(page.locator("#preset-error")).toContainText("Исправьте входные данные");
  await expect(page.locator("#json-editor")).toHaveValue('{"context":');
  await expect(page.locator("#validation-errors")).toContainText("JSON");
  expect(presetPosts).toBe(0);
});

test("fixed fields are selectable only while their values exist in the preset input", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });

  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await expect(page.locator("#fixed-fields").getByLabel("context")).toBeEnabled();
  await expect(page.locator("#fixed-fields").getByLabel("audience")).toBeDisabled();

  await page.locator("#json-mode").click();
  await page.locator("#json-editor").fill(JSON.stringify({...A06.example_input, audience: "Команда"}));
  await expect(page.locator("#fixed-fields").getByLabel("audience")).toBeEnabled();
  await page.locator("#fixed-fields").getByLabel("audience").check();
  await page.locator("#json-editor").fill(JSON.stringify(A06.example_input));
  await expect(page.locator("#fixed-fields").getByLabel("audience")).toBeDisabled();
  await expect(page.locator("#fixed-fields").getByLabel("audience")).not.toBeChecked();
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
  await expect(page.locator("#preset-state")).toContainText("Открыта сохранённая версия");
  await page.locator("#run-button").click();
  await expect(page.locator("#preset-state")).toContainText("Есть несохранённый черновик");
});

test("new preset metadata participates in discard protection and atom changes clear its association", async ({page}) => {
  await page.route("http://atom-lab.test/v1/atom-lab/presets", async (route) => {
    await route.fulfill({contentType: "application/json", body: JSON.stringify({items: [], next_cursor: null})});
  });
  await unlockAtom(page, "A06");
  await page.locator("#fill-example").click();
  await page.locator("#presets-button").click();
  await page.locator("#preset-name").fill("Несохранённый пресет");
  await page.locator("#preset-description").fill("Не потерять metadata");
  await page.locator("#fixed-fields").getByLabel("context").check();

  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A06");
  await expect(page.locator("#preset-name")).toHaveValue("Несохранённый пресет");

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", {name: /A05/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#preset-name")).toHaveValue("");
  await expect(page.locator("#preset-version-select option")).toHaveCount(0);
  await expect(page.locator("#save-preset")).toHaveText("Сохранить новый");
  await expect(page.locator("#preset-state")).toContainText("Нет несохранённых изменений");

  await expect(page.locator("#preset-name")).toBeEnabled();
  await expect(page.locator("#fixed-fields").getByLabel("issues")).toBeVisible();
  await page.locator("#preset-name").fill("Новый после смены атома");
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", {name: /A06/}).click();
  await expect(page.locator("#atom-title")).toContainText("A05");
  await expect(page.locator("#preset-name")).toHaveValue("Новый после смены атома");
});

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
  const historyButtons = page.locator("#history-list button");
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
  await expect(page.locator("#history-list button")).toHaveCount(2);
  await page.getByRole("button", {name: /A06 · failed/}).click();
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
  await page.locator("#run-button").click();
  await expect.poll(() => runPosts).toBe(1);
  expect(adaptedRunBody.preset_ref).toBeNull();
  await page.locator("#presets-button").click();
  await page.locator("#preset-name").fill("Адаптированный пресет");
  await page.locator("#save-preset").click();
  await expect.poll(() => adaptedPresetBody).not.toBeNull();
  expect(adaptedPresetBody.source_run_id).toBeNull();
});

test("saving from history uses the selected snapshot instead of the unrelated editor draft", async ({page}) => {
  page.on("dialog", (dialog) => dialog.accept());
  const detail = historyDetail({runId: "run-history-source", prompt: "Промпт выбранной истории"});
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
  await page.locator("#close-presets").click();
  await page.locator("#history-button").click();
  await page.locator("#history-list button").click();
  await page.locator("#save-history-preset").click();
  await expect(page.locator("#fixed-fields").getByLabel("objective")).toBeVisible();
  await page.locator("#close-presets").click();
  await page.locator("#run-button").click();
  await expect.poll(() => runBody).not.toBeNull();
  expect(runBody.preset_ref).toEqual({preset_id: editorPreset.preset_id, version: 1});
  await page.locator("#presets-button").click();
  await page.locator("#preset-name").fill("Из выбранной истории");
  await page.locator("#preset-description").fill("Не из текущего A05 draft");
  await page.locator("#save-preset").click();
  await expect.poll(() => savedBody).not.toBeNull();

  expect(savedBody.atom_id).toBe("A06");
  expect(savedBody.base_action_config_id).toBe(detail.snapshot.action.config_id);
  expect(savedBody.schema_refs).toEqual({
    input: {schema_ref: detail.snapshot.schemas.input.ref, version: detail.snapshot.schemas.input.version},
    output: {schema_ref: detail.snapshot.schemas.output.ref, version: detail.snapshot.schemas.output.version},
  });
  expect(savedBody.example_input).toEqual(detail.snapshot.input);
  expect(savedBody.prompt).toBe(detail.snapshot.prompt.content);
  expect(savedBody.prompt_ref).toBe(detail.snapshot.prompt.ref);
  expect(savedBody.model_id).toBe(detail.snapshot.provider.model_id);
  expect(savedBody.reasoning_effort).toBe(detail.snapshot.provider.reasoning_effort);
  expect(savedBody.source_run_id).toBe(detail.run_id);
});
