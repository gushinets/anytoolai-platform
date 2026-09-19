const ACCESS_HEADER = "X-Atom-Lab-Access-Code";
const DIRTY_WARNING = "Несохранённые изменения будут потеряны. Продолжить?";

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function schemaTypes(schema) {
  if (Array.isArray(schema?.type)) return schema.type;
  if (typeof schema?.type === "string") return [schema.type];
  return [];
}

function primaryType(schema, value) {
  const types = schemaTypes(schema).filter((type) => type !== "null");
  if (types.length > 0) return types[0];
  if (Array.isArray(value)) return "array";
  if (value !== null && typeof value === "object") return "object";
  return typeof value;
}

function jsonKind(value) {
  if (value === null) return "null";
  if (Array.isArray(value)) return "array";
  return typeof value;
}

function fieldKey(path) {
  return pathLabel(path);
}

function fieldControlId(path, suffix = "control") {
  return controlIdForLabel(fieldKey(path), suffix);
}

function controlIdForLabel(label, suffix = "control") {
  return `field-${encodeURIComponent(label).replaceAll("%", "-")}-${suffix}`;
}

function firstControlId(schema, path) {
  return schemaTypes(schema).length === 0 && !Array.isArray(schema?.enum)
    ? fieldControlId(path, "type")
    : fieldControlId(path);
}

function pathLabel(path) {
  if (path.length === 0) return "input";
  return path.reduce((result, segment) => (
    typeof segment === "number" ? `${result}[${segment}]` : result ? `${result}.${segment}` : segment
  ), "");
}

function defineOwn(target, key, value) {
  Object.defineProperty(target, key, {
    value,
    enumerable: true,
    configurable: true,
    writable: true,
  });
}

function resolveParent(payload, path, create) {
  let current = payload;
  for (let index = 0; index < path.length - 1; index += 1) {
    const segment = path[index];
    if (!Object.hasOwn(current, segment)) {
      if (!create) return null;
      defineOwn(current, segment, typeof path[index + 1] === "number" ? [] : {});
    }
    current = current[segment];
    if (current === undefined || current === null) return null;
  }
  return current;
}

function valueAtPath(payload, path) {
  let current = payload;
  for (const segment of path) {
    if (current === null || typeof current !== "object" || !Object.hasOwn(current, segment)) {
      return undefined;
    }
    current = current[segment];
  }
  return current;
}

export function hasDraftPath(session, path) {
  if (path.length === 0) return true;
  const parent = resolveParent(session.payload, path, false);
  return parent !== null && Object.hasOwn(parent, path.at(-1));
}

export function createDraftSession(atom) {
  const session = {
    atom,
    payload: {},
    baselinePayload: {},
    basePrompt: atom.prompt,
    prompt: atom.prompt,
    mode: "form",
    jsonText: "{}",
    jsonError: null,
    inputErrors: new Map(),
  };
  Object.defineProperty(session, "dirty", {
    enumerable: true,
    get() {
      return this.prompt !== this.basePrompt
        || !sameJson(this.payload, this.baselinePayload)
        || this.jsonError !== null
        || this.inputErrors.size > 0;
    },
  });
  return session;
}

export function getDraftPayload(session) {
  return cloneJson(session.payload);
}

export function setDraftPath(session, path, value) {
  if (path.length === 0) {
    session.payload = cloneJson(value);
  } else {
    const parent = resolveParent(session.payload, path, true);
    if (parent === null) throw new Error(`Cannot set ${pathLabel(path)}`);
    defineOwn(parent, path.at(-1), cloneJson(value));
  }
  session.jsonError = null;
  session.inputErrors.delete(fieldKey(path));
}

export function omitDraftPath(session, path) {
  if (path.length === 0) {
    session.payload = {};
    return;
  }
  const parent = resolveParent(session.payload, path, false);
  if (parent === null) return;
  if (Array.isArray(parent) && typeof path.at(-1) === "number") {
    parent.splice(path.at(-1), 1);
  } else {
    delete parent[path.at(-1)];
  }
  session.inputErrors.delete(fieldKey(path));
}

export function replaceWithExample(session) {
  session.payload = cloneJson(session.atom.example_input);
  session.jsonText = JSON.stringify(session.payload, null, 2);
  session.jsonError = null;
  session.inputErrors.clear();
}

export function resetPrompt(session) {
  session.prompt = session.basePrompt;
}

export function serializeDraft(session) {
  return JSON.stringify(session.payload, null, 2);
}

export function applyJsonText(session, text) {
  session.jsonText = text;
  try {
    const parsed = JSON.parse(text);
    if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
      session.jsonError = "JSON входа должен содержать объект.";
      return false;
    }
    session.payload = parsed;
    session.jsonError = null;
    return true;
  } catch {
    session.jsonError = "Некорректный JSON. Исправьте синтаксис перед продолжением.";
    return false;
  }
}

export function switchEditorMode(session, mode) {
  if (session.mode === mode) return true;
  if (mode === "json") {
    if (session.inputErrors.size > 0) return false;
    session.mode = "json";
    session.jsonText = serializeDraft(session);
    session.jsonError = null;
    return true;
  }
  if (mode !== "form") throw new Error(`Unknown editor mode: ${mode}`);
  if (!applyJsonText(session, session.jsonText)) return false;
  session.mode = "form";
  return true;
}

export function collectSchemaFeatures(schema, features = new Set()) {
  const types = schemaTypes(schema);
  if (types.length === 0) features.add("untyped");
  for (const type of types) features.add(type);
  if (Array.isArray(schema?.enum)) features.add("enum");
  if (
    (types.includes("object") || schema?.properties || schema?.additionalProperties !== undefined)
    && schema?.additionalProperties !== false
  ) {
    features.add("dynamic-dictionary");
  }
  for (const property of Object.values(schema?.properties ?? {})) {
    collectSchemaFeatures(property, features);
  }
  if (schema?.items) collectSchemaFeatures(schema.items, features);
  if (schema?.additionalProperties && typeof schema.additionalProperties === "object") {
    collectSchemaFeatures(schema.additionalProperties, features);
  }
  return features;
}

function validationError(errors, path, message) {
  errors.push({path: pathLabel(path), message});
}

function validateValue(value, schema, path, errors) {
  const types = schemaTypes(schema);
  if (value === null) {
    if (types.length > 0 && !types.includes("null")) {
      validationError(errors, path, "Значение не может быть null.");
    }
    return;
  }
  const type = primaryType(schema, value);
  const matchesType = types.length === 0
    || (types.includes("object") && typeof value === "object" && !Array.isArray(value))
    || (types.includes("array") && Array.isArray(value))
    || (types.includes("string") && typeof value === "string")
    || (types.includes("boolean") && typeof value === "boolean")
    || (types.includes("number") && typeof value === "number" && Number.isFinite(value))
    || (types.includes("integer") && Number.isInteger(value));
  if (!matchesType) {
    validationError(errors, path, "Значение имеет неверный тип.");
    return;
  }
  if (Array.isArray(schema.enum) && !schema.enum.some((item) => sameJson(item, value))) {
    validationError(errors, path, "Выберите одно из допустимых значений.");
    return;
  }
  if (type === "object") {
    const properties = schema.properties ?? {};
    for (const required of schema.required ?? []) {
      if (!Object.hasOwn(value, required)) {
        validationError(errors, [...path, required], "Обязательное поле не заполнено.");
      }
    }
    for (const [key, item] of Object.entries(value)) {
      if (Object.hasOwn(properties, key)) {
        validateValue(item, properties[key], [...path, key], errors);
      } else if (schema.additionalProperties === false) {
        validationError(errors, [...path, key], "Поле не предусмотрено контрактом.");
      } else if (schema.additionalProperties && typeof schema.additionalProperties === "object") {
        validateValue(item, schema.additionalProperties, [...path, key], errors);
      }
    }
  } else if (type === "array") {
    if (schema.minItems !== undefined && value.length < schema.minItems) {
      validationError(errors, path, `Добавьте не менее ${schema.minItems} элементов.`);
    }
    if (schema.uniqueItems) {
      const serialized = value.map((item) => JSON.stringify(item));
      if (new Set(serialized).size !== serialized.length) {
        validationError(errors, path, "Элементы списка не должны повторяться.");
      }
    }
    value.forEach((item, index) => validateValue(item, schema.items ?? {}, [...path, index], errors));
  } else if (type === "string") {
    if (schema.minLength !== undefined && value.length < schema.minLength) {
      validationError(errors, path, "Значение слишком короткое.");
    } else if (schema.pattern && !(new RegExp(schema.pattern)).test(value)) {
      validationError(errors, path, "Значение не соответствует требуемому формату.");
    }
  } else if (type === "number" || type === "integer") {
    if (schema.minimum !== undefined && value < schema.minimum) {
      validationError(errors, path, `Значение должно быть не меньше ${schema.minimum}.`);
    } else if (schema.exclusiveMinimum !== undefined && value <= schema.exclusiveMinimum) {
      validationError(errors, path, `Значение должно быть больше ${schema.exclusiveMinimum}.`);
    } else if (schema.maximum !== undefined && value > schema.maximum) {
      validationError(errors, path, `Значение должно быть не больше ${schema.maximum}.`);
    }
  }
}

export function validateDraft(session) {
  if (session.jsonError) return [{path: "input", message: session.jsonError}];
  const errors = [];
  validateValue(session.payload, session.atom.input_schema, [], errors);
  for (const [path, message] of session.inputErrors) errors.push({path, message});
  return errors;
}

function initialValue(schema) {
  if (Array.isArray(schema?.enum) && schema.enum.length > 0) return cloneJson(schema.enum[0]);
  switch (primaryType(schema, undefined)) {
    case "object": return {};
    case "array": return [];
    case "boolean": return false;
    case "number":
    case "integer": return 0;
    case "string": return "";
    default: return null;
  }
}

function button(document, label, onClick) {
  const node = document.createElement("button");
  node.type = "button";
  node.textContent = label;
  node.addEventListener("click", onClick);
  return node;
}

function renderValidation(document, container, session) {
  container.replaceChildren();
  const errors = validateDraft(session);
  if (errors.length === 0) return;
  const heading = document.createElement("p");
  heading.textContent = "Исправьте поля:";
  const list = document.createElement("ul");
  for (const error of errors) {
    const item = document.createElement("li");
    const errorId = controlIdForLabel(error.path, "error");
    item.id = errorId;
    const control = typeof document.getElementById === "function"
      ? document.getElementById(controlIdForLabel(error.path))
        ?? document.getElementById(controlIdForLabel(error.path, "type"))
        ?? document.getElementById(controlIdForLabel(error.path, "add"))
      : null;
    if (control) {
      control.setAttribute("aria-invalid", "true");
      control.setAttribute("aria-describedby", errorId);
      const link = button(document, `${error.path}: ${error.message}`, () => control.focus());
      link.className = "error-link";
      item.append(link);
    } else {
      item.textContent = `${error.path}: ${error.message}`;
    }
    list.append(item);
  }
  container.append(heading, list);
}

function matchesDeclaredType(value, schema) {
  const types = schemaTypes(schema);
  if (types.length === 0) return true;
  if (value === null) return types.includes("null");
  return (types.includes("object") && typeof value === "object" && !Array.isArray(value))
    || (types.includes("array") && Array.isArray(value))
    || (types.includes("string") && typeof value === "string")
    || (types.includes("boolean") && typeof value === "boolean")
    || (types.includes("number") && typeof value === "number" && Number.isFinite(value))
    || (types.includes("integer") && Number.isInteger(value));
}

function appendRecoverableJson(context, wrapper, path, label, value) {
  const {document, session, rerender} = context;
  const input = document.createElement("textarea");
  input.id = fieldControlId(path);
  input.rows = 3;
  input.value = JSON.stringify(value, null, 2);
  input.setAttribute("aria-label", `${label}, JSON-значение`);
  input.setAttribute("aria-invalid", "true");
  input.addEventListener("change", () => {
    try {
      setDraftPath(session, path, JSON.parse(input.value));
      rerender(true, input.id);
    } catch {
      session.inputErrors.set(fieldKey(path), "Введите корректное JSON-значение.");
      input.setAttribute("aria-invalid", "true");
      rerender(false);
    }
  });
  wrapper.append(input);
}

function renderUntyped(context, wrapper, path, label, value) {
  const {document, session, rerender} = context;
  const select = document.createElement("select");
  select.id = fieldControlId(path, "type");
  select.setAttribute("aria-label", `Тип значения «${label}»`);
  const kinds = ["string", "number", "boolean", "object", "array", "null"];
  const names = {
    string: "Строка", number: "Число", boolean: "Логическое значение",
    object: "Объект", array: "Массив", null: "null",
  };
  for (const kind of kinds) {
    const option = document.createElement("option");
    option.value = kind;
    option.textContent = names[kind];
    option.selected = kind === jsonKind(value);
    select.append(option);
  }
  select.value = jsonKind(value);
  select.addEventListener("change", () => {
    const defaults = {string: "", number: 0, boolean: false, object: {}, array: [], null: null};
    setDraftPath(session, path, defaults[select.value]);
    rerender(true, fieldControlId(path, "type"));
  });
  wrapper.append(select);

  const kind = jsonKind(value);
  if (kind === "object") {
    renderObject(context, wrapper, {type: "object", additionalProperties: {}}, path, value);
  } else if (kind === "array") {
    renderArray(context, wrapper, {type: "array", items: {}}, path, value);
  } else if (kind === "string" || kind === "number") {
    const input = document.createElement("input");
    input.id = fieldControlId(path);
    input.type = kind === "number" ? "number" : "text";
    input.value = String(value);
    input.setAttribute("aria-label", label);
    input.addEventListener("input", () => {
      if (kind === "string") {
        setDraftPath(session, path, input.value);
      } else if (input.value !== "" && Number.isFinite(Number(input.value))) {
        setDraftPath(session, path, Number(input.value));
      } else {
        session.inputErrors.set(fieldKey(path), "Введите корректное число.");
      }
      rerender(false);
    });
    wrapper.append(input);
  } else if (kind === "boolean") {
    const input = document.createElement("input");
    input.id = fieldControlId(path);
    input.type = "checkbox";
    input.checked = value;
    input.setAttribute("aria-label", label);
    input.addEventListener("change", () => {
      setDraftPath(session, path, input.checked);
      rerender(false);
    });
    wrapper.append(input);
  }
}

function renderField(context, container, schema, path, label, required) {
  const {document, session, rerender} = context;
  const exists = hasDraftPath(session, path);
  const wrapper = document.createElement("div");
  wrapper.className = "schema-field";
  wrapper.dataset.path = pathLabel(path);
  const heading = document.createElement("div");
  heading.className = "field-heading";
  const title = document.createElement("strong");
  title.textContent = label;
  if (required) {
    const mark = document.createElement("span");
    mark.className = "required-mark";
    mark.textContent = " *";
    title.append(mark);
  }
  heading.append(title);
  if (!exists) {
    const addButton = button(document, `Добавить поле «${label}»`, () => {
      setDraftPath(session, path, initialValue(schema));
      rerender(true, firstControlId(schema, path));
    });
    addButton.id = fieldControlId(path, "add");
    heading.append(addButton);
    wrapper.append(heading);
    container.append(wrapper);
    return;
  }
  if (!required && path.length > 0) {
    const omitButton = button(document, `Не передавать «${label}»`, () => {
      omitDraftPath(session, path);
      rerender(true, fieldControlId(path, "add"));
    });
    omitButton.id = fieldControlId(path, "omit");
    heading.append(omitButton);
  }
  wrapper.append(heading);
  if (schema.description) {
    const description = document.createElement("p");
    description.className = "field-description";
    description.textContent = schema.description;
    wrapper.append(description);
  }
  const value = valueAtPath(session.payload, path);
  if (schemaTypes(schema).length === 0 && !Array.isArray(schema.enum)) {
    renderUntyped(context, wrapper, path, label, value);
    container.append(wrapper);
    return;
  }
  const allowsNull = schemaTypes(schema).includes("null");
  if (allowsNull) {
    const nullLabel = document.createElement("label");
    const nullInput = document.createElement("input");
    nullInput.type = "checkbox";
    nullInput.checked = value === null;
    nullInput.addEventListener("change", () => {
      setDraftPath(session, path, nullInput.checked ? null : initialValue(schema));
      rerender();
    });
    nullLabel.append(nullInput);
    const nullText = document.createElement("span");
    nullText.textContent = " Передать null";
    nullLabel.append(nullText);
    wrapper.append(nullLabel);
    if (value === null) {
      container.append(wrapper);
      return;
    }
  }
  if (!matchesDeclaredType(value, schema)) {
    appendRecoverableJson(context, wrapper, path, label, value);
    container.append(wrapper);
    return;
  }
  const type = primaryType(schema, value);
  if (type === "object") {
    renderObject(context, wrapper, schema, path, value);
  } else if (type === "array") {
    renderArray(context, wrapper, schema, path, value);
  } else if (Array.isArray(schema.enum)) {
    const select = document.createElement("select");
    select.setAttribute("aria-label", label);
    for (const optionValue of schema.enum) {
      const option = document.createElement("option");
      option.value = String(optionValue);
      option.textContent = String(optionValue);
      option.selected = sameJson(optionValue, value);
      select.append(option);
    }
    select.value = String(value);
    select.id = fieldControlId(path);
    select.addEventListener("change", () => {
      const selected = schema.enum.find((item) => String(item) === select.value);
      setDraftPath(session, path, selected);
      rerender(false);
    });
    wrapper.append(select);
  } else if (type === "boolean") {
    const input = document.createElement("input");
    input.id = fieldControlId(path);
    input.type = "checkbox";
    input.checked = value;
    input.setAttribute("aria-label", label);
    input.addEventListener("change", () => {
      setDraftPath(session, path, input.checked);
      rerender(false);
    });
    wrapper.append(input);
  } else if (type === "number" || type === "integer") {
    const input = document.createElement("input");
    input.id = fieldControlId(path);
    input.type = "number";
    input.value = String(value);
    input.step = type === "integer" ? "1" : "any";
    input.setAttribute("aria-label", label);
    input.addEventListener("input", () => {
      const isInteger = type === "integer";
      const exactInteger = /^-?(0|[1-9]\d*)$/.test(input.value);
      const parsed = Number(input.value);
      if (input.value !== "" && Number.isFinite(parsed) && (!isInteger || exactInteger)) {
        setDraftPath(session, path, parsed);
      } else {
        session.inputErrors.set(
          fieldKey(path),
          isInteger ? "Значение должно быть целым числом." : "Введите корректное число.",
        );
      }
      rerender(false);
    });
    wrapper.append(input);
  } else if (type === "string") {
    const input = document.createElement("textarea");
    input.id = fieldControlId(path);
    input.rows = 2;
    input.value = value;
    input.setAttribute("aria-label", label);
    input.addEventListener("input", () => {
      setDraftPath(session, path, input.value);
      rerender(false);
    });
    wrapper.append(input);
  } else {
    const input = document.createElement("textarea");
    input.rows = 3;
    input.value = JSON.stringify(value, null, 2);
    input.setAttribute("aria-label", `${label}, JSON-значение`);
    input.addEventListener("change", () => {
      try {
        setDraftPath(session, path, JSON.parse(input.value));
        rerender();
      } catch {
        input.setAttribute("aria-invalid", "true");
      }
    });
    wrapper.append(input);
  }
  container.append(wrapper);
}

function renderObject(context, container, schema, path, value) {
  const {document, session, rerender} = context;
  const properties = schema.properties ?? {};
  const required = new Set(schema.required ?? []);
  for (const [key, propertySchema] of Object.entries(properties)) {
    renderField(context, container, propertySchema, [...path, key], key, required.has(key));
  }
  const allowsDynamic = schema.additionalProperties !== false;
  const dynamicSchema = typeof schema.additionalProperties === "object" ? schema.additionalProperties : {};
  for (const key of Object.keys(value).filter((item) => !Object.hasOwn(properties, item))) {
    const row = document.createElement("div");
    row.className = "schema-object";
    const keyInput = document.createElement("input");
    keyInput.className = "dynamic-key";
    keyInput.value = key;
    keyInput.disabled = !allowsDynamic;
    keyInput.setAttribute("aria-label", `Ключ ${pathLabel([...path, key])}`);
    keyInput.addEventListener("change", () => {
      const nextKey = keyInput.value;
      if (!allowsDynamic || nextKey === key || Object.hasOwn(value, nextKey)) return;
      defineOwn(value, nextKey, value[key]);
      delete value[key];
      rerender(true, fieldControlId([...path, nextKey], "key"));
    });
    keyInput.id = fieldControlId([...path, key], "key");
    row.append(keyInput);
    renderField(context, row, dynamicSchema, [...path, key], `Значение «${key}»`, false);
    container.append(row);
  }
  if (allowsDynamic) {
    const addKeyButton = button(document, "Добавить ключ", () => {
      let index = 1;
      while (Object.hasOwn(value, `key_${index}`)) index += 1;
      setDraftPath(session, [...path, `key_${index}`], initialValue(dynamicSchema));
      rerender(true, firstControlId(dynamicSchema, [...path, `key_${index}`]));
    });
    addKeyButton.id = fieldControlId(path, "add-key");
    container.append(addKeyButton);
  }
}

function renderArray(context, container, schema, path, value) {
  const {document, session, rerender} = context;
  value.forEach((_item, index) => {
    const row = document.createElement("div");
    row.className = "array-item";
    renderField(context, row, schema.items ?? {}, [...path, index], `Элемент ${index + 1}`, true);
    const removeButton = button(document, `Удалить элемент ${index + 1}`, () => {
      omitDraftPath(session, [...path, index]);
      const nextIndex = Math.min(index, value.length - 1);
      const focusId = value.length > 0
        ? firstControlId(schema.items ?? {}, [...path, nextIndex])
        : fieldControlId(path, "add-item");
      rerender(true, focusId);
    });
    row.append(removeButton);
    container.append(row);
  });
  const addItemButton = button(document, "Добавить элемент", () => {
    const index = value.length;
    value.push(initialValue(schema.items ?? {}));
    rerender(true, firstControlId(schema.items ?? {}, [...path, index]));
  });
  addItemButton.id = fieldControlId(path, "add-item");
  container.append(addItemButton);
}

function requiredNode(document, selector) {
  const node = document.querySelector(selector);
  if (!node) throw new Error(`Atom Lab node is missing: ${selector}`);
  return node;
}

export function bootstrapAtomLab({document, fetchImpl, confirmImpl}) {
  const nodes = Object.fromEntries([
    "access-form", "access-code", "access-panel", "workspace", "status", "atom-navigation",
    "atom-title", "atom-action-type", "atom-description", "atom-transformation", "input-schema",
    "output-schema", "input-tab", "prompt-tab", "input-panel", "prompt-panel", "form-mode",
    "json-mode", "input-editor", "json-panel", "json-editor", "json-error", "prompt-editor",
    "fill-example", "reset-prompt", "draft-state", "validation-errors", "presets-button",
    "history-button",
  ].map((id) => [id, requiredNode(document, `#${id}`)]));
  let accessCode = "";
  let catalog = [];
  let session = null;
  let selectedAtomId = null;

  const updateDraftState = () => {
    if (!session) return;
    nodes["draft-state"].textContent = session.dirty ? "Есть несохранённые правки." : "Черновик без изменений.";
    renderValidation(document, nodes["validation-errors"], session);
  };

  const renderEditor = (replaceFields = true, focusId = null) => {
    if (!session) return;
    nodes["form-mode"].setAttribute("aria-pressed", String(session.mode === "form"));
    nodes["json-mode"].setAttribute("aria-pressed", String(session.mode === "json"));
    nodes["input-editor"].hidden = session.mode !== "form";
    nodes["json-panel"].hidden = session.mode !== "json";
    if (session.mode === "json") {
      nodes["json-editor"].value = session.jsonText;
      nodes["json-error"].textContent = session.jsonError ?? "";
    } else if (replaceFields) {
      nodes["input-editor"].replaceChildren();
      renderObject(
        {document, session, rerender: renderEditor},
        nodes["input-editor"],
        session.atom.input_schema,
        [],
        session.payload,
      );
      if (focusId && typeof document.getElementById === "function") {
        document.getElementById(focusId)?.focus();
      }
    }
    updateDraftState();
  };

  const renderNavigation = () => {
    nodes["atom-navigation"].replaceChildren();
    for (const atom of catalog) {
      const item = button(document, `${atom.atom_id} · ${atom.action_type}`, () => selectAtom(atom));
      item.setAttribute("aria-current", String(atom.atom_id === selectedAtomId));
      nodes["atom-navigation"].append(item);
    }
  };

  const selectAtom = (atom) => {
    if (session?.dirty && !confirmImpl(DIRTY_WARNING)) return;
    selectedAtomId = atom.atom_id;
    session = createDraftSession(atom);
    nodes["atom-title"].textContent = `${atom.atom_id} · ${atom.action_type}`;
    nodes["atom-action-type"].textContent = atom.action_type;
    nodes["atom-description"].textContent = atom.description;
    nodes["atom-transformation"].textContent = `Принимает контракт ${atom.schema_refs.input.schema_ref} v${atom.schema_refs.input.version} и возвращает ${atom.schema_refs.output.schema_ref} v${atom.schema_refs.output.version}.`;
    nodes["input-schema"].textContent = JSON.stringify(atom.input_schema, null, 2);
    nodes["output-schema"].textContent = JSON.stringify(atom.output_schema, null, 2);
    nodes["prompt-editor"].value = session.prompt;
    renderNavigation();
    renderEditor();
  };

  const showInputTab = (showInput) => {
    nodes["input-panel"].hidden = !showInput;
    nodes["prompt-panel"].hidden = showInput;
    nodes["input-tab"].setAttribute("aria-selected", String(showInput));
    nodes["prompt-tab"].setAttribute("aria-selected", String(!showInput));
  };

  nodes["access-form"].addEventListener("submit", async (event) => {
    event.preventDefault();
    accessCode = nodes["access-code"].value;
    nodes["access-code"].value = "";
    nodes.status.textContent = "Загрузка каталога…";
    try {
      const response = await fetchImpl("/v1/atom-lab/atoms", {headers: {[ACCESS_HEADER]: accessCode}});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message ?? "Не удалось открыть каталог.");
      catalog = payload;
      nodes["access-panel"].hidden = true;
      nodes.workspace.hidden = false;
      nodes.status.textContent = `Доступно атомов: ${catalog.length}.`;
      selectAtom(catalog[0]);
    } catch (error) {
      accessCode = "";
      nodes["access-panel"].hidden = false;
      nodes.workspace.hidden = true;
      nodes.status.textContent = error instanceof Error ? error.message : "Не удалось открыть каталог.";
      nodes["access-code"].focus();
    }
  });
  nodes["input-tab"].addEventListener("click", () => showInputTab(true));
  nodes["prompt-tab"].addEventListener("click", () => showInputTab(false));
  nodes["form-mode"].addEventListener("click", () => {
    if (switchEditorMode(session, "form")) renderEditor();
    else renderEditor(false);
  });
  nodes["json-mode"].addEventListener("click", () => {
    if (!switchEditorMode(session, "json")) {
      renderEditor(false);
      return;
    }
    renderEditor();
  });
  nodes["json-editor"].addEventListener("input", () => {
    applyJsonText(session, nodes["json-editor"].value);
    nodes["json-error"].textContent = session.jsonError ?? "";
    updateDraftState();
  });
  nodes["prompt-editor"].addEventListener("input", () => {
    session.prompt = nodes["prompt-editor"].value;
    updateDraftState();
  });
  nodes["fill-example"].addEventListener("click", () => {
    if (session.dirty && !confirmImpl(DIRTY_WARNING)) return;
    replaceWithExample(session);
    renderEditor();
  });
  nodes["reset-prompt"].addEventListener("click", () => {
    if (session.prompt !== session.basePrompt && !confirmImpl(DIRTY_WARNING)) return;
    resetPrompt(session);
    nodes["prompt-editor"].value = session.prompt;
    updateDraftState();
  });
  for (const id of ["presets-button", "history-button"]) {
    nodes[id].addEventListener("click", () => {
      if (session?.dirty && !confirmImpl(DIRTY_WARNING)) return;
      nodes.status.textContent = "Раздел будет подключён в следующем этапе Atom Lab.";
    });
  }

  showInputTab(true);
  return {getSession: () => session};
}

if (typeof document !== "undefined" && document.querySelector("#access-form")) {
  bootstrapAtomLab({
    document,
    fetchImpl: (...args) => fetch(...args),
    confirmImpl: (message) => globalThis.confirm(message),
  });
}
