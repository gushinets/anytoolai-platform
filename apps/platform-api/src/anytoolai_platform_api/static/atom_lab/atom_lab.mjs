const ACCESS_HEADER = "X-Atom-Lab-Access-Code";
const DIRTY_WARNING = "Несохранённые изменения будут потеряны. Продолжить?";
const RUN_POLL_INTERVAL_MS = 250;
const RUN_POLL_MAX_BACKOFF_MS = 4_000;
const RUN_POLL_TIMEOUT_MS = 90_000;
const RETRYABLE_SUBMISSION_STATUSES = new Set([408, 425, 500, 502, 503, 504]);
const TERMINAL_RUN_STATUSES = new Set(["succeeded", "failed", "expired", "cancelled"]);
const RUN_PRESENTATION = {
  queued: {label: "Ожидает запуска", tone: "pending", help: "Запуск принят и ожидает обработки."},
  running: {label: "Выполняется", tone: "pending", help: "Ожидаем ответ модели и проверяем результат."},
  succeeded: {label: "Завершён", tone: "success", help: "Ответ прошёл проверку контракта атома."},
  failed: {label: "Ошибка", tone: "error", help: "Запуск завершился без корректного результата. Подробности доступны в диагностике."},
  expired: {label: "Истёк", tone: "warning", help: "Срок выполнения запуска истёк."},
  cancelled: {label: "Отменён", tone: "neutral", help: "Запуск отменён."},
};
const RUN_STATUSES = new Set(Object.keys(RUN_PRESENTATION));
const PROVIDER_CALL_STATUSES = new Set(["created", "running", "succeeded", "failed", "timed_out"]);
const REASONING_EFFORTS = new Set(["none", "minimal", "low", "medium", "high", "xhigh", "max"]);
const MODEL_COMPATIBILITIES = new Set(["compatible", "unknown", "unsupported"]);
const MODEL_REASONS = new Set([
  "override_compatible",
  "override_unknown",
  "override_unsupported",
  "litellm_metadata_missing",
  "litellm_compatibility_incomplete",
  "confirmed_openai_text_gpt",
]);
const MODEL_REFRESH_STATUSES = new Set(["current", "pending", "running"]);
const ATOM_LABELS = {
  A01: {name: "Извлечь поля", input: "Текст и список полей", output: "Значения и пропуски"},
  A02: {name: "Оценить совпадение", input: "Два текста и критерии", output: "Оценка соответствия"},
  A03: {name: "Оценить по шкалам", input: "Текст и шкалы оценки", output: "Оценки по шкалам"},
  A04: {name: "Найти пробелы", input: "Текст, контекст и категории", output: "Найденные проблемы"},
  A05: {name: "Составить вопросы", input: "Проблемы и контекст", output: "Уточняющие вопросы"},
  A06: {name: "Убедить читателя", input: "Контекст, цель и ограничения", output: "Убедительный текст"},
  A07: {name: "Ответить клиенту", input: "Ситуация, цель и тон", output: "Готовый ответ"},
  A08: {name: "Переписать текст", input: "Исходный текст и пробел", output: "Варианты переписывания"},
  A09: {name: "Выбрать аргумент", input: "Сигналы, цель и варианты", output: "Аргумент и обоснование"},
  A10: {name: "Собрать отчёт", input: "Шаблон и данные", output: "Документ по шаблону"},
  A11: {name: "Сравнить тексты", input: "Два текста, категории и критерии", output: "Результат сравнения"},
};
const ATOM_IDS = new Set(Object.keys(ATOM_LABELS));
const PROMPT_GROUPS = {platform: "Платформа", product: "Продукты", lab: "Сохранённые в Lab"};
const CONFIRMED_PRESET_PREWRITE_FAILURE_CODES = new Set([
  "atom_lab_catalog_unavailable",
  "atom_lab_unavailable",
  "runtime_storage_unavailable",
]);

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function canonicalJson(value) {
  if (Array.isArray(value)) return value.map(canonicalJson);
  if (!isRecord(value)) return value;
  return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, canonicalJson(value[key])]),
  );
}

function sameJsonSemantically(left, right) {
  return JSON.stringify(canonicalJson(left)) === JSON.stringify(canonicalJson(right));
}

function retryAfterDelayMs(value, nowMs) {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  if (/^\d+$/.test(normalized)) {
    const delay = Number(normalized) * 1_000;
    return Number.isSafeInteger(delay) ? delay : null;
  }
  const retryAt = Date.parse(normalized);
  return Number.isFinite(retryAt) ? Math.max(0, retryAt - nowMs) : null;
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
  return JSON.stringify(path);
}

function fieldControlId(path, suffix = "control") {
  return controlIdForKey(fieldKey(path), suffix);
}

function controlIdForKey(key, suffix = "control") {
  return `field-${encodeURIComponent(key).replaceAll("%", "-")}-${suffix}`;
}

function firstControlId(schema, path, value) {
  if (schemaTypes(schema).length === 0 && !Array.isArray(schema?.enum)) {
    return fieldControlId(path, "type");
  }
  if (value === null && schemaTypes(schema).includes("null")) {
    return fieldControlId(path, "null");
  }
  const type = primaryType(schema, value);
  if (type === "object") {
    const properties = Object.entries(schema.properties ?? {});
    if (properties.length > 0) {
      const [key, childSchema] = properties[0];
      const childPath = [...path, key];
      return value && Object.hasOwn(value, key)
        ? firstControlId(childSchema, childPath, value[key])
        : fieldControlId(childPath, "add");
    }
    return fieldControlId(path, "add-key");
  }
  if (type === "array") {
    return Array.isArray(value) && value.length > 0
      ? firstControlId(schema.items ?? {}, [...path, 0], value[0])
      : fieldControlId(path, "add-item");
  }
  return fieldControlId(path);
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
    baselinePrompt: atom.prompt,
    prompt: atom.prompt,
    mode: "form",
    jsonText: "{}",
    jsonError: null,
    inputErrors: new Map(),
    presetRef: null,
    sourceRunId: null,
    promptSourceRef: null,
    promptSourceNeedsValidation: false,
    promptSourceDetached: false,
    promptOptions: null,
    promptTrial: null,
    validationRequested: false,
    arrayExpansion: new Map(),
    arraySummaries: [],
  };
  Object.defineProperty(session, "dirty", {
    enumerable: true,
    get() {
      return this.prompt !== this.baselinePrompt
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

export function describeModelOption(model) {
  let reasoningMode = "unknown";
  if (model.reasoning_supported === false) reasoningMode = "unsupported";
  else if (
    model.reasoning_supported === true
    && Array.isArray(model.allowed_reasoning_efforts)
  ) reasoningMode = "supported";
  return {
    modelId: model.model_id,
    selectable: model.compatibility === "compatible",
    compatibility: model.compatibility,
    reason: model.reason,
    reasoningMode,
    allowedEfforts: Array.isArray(model.allowed_reasoning_efforts)
      ? [...model.allowed_reasoning_efforts]
      : [],
  };
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.length > 0;
}

function isAtomId(value) {
  return ATOM_IDS.has(value);
}

function isNullableString(value) {
  return value === null || typeof value === "string";
}

function isNonNegativeInteger(value) {
  return Number.isInteger(value) && value >= 0;
}

function isNullableBoolean(value) {
  return value === null || typeof value === "boolean";
}

function isNullableReasoningEffort(value) {
  return value === null || REASONING_EFFORTS.has(value);
}

function isStringMap(value) {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "string");
}

function isModelCatalogItem(value) {
  return isRecord(value)
    && isNonEmptyString(value.model_id)
    && MODEL_COMPATIBILITIES.has(value.compatibility)
    && MODEL_REASONS.has(value.reason)
    && isNullableBoolean(value.reasoning_supported)
    && (value.allowed_reasoning_efforts === null
      || (Array.isArray(value.allowed_reasoning_efforts)
        && value.allowed_reasoning_efforts.every((effort) => REASONING_EFFORTS.has(effort))))
    && isRecord(value.provenance)
    && Object.values(value.provenance).every(isStringMap);
}

function parseModelCatalog(value) {
  if (
    !isRecord(value)
    || !Array.isArray(value.items)
    || !value.items.every(isModelCatalogItem)
    || !isNullableString(value.snapshot_id)
    || !isNullableString(value.last_success_at)
    || typeof value.stale !== "boolean"
    || !MODEL_REFRESH_STATUSES.has(value.refresh_status)
    || !isNullableString(value.error)
  ) return null;
  return value;
}

function parseModelRefresh(value) {
  if (
    !isRecord(value)
    || !isNullableString(value.snapshot_id)
    || !isNullableString(value.last_success_at)
    || typeof value.stale !== "boolean"
    || !MODEL_REFRESH_STATUSES.has(value.refresh_status)
    || !isNullableString(value.error)
  ) return null;
  return value;
}

function isProviderCallDiagnostic(value) {
  return isRecord(value)
    && isNonEmptyString(value.provider_call_id)
    && isNonEmptyString(value.action_run_id)
    && PROVIDER_CALL_STATUSES.has(value.status)
    && isNonNegativeInteger(value.semantic_attempt_index)
    && isNonNegativeInteger(value.transport_attempt_index)
    && isNonNegativeInteger(value.physical_call_index)
    && isNullableString(value.response_model_id)
    && isNullableString(value.error_code)
    && isNonNegativeInteger(value.latency_ms);
}

function isDebugArtifact(value) {
  return isRecord(value)
    && isNonEmptyString(value.artifact_id)
    && isNullableString(value.error_code)
    && isNullableString(value.raw_output_text)
    && typeof value.truncated === "boolean"
    && typeof value.redacted === "boolean";
}

export function pollingTimedOut(startedAt, now, timeoutMs) {
  return now - startedAt >= timeoutMs;
}

export function parseAcceptedRun(value) {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.run_id)
    || !isNonEmptyString(value.scenario_session_id)
    || !isNonEmptyString(value.job_id)
    || !RUN_STATUSES.has(value.status)
  ) return null;
  return {
    run_id: value.run_id,
    scenario_session_id: value.scenario_session_id,
    job_id: value.job_id,
    status: value.status,
  };
}

export function parseRunDetail(value, expectedRunId) {
  const diagnostics = value?.diagnostics;
  const runtimeIds = value?.runtime_ids;
  if (
    !isRecord(value)
    || value.run_id !== expectedRunId
    || !RUN_STATUSES.has(value.status)
    || !isRecord(value.snapshot)
    || !isAtomId(value.snapshot.atom_id)
    || !isRecord(runtimeIds)
    || !isNullableString(runtimeIds.scenario_session_id)
    || !isNullableString(runtimeIds.job_id)
    || !isNullableString(runtimeIds.action_run_id)
    || !isNullableString(runtimeIds.artifact_id)
    || !isRecord(diagnostics)
    || (value.result !== null && !isRecord(value.result) && !Array.isArray(value.result))
    || ((value.status === "succeeded") !== (value.result !== null))
    || !isNonEmptyString(value.created_at)
    || !isNullableString(value.started_at)
    || !isNullableString(value.finished_at)
    || !isNullableString(diagnostics.error_code)
    || !(diagnostics.duration_ms === null
      || (typeof diagnostics.duration_ms === "number" && diagnostics.duration_ms >= 0))
    || !isNonEmptyString(diagnostics.requested_model_id)
    || !isNullableReasoningEffort(diagnostics.requested_reasoning_effort)
    || !isNullableString(diagnostics.response_model_id)
    || !isNonNegativeInteger(diagnostics.validation_attempts)
    || !isNonNegativeInteger(diagnostics.transport_attempts)
    || !isNonNegativeInteger(diagnostics.physical_calls)
    || !isNullableBoolean(diagnostics.succeeded_first_attempt)
    || !Array.isArray(diagnostics.provider_calls)
    || !diagnostics.provider_calls.every(isProviderCallDiagnostic)
    || typeof diagnostics.provider_calls_truncated !== "boolean"
    || !Array.isArray(diagnostics.debug_artifacts)
    || !diagnostics.debug_artifacts.every(isDebugArtifact)
    || typeof diagnostics.debug_artifacts_truncated !== "boolean"
  ) return null;
  return {
    run_id: value.run_id,
    status: value.status,
    snapshot: value.snapshot,
    runtime_ids: value.runtime_ids,
    result: value.result,
    diagnostics: value.diagnostics,
    created_at: value.created_at,
    started_at: value.started_at,
    finished_at: value.finished_at,
  };
}

function isPositiveInteger(value) {
  return Number.isInteger(value) && value > 0;
}

function isPresetSummary(value) {
  return isRecord(value)
    && isNonEmptyString(value.preset_id)
    && isPositiveInteger(value.latest_version)
    && isNonEmptyString(value.name)
    && typeof value.description === "string"
    && isAtomId(value.atom_id)
    && isNonEmptyString(value.created_at)
    && isNonEmptyString(value.updated_at);
}

function isPresetVersionSummary(value) {
  return isRecord(value)
    && isNonEmptyString(value.preset_id)
    && isPositiveInteger(value.version)
    && isNonEmptyString(value.name)
    && typeof value.description === "string"
    && isAtomId(value.atom_id)
    && isNonEmptyString(value.created_at);
}

function isSchemaReference(value) {
  return isRecord(value)
    && isNonEmptyString(value.schema_ref)
    && isPositiveInteger(value.version);
}

export function presetContractMatchesAtom(configuration, atom) {
  const configuredSchemas = configuration?.schema_refs;
  const currentSchemas = atom?.schema_refs;
  return Boolean(
    isRecord(configuration)
    && isRecord(atom)
    && configuration.atom_id === atom.atom_id
    && configuration.base_action_config_id === atom.base_action_config_id
    && configuration.prompt_ref === atom.prompt_ref
    && isSchemaReference(configuredSchemas?.input)
    && isSchemaReference(configuredSchemas?.output)
    && configuredSchemas.input.schema_ref === currentSchemas?.input?.schema_ref
    && configuredSchemas.input.version === currentSchemas?.input?.version
    && configuredSchemas.output.schema_ref === currentSchemas?.output?.schema_ref
    && configuredSchemas.output.version === currentSchemas?.output?.version
  );
}

function historyPresetConfiguration(detail) {
  const snapshot = detail.snapshot;
  return {
    atom_id: snapshot.atom_id,
    base_action_config_id: snapshot.action?.config_id,
    schema_refs: {
      input: {schema_ref: snapshot.schemas?.input?.ref, version: snapshot.schemas?.input?.version},
      output: {schema_ref: snapshot.schemas?.output?.ref, version: snapshot.schemas?.output?.version},
    },
    prompt: snapshot.prompt?.content,
    prompt_ref: snapshot.prompt?.ref,
    prompt_source_ref: snapshot.prompt?.source_ref ?? null,
    model_id: snapshot.provider?.model_id,
    reasoning_effort: snapshot.provider?.reasoning_effort ?? null,
    example_input: snapshot.input,
    source_run_id: detail.run_id,
  };
}

export function parsePresetVersion(value, expectedPresetId = null, expectedVersion = null) {
  if (
    !isRecord(value)
    || !isNonEmptyString(value.preset_id)
    || (expectedPresetId !== null && value.preset_id !== expectedPresetId)
    || !isPositiveInteger(value.version)
    || (expectedVersion !== null && value.version !== expectedVersion)
    || !isNonEmptyString(value.name)
    || typeof value.description !== "string"
    || !isAtomId(value.atom_id)
    || !isNonEmptyString(value.base_action_config_id)
    || !isRecord(value.schema_refs)
    || !isSchemaReference(value.schema_refs.input)
    || !isSchemaReference(value.schema_refs.output)
    || !isNonEmptyString(value.prompt)
    || !isNonEmptyString(value.prompt_ref)
    || !isNonEmptyString(value.model_id)
    || !isNullableReasoningEffort(value.reasoning_effort)
    || !Array.isArray(value.fixed_fields)
    || !value.fixed_fields.every(isNonEmptyString)
    || new Set(value.fixed_fields).size !== value.fixed_fields.length
    || !isRecord(value.example_input)
    || !isNullableString(value.source_run_id)
    || !(value.prompt_source_ref === undefined || isNullableString(value.prompt_source_ref))
    || !isNonEmptyString(value.created_at)
  ) return null;
  return value;
}

function parsePage(value, itemParser) {
  if (
    !isRecord(value)
    || !Array.isArray(value.items)
    || !value.items.every(itemParser)
    || !(value.next_cursor === null || isNonEmptyString(value.next_cursor))
  ) return null;
  return value;
}

export function parsePresetList(value) {
  return parsePage(value, isPresetSummary);
}

export function parsePresetVersionList(value, expectedPresetId = null) {
  return parsePage(value, (item) => isPresetVersionSummary(item)
    && (expectedPresetId === null || item.preset_id === expectedPresetId));
}

function isRunSummary(value) {
  const hasPresetId = isNonEmptyString(value?.preset_id);
  const hasPresetVersion = isPositiveInteger(value?.preset_version);
  return isRecord(value)
    && isNonEmptyString(value.run_id)
    && RUN_STATUSES.has(value.status)
    && isAtomId(value.atom_id)
    && isNonEmptyString(value.model_id)
    && ((value.preset_id === null && value.preset_version === null)
      || (hasPresetId && hasPresetVersion))
    && isNonEmptyString(value.created_at)
    && isNullableString(value.started_at)
    && isNullableString(value.finished_at);
}

export function parseRunList(value) {
  return parsePage(value, isRunSummary);
}

export function parsePresetExport(value, presetId, version) {
  if (
    !isRecord(value)
    || value.format_version !== 1
    || value.preset_id !== presetId
    || value.version !== version
    || !isRecord(value.configuration)
  ) return null;
  const synthetic = {
    ...value.configuration,
    preset_id: presetId,
    version,
    created_at: "export",
  };
  return parsePresetVersion(synthetic, presetId, version) ? value : null;
}

export function createRunSubmission(session, {modelId, reasoningEffort, idempotencyKey}) {
  const input = getDraftPayload(session);
  const addressedModelId = modelId.startsWith("openai/") ? modelId : `openai/${modelId}`;
  const snapshot = {
    atom_id: session.atom.atom_id,
    input,
    prompt: session.prompt,
    ...(session.promptSourceRef ? {prompt_source_ref: session.promptSourceRef} : {}),
    model_id: addressedModelId,
    reasoning_effort: reasoningEffort,
  };
  return {
    idempotencyKey,
    snapshot: cloneJson(snapshot),
    body: {...cloneJson(snapshot), preset_ref: cloneJson(session.presetRef)},
  };
}

function clearInputErrorsAtOrBelow(session, path) {
  for (const [key, error] of session.inputErrors) {
    if (pathStartsWith(error.path, path)) session.inputErrors.delete(key);
  }
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
  clearInputErrorsAtOrBelow(session, path);
}

function pathStartsWith(path, prefix) {
  return prefix.every((segment, index) => path[index] === segment);
}

function reconcileInputErrorsAfterOmit(session, path, removedArrayItem) {
  const nextErrors = new Map();
  const parentPath = path.slice(0, -1);
  const removedIndex = path.at(-1);
  for (const error of session.inputErrors.values()) {
    if (pathStartsWith(error.path, path)) continue;
    let nextPath = error.path;
    if (
      removedArrayItem
      && pathStartsWith(error.path, parentPath)
      && typeof error.path[parentPath.length] === "number"
      && error.path[parentPath.length] > removedIndex
    ) {
      nextPath = [...error.path];
      nextPath[parentPath.length] -= 1;
    }
    nextErrors.set(fieldKey(nextPath), {path: nextPath, message: error.message});
  }
  session.inputErrors = nextErrors;
}

function rebaseInputErrors(session, fromPath, toPath) {
  const nextErrors = new Map();
  for (const error of session.inputErrors.values()) {
    const nextPath = pathStartsWith(error.path, fromPath)
      ? [...toPath, ...error.path.slice(fromPath.length)]
      : error.path;
    nextErrors.set(fieldKey(nextPath), {path: nextPath, message: error.message});
  }
  session.inputErrors = nextErrors;
}

function setInputError(session, path, message) {
  session.inputErrors.set(fieldKey(path), {path: [...path], message});
}

export function omitDraftPath(session, path) {
  if (path.length === 0) {
    session.payload = {};
    session.inputErrors.clear();
    return;
  }
  const parent = resolveParent(session.payload, path, false);
  if (parent === null) return;
  const removedArrayItem = Array.isArray(parent) && typeof path.at(-1) === "number";
  if (removedArrayItem) {
    parent.splice(path.at(-1), 1);
  } else {
    delete parent[path.at(-1)];
  }
  reconcileInputErrorsAfterOmit(session, path, removedArrayItem);
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

function jsonNumberTokens(text) {
  const tokens = [];
  let inString = false;
  let escaped = false;
  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (character === "\\") escaped = true;
      else if (character === '"') inString = false;
      continue;
    }
    if (character === '"') {
      inString = true;
      continue;
    }
    if (character !== "-" && (character < "0" || character > "9")) continue;
    const match = text.slice(index).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (!match) continue;
    tokens.push(match[0]);
    index += match[0].length - 1;
  }
  return tokens;
}

function normalizedDecimal(text) {
  let source = text.toLowerCase();
  let sign = 1n;
  if (source.startsWith("-")) {
    sign = -1n;
    source = source.slice(1);
  }
  const [mantissa, exponentText = "0"] = source.split("e");
  const [whole, fraction = ""] = mantissa.split(".");
  let digits = `${whole}${fraction}`.replace(/^0+/, "") || "0";
  let exponent = Number(exponentText) - fraction.length;
  if (digits === "0") return {coefficient: 0n, exponent: 0};
  while (digits.endsWith("0")) {
    digits = digits.slice(0, -1);
    exponent += 1;
  }
  return {coefficient: sign * BigInt(digits), exponent};
}

function numberRoundTrips(token) {
  const value = Number(token);
  if (!Number.isFinite(value)) return false;
  const original = normalizedDecimal(token);
  const serialized = normalizedDecimal(JSON.stringify(value));
  return original.coefficient === serialized.coefficient && original.exponent === serialized.exponent;
}

function hasNonRoundTrippableNumber(text) {
  return jsonNumberTokens(text).some((token) => !numberRoundTrips(token));
}

const NUMBER_PRECISION_ERROR = "Число нельзя сохранить без потери точности.";

export function applyJsonText(session, text) {
  session.jsonText = text;
  try {
    const parsed = JSON.parse(text);
    if (hasNonRoundTrippableNumber(text)) {
      session.jsonError = "JSON содержит число, которое браузер не может сохранить без потери точности.";
      return false;
    }
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
  const error = {path: pathLabel(path), message};
  Object.defineProperty(error, "key", {value: fieldKey(path)});
  errors.push(error);
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
  for (const error of session.inputErrors.values()) {
    validationError(errors, error.path, error.message);
  }
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

function clearValidationPresentation(document, container, session) {
  for (const [controlId, previous] of session.validationAttributes ?? []) {
    const control = document.getElementById?.(controlId);
    if (!control) continue;
    if (previous.ariaInvalid === null) control.removeAttribute("aria-invalid");
    else control.setAttribute("aria-invalid", previous.ariaInvalid);
    if (previous.ariaDescribedBy === null) control.removeAttribute("aria-describedby");
    else control.setAttribute("aria-describedby", previous.ariaDescribedBy);
  }
  session.validationAttributes = new Map();
  container.replaceChildren();
}

function openControlDetails(control) {
  for (let parent = control?.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === "DETAILS") parent.open = true;
  }
}

function focusEditorControl(document, control) {
  if (!control) return;
  for (const tab of ["input", "prompt"]) {
    if (control.closest?.(`#${tab}-panel`)?.hidden) document.getElementById(`${tab}-tab`).click();
  }
  openControlDetails(control);
  control.focus();
}

function renderValidation(document, container, session, admissionErrors = []) {
  clearValidationPresentation(document, container, session);
  session.validationRequested ||= session.dirty;
  if (!session.validationRequested && Object.keys(session.payload).length === 0
    && !session.jsonError && session.inputErrors.size === 0 && admissionErrors.length === 0) return;
  const errors = [...validateDraft(session), ...admissionErrors];
  if (errors.length === 0) return;
  const heading = document.createElement("p");
  heading.textContent = "Исправьте поля:";
  const list = document.createElement("ul");
  for (const error of errors) {
    const item = document.createElement("li");
    const errorId = controlIdForKey(error.key ?? error.path, "error");
    item.id = errorId;
    const control = typeof document.getElementById === "function"
      ? document.getElementById(error.controlId ?? (session.mode === "json"
        ? "json-editor" : controlIdForKey(error.key ?? error.path)))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "type"))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "add"))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "add-item"))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "add-key"))
      : null;
    if (control) {
      openControlDetails(control);
      if (!session.validationAttributes.has(control.id)) {
        session.validationAttributes.set(control.id, {
          ariaInvalid: control.getAttribute?.("aria-invalid") ?? null,
          ariaDescribedBy: control.getAttribute?.("aria-describedby") ?? null,
        });
      }
      control.setAttribute("aria-invalid", "true");
      const descriptions = [control.getAttribute?.("aria-describedby"), errorId].filter(Boolean);
      control.setAttribute("aria-describedby", [...new Set(descriptions)].join(" "));
      const link = button(document, `${error.path}: ${error.message}`, () => focusEditorControl(document, control));
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
  input.addEventListener("change", () => {
    try {
      const parsed = JSON.parse(input.value);
      if (hasNonRoundTrippableNumber(input.value)) throw new Error("Inexact JSON number");
      setDraftPath(session, path, parsed);
      rerender(true, input.id);
    } catch {
      setInputError(session, path, "Введите корректное JSON-значение.");
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
    const input = document.createElement(kind === "string" ? "textarea" : "input");
    input.id = fieldControlId(path);
    if (kind === "number") input.type = "number";
    else input.rows = 2;
    input.value = String(value);
    input.setAttribute("aria-label", label);
    input.addEventListener("input", () => {
      if (kind === "string") {
        setDraftPath(session, path, input.value);
      } else if (input.value !== "" && Number.isFinite(Number(input.value))) {
        if (numberRoundTrips(input.value)) {
          setDraftPath(session, path, Number(input.value));
        } else {
          setInputError(session, path, NUMBER_PRECISION_ERROR);
        }
      } else {
        setInputError(session, path, "Введите корректное число.");
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
  const value = valueAtPath(session.payload, path);
  const type = primaryType(schema, value);
  const compound = type === "object" || type === "array";
  const heading = document.createElement("div");
  heading.className = "field-heading";
  const title = document.createElement(exists && !compound ? "label" : "strong");
  if (exists && !compound) title.htmlFor = firstControlId(schema, path, value);
  title.textContent = label;
  if (required && typeof path.at(-1) !== "number" && type !== "boolean") {
    const mark = document.createElement("span");
    mark.className = "required-mark";
    mark.textContent = " *";
    title.append(mark);
  }
  heading.append(title);
  if (!exists) {
    const addButton = button(document, `Добавить поле «${label}»`, () => {
      const valueToAdd = initialValue(schema);
      setDraftPath(session, path, valueToAdd);
      rerender(true, firstControlId(schema, path, valueToAdd));
    });
    addButton.id = fieldControlId(path, "add");
    heading.append(addButton);
    wrapper.append(heading);
    container.append(wrapper);
    return heading;
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
  const descriptionText = session.atom.atom_id === "A01" && path.length === 1 && path[0] === "strict"
    ? "При включении все поля с required=true должны быть найдены. Если их нет, ответ не пройдёт проверку. При выключении допустим частичный результат с missing_fields."
    : schema.description;
  if (descriptionText) {
    const description = document.createElement("p");
    description.id = fieldControlId(path, "description");
    description.className = "field-description";
    description.textContent = descriptionText;
    wrapper.append(description);
  }
  if (schemaTypes(schema).length === 0 && !Array.isArray(schema.enum)) {
    renderUntyped(context, wrapper, path, label, value);
    container.append(wrapper);
    return heading;
  }
  const allowsNull = schemaTypes(schema).includes("null");
  if (allowsNull) {
    const nullLabel = document.createElement("label");
    const nullInput = document.createElement("input");
    nullInput.id = fieldControlId(path, "null");
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
      return heading;
    }
  }
  if (!matchesDeclaredType(value, schema)) {
    appendRecoverableJson(context, wrapper, path, label, value);
    container.append(wrapper);
    return heading;
  }
  if (type === "object") {
    renderObject(context, wrapper, schema, path, value);
  } else if (type === "array") {
    renderArray(context, wrapper, schema, path, value);
  } else if (Array.isArray(schema.enum)) {
    if (required && !allowsNull) wrapper.classList.add("schema-inline");
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
    if (!allowsNull) wrapper.classList.add("schema-boolean");
    const input = document.createElement("input");
    input.id = fieldControlId(path);
    input.type = "checkbox";
    input.checked = value;
    input.setAttribute("aria-label", label);
    if (descriptionText) input.setAttribute("aria-describedby", fieldControlId(path, "description"));
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
        if (numberRoundTrips(input.value)) {
          setDraftPath(session, path, parsed);
        } else {
          setInputError(session, path, NUMBER_PRECISION_ERROR);
        }
      } else {
        setInputError(
          session,
          path,
          isInteger ? "Значение должно быть целым числом." : "Введите корректное число.",
        );
      }
      rerender(false);
    });
    wrapper.append(input);
  } else if (type === "string") {
    const input = document.createElement("textarea");
    input.id = fieldControlId(path);
    input.rows = schema.pattern ? 1 : 2;
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
  return heading;
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
      if (!allowsDynamic || nextKey === key) return;
      if (Object.hasOwn(value, nextKey)) {
        keyInput.value = key;
        return;
      }
      defineOwn(value, nextKey, value[key]);
      delete value[key];
      rebaseInputErrors(session, [...path, key], [...path, nextKey]);
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
      rerender(true, firstControlId(
        dynamicSchema,
        [...path, `key_${index}`],
        value[`key_${index}`],
      ));
    });
    addKeyButton.id = fieldControlId(path, "add-key");
    container.append(addKeyButton);
  }
}

function renderArray(context, container, schema, path, value) {
  const {document, session, rerender} = context;
  value.forEach((item, index) => {
    const itemPath = [...path, index];
    const collapsible = isRecord(item) && primaryType(schema.items ?? {}, item) === "object";
    const row = document.createElement(collapsible ? "details" : "div");
    row.className = collapsible ? "array-item array-item-object" : "array-item";
    if (collapsible) {
      const summary = document.createElement("summary");
      row.open = session.arrayExpansion.get(fieldKey(itemPath)) ?? false;
      row.addEventListener("toggle", () => session.arrayExpansion.set(fieldKey(itemPath), row.open));
      session.arraySummaries.push(() => {
        const current = valueAtPath(session.payload, itemPath);
        const name = document.createElement("code");
        name.textContent = typeof current?.name === "string" && current.name
          ? current.name : typeof current?.id === "string" && current.id ? current.id : `Элемент ${index + 1}`;
        const metadata = document.createElement("span");
        metadata.className = "array-item-meta";
        metadata.textContent = [
          typeof current?.type === "string" ? current.type : "",
          typeof current?.required === "boolean" ? current.required ? "обязательное" : "необязательное" : "",
        ].filter(Boolean).join(" · ");
        summary.replaceChildren(name, metadata);
      });
      row.append(summary);
    }
    const heading = renderField(
      context, row, schema.items ?? {}, [...path, index], `Элемент ${index + 1}`, true,
    );
    const removeButton = button(document, `Удалить элемент ${index + 1}`, () => {
      omitDraftPath(session, [...path, index]);
      const nextIndex = Math.min(index, value.length - 1);
      const focusId = value.length > 0
        ? firstControlId(schema.items ?? {}, [...path, nextIndex], value[nextIndex])
        : fieldControlId(path, "add-item");
      rerender(true, focusId);
    });
    removeButton.className = "remove-array-item";
    heading.append(removeButton);
    container.append(row);
  });
  const addItemButton = button(document, "Добавить элемент", () => {
    const index = value.length;
    const valueToAdd = initialValue(schema.items ?? {});
    value.push(valueToAdd);
    rerender(true, firstControlId(schema.items ?? {}, [...path, index], valueToAdd));
  });
  addItemButton.id = fieldControlId(path, "add-item");
  container.append(addItemButton);
}

function requiredNode(document, selector) {
  const node = document.querySelector(selector);
  if (!node) throw new Error(`Atom Lab node is missing: ${selector}`);
  return node;
}

function safeApiMessage(payload, fallback) {
  return typeof payload?.error?.message === "string" ? payload.error.message : fallback;
}

function parseAtomLabError(payload) {
  if (
    !isRecord(payload)
    || !isRecord(payload.error)
    || !isNonEmptyString(payload.error.code)
    || !isNonEmptyString(payload.error.message)
    || !Array.isArray(payload.error.field_errors)
    || !payload.error.field_errors.every((fieldError) => (
      isRecord(fieldError)
      && isNonEmptyString(fieldError.path)
      && isNonEmptyString(fieldError.message)
    ))
  ) return null;
  return {
    code: payload.error.code,
    message: payload.error.message,
    fieldErrors: payload.error.field_errors,
  };
}

function renderContractFields(document, container, schema) {
  const required = new Set(schema.required ?? []);
  const requiredList = document.createElement("ul");
  requiredList.className = "contract-field-list contract-field-list-required";
  const optionalList = document.createElement("ul");
  optionalList.className = "contract-field-list";
  for (const key of Object.keys(schema.properties ?? {})) {
    const item = document.createElement("li");
    const name = document.createElement("code");
    name.textContent = key;
    item.append(name);
    if (required.has(key)) {
      requiredList.append(item);
    } else {
      const marker = document.createElement("span");
      marker.className = "contract-optional";
      marker.textContent = " опционально";
      item.append(marker);
      optionalList.append(item);
    }
  }
  container.replaceChildren(requiredList, optionalList);
  if (requiredList.children.length + optionalList.children.length === 0) {
    const hint = document.createElement("p");
    hint.className = "help-text";
    hint.textContent = "См. полную JSON Schema.";
    container.replaceChildren(hint);
  }
}

function renderReadableResult(document, container, value) {
  container.replaceChildren();
  if (value === null || typeof value !== "object") {
    const text = document.createElement("p");
    text.textContent = value === null ? "null" : String(value);
    container.append(text);
    return;
  }
  const list = document.createElement("dl");
  for (const [key, item] of Object.entries(value)) {
    const term = document.createElement("dt");
    term.className = "result-key";
    term.textContent = key;
    const description = document.createElement("dd");
    if (typeof item !== "string") description.className = "result-structured-value";
    description.textContent = typeof item === "string" ? item : JSON.stringify(item, null, 2);
    list.append(term, description);
  }
  container.append(list);
}

function formatLabDate(value) {
  const date = new Date(value);
  return Number.isFinite(date.getTime())
    ? date.toLocaleString("ru-RU", {dateStyle: "medium", timeStyle: "medium"})
    : value;
}

function formatDuration(milliseconds) {
  return milliseconds === null ? "—"
    : milliseconds >= 1000
      ? `${(milliseconds / 1000).toLocaleString("ru-RU", {maximumFractionDigits: 2})} с (${milliseconds} мс)`
      : `${milliseconds} мс`;
}

function renderFacts(document, container, rows) {
  container.replaceChildren();
  for (const [label, value] of rows) {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = String(value);
    row.append(term, description);
    container.append(row);
  }
}

function renderRunMetadata(document, container, diagnostics) {
  const groups = [
    ["Модель и reasoning", [
      ["Запрошенная модель", diagnostics.requested_model_id],
      ["Модель в ответе", diagnostics.response_model_id ?? "Неизвестна"],
      ["Reasoning", diagnostics.requested_reasoning_effort ?? "Не запрошен"],
    ]],
    ["Время и попытки", [
      ["Длительность", formatDuration(diagnostics.duration_ms)],
      ["Проверок ответа", diagnostics.validation_attempts],
      ["Попыток отправки", diagnostics.transport_attempts],
      ["Вызовов провайдера", diagnostics.physical_calls],
    ]],
  ];
  container.replaceChildren();
  for (const [title, rows] of groups) {
    const group = document.createElement("section");
    group.className = "metadata-group";
    const heading = document.createElement("h4");
    heading.textContent = title;
    const list = document.createElement("dl");
    renderFacts(document, list, rows);
    group.append(heading, list);
    container.append(group);
  }
}

function modelReasonText(option) {
  if (option.reasoningMode === "unsupported") {
    return "Эта модель не поддерживает reasoning для текущего пути.";
  }
  if (option.reasoningMode === "unknown") {
    return "Поддерживаемые уровни reasoning неизвестны; запуск будет без effort.";
  }
  return "Доступны только подтверждённые каталогом уровни reasoning.";
}

export function bootstrapAtomLab({
  document,
  fetchImpl,
  confirmImpl,
  scheduleImpl = (callback, delay) => globalThis.setTimeout(callback, delay),
  cancelScheduleImpl = (id) => globalThis.clearTimeout(id),
  AbortControllerImpl = globalThis.AbortController,
  lifecycleTarget = globalThis,
  nowImpl = () => Date.now(),
  pollTimeoutMs = RUN_POLL_TIMEOUT_MS,
  catalogLoadTimeoutMs = 30_000,
  catalogRefreshTimeoutMs = 30_000,
  submissionTimeoutMs = 30_000,
  protectedRequestTimeoutMs = 30_000,
  idempotencyKeyFactory = () => globalThis.crypto?.randomUUID?.()
    ?? `run-${Date.now()}-${Math.random().toString(16).slice(2)}`,
}) {
  const nodes = Object.fromEntries([
    "access-form", "access-code", "access-panel", "workspace", "status", "atom-navigation", "atom-count",
    "atom-title", "atom-action-type", "atom-description", "input-schema",
    "input-contract-label", "output-contract-label", "input-contract-fields", "output-contract-fields",
    "input-schema-ref", "output-schema-ref", "input-schema-version", "output-schema-version",
    "output-schema", "input-tab", "prompt-tab", "input-panel", "prompt-panel", "form-mode",
    "json-mode", "input-editor", "json-panel", "json-editor", "json-error", "prompt-editor",
    "prompt-select", "prompt-origin", "prompt-load-status", "retry-prompts", "prompt-tab-state",
    "prompt-test-status", "run-prompt-ref", "run-prompt-state", "save-prompt-panel",
    "save-prompt-form", "save-prompt-name", "save-prompt", "save-prompt-status",
    "fill-example", "reset-prompt", "draft-state", "validation-errors", "presets-button",
    "history-button", "model-select", "reasoning-effort", "reasoning-help",
    "model-catalog-warning", "refresh-models", "run-button", "retry-submit", "retry-read", "run-state",
    "launch-readiness", "response-draft-warning",
    "run-status", "run-status-help", "result-caption", "run-metadata-section", "run-technical",
    "submitted-snapshot", "result-section", "result-readable", "result-json",
    "invalid-response", "invalid-response-code", "invalid-response-raw", "run-metadata",
    "run-diagnostics", "presets-panel", "close-presets", "preset-list", "load-more-presets",
    "preset-name", "preset-description", "fixed-fields", "preset-version-select", "new-preset",
    "load-more-versions",
    "save-preset", "export-preset", "preset-state", "preset-error", "preset-export",
    "preset-export-download",
    "preset-conflict", "open-latest-preset", "save-as-new-preset", "history-panel",
    "preset-compatibility", "adapt-preset", "preset-readonly",
    "close-history", "history-list", "load-more-history", "history-warning", "history-detail",
    "restore-history", "save-history-preset", "history-error",
    "workbench-button", "atom-sidebar", "atom-passport", "run-controls", "request-response",
    "preset-empty", "preset-heading", "preset-selected-name", "preset-context",
    "preset-view-description", "preset-view-actions", "preset-editor-form", "preset-editor-title",
    "preset-source", "apply-preset", "edit-preset", "cancel-preset", "preset-configuration",
    "preset-config-metadata", "preset-input-fields", "preset-input-json", "preset-prompt",
    "preset-technical", "preset-list-state", "history-context", "history-list-state",
    "history-record", "history-created", "history-detail-title", "collapse-history",
    "history-status", "history-status-text", "history-status-help", "history-summary",
    "history-result-tab", "history-request-tab", "history-diagnostics-tab",
    "history-result-panel", "history-request-panel", "history-diagnostics-panel",
    "history-result-readable", "history-result-message", "history-result-json",
    "history-invalid", "history-invalid-code", "history-invalid-raw", "history-input-json",
    "history-prompt", "history-snapshot", "history-metadata", "history-diagnostics-json", "history-runtime-json",
  ].map((id) => [id, requiredNode(document, `#${id}`)]));
  const accessCodeRequired = nodes["access-panel"].dataset.autoOpen !== "true";
  let accessCode = "";
  let catalog = [];
  let session = null;
  let selectedAtomId = null;
  let modelCatalog = null;
  let modelCatalogRefreshStatus = null;
  let modelCatalogReadGeneration = 0;
  let modelOptions = [];
  let activeSubmission = null;
  let displayedSubmission = null;
  let submitInFlight = false;
  let modelCatalogPollTimer = null;
  let modelCatalogPollStartedAt = null;
  let modelCatalogPollFailures = 0;
  let runPollTimer = null;
  let activeModelCatalogAbortController = null;
  let activeModelCatalogReadTimeoutId = null;
  let activeModelRefreshAbortController = null;
  let activeModelRefreshTimeoutId = null;
  let modelCatalogReloadPending = false;
  let activeRunAbortController = null;
  let activeSubmissionAbortController = null;
  let admissionErrors = [];
  let presetItems = [];
  let presetCursor = null;
  let selectedPresetSummary = null;
  let selectedPresetVersion = null;
  let presetVersions = [];
  let presetVersionsCursor = null;
  let presetDraftBaseline = null;
  let presetEditorActive = false;
  let presetLibraryLoading = false;
  let presetOpenInFlight = false;
  let presetOpenGeneration = 0;
  let presetReadOnly = false;
  let presetSaveInFlight = false;
  let presetExportGeneration = 0;
  let presetListLoadGeneration = 0;
  let presetListLoadInFlight = false;
  let presetVersionPageGeneration = 0;
  let presetVersionPageInFlight = false;
  let conflictLatestPreset = null;
  let presetSaveOutcomeUnknown = null;
  let historyItems = [];
  let historyCursor = null;
  let historyListLoadGeneration = 0;
  let historyListLoadInFlight = false;
  let selectedHistoryDetail = null;
  let selectedHistoryCompatible = false;
  let historyOpenGeneration = 0;
  let historyOpenInFlight = false;
  let restoredHistoryDraft = false;
  let presetSourceOverride = null;
  let paused = false;
  let destroyed = false;

  const showLibrary = (section = null) => {
    nodes["presets-panel"].hidden = section !== "presets";
    nodes["history-panel"].hidden = section !== "history";
    nodes.workspace.dataset.library = section ?? "";
    for (const id of ["atom-sidebar", "atom-passport", "run-controls", "request-response"]) {
      nodes[id].hidden = section !== null;
    }
    for (const [id, view] of [["workbench-button", null], ["presets-button", "presets"], ["history-button", "history"]]) {
      if (section === view) nodes[id].setAttribute("aria-current", "page");
      else nodes[id].removeAttribute("aria-current");
    }
  };

  const presetHasUnsavedDraft = () => Boolean(
    !presetReadOnly
    && presetEditorActive
    && presetDraftBaseline !== null
    && presetFingerprint(currentPresetPayload()) !== presetDraftBaseline
  );

  const hasUnsavedDraft = () => Boolean(
    session?.dirty
    || restoredHistoryDraft
    || presetHasUnsavedDraft(),
  );

  const updateRunButton = () => {
    const option = selectedModelOption();
    const effort = nodes["reasoning-effort"].value;
    const hasValidSelection = Boolean(option?.selectable)
      && (effort === "" || option.allowedEfforts.includes(effort));
    const submissionBlocksNewRun = Boolean(activeSubmission && (
      !activeSubmission.runId || !activeSubmission.terminal
    ));
    nodes["run-button"].disabled = submitInFlight || !hasValidSelection || submissionBlocksNewRun
      || Boolean(session?.promptSourceNeedsValidation);
    nodes["launch-readiness"].textContent = submitInFlight
      ? "Отправка запроса…"
      : submissionBlocksNewRun
        ? activeSubmission.runId ? "Ожидаем завершения принятого запуска" : "Ожидаем подтверждения приёма запроса"
        : session?.promptSourceNeedsValidation
          ? "Проверьте источник промпта во вкладке «Промпт»"
          : !hasValidSelection
            ? "Выберите модель и доступный reasoning"
            : session && (validateDraft(session).length > 0 || !session.prompt.trim() || admissionErrors.length > 0)
              ? "Проверьте входные данные и промпт"
              : "Черновик готов к запуску";
    if (session) {
      renderPromptStatus();
      nodes["response-draft-warning"].hidden = !displayedSubmission
        || matchesDraftSnapshot(displayedSubmission.snapshot);
    }
  };

  const selectedModelOption = () => modelOptions.find(
    (option) => option.modelId === nodes["model-select"].value,
  ) ?? null;

  const renderModelCatalogWarning = (selectionInvalidated = false) => {
    const lastSuccess = modelCatalog?.stale && modelCatalog.last_success_at
      ? ` Последнее успешное обновление: ${modelCatalog.last_success_at}.`
      : "";
    nodes["model-catalog-warning"].textContent = selectionInvalidated
      ? `Выбранная модель больше недоступна. Выберите модель заново.${lastSuccess}`
      : modelCatalog?.stale
        ? `Каталог моделей устарел.${lastSuccess}${modelCatalog.error ? ` ${modelCatalog.error}` : ""}`
        : "";
  };

  const showModelCatalogFailure = (message) => {
    if (!modelCatalog) {
      nodes["model-catalog-warning"].textContent = message;
      return;
    }
    modelCatalog = {...modelCatalog, stale: true, error: message};
    const selectionInvalidated = Boolean(nodes["model-select"].value)
      && selectedModelOption()?.selectable !== true;
    renderModelCatalogWarning(selectionInvalidated);
  };

  const admissionErrorAppliesToDraft = (path, submission) => {
    if (session.atom.atom_id !== submission.body.atom_id) return false;
    if (path === "model_id") {
      const modelId = nodes["model-select"].value;
      const addressedModelId = modelId.startsWith("openai/") ? modelId : `openai/${modelId}`;
      return addressedModelId === submission.body.model_id;
    }
    if (path === "reasoning_effort") {
      return (nodes["reasoning-effort"].value || null) === submission.body.reasoning_effort;
    }
    if (path === "input" || path.startsWith("input.") || path.startsWith("input[")) {
      return sameJson(getDraftPayload(session), submission.body.input);
    }
    if (path === "prompt") return session.prompt === submission.body.prompt;
    return false;
  };

  const refreshAdmissionValidation = () => {
    if (!session) return;
    admissionErrors = admissionErrors.filter(({path, submission}) => (
      submission && admissionErrorAppliesToDraft(path, submission)
    ));
    renderValidation(document, nodes["validation-errors"], session, admissionErrors);
  };

  const renderSelectedHistoryWarning = () => {
    if (!selectedHistoryDetail) return;
    const modelId = selectedHistoryDetail.snapshot.provider?.model_id;
    const rawModelId = modelId?.startsWith("openai/") ? modelId.slice("openai/".length) : modelId;
    const modelAvailable = modelOptions.some((item) => item.modelId === rawModelId && item.selectable);
    nodes["history-warning"].textContent = !selectedHistoryCompatible
      ? "Исторический контракт недоступен. Снимок доступен только для чтения; восстановление требует явной адаптации к текущему контракту."
      : !modelAvailable
        ? "Историческая модель недоступна. Снимок можно восстановить, но перед запуском нужно явно выбрать модель."
        : "";
  };

  const renderReasoning = (preferredEffort = "") => {
    const option = selectedModelOption();
    nodes["reasoning-effort"].replaceChildren();
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "Не задавать";
    nodes["reasoning-effort"].append(none);
    for (const effort of option?.allowedEfforts ?? []) {
      const item = document.createElement("option");
      item.value = effort;
      item.textContent = effort;
      nodes["reasoning-effort"].append(item);
    }
    const effortRemainsAllowed = option?.allowedEfforts.includes(preferredEffort);
    if (preferredEffort && !effortRemainsAllowed) {
      const invalidated = document.createElement("option");
      invalidated.value = preferredEffort;
      invalidated.textContent = `${preferredEffort} — больше не поддерживается`;
      invalidated.disabled = true;
      nodes["reasoning-effort"].append(invalidated);
    }
    nodes["reasoning-effort"].value = effortRemainsAllowed || preferredEffort ? preferredEffort : "";
    nodes["reasoning-effort"].disabled = option?.reasoningMode !== "supported"
      && !(preferredEffort && !effortRemainsAllowed);
    nodes["reasoning-help"].textContent = option ? modelReasonText(option) : "Выберите модель.";
    if (preferredEffort && !effortRemainsAllowed) {
      nodes["reasoning-help"].textContent = "Выбранный reasoning effort больше не поддерживается. Выберите effort заново.";
    }
    updateRunButton();
    refreshAdmissionValidation();
  };

  const renderModelCatalog = () => {
    const previousModelId = nodes["model-select"].value;
    const previousReasoningEffort = nodes["reasoning-effort"].value;
    nodes["model-select"].replaceChildren();
    for (const option of modelOptions) {
      const item = document.createElement("option");
      item.value = option.modelId;
      item.textContent = option.selectable ? option.modelId
        : option.compatibility === "unknown"
          ? `${option.modelId} — совместимость неизвестна (${option.reason})`
          : `${option.modelId} — не поддерживается (${option.reason})`;
      item.disabled = !option.selectable;
      nodes["model-select"].append(item);
    }
    const first = modelOptions.find((option) => option.selectable);
    const previous = modelOptions.find((option) => option.modelId === previousModelId);
    const previousRemainsSelectable = previous?.selectable === true;
    const selectionInvalidated = Boolean(previousModelId) && !previousRemainsSelectable;
    if (selectionInvalidated && !previous) {
      const invalidated = document.createElement("option");
      invalidated.value = previousModelId;
      invalidated.textContent = `${previousModelId} — больше не доступна`;
      invalidated.disabled = true;
      invalidated.dataset.modelUnavailablePlaceholder = "true";
      nodes["model-select"].append(invalidated);
    }
    const selected = previousRemainsSelectable ? previous : selectionInvalidated ? null : first;
    const selectedModelId = selected?.modelId ?? (selectionInvalidated ? previousModelId : "");
    nodes["model-select"].value = selectedModelId;
    nodes["model-select"].disabled = !first;
    renderModelCatalogWarning(selectionInvalidated);
    renderReasoning(previousModelId && selectedModelId === previousModelId ? previousReasoningEffort : "");
    renderSelectedHistoryWarning();
  };

  const loadModels = async ({timeoutMs = catalogLoadTimeoutMs} = {}) => {
    const generation = modelCatalogReadGeneration + 1;
    modelCatalogReadGeneration = generation;
    const controller = timeoutMs === null ? null : new AbortControllerImpl();
    let timedOut = false;
    const timeoutId = controller === null ? null : scheduleImpl(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    if (controller) {
      activeModelCatalogAbortController = controller;
      activeModelCatalogReadTimeoutId = timeoutId;
    }
    try {
      const response = await fetchImpl("/v1/atom-lab/models", {
        headers: {[ACCESS_HEADER]: accessCode},
        ...(controller ? {signal: controller.signal} : {}),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(safeApiMessage(payload, "Каталог моделей недоступен."));
      const parsedCatalog = parseModelCatalog(payload);
      if (!parsedCatalog) {
        throw new Error("Каталог моделей вернул некорректный ответ.");
      }
      if (generation !== modelCatalogReadGeneration) return null;
      modelCatalog = parsedCatalog;
      modelCatalogRefreshStatus = parsedCatalog.refresh_status;
      modelOptions = parsedCatalog.items.map(describeModelOption);
      renderModelCatalog();
      return true;
    } catch (error) {
      if (generation !== modelCatalogReadGeneration) return null;
      if (error?.name === "AbortError" && (destroyed || paused)) return null;
      const readTimedOut = error?.name === "AbortError" && timedOut;
      const message = readTimedOut
        ? "Время ожидания каталога моделей истекло."
        : error instanceof Error
        ? error.message
        : "Каталог моделей недоступен.";
      if (modelCatalog) {
        modelCatalog = {...modelCatalog, stale: true, error: message};
        renderModelCatalog();
        return readTimedOut ? "timed_out" : false;
      }
      modelCatalog = null;
      modelOptions = [];
      nodes["model-select"].replaceChildren();
      nodes["model-select"].disabled = true;
      nodes["reasoning-effort"].disabled = true;
      nodes["run-button"].disabled = true;
      nodes["model-catalog-warning"].textContent = message;
      renderSelectedHistoryWarning();
      return readTimedOut ? "timed_out" : false;
    } finally {
      if (timeoutId !== null) cancelScheduleImpl(timeoutId);
      if (activeModelCatalogAbortController === controller) activeModelCatalogAbortController = null;
      if (activeModelCatalogReadTimeoutId === timeoutId) activeModelCatalogReadTimeoutId = null;
    }
  };

  const stopModelCatalogPolling = ({preserveDeadline = false} = {}) => {
    if (modelCatalogPollTimer !== null) cancelScheduleImpl(modelCatalogPollTimer);
    if (activeModelCatalogReadTimeoutId !== null) cancelScheduleImpl(activeModelCatalogReadTimeoutId);
    activeModelCatalogReadTimeoutId = null;
    activeModelCatalogAbortController?.abort();
    activeModelCatalogAbortController = null;
    modelCatalogPollTimer = null;
    if (!preserveDeadline) modelCatalogPollStartedAt = null;
    modelCatalogPollFailures = 0;
  };

  const pollModelCatalog = async () => {
    modelCatalogPollTimer = null;
    if (destroyed || paused) return;
    if (pollingTimedOut(modelCatalogPollStartedAt, nowImpl(), pollTimeoutMs)) {
      showModelCatalogFailure("Время ожидания обновления каталога истекло.");
      stopModelCatalogPolling();
      return;
    }
    const remainingBeforeRead = pollTimeoutMs - (nowImpl() - modelCatalogPollStartedAt);
    const loaded = await loadModels({timeoutMs: remainingBeforeRead});
    if (loaded === null) return;
    if (loaded === "timed_out") {
      stopModelCatalogPolling();
      return;
    }
    if (destroyed || paused || (loaded && !["pending", "running"].includes(modelCatalog?.refresh_status))) {
      stopModelCatalogPolling();
      return;
    }
    if (pollingTimedOut(modelCatalogPollStartedAt, nowImpl(), pollTimeoutMs)) {
      showModelCatalogFailure("Время ожидания обновления каталога истекло.");
      stopModelCatalogPolling();
      return;
    }
    modelCatalogPollFailures = loaded ? 0 : modelCatalogPollFailures + 1;
    const remaining = pollTimeoutMs - (nowImpl() - modelCatalogPollStartedAt);
    const desiredDelay = loaded
      ? RUN_POLL_INTERVAL_MS
      : Math.min(
        RUN_POLL_INTERVAL_MS * (2 ** Math.min(modelCatalogPollFailures - 1, 30)),
        RUN_POLL_MAX_BACKOFF_MS,
      );
    const delay = Math.min(desiredDelay, remaining);
    if (modelCatalogPollTimer !== null) cancelScheduleImpl(modelCatalogPollTimer);
    modelCatalogPollTimer = scheduleImpl(pollModelCatalog, delay);
  };

  const startModelCatalogPolling = () => {
    if (destroyed || paused || modelCatalogPollTimer !== null) return;
    if (modelCatalogPollStartedAt === null) modelCatalogPollStartedAt = nowImpl();
    const remaining = Math.max(0, pollTimeoutMs - (nowImpl() - modelCatalogPollStartedAt));
    modelCatalogPollTimer = scheduleImpl(
      pollModelCatalog,
      Math.min(RUN_POLL_INTERVAL_MS, remaining),
    );
  };

  const reloadCurrentModelCatalog = async () => {
    modelCatalogReloadPending = true;
    const loaded = await loadModels();
    if (loaded !== null) modelCatalogReloadPending = false;
    return loaded;
  };

  const unknownWriteOutcome = () => {
    const failure = new Error("Сервер мог сохранить изменения, но подтверждение не получено.");
    failure.code = "request_outcome_unknown";
    failure.outcomeUnknown = true;
    return failure;
  };

  const protectedJson = async (url, requestOptions = {}) => {
    const {timeoutMs = protectedRequestTimeoutMs, ...options} = requestOptions;
    const controller = new AbortControllerImpl();
    let timedOut = false;
    let response = null;
    const timeoutId = scheduleImpl(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
    try {
      response = await fetchImpl(url, {
        ...options,
        signal: controller.signal,
        headers: {
          [ACCESS_HEADER]: accessCode,
          ...(options.body === undefined ? {} : {"Content-Type": "application/json"}),
          ...(options.headers ?? {}),
        },
      });
      const payload = await response.json().catch((error) => {
        if (error?.name === "AbortError") throw error;
        return null;
      });
      if (!response.ok) {
        const error = parseAtomLabError(payload);
        const failure = new Error(error?.message ?? safeApiMessage(payload, "Операция не выполнена."));
        failure.code = error?.code ?? "request_failed";
        failure.status = response.status;
        failure.fieldErrors = error?.fieldErrors ?? [];
        throw failure;
      }
      return payload;
    } catch (error) {
      if (error?.code === "request_outcome_unknown") throw error;
      const confirmedPreWriteFailure = error?.status === 503
        && CONFIRMED_PRESET_PREWRITE_FAILURE_CODES.has(error.code);
      if (options.method === "POST" && (
        timedOut
        || response === null
        || response.ok
        || (Number.isInteger(error?.status) && error.status >= 500 && error.status <= 599
          && !confirmedPreWriteFailure)
      )) {
        throw unknownWriteOutcome();
      }
      if (error?.status !== undefined) throw error;
      if (error?.name !== "AbortError" || !timedOut) throw error;
      const failure = new Error("Время ожидания ответа истекло.");
      failure.code = "request_timeout";
      failure.outcomeUnknown = false;
      throw failure;
    } finally {
      cancelScheduleImpl(timeoutId);
    }
  };

  const presetSourceFromConfiguration = (configuration) => ({
    atom: catalog.find((item) => item.atom_id === configuration.atom_id),
    base_action_config_id: configuration.base_action_config_id,
    schema_refs: cloneJson(configuration.schema_refs),
    input: cloneJson(configuration.example_input),
    prompt: configuration.prompt,
    prompt_ref: configuration.prompt_ref,
    promptSourceRef: configuration.prompt_source_ref ?? null,
    modelId: configuration.model_id,
    reasoningEffort: configuration.reasoning_effort,
    sourceRunId: configuration.source_run_id,
  });

  const topLevelFields = () => Object.keys(
    (presetSourceOverride?.atom ?? session?.atom)?.input_schema.properties ?? {},
  );

  const selectedFixedFields = () => [...nodes["fixed-fields"].querySelectorAll("input")]
    .filter((input) => input.checked)
    .map((input) => input.value);

  const fixedFieldInput = () => presetSourceOverride?.input ?? getDraftPayload(session);

  const syncFixedFieldAvailability = () => {
    const inputPayload = fixedFieldInput();
    for (const input of nodes["fixed-fields"].querySelectorAll("input")) {
      const available = isRecord(inputPayload) && Object.hasOwn(inputPayload, input.value);
      input.dataset.available = String(available);
      if (!available) input.checked = false;
    }
    updatePresetEditorDisabled();
  };

  const renderFixedFields = (fixedFields = []) => {
    nodes["fixed-fields"].replaceChildren();
    const selected = new Set(fixedFields);
    for (const field of topLevelFields()) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = field;
      const available = isRecord(fixedFieldInput()) && Object.hasOwn(fixedFieldInput(), field);
      input.dataset.available = String(available);
      input.checked = available && selected.has(field);
      input.disabled = !available;
      input.addEventListener("change", () => renderPresetState());
      const caption = document.createElement("span");
      caption.textContent = field;
      label.append(input, caption);
      nodes["fixed-fields"].append(label);
    }
  };

  const addressedModelId = (modelId) => modelId.startsWith("openai/")
    ? modelId
    : `openai/${modelId}`;

  const currentPresetPayload = () => {
    const source = presetSourceOverride;
    const atom = source?.atom ?? session.atom;
    return {
      name: nodes["preset-name"].value,
      description: nodes["preset-description"].value,
      atom_id: atom.atom_id,
      base_action_config_id: source?.base_action_config_id ?? atom.base_action_config_id,
      schema_refs: cloneJson(source?.schema_refs ?? atom.schema_refs),
      prompt: source?.prompt ?? session.prompt,
      prompt_ref: source?.prompt_ref ?? atom.prompt_ref,
      model_id: source?.modelId ?? addressedModelId(nodes["model-select"].value),
      reasoning_effort: source
        ? (source.reasoningEffort ?? null)
        : (nodes["reasoning-effort"].value || null),
      fixed_fields: selectedFixedFields(),
      example_input: cloneJson(source?.input ?? getDraftPayload(session)),
      source_run_id: source?.sourceRunId ?? session.sourceRunId,
      prompt_source_ref: source ? source.promptSourceRef : session.promptSourceRef,
    };
  };

  const presetPayloadFromVersion = (version) => ({
    name: version.name,
    description: version.description,
    atom_id: version.atom_id,
    base_action_config_id: version.base_action_config_id,
    schema_refs: cloneJson(version.schema_refs),
    prompt: version.prompt,
    prompt_ref: version.prompt_ref,
    model_id: version.model_id,
    reasoning_effort: version.reasoning_effort,
    fixed_fields: cloneJson(version.fixed_fields),
    example_input: cloneJson(version.example_input),
    source_run_id: version.source_run_id,
    prompt_source_ref: version.prompt_source_ref ?? null,
  });

  const presetFingerprint = (payload) => JSON.stringify(payload);

  const renderPresetDetails = () => {
    const selected = selectedPresetVersion;
    const editing = presetEditorActive && !presetReadOnly;
    const configuration = editing ? currentPresetPayload() : selected;
    nodes["preset-empty"].hidden = Boolean(selected) || editing;
    nodes["preset-heading"].hidden = selected === null;
    nodes["preset-editor-form"].hidden = !editing;
    nodes["preset-view-actions"].hidden = selected === null || editing;
    nodes["preset-view-description"].hidden = selected === null || editing || !selected.description;
    nodes["preset-view-description"].textContent = selected?.description ?? "";
    nodes["preset-configuration"].hidden = configuration === null;
    nodes["preset-technical"].hidden = selected === null;
    nodes["preset-readonly"].textContent = selected ? JSON.stringify(selected, null, 2) : "";
    if (selected) {
      nodes["preset-selected-name"].textContent = selected.name;
      nodes["preset-context"].textContent = `${selected.atom_id} · ${ATOM_LABELS[selected.atom_id].name}`;
    }
    if (!configuration) return;
    nodes["preset-editor-title"].textContent = selected ? `Новая версия на основе v${selected.version}` : "Новый пресет";
    nodes["preset-source"].textContent = presetSourceOverride
      ? `Источник: сохранённый запуск ${presetSourceOverride.sourceRunId}. Настройки и вход не связаны с текущим черновиком.`
      : `Источник: текущий черновик ${session.atom.atom_id}. Вход, промпт и настройки можно изменить в лаборатории.`;
    const rows = [
      ["Атом", `${configuration.atom_id} · ${ATOM_LABELS[configuration.atom_id].name}`],
      ["Модель", configuration.model_id],
      ["Reasoning", configuration.reasoning_effort ?? "Не запрошен"],
      ["Промпт", configuration.prompt_ref],
      ["Конфигурация действия", configuration.base_action_config_id],
      ["Схема входа", `${configuration.schema_refs.input.schema_ref} · v${configuration.schema_refs.input.version}`],
      ["Схема выхода", `${configuration.schema_refs.output.schema_ref} · v${configuration.schema_refs.output.version}`],
    ];
    if (selected && !editing) rows.push(["Сохранена", formatLabDate(selected.created_at)]);
    if (configuration.source_run_id) rows.push(["Исходный запуск", configuration.source_run_id]);
    renderFacts(document, nodes["preset-config-metadata"], rows);
    nodes["preset-input-fields"].replaceChildren();
    for (const key of Object.keys(configuration.example_input)) {
      const field = document.createElement("span");
      const fixed = configuration.fixed_fields.includes(key);
      field.className = "preset-field";
      field.dataset.fixed = String(fixed);
      field.textContent = `${key}${fixed ? " · закреплено" : ""}`;
      nodes["preset-input-fields"].append(field);
    }
    nodes["preset-input-json"].textContent = JSON.stringify(configuration.example_input, null, 2);
    nodes["preset-prompt"].textContent = configuration.prompt;
  };

  const renderPresetState = () => {
    if (!session) return;
    renderPresetDetails();
    nodes["save-preset"].textContent = selectedPresetVersion ? "Сохранить новую версию" : "Сохранить новый";
    if (!selectedPresetVersion && !presetEditorActive) {
      nodes["preset-state"].textContent = "";
      return;
    }
    if (presetReadOnly && selectedPresetVersion) {
      nodes["preset-state"].textContent = `Пресет ${selectedPresetVersion.preset_id}, версия ${selectedPresetVersion.version}. Исторический контракт доступен только для чтения.`;
      return;
    }
    const changed = presetHasUnsavedDraft();
    if (selectedPresetVersion && !presetEditorActive) {
      nodes["preset-state"].textContent = "Открыта сохранённая версия. Только чтение. Изменения сохраняются новой версией.";
      return;
    }
    const source = presetSourceOverride ? "Снимок истории" : selectedPresetVersion
      ? `Пресет ${selectedPresetVersion.preset_id}, версия ${selectedPresetVersion.version}`
      : "Новый пресет";
    const unchanged = selectedPresetVersion ? "Открыта сохранённая версия." : "Нет несохранённых изменений.";
    nodes["preset-state"].textContent = `${source}. ${changed ? "Есть несохранённый черновик." : unchanged}${
      !presetSourceOverride && session.promptSourceNeedsValidation
        ? " Проверка источника ещё не завершена. Повторить загрузку можно во вкладке «Промпт»."
        : !presetSourceOverride && session.promptSourceDetached
          ? " Исторический источник недоступен. Текст промпта сохранён." : ""
    }`;
    nodes["save-preset"].textContent = selectedPresetVersion ? "Сохранить новую версию" : "Сохранить новый";
  };

  const applyModelSelection = (modelId, reasoningEffort) => {
    for (const placeholder of nodes["model-select"].querySelectorAll("option[data-model-unavailable-placeholder]")) {
      placeholder.remove();
    }
    renderModelCatalogWarning();
    const raw = modelId.startsWith("openai/") ? modelId.slice("openai/".length) : modelId;
    const option = modelOptions.find((item) => item.modelId === raw || addressedModelId(item.modelId) === modelId);
    const value = option?.modelId ?? raw;
    if (!option) {
      const unavailable = document.createElement("option");
      unavailable.value = value;
      unavailable.textContent = `${modelId} — недоступна`;
      unavailable.disabled = true;
      unavailable.dataset.modelUnavailablePlaceholder = "true";
      nodes["model-select"].append(unavailable);
    }
    nodes["model-select"].value = value;
    renderReasoning(reasoningEffort ?? "");
    if (!option) nodes["model-catalog-warning"].textContent = "Сохранённая модель недоступна. Выберите доступную модель перед запуском.";
  };

  const applyConfigurationToEditor = (configuration, {presetRef = null, sourceRunId = null, restored = false, adapted = false} = {}) => {
    const atom = catalog.find((item) => item.atom_id === configuration.atom_id);
    if (!atom) return false;
    selectAtom(atom, {force: true, preservePreset: true});
    session.payload = cloneJson(configuration.example_input ?? configuration.input);
    session.baselinePayload = restored ? {} : cloneJson(session.payload);
    session.prompt = configuration.prompt;
    session.baselinePrompt = restored ? session.basePrompt : configuration.prompt;
    session.presetRef = presetRef;
    session.sourceRunId = sourceRunId;
    session.promptSourceRef = configuration.prompt_source_ref ?? null;
    session.promptSourceNeedsValidation = adapted && session.promptSourceRef !== null;
    restoredHistoryDraft = restored;
    nodes["prompt-editor"].value = session.prompt;
    renderPromptOptions();
    applyModelSelection(configuration.model_id, configuration.reasoning_effort);
    renderEditor();
    if (session.promptSourceNeedsValidation) void loadPromptOptions();
    return true;
  };

  const renderPresetList = () => {
    nodes["preset-list"].replaceChildren();
    for (const preset of presetItems) {
      const item = button(document, preset.name, () => openPreset(preset));
      const metadata = document.createElement("small");
      metadata.textContent = `${preset.atom_id} · ${ATOM_LABELS[preset.atom_id].name} · v${preset.latest_version}`;
      item.append(metadata);
      item.dataset.presetId = preset.preset_id;
      if (preset.description) {
        const description = document.createElement("small");
        description.textContent = preset.description;
        item.append(description);
      }
      item.setAttribute("aria-current", String(preset.preset_id === selectedPresetSummary?.preset_id));
      nodes["preset-list"].append(item);
    }
    nodes["load-more-presets"].hidden = presetCursor === null;
    nodes["preset-list-state"].textContent = presetItems.length === 0
      ? "Сохранённых пресетов пока нет. Создайте первый из черновика в лаборатории."
      : `Загружено пресетов: ${presetItems.length}${presetCursor ? " · есть ещё" : ""}`;
    updatePresetEditorDisabled();
  };

  const presetSaveOutcomeUnknownMessage = () => presetSaveOutcomeUnknown?.kind === "update"
    ? "Результат сохранения неизвестен: сервер мог создать новую версию. Не повторяйте Save; заново откройте этот пресет и проверьте список версий."
    : "Результат создания неизвестен: сервер мог создать пресет. Не повторяйте Save; перезагрузите страницу и проверьте библиотеку.";

  const setPresetError = (message = "") => {
    const outcomeMessage = presetSaveOutcomeUnknown ? presetSaveOutcomeUnknownMessage() : "";
    nodes["preset-error"].textContent = outcomeMessage && message
      ? `${outcomeMessage} ${message}`
      : outcomeMessage || message;
  };

  const loadPresets = async ({append = false, merge = false} = {}) => {
    if (append && presetListLoadInFlight) return false;
    const generation = ++presetListLoadGeneration;
    const cursor = append ? presetCursor : null;
    const previousItems = presetItems;
    const previousCursor = presetCursor;
    presetListLoadInFlight = true;
    nodes["preset-list-state"].textContent = "Загрузка пресетов…";
    updatePresetEditorDisabled();
    setPresetError();
    try {
      const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
      const parsed = parsePresetList(await protectedJson(`/v1/atom-lab/presets${query}`));
      if (!parsed) throw new Error("Список пресетов вернул некорректный ответ.");
      if (generation !== presetListLoadGeneration) return false;
      if (append) {
        presetItems = [...presetItems, ...parsed.items];
        presetCursor = parsed.next_cursor;
      } else if (merge && previousItems.length > 0
        && parsed.items.some((item) => previousItems.some(
          (previousItem) => previousItem.preset_id === item.preset_id,
        ))) {
        const refreshedIds = new Set(parsed.items.map((item) => item.preset_id));
        presetItems = [
          ...parsed.items,
          ...previousItems.filter((item) => !refreshedIds.has(item.preset_id)),
        ];
        presetCursor = previousCursor;
      } else {
        presetItems = parsed.items;
        presetCursor = parsed.next_cursor;
      }
      renderPresetList();
      return true;
    } catch (error) {
      if (generation !== presetListLoadGeneration) return false;
      setPresetError(error instanceof Error ? error.message : "Не удалось загрузить пресеты.");
      nodes["preset-list-state"].textContent = "Не удалось обновить библиотеку. Повторно откройте раздел «Пресеты».";
      return false;
    } finally {
      if (generation === presetListLoadGeneration) {
        presetListLoadInFlight = false;
        updatePresetEditorDisabled();
      }
    }
  };

  const updatePresetEditorDisabled = () => {
    const operationLocked = presetLibraryLoading || presetOpenInFlight || presetSaveInFlight;
    const versionControlsLocked = operationLocked
      || presetVersionPageInFlight
      || presetSaveOutcomeUnknown !== null;
    const editorLocked = operationLocked || presetReadOnly || !presetEditorActive;
    const draftLocked = presetOpenInFlight || presetSaveInFlight;
    nodes.workspace.inert = draftLocked;
    nodes.workspace.setAttribute("aria-busy", String(draftLocked));
    for (const id of ["preset-name", "preset-description", "save-preset"]) nodes[id].disabled = editorLocked;
    for (const id of ["preset-version-select", "load-more-versions"]) {
      nodes[id].disabled = versionControlsLocked;
    }
    nodes["new-preset"].disabled = versionControlsLocked || presetSaveOutcomeUnknown;
    for (const id of ["apply-preset", "edit-preset"]) {
      nodes[id].disabled = operationLocked || presetReadOnly || selectedPresetVersion === null || presetSaveOutcomeUnknown !== null;
    }
    nodes["cancel-preset"].disabled = versionControlsLocked;
    const promptSourcePending = !presetSourceOverride && session?.promptSourceNeedsValidation;
    nodes["save-preset"].disabled = editorLocked || presetSaveOutcomeUnknown || promptSourcePending;
    nodes["save-as-new-preset"].disabled = versionControlsLocked || presetSaveOutcomeUnknown || promptSourcePending;
    nodes["open-latest-preset"].disabled = versionControlsLocked || conflictLatestPreset === null;
    nodes["export-preset"].disabled = operationLocked || selectedPresetVersion === null;
    nodes["adapt-preset"].disabled = operationLocked || !presetReadOnly;
    nodes["load-more-presets"].disabled = operationLocked || presetListLoadInFlight;
    for (const buttonNode of nodes["preset-list"].querySelectorAll("button")) {
      buttonNode.disabled = operationLocked || presetListLoadInFlight;
    }
    for (const input of nodes["fixed-fields"].querySelectorAll("input")) {
      input.disabled = editorLocked || input.dataset.available !== "true";
    }
  };

  const clearPresetExport = () => {
    presetExportGeneration += 1;
    nodes["preset-export"].textContent = "";
    nodes["preset-export"].hidden = true;
    nodes["preset-export-download"].href = "";
    nodes["preset-export-download"].download = "";
    nodes["preset-export-download"].hidden = true;
  };

  const setPresetLibraryLoading = (loading) => {
    presetLibraryLoading = loading;
    updatePresetEditorDisabled();
    if (loading) nodes["preset-state"].textContent = "Загрузка пресетов…";
  };

  const setPresetReadOnly = (readOnly, configuration = null) => {
    presetReadOnly = readOnly;
    nodes["preset-compatibility"].hidden = !readOnly;
    nodes["preset-readonly"].textContent = readOnly ? JSON.stringify(configuration, null, 2) : "";
    updatePresetEditorDisabled();
  };

  const fetchPresetVersion = async (presetId, version) => {
    const parsed = parsePresetVersion(
      await protectedJson(`/v1/atom-lab/presets/${encodeURIComponent(presetId)}/versions/${version}`),
      presetId,
      version,
    );
    if (!parsed) throw new Error("Версия пресета вернула некорректный ответ.");
    return parsed;
  };

  const commitPresetVersion = (parsed, {applyToEditor = false} = {}) => {
    const {preset_id: presetId, version} = parsed;
    selectedPresetVersion = cloneJson(parsed);
    presetEditorActive = false;
    presetSourceOverride = applyToEditor ? null : presetSourceFromConfiguration(parsed);
    nodes["preset-name"].value = parsed.name;
    nodes["preset-description"].value = parsed.description;
    nodes["preset-version-select"].value = String(version);
    conflictLatestPreset = null;
    nodes["preset-conflict"].hidden = true;
    clearPresetExport();
    const atom = catalog.find((item) => item.atom_id === parsed.atom_id);
    if (!presetContractMatchesAtom(parsed, atom)) {
      presetDraftBaseline = null;
      renderFixedFields([]);
      setPresetReadOnly(true, parsed);
      renderPresetState();
      return;
    }
    setPresetReadOnly(false);
    if (applyToEditor) {
      applyConfigurationToEditor(parsed, {
        presetRef: {preset_id: presetId, version},
        sourceRunId: parsed.source_run_id,
      });
    }
    renderFixedFields(parsed.fixed_fields);
    presetDraftBaseline = presetFingerprint(currentPresetPayload());
    renderPresetState();
  };

  const reconcileCommittedPresetVersion = (parsed, recovery) => {
    selectedPresetVersion = cloneJson(parsed);
    presetEditorActive = true;
    nodes["preset-version-select"].value = String(parsed.version);
    conflictLatestPreset = null;
    nodes["preset-conflict"].hidden = true;
    clearPresetExport();
    setPresetReadOnly(false);
    if (!recovery.preserveEditor && session === recovery.ownerSession) {
      session.baselinePayload = cloneJson(recovery.payload.example_input);
      session.baselinePrompt = recovery.payload.prompt;
      session.presetRef = {preset_id: parsed.preset_id, version: parsed.version};
    }
    presetDraftBaseline = presetFingerprint(recovery.payload);
    updateDraftState();
    renderPresetState();
  };

  const fetchPresetVersions = async (presetId, {cursor = null} = {}) => {
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    const parsed = parsePresetVersionList(await protectedJson(
      `/v1/atom-lab/presets/${encodeURIComponent(presetId)}/versions${query}`,
    ), presetId);
    if (!parsed) throw new Error("Список версий вернул некорректный ответ.");
    return parsed;
  };

  const commitPresetVersions = (parsed, {append = false} = {}) => {
    const combined = append ? [...presetVersions, ...parsed.items] : parsed.items;
    const seenVersions = new Set();
    presetVersions = combined.filter((item) => {
      if (seenVersions.has(item.version)) return false;
      seenVersions.add(item.version);
      return true;
    }).sort((left, right) => right.version - left.version);
    presetVersionsCursor = parsed.next_cursor;
    const selectedValue = nodes["preset-version-select"].value;
    nodes["preset-version-select"].replaceChildren();
    for (const version of presetVersions) {
      const option = document.createElement("option");
      option.value = String(version.version);
      option.textContent = `v${version.version}${version.version === presetVersions[0]?.version ? " · последняя" : ""} · ${formatLabDate(version.created_at)}`;
      nodes["preset-version-select"].append(option);
    }
    if (selectedValue) nodes["preset-version-select"].value = selectedValue;
    nodes["load-more-versions"].hidden = presetVersionsCursor === null;
  };

  const materializePresetVersion = (version) => {
    if (presetVersions.some((item) => item.version === version.version)) return;
    commitPresetVersions({
      items: [...presetVersions, {
        preset_id: version.preset_id,
        version: version.version,
        name: version.name,
        description: version.description,
        atom_id: version.atom_id,
        created_at: version.created_at,
      }],
      next_cursor: presetVersionsCursor,
    });
  };

  const loadMorePresetVersions = async () => {
    if (!selectedPresetSummary || presetVersionPageInFlight || presetVersionsCursor === null) return;
    const presetId = selectedPresetSummary.preset_id;
    const cursor = presetVersionsCursor;
    const generation = ++presetVersionPageGeneration;
    presetVersionPageInFlight = true;
    updatePresetEditorDisabled();
    try {
      const parsed = await fetchPresetVersions(presetId, {cursor});
      if (generation !== presetVersionPageGeneration || selectedPresetSummary?.preset_id !== presetId) return;
      commitPresetVersions(parsed, {append: true});
    } catch (error) {
      if (generation === presetVersionPageGeneration) setPresetError(error.message);
    } finally {
      if (generation === presetVersionPageGeneration) {
        presetVersionPageInFlight = false;
        updatePresetEditorDisabled();
      }
    }
  };

  const openPreset = async (
    preset,
    preferredVersion = null,
    {force = false, refreshVersions = true, versionsPageOverride = null, applyToEditor = false} = {},
  ) => {
    if (presetSaveInFlight && !force) return false;
    const unknownUpdateRecovery = !force
      && preferredVersion === null
      && presetSaveOutcomeUnknown?.kind === "update"
      && presetSaveOutcomeUnknown.presetId === preset.preset_id
      ? presetSaveOutcomeUnknown
      : null;
    const preservesRecoveryDraft = unknownUpdateRecovery
      && session === unknownUpdateRecovery.ownerSession
      && selectedPresetVersion?.preset_id === unknownUpdateRecovery.presetId
      && selectedPresetVersion.version === unknownUpdateRecovery.baseVersion
      && presetSourceOverride === unknownUpdateRecovery.ownerPresetSource;
    if (!preservesRecoveryDraft && !force && presetHasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return false;
    const focusVersion = document.activeElement === nodes["preset-version-select"];
    const focusPresetId = document.activeElement?.dataset?.presetId;
    const generation = ++presetOpenGeneration;
    presetVersionPageGeneration += 1;
    presetVersionPageInFlight = false;
    presetOpenInFlight = true;
    clearPresetExport();
    updatePresetEditorDisabled();
    setPresetError();
    nodes["preset-state"].textContent = "Загрузка версии пресета…";
    try {
      let versionsPage;
      let version;
      if (preferredVersion === null) {
        versionsPage = refreshVersions
          ? await fetchPresetVersions(preset.preset_id)
          : versionsPageOverride;
        const latest = versionsPage?.items[0];
        if (!latest) throw new Error("Сервер не вернул актуальную версию пресета.");
        version = await fetchPresetVersion(preset.preset_id, latest.version);
      } else {
        [versionsPage, version] = await Promise.all([
          refreshVersions
            ? fetchPresetVersions(preset.preset_id)
            : Promise.resolve(versionsPageOverride),
          fetchPresetVersion(preset.preset_id, preferredVersion),
        ]);
      }
      if (generation !== presetOpenGeneration) return false;
      if (versionsPage) commitPresetVersions(versionsPage);
      if (preservesRecoveryDraft && selectedPresetVersion) {
        materializePresetVersion(selectedPresetVersion);
        nodes["preset-version-select"].value = String(selectedPresetVersion.version);
      }
      if (preferredVersion !== null) materializePresetVersion(version);
      const latest = versionsPage?.items[0] ?? null;
      const summary = latest ? {
        ...preset,
        latest_version: latest.version,
        name: latest.name,
        description: latest.description,
        atom_id: latest.atom_id,
        updated_at: latest.created_at,
      } : preset;
      presetItems = presetItems.map((item) => item.preset_id === summary.preset_id ? summary : item);
      selectedPresetSummary = summary;
      if (unknownUpdateRecovery && !preservesRecoveryDraft) {
        presetSaveOutcomeUnknown = null;
      } else if (unknownUpdateRecovery) {
        if (latest.version < unknownUpdateRecovery.baseVersion) {
          throw new Error("Список версий не содержит базовую версию неизвестного сохранения.");
        }
        if (latest.version === unknownUpdateRecovery.baseVersion) {
          presetSaveOutcomeUnknown = null;
          setPresetError("Новая версия не найдена. Локальный черновик сохранён; можно повторить Save.");
          renderPresetList();
          renderPresetState();
          return true;
        }
        const expectedVersion = latest.version === unknownUpdateRecovery.expectedVersion
          ? version
          : await fetchPresetVersion(preset.preset_id, unknownUpdateRecovery.expectedVersion);
        if (generation !== presetOpenGeneration) return false;
        presetSaveOutcomeUnknown = null;
        if (sameJsonSemantically(
          presetPayloadFromVersion(expectedVersion),
          unknownUpdateRecovery.payload,
        )) {
          materializePresetVersion(expectedVersion);
          reconcileCommittedPresetVersion(expectedVersion, unknownUpdateRecovery);
          renderPresetList();
          setPresetError();
          return true;
        }
        if (selectedPresetVersion) {
          materializePresetVersion(selectedPresetVersion);
          nodes["preset-version-select"].value = String(selectedPresetVersion.version);
        }
        conflictLatestPreset = {summary, version: latest.version};
        nodes["preset-conflict"].hidden = false;
        setPresetError("Конфликт сохранения: актуальная версия отличается от локального черновика. Значения черновика сохранены.");
        renderPresetList();
        renderPresetState();
        return true;
      }
      commitPresetVersion(version, {applyToEditor});
      renderPresetList();
      setPresetError();
      return true;
    } catch (error) {
      if (generation !== presetOpenGeneration) return false;
      if (selectedPresetVersion) nodes["preset-version-select"].value = String(selectedPresetVersion.version);
      setPresetError(error instanceof Error ? error.message : "Не удалось открыть пресет.");
      renderPresetState();
      return false;
    } finally {
      if (generation === presetOpenGeneration) {
        presetOpenInFlight = false;
        updatePresetEditorDisabled();
        if (focusVersion) nodes["preset-version-select"].focus();
        else if (focusPresetId) {
          for (const item of nodes["preset-list"].querySelectorAll("button")) {
            if (item.dataset.presetId === focusPresetId) item.focus();
          }
        }
      }
    }
  };

  const startNewPreset = ({fromHistory = null, activate = true, clearSessionPreset = true} = {}) => {
    setPresetReadOnly(false);
    presetEditorActive = activate;
    selectedPresetSummary = null;
    selectedPresetVersion = null;
    presetSourceOverride = fromHistory;
    if (clearSessionPreset) session.presetRef = null;
    nodes["preset-name"].value = fromHistory ? `Запуск ${fromHistory.sourceRunId}` : "";
    nodes["preset-description"].value = "";
    nodes["preset-version-select"].replaceChildren();
    nodes["load-more-versions"].hidden = true;
    clearPresetExport();
    conflictLatestPreset = null;
    nodes["preset-conflict"].hidden = true;
    if (activate) renderFixedFields([]);
    else nodes["fixed-fields"].replaceChildren();
    updatePresetEditorDisabled();
    presetDraftBaseline = presetFingerprint({
      ...currentPresetPayload(),
      name: "",
      description: "",
      fixed_fields: [],
    });
    renderPresetState();
  };

  const editSelectedPreset = ({openWorkbench = false} = {}) => {
    if (!selectedPresetVersion || presetReadOnly || presetOpenInFlight || presetSaveInFlight || presetSaveOutcomeUnknown) return;
    const version = selectedPresetVersion;
    const alreadyApplied = session.presetRef?.preset_id === version.preset_id
      && session.presetRef.version === version.version;
    if (!alreadyApplied) {
      if (hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
      if (!applyConfigurationToEditor(version, {
        presetRef: {preset_id: version.preset_id, version: version.version},
        sourceRunId: version.source_run_id,
      })) return;
    }
    presetSourceOverride = null;
    presetEditorActive = true;
    renderFixedFields(version.fixed_fields);
    presetDraftBaseline = presetFingerprint(presetPayloadFromVersion(version));
    renderPresetState();
    updatePresetEditorDisabled();
    if (openWorkbench) {
      showLibrary();
      nodes.status.textContent = `Пресет «${version.name}», v${version.version}, открыт в лаборатории. Изменения можно сохранить новой версией в разделе «Пресеты».`;
    } else nodes["preset-name"].focus();
  };

  const savePreset = async ({forceNew = false} = {}) => {
    if (!presetEditorActive || presetLibraryLoading || presetOpenInFlight || presetReadOnly || presetSaveInFlight
      || presetSaveOutcomeUnknown || (!presetSourceOverride && session.promptSourceNeedsValidation)) return;
    if (!presetSourceOverride && validateDraft(session).length > 0) {
      session.validationRequested = true;
      showInputTab(true);
      renderValidation(document, nodes["validation-errors"], session, admissionErrors);
      setPresetError("Исправьте входные данные перед сохранением пресета.");
      nodes.status.textContent = "Исправьте входные данные перед сохранением пресета. Затем вернитесь в «Пресеты»: настройки остались в черновике.";
      nodes["validation-errors"].querySelector("button")?.click();
      return;
    }
    presetSaveInFlight = true;
    updatePresetEditorDisabled();
    setPresetError();
    nodes.status.textContent = "";
    const payload = currentPresetPayload();
    const updating = Boolean(selectedPresetVersion) && !forceNew;
    const expectedPresetId = updating ? selectedPresetVersion.preset_id : null;
    const expectedVersion = updating ? selectedPresetVersion.version + 1 : 1;
    const url = updating
      ? `/v1/atom-lab/presets/${encodeURIComponent(selectedPresetVersion.preset_id)}/versions`
      : "/v1/atom-lab/presets";
    const body = updating ? {...payload, base_version: selectedPresetVersion.version} : payload;
    const preserveEditor = presetSourceOverride !== null;
    try {
      const created = await protectedJson(url, {method: "POST", body: JSON.stringify(body)});
      if (!isRecord(created) || !isNonEmptyString(created.preset_id) || !isPositiveInteger(created.version)
        || !isNonEmptyString(created.created_at)
        || created.version !== expectedVersion
        || (expectedPresetId !== null && created.preset_id !== expectedPresetId)) {
        throw unknownWriteOutcome();
      }
      if (!updating) await loadPresets();
      const currentSummary = presetItems.find((item) => item.preset_id === created.preset_id)
        ?? (selectedPresetSummary?.preset_id === created.preset_id ? selectedPresetSummary : null);
      const summary = {
        ...currentSummary,
        preset_id: created.preset_id,
        latest_version: created.version,
        name: payload.name,
        description: payload.description,
        atom_id: payload.atom_id,
        created_at: currentSummary?.created_at ?? created.created_at,
        updated_at: created.created_at,
      };
      if (presetItems.some((item) => item.preset_id === created.preset_id)) {
        presetItems = presetItems.map((item) => item.preset_id === created.preset_id ? summary : item);
      } else {
        presetItems = [summary, ...presetItems];
      }
      const readBack = await openPreset(summary, created.version, {
        force: true,
        applyToEditor: !preserveEditor,
      });
      if (readBack) {
        nodes["preset-state"].textContent = `Сохранена неизменяемая версия ${created.version}.`;
      } else {
        const localVersion = {
          ...cloneJson(payload),
          preset_id: created.preset_id,
          version: created.version,
          created_at: created.created_at,
        };
        if (!presetItems.some((item) => item.preset_id === created.preset_id)) {
          presetItems = [summary, ...presetItems];
        }
        selectedPresetSummary = summary;
        commitPresetVersions({items: [{
          preset_id: created.preset_id,
          version: created.version,
          name: payload.name,
          description: payload.description,
          atom_id: payload.atom_id,
          created_at: created.created_at,
        }], next_cursor: null});
        commitPresetVersion(localVersion, {applyToEditor: !preserveEditor});
        renderPresetList();
        nodes["preset-state"].textContent = `Версия ${created.version} сохранена; повторное чтение не удалось.`;
        setPresetError("Сохранение завершено, но сервер не вернул сохранённую версию при повторном чтении. Повторный Save обновит эту identity.");
      }
    } catch (error) {
      if (error?.code === "request_outcome_unknown") {
        presetSaveOutcomeUnknown = {
          kind: updating ? "update" : "create",
          presetId: expectedPresetId,
          ...(updating ? {
            baseVersion: selectedPresetVersion.version,
            expectedVersion,
            payload: cloneJson(payload),
            ownerSession: session,
            ownerPresetSource: presetSourceOverride,
            preserveEditor,
          } : {}),
        };
        conflictLatestPreset = null;
        nodes["preset-conflict"].hidden = true;
        setPresetError();
        renderPresetState();
        return;
      }
      if (error?.code === "preset_version_conflict") {
        conflictLatestPreset = null;
        nodes["preset-conflict"].hidden = false;
        try {
          const presetId = selectedPresetVersion?.preset_id;
          const latestPage = presetId ? await fetchPresetVersions(presetId) : null;
          const latest = latestPage?.items[0];
          if (presetId && latest && latest.version > selectedPresetVersion.version) {
            const currentSummary = selectedPresetSummary?.preset_id === presetId
              ? selectedPresetSummary
              : null;
            conflictLatestPreset = {
              summary: {
                preset_id: presetId,
                latest_version: latest.version,
                name: latest.name,
                description: latest.description,
                atom_id: latest.atom_id,
                created_at: currentSummary?.created_at ?? latest.created_at,
                updated_at: latest.created_at,
              },
              version: latest.version,
            };
          }
        } catch {
          // The recovery action stays disabled when latest-version refresh is unavailable.
        }
        if (conflictLatestPreset === null) {
          setPresetError("Конфликт сохранения. Не удалось получить актуальную версию; повторите загрузку пресета вручную. Значения черновика сохранены.");
          renderPresetState();
          return;
        }
      }
      const fieldErrors = Array.isArray(error?.fieldErrors)
        ? error.fieldErrors.map(({path, message}) => `${path}: ${message}`).join("; ")
        : "";
      const details = fieldErrors ? ` Поля: ${fieldErrors}.` : "";
      setPresetError(`${error instanceof Error ? error.message : "Не удалось сохранить пресет."}${details} Значения черновика сохранены.`);
      renderPresetState();
    } finally {
      presetSaveInFlight = false;
      updatePresetEditorDisabled();
    }
  };

  const renderHistoryList = () => {
    nodes["history-record"].hidden = !historyItems.some(run => run.run_id === selectedHistoryDetail?.run_id);
    nodes["history-panel"].append(nodes["history-record"]);
    nodes["history-list"].replaceChildren();
    for (const run of historyItems) {
      const selected = run.run_id === selectedHistoryDetail?.run_id;
      const row = document.createElement("tr");
      row.dataset.selected = String(selected);
      const date = document.createElement("td");
      date.dataset.label = "Создан";
      const item = button(document, formatLabDate(run.created_at), () => openHistoryRun(run.run_id));
      item.className = "history-open";
      item.dataset.runId = run.run_id;
      item.setAttribute("aria-expanded", String(selected));
      item.setAttribute("aria-controls", "history-record");
      item.setAttribute("aria-current", String(selected));
      date.append(item);
      const atom = document.createElement("td");
      atom.dataset.label = "Атом";
      atom.textContent = `${run.atom_id} · ${ATOM_LABELS[run.atom_id].name}`;
      const status = document.createElement("td");
      status.dataset.label = "Статус";
      const badge = document.createElement("span");
      badge.className = "status-badge";
      badge.dataset.tone = RUN_PRESENTATION[run.status].tone;
      badge.textContent = run.status === "succeeded" ? "Успешно" : RUN_PRESENTATION[run.status].label;
      status.append(badge);
      const model = document.createElement("td");
      model.dataset.label = "Модель";
      model.textContent = run.model_id;
      if (run.preset_id) {
        const preset = document.createElement("small");
        preset.textContent = `${run.preset_id} · v${run.preset_version}`;
        model.append(preset);
      }
      row.append(date, atom, status, model);
      nodes["history-list"].append(row);
      if (selected) {
        const details = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 4;
        cell.className = "history-expanded";
        cell.append(nodes["history-record"]);
        details.append(cell);
        nodes["history-list"].append(details);
      }
    }
    nodes["load-more-history"].hidden = historyCursor === null;
    nodes["history-list-state"].textContent = historyItems.length === 0
      ? "Запусков пока нет. Выполните первый в лаборатории — его настройки и ответ появятся здесь."
      : `Загружено запусков: ${historyItems.length}${historyCursor ? " · есть ещё" : ""}`;
    updateHistoryControls();
  };

  const showHistoryTab = (active) => {
    for (const tab of ["result", "request", "diagnostics"]) {
      nodes[`history-${tab}-tab`].setAttribute("aria-selected", String(tab === active));
      nodes[`history-${tab}-tab`].tabIndex = tab === active ? 0 : -1;
      nodes[`history-${tab}-panel`].hidden = tab !== active;
    }
  };

  const renderHistoryDetail = (detail) => {
    const diagnostics = detail.diagnostics;
    const state = RUN_PRESENTATION[detail.status];
    nodes["history-detail-title"].textContent = `${detail.snapshot.atom_id} · ${ATOM_LABELS[detail.snapshot.atom_id].name}`;
    nodes["history-created"].textContent = formatLabDate(detail.created_at);
    nodes["history-status"].dataset.tone = state.tone;
    nodes["history-status-text"].textContent = detail.status === "succeeded" ? "Завершён успешно" : state.label;
    nodes["history-status-help"].textContent = `${state.help}${diagnostics.error_code ? ` Код ошибки: ${diagnostics.error_code}.` : ""}`;
    renderFacts(document, nodes["history-summary"], [
      ["Модель", diagnostics.requested_model_id],
      ["Reasoning", diagnostics.requested_reasoning_effort ?? "Не запрошен"],
      ["Длительность", formatDuration(diagnostics.duration_ms)],
    ]);
    const succeeded = detail.status === "succeeded" && detail.result !== null;
    nodes["history-result-readable"].hidden = !succeeded;
    if (succeeded) renderReadableResult(document, nodes["history-result-readable"], detail.result);
    else nodes["history-result-readable"].replaceChildren();
    nodes["history-result-message"].textContent = succeeded ? "" : state.help;
    nodes["history-result-json"].textContent = JSON.stringify(detail.result, null, 2);
    const debug = diagnostics.debug_artifacts[0];
    nodes["history-invalid"].hidden = detail.status !== "failed" || !debug;
    nodes["history-invalid-code"].textContent = debug
      ? `${diagnostics.error_code ?? "invalid_response"}${debug.truncated ? " · Сырой ответ обрезан." : ""}` : "";
    nodes["history-invalid-raw"].textContent = debug?.raw_output_text ?? "";
    nodes["history-input-json"].textContent = JSON.stringify(detail.snapshot.input, null, 2);
    nodes["history-prompt"].textContent = detail.snapshot.prompt?.content ?? "Снимок не содержит текст промпта.";
    nodes["history-snapshot"].textContent = JSON.stringify(detail.snapshot, null, 2);
    renderRunMetadata(document, nodes["history-metadata"], diagnostics);
    nodes["history-diagnostics-json"].textContent = JSON.stringify(diagnostics, null, 2);
    nodes["history-runtime-json"].textContent = JSON.stringify({run_id: detail.run_id, ...detail.runtime_ids}, null, 2);
    nodes["history-detail"].textContent = JSON.stringify(detail, null, 2);
    showHistoryTab("result");
  };

  const loadHistory = async ({append = false} = {}) => {
    if (append && historyListLoadInFlight) return false;
    const generation = ++historyListLoadGeneration;
    const cursor = append ? historyCursor : null;
    historyListLoadInFlight = true;
    nodes["history-list-state"].textContent = "Загрузка истории…";
    updateHistoryControls();
    nodes["history-error"].textContent = "";
    try {
      const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
      const parsed = parseRunList(await protectedJson(`/v1/atom-lab/runs${query}`));
      if (!parsed) throw new Error("История вернула некорректный ответ.");
      if (generation !== historyListLoadGeneration) return false;
      historyItems = append ? [...historyItems, ...parsed.items] : parsed.items;
      historyCursor = parsed.next_cursor;
      renderHistoryList();
      return true;
    } catch (error) {
      if (generation !== historyListLoadGeneration) return false;
      nodes["history-error"].textContent = error instanceof Error ? error.message : "Не удалось загрузить историю.";
      nodes["history-list-state"].textContent = "Не удалось обновить список. Повторно откройте историю запусков.";
      return false;
    } finally {
      if (generation === historyListLoadGeneration) {
        historyListLoadInFlight = false;
        updateHistoryControls();
      }
    }
  };

  const historyConfiguration = (detail) => {
    const configuration = historyPresetConfiguration(detail);
    return {...configuration, input: configuration.example_input};
  };

  const currentContractMatchesHistory = (detail) => {
    const configuration = historyPresetConfiguration(detail);
    const atom = catalog.find((item) => item.atom_id === detail.snapshot.atom_id);
    return presetContractMatchesAtom(configuration, atom);
  };

  const updateHistoryControls = () => {
    const listLocked = historyListLoadInFlight || historyOpenInFlight;
    for (const buttonNode of nodes["history-list"].querySelectorAll("button")) {
      if (buttonNode.dataset.runId) buttonNode.disabled = listLocked;
    }
    nodes["load-more-history"].disabled = listLocked;
    nodes["restore-history"].disabled = historyOpenInFlight || selectedHistoryDetail === null;
    nodes["save-history-preset"].disabled = historyOpenInFlight
      || selectedHistoryDetail === null
      || !selectedHistoryCompatible;
  };

  const openHistoryRun = async (runId) => {
    const keepRowFocus = document.activeElement?.dataset?.runId === runId;
    const generation = ++historyOpenGeneration;
    historyOpenInFlight = true;
    updateHistoryControls();
    nodes["history-error"].textContent = "";
    try {
      const parsed = parseRunDetail(await protectedJson(`/v1/atom-lab/runs/${encodeURIComponent(runId)}`), runId);
      if (!parsed) throw new Error("Снимок запуска вернул некорректный ответ.");
      if (generation !== historyOpenGeneration) return;
      selectedHistoryDetail = cloneJson(parsed);
      renderHistoryDetail(parsed);
      const compatible = currentContractMatchesHistory(parsed);
      selectedHistoryCompatible = compatible;
      renderHistoryList();
      renderSelectedHistoryWarning();
      nodes["restore-history"].textContent = compatible ? "Восстановить запрос в лаборатории" : "Адаптировать к текущему контракту";
    } catch (error) {
      if (generation !== historyOpenGeneration) return;
      nodes["history-error"].textContent = error instanceof Error ? error.message : "Не удалось открыть запуск.";
    } finally {
      if (generation === historyOpenGeneration) {
        historyOpenInFlight = false;
        updateHistoryControls();
        if (keepRowFocus) {
          for (const item of nodes["history-list"].querySelectorAll("button")) {
            if (item.dataset.runId === runId) item.focus();
          }
        }
      }
    }
  };

  const setRunState = (message, tone = "neutral", help = "") => {
    nodes["run-state"].textContent = message;
    nodes["run-status"].dataset.tone = tone;
    const previousResult = tone !== "success" && !nodes["result-section"].hidden
      ? "Ниже показан результат предыдущего принятого запуска." : "";
    nodes["run-status-help"].textContent = [help, previousResult].filter(Boolean).join(" ");
  };

  const setAcceptedRunState = (status, errorCode = null) => {
    const state = RUN_PRESENTATION[status];
    const message = status === "succeeded" ? "Завершён успешно" : state.label;
    const help = errorCode ? `${state.help} Код ошибки: ${errorCode}.` : state.help;
    setRunState(message, state.tone, help);
  };

  const displayAcceptedSubmission = (submission) => {
    displayedSubmission = submission;
    nodes["submitted-snapshot"].textContent = JSON.stringify(submission.snapshot, null, 2);
    nodes["run-metadata"].replaceChildren();
    nodes["run-metadata-section"].hidden = true;
    nodes["run-technical"].hidden = false;
    nodes["run-diagnostics"].textContent = JSON.stringify({
      run_id: submission.runId,
      ...submission.runtimeIds,
      provider_call_ids: [],
      error_code: null,
    }, null, 2);
    nodes["result-section"].hidden = true;
    nodes["result-readable"].replaceChildren();
    nodes["result-json"].textContent = "";
    nodes["invalid-response"].hidden = true;
    nodes["invalid-response-code"].textContent = "";
    nodes["invalid-response-raw"].textContent = "";
  };

  const renderRunDetail = (detail, submission) => {
    if (activeSubmission !== submission) return;
    const diagnostics = detail.diagnostics;
    setAcceptedRunState(detail.status, diagnostics.error_code);
    renderRunMetadata(document, nodes["run-metadata"], diagnostics);
    nodes["run-metadata-section"].hidden = false;
    submission.runtimeIds = {
      ...submission.runtimeIds,
      ...Object.fromEntries(
        Object.entries(detail.runtime_ids).filter(([, value]) => value !== null),
      ),
    };
    nodes["run-diagnostics"].textContent = JSON.stringify({
      run_id: detail.run_id,
      ...submission.runtimeIds,
      provider_call_ids: (diagnostics.provider_calls ?? []).map((call) => call.provider_call_id),
      error_code: diagnostics.error_code ?? null,
    }, null, 2);
    const succeeded = detail.status === "succeeded" && detail.result !== null;
    nodes["result-section"].hidden = !succeeded;
    if (succeeded) {
      nodes["result-caption"].textContent =
        `${submission.snapshot.atom_id} · ${diagnostics.response_model_id ?? diagnostics.requested_model_id}`;
      renderReadableResult(document, nodes["result-readable"], detail.result);
      nodes["result-json"].textContent = JSON.stringify(detail.result, null, 2);
      submission.ownerSession.promptTrial = {runId: submission.runId, snapshot: submission.snapshot};
    }
    const debugArtifact = (diagnostics.debug_artifacts ?? [])[0];
    const invalid = detail.status === "failed" && Boolean(debugArtifact);
    nodes["invalid-response"].hidden = !invalid;
    if (invalid) {
      const truncation = debugArtifact.truncated ? "Сырой ответ обрезан." : "";
      nodes["invalid-response-code"].textContent = [
        diagnostics.error_code ?? "invalid_response",
        truncation,
      ].filter(Boolean).join(" · ");
      nodes["invalid-response-raw"].textContent = debugArtifact.raw_output_text ?? "Сырой ответ недоступен.";
    }
    submission.detailLoaded = true;
    submission.terminal = TERMINAL_RUN_STATUSES.has(detail.status);
    nodes["retry-read"].hidden = true;
    updateRunButton();
  };

  const scheduleNextPoll = (submission, {retryable = false, retryAfterMs = null} = {}) => {
    if (destroyed || paused) return;
    const remaining = pollTimeoutMs - (nowImpl() - submission.pollStartedAt);
    if (remaining <= 0) {
      setRunState(
        "Время ожидания в браузере истекло. Backend job не отменён.", "warning",
        "Повторите чтение, чтобы узнать состояние принятого запуска.",
      );
      nodes["retry-read"].hidden = false;
      return;
    }
    if (retryable) submission.pollFailureCount = (submission.pollFailureCount ?? 0) + 1;
    const backoff = retryable
      ? Math.min(
        RUN_POLL_INTERVAL_MS * (2 ** Math.min(submission.pollFailureCount - 1, 30)),
        RUN_POLL_MAX_BACKOFF_MS,
      )
      : RUN_POLL_INTERVAL_MS;
    const delay = Math.min(Math.max(backoff, retryAfterMs ?? 0), remaining);
    if (runPollTimer !== null) cancelScheduleImpl(runPollTimer);
    runPollTimer = scheduleImpl(() => {
      runPollTimer = null;
      return pollRun(submission);
    }, delay);
  };

  const fetchRunBeforeDeadline = async (submission) => {
    if (destroyed || paused) return {cancelled: true};
    const remaining = pollTimeoutMs - (nowImpl() - submission.pollStartedAt);
    if (remaining <= 0) return {timedOut: true};
    const controller = new AbortControllerImpl();
    activeRunAbortController = controller;
    const timeoutId = scheduleImpl(() => controller.abort(), remaining);
    try {
      const response = await fetchImpl(`/v1/atom-lab/runs/${submission.runId}`, {
        headers: {[ACCESS_HEADER]: accessCode},
        signal: controller.signal,
      });
      let payload = null;
      try {
        payload = await response.json();
      } catch (error) {
        if (error?.name === "AbortError") throw error;
      }
      return {response, payload, timedOut: false};
    } catch (error) {
      if (destroyed && error?.name === "AbortError") return {cancelled: true};
      if (error?.name === "AbortError") return {timedOut: true};
      throw error;
    } finally {
      cancelScheduleImpl(timeoutId);
      if (activeRunAbortController === controller) activeRunAbortController = null;
    }
  };

  const pollRun = async (submission = activeSubmission) => {
    if (destroyed || paused || !submission?.runId || activeSubmission !== submission) return;
    nodes["retry-read"].hidden = true;
    try {
      const {response, payload, timedOut, cancelled} = await fetchRunBeforeDeadline(submission);
      if (destroyed || paused || cancelled || activeSubmission !== submission) return;
      if (timedOut) {
        setRunState(
          "Время ожидания в браузере истекло. Backend job не отменён.", "warning",
          "Повторите чтение, чтобы узнать состояние принятого запуска.",
        );
        nodes["retry-read"].hidden = false;
        return;
      }
      if (!response.ok) {
        const retryable = [408, 425, 429, 500, 502, 503, 504].includes(response.status);
        if (retryable) {
          const retryAfterMs = response.status === 429
            ? retryAfterDelayMs(response.headers?.get?.("Retry-After"), nowImpl())
            : null;
          setRunState(
            "Переподключение… Запуск принят; текущее состояние временно неизвестно.", "warning",
            "Повторно запрашиваем состояние запуска.",
          );
          scheduleNextPoll(submission, {retryable: true, retryAfterMs});
          return;
        }
        const code = typeof payload?.error?.code === "string" ? payload.error.code : "request_failed";
        setRunState(
          `${code}: ${safeApiMessage(payload, "Не удалось прочитать запуск.")}`, "warning",
          "Состояние выполнения не подтверждено. Повторите чтение запуска.",
        );
        nodes["retry-read"].hidden = false;
        return;
      }
      const detail = parseRunDetail(payload, submission.runId);
      const matchesSubmission = detail
        && detail.diagnostics.requested_model_id === submission.snapshot.model_id
        && detail.diagnostics.requested_reasoning_effort === submission.snapshot.reasoning_effort
        && ["scenario_session_id", "job_id", "action_run_id", "artifact_id"].every((key) => (
          submission.runtimeIds[key] === null
          || detail.runtime_ids[key] === null
          || detail.runtime_ids[key] === submission.runtimeIds[key]
        ));
      if (!matchesSubmission) {
        setRunState(
          "Некорректный ответ API. Запуск сохранён для повторного чтения.", "warning",
          "Состояние выполнения не подтверждено.",
        );
        nodes["retry-read"].hidden = false;
        return;
      }
      submission.pollFailureCount = 0;
      renderRunDetail(detail, submission);
      if (!TERMINAL_RUN_STATUSES.has(detail.status)) {
        scheduleNextPoll(submission);
      }
    } catch {
      if (destroyed || paused || activeSubmission !== submission) return;
      setRunState(
        "Переподключение… Запуск принят; текущее состояние временно неизвестно.", "warning",
        "Повторно запрашиваем состояние запуска.",
      );
      scheduleNextPoll(submission, {retryable: true});
    }
  };

  const submitRun = async ({retry = false} = {}) => {
    if (destroyed || paused || submitInFlight || !session) return;
    const pendingReplay = retry && activeSubmission && !activeSubmission.runId;
    if (!pendingReplay && session.promptSourceNeedsValidation) {
      showInputTab(false);
      return;
    }
    if (!pendingReplay) {
      session.validationRequested = true;
      admissionErrors = [];
      renderValidation(document, nodes["validation-errors"], session, admissionErrors);
      const errors = validateDraft(session);
      if (errors.length > 0) {
        if (nodes["input-panel"].hidden) showInputTab(true);
        renderValidation(document, nodes["validation-errors"], session, admissionErrors);
        setRunState("Исправьте входные данные перед запуском.", "warning", "Запуск не отправлен.");
        nodes["validation-errors"].querySelector("button")?.click();
        return;
      }
      const option = selectedModelOption();
      if (!option?.selectable) {
        setRunState("Выберите доступную модель.", "warning", "Запуск не отправлен.");
        return;
      }
      activeSubmission = {
        ...createRunSubmission(session, {
          modelId: option.modelId,
          reasoningEffort: nodes["reasoning-effort"].value || null,
          idempotencyKey: idempotencyKeyFactory(),
        }),
        ownerSession: session,
      };
    }
    const submission = activeSubmission;
    submitInFlight = true;
    updateRunButton();
    nodes["retry-submit"].hidden = true;
    nodes["retry-read"].hidden = true;
    setRunState("Отправка запуска…", "pending", "Ожидаем подтверждение приёма запуска.");
    const controller = new AbortControllerImpl();
    activeSubmissionAbortController = controller;
    const timeoutId = scheduleImpl(() => controller.abort(), submissionTimeoutMs);
    try {
      const response = await fetchImpl("/v1/atom-lab/runs", {
        method: "POST",
        headers: {
          [ACCESS_HEADER]: accessCode,
          "Content-Type": "application/json",
          "Idempotency-Key": submission.idempotencyKey,
        },
        body: JSON.stringify(submission.body),
        signal: controller.signal,
      });
      if (!response.ok && RETRYABLE_SUBMISSION_STATUSES.has(response.status)) {
        setRunState(
          "Результат отправки неизвестен. Повторите тот же submission безопасно.", "warning",
          "Повторная отправка использует прежний ключ запуска.",
        );
        nodes["retry-submit"].hidden = false;
        return;
      }
      const payload = response.ok
        ? await response.json()
        : await response.json().catch(() => null);
      if (!response.ok) {
        const error = parseAtomLabError(payload);
        const code = error?.code ?? "request_failed";
        admissionErrors = (error?.fieldErrors ?? [])
          .filter(({path}) => admissionErrorAppliesToDraft(path, submission))
          .map(({path, message}) => ({
            path,
            message,
            submission,
            key: `admission:${path}`,
            controlId: path === "model_id"
              ? "model-select"
              : path === "reasoning_effort"
                ? "reasoning-effort"
                : path === "prompt"
                  ? "prompt-editor"
                  : undefined,
          }));
        renderValidation(document, nodes["validation-errors"], session, admissionErrors);
        if (admissionErrors.some(({path}) => path === "prompt")) showInputTab(false);
        setRunState(
          `${code}: ${error?.message ?? safeApiMessage(payload, "Запуск не принят.")} Черновик сохранён.`,
          "error", "Исправьте параметры перед следующей отправкой.",
        );
        activeSubmission = null;
        return;
      }
      const accepted = parseAcceptedRun(payload);
      if (!accepted) {
        setRunState(
          "Некорректный ответ API после отправки. Повторите тот же submission безопасно.", "warning",
          "Подтверждение приёма не получено. Повторная отправка использует прежний ключ запуска.",
        );
        nodes["retry-submit"].hidden = false;
        return;
      }
      admissionErrors = [];
      renderValidation(document, nodes["validation-errors"], session, admissionErrors);
      submission.runId = accepted.run_id;
      if (session === submission.ownerSession) {
        submission.ownerSession.sourceRunId = accepted.run_id;
        renderPresetState();
      }
      submission.runtimeIds = {
        scenario_session_id: accepted.scenario_session_id,
        job_id: accepted.job_id,
        action_run_id: null,
        artifact_id: null,
      };
      submission.detailLoaded = false;
      submission.terminal = false;
      submission.pollStartedAt = nowImpl();
      submission.pollFailureCount = 0;
      displayAcceptedSubmission(submission);
      if (accepted.status === "queued" || accepted.status === "running") {
        setAcceptedRunState(accepted.status);
      } else {
        setRunState("Запуск принят. Загружаем результат…", "pending");
      }
      if (runPollTimer !== null) cancelScheduleImpl(runPollTimer);
      runPollTimer = scheduleImpl(() => {
        runPollTimer = null;
        return pollRun(submission);
      }, 0);
    } catch (error) {
      if (destroyed) return;
      const message = error?.name === "AbortError"
        ? "Результат отправки неизвестен. Повторите тот же submission безопасно."
        : error instanceof Error
          ? `${error.message} Черновик сохранён.`
          : "Сетевая ошибка. Черновик сохранён.";
      setRunState(message, "warning", "Подтверждение приёма не получено.");
      nodes["retry-submit"].hidden = false;
    } finally {
      cancelScheduleImpl(timeoutId);
      if (activeSubmissionAbortController === controller) activeSubmissionAbortController = null;
      submitInFlight = false;
      updateRunButton();
    }
  };

  const updateDraftState = () => {
    if (!session) return;
    nodes["draft-state"].textContent = session.dirty || restoredHistoryDraft
      ? session.prompt === session.baselinePrompt && !restoredHistoryDraft
        ? "Есть несохранённые правки во входных данных."
        : "Есть несохранённые правки."
      : session.presetRef
        ? `Открыта сохранённая версия ${session.presetRef.version}.`
        : "Черновик без изменений.";
    refreshAdmissionValidation();
    updateRunButton();
    if (presetEditorActive || !nodes["presets-panel"].hidden) {
      syncFixedFieldAvailability();
      renderPresetState();
    }
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
      session.arraySummaries = [];
      nodes["input-editor"].replaceChildren();
      renderObject(
        {document, session, rerender: renderEditor},
        nodes["input-editor"],
        session.atom.input_schema,
        [],
        session.payload,
      );
      if (focusId && typeof document.getElementById === "function") {
        focusEditorControl(document, document.getElementById(focusId));
      }
    }
    for (const updateSummary of session.arraySummaries) updateSummary();
    updateDraftState();
  };

  const renderNavigation = () => {
    nodes["atom-navigation"].replaceChildren();
    for (const atom of catalog) {
      const item = button(document, `${atom.atom_id} · ${ATOM_LABELS[atom.atom_id].name}`, () => selectAtom(atom));
      item.setAttribute("aria-current", String(atom.atom_id === selectedAtomId));
      nodes["atom-navigation"].append(item);
    }
  };

  const promptRefFor = (draft) => draft.promptSourceRef ?? draft.atom.prompt_ref;
  const promptUrl = (draft) => `/v1/atom-lab/atoms/${draft.atom.atom_id}/prompts`;
  const validPromptOption = (option) => isRecord(option)
    && Object.hasOwn(PROMPT_GROUPS, option.group)
    && isNonEmptyString(option.ref)
    && isNonEmptyString(option.name)
    && isNonEmptyString(option.prompt)
    && isNullableString(option.source_ref)
    && isNullableString(option.source_run_id);

  const matchesDraftSnapshot = (snapshot) => {
    const model = selectedModelOption()?.modelId;
    if (!model || session.jsonError || session.inputErrors.size > 0) return false;
    return snapshot.atom_id === session.atom.atom_id
      && snapshot.prompt === session.prompt
      && (snapshot.prompt_source_ref ?? session.atom.prompt_ref) === promptRefFor(session)
      && snapshot.model_id === (model.startsWith("openai/") ? model : `openai/${model}`)
      && snapshot.reasoning_effort === (nodes["reasoning-effort"].value || null)
      && sameJsonSemantically(snapshot.input, getDraftPayload(session));
  };

  const matchingPromptTrial = (draft) => draft.promptTrial && matchesDraftSnapshot(draft.promptTrial.snapshot)
    ? draft.promptTrial.runId : null;

  const renderPromptStatus = () => {
    const ref = promptRefFor(session);
    const selected = session.promptOptions?.find((option) => option.ref === ref);
    const edited = session.prompt !== session.basePrompt;
    nodes["run-prompt-ref"].textContent = ref;
    nodes["run-prompt-state"].textContent = edited ? "Изменён вручную" : "";
    nodes["prompt-tab-state"].textContent = edited ? " · изменён" : "";
    nodes["prompt-origin"].textContent = session.promptSourceDetached
      ? "Исторический источник недоступен для текущего контракта. Текст промпта сохранён."
      : selected?.source_ref
        ? `${PROMPT_GROUPS[selected.group]} · Основа: ${selected.source_ref}`
        : PROMPT_GROUPS[selected?.group ?? "platform"];
    const status = matchingPromptTrial(session)
      ? "Пробный запуск завершён. Ответ прошёл контракт."
      : selected?.source_run_id && !edited
        ? "У сохранённого текста есть пробный запуск в истории."
        : session.promptTrial
          ? "Текст или настройки изменились после пробного запуска."
          : "Для текущего текста нет успешного пробного запуска.";
    if (nodes["prompt-test-status"].textContent !== status) nodes["prompt-test-status"].textContent = status;
  };

  const renderPromptOptions = () => {
    const picker = nodes["prompt-select"];
    picker.replaceChildren();
    const options = session.promptOptions ?? [{
      ref: session.atom.prompt_ref, name: session.atom.prompt_ref, group: "platform",
    }];
    for (const [group, label] of Object.entries(PROMPT_GROUPS)) {
      const entries = options.filter((option) => option.group === group);
      if (entries.length === 0) continue;
      const container = document.createElement("optgroup");
      container.label = label;
      for (const entry of entries) {
        const option = document.createElement("option");
        option.value = entry.ref;
        option.textContent = entry.name;
        container.append(option);
      }
      picker.append(container);
    }
    picker.value = promptRefFor(session);
    renderPromptStatus();
  };

  const loadPromptOptions = async () => {
    const draft = session;
    if (!draft || draft.promptOptions || draft.loadingPrompts) return;
    draft.loadingPrompts = true;
    nodes["retry-prompts"].hidden = true;
    nodes["prompt-load-status"].textContent = "Загрузка промптов…";
    try {
      const options = await protectedJson(promptUrl(draft));
      if (!Array.isArray(options) || !options.every(validPromptOption)
        || !options.some((option) => option.ref === draft.atom.prompt_ref)) {
        throw new Error("Список промптов вернул некорректный ответ.");
      }
      draft.promptOptions = options;
      const reconcileSource = draft.promptSourceNeedsValidation;
      if (reconcileSource) {
        draft.promptSourceDetached = !options.some((option) => option.ref === draft.promptSourceRef);
        if (draft.promptSourceDetached) draft.promptSourceRef = null;
        draft.promptSourceNeedsValidation = false;
      }
      draft.basePrompt = options.find((option) => option.ref === promptRefFor(draft))?.prompt
        ?? draft.basePrompt;
      if (session !== draft) return;
      renderPromptOptions();
      nodes["save-prompt"].disabled = Boolean(draft.savingPrompt);
      nodes["prompt-load-status"].textContent = "";
      if (reconcileSource) updateDraftState();
    } catch (error) {
      if (session !== draft) return;
      nodes["prompt-load-status"].textContent = error.message;
      nodes["retry-prompts"].hidden = false;
    } finally {
      draft.loadingPrompts = false;
    }
  };

  const applyPromptOption = (option) => {
    session.promptSourceRef = option.ref === session.atom.prompt_ref ? null : option.ref;
    session.promptSourceDetached = false;
    session.basePrompt = option.prompt;
    session.baselinePrompt = option.prompt;
    session.prompt = option.prompt;
    nodes["prompt-editor"].value = session.prompt;
    updateDraftState();
  };

  const selectAtom = (atom, {force = false, preservePreset = false} = {}) => {
    if (!force && hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    if (session) clearValidationPresentation(document, nodes["validation-errors"], session);
    selectedAtomId = atom.atom_id;
    session = createDraftSession(atom);
    restoredHistoryDraft = false;
    admissionErrors = [];
    const atomCode = document.createElement("span");
    atomCode.className = "atom-id";
    atomCode.textContent = atom.atom_id;
    const atomName = document.createElement("span");
    atomName.textContent = ATOM_LABELS[atom.atom_id].name;
    nodes["atom-title"].replaceChildren(atomCode, atomName);
    nodes["atom-action-type"].textContent = atom.action_type;
    nodes["atom-description"].textContent = atom.description;
    for (const direction of ["input", "output"]) {
      nodes[`${direction}-contract-label`].textContent = ATOM_LABELS[atom.atom_id][direction];
      nodes[`${direction}-schema-ref`].textContent = atom.schema_refs[direction].schema_ref;
      nodes[`${direction}-schema-version`].textContent = `Версия ${atom.schema_refs[direction].version}`;
      renderContractFields(document, nodes[`${direction}-contract-fields`], atom[`${direction}_schema`]);
    }
    nodes["input-schema"].textContent = JSON.stringify(atom.input_schema, null, 2);
    nodes["output-schema"].textContent = JSON.stringify(atom.output_schema, null, 2);
    nodes["prompt-editor"].value = session.prompt;
    nodes["save-prompt-panel"].open = false;
    nodes["save-prompt-name"].value = "";
    nodes["save-prompt-status"].textContent = "";
    nodes["save-prompt"].disabled = true;
    nodes["prompt-load-status"].textContent = "";
    nodes["retry-prompts"].hidden = true;
    renderPromptOptions();
    if (nodes["prompt-tab"].getAttribute?.("aria-selected") === "true") void loadPromptOptions();
    renderNavigation();
    renderEditor();
    if (!preservePreset) startNewPreset({activate: false});
  };

  const showInputTab = (showInput) => {
    showLibrary();
    nodes["input-panel"].hidden = !showInput;
    nodes["prompt-panel"].hidden = showInput;
    nodes["input-tab"].setAttribute("aria-selected", String(showInput));
    nodes["prompt-tab"].setAttribute("aria-selected", String(!showInput));
    nodes["input-tab"].tabIndex = showInput ? 0 : -1;
    nodes["prompt-tab"].tabIndex = showInput ? -1 : 0;
    if (!showInput) void loadPromptOptions();
  };

  const openCatalog = async () => {
    nodes.status.textContent = "Загрузка каталога…";
    try {
      const response = await fetchImpl("/v1/atom-lab/atoms", {headers: {[ACCESS_HEADER]: accessCode}});
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message ?? "Не удалось открыть каталог.");
      catalog = payload;
      nodes["access-panel"].hidden = true;
      nodes.workspace.hidden = false;
      nodes["atom-count"].textContent = String(catalog.length);
      nodes.status.textContent = "";
      selectAtom(catalog[0]);
      nodes["presets-button"].disabled = false;
      nodes["history-button"].disabled = false;
      nodes["workbench-button"].disabled = false;
      await reloadCurrentModelCatalog();
    } catch (error) {
      accessCode = "";
      nodes["access-panel"].hidden = !accessCodeRequired;
      nodes.workspace.hidden = true;
      nodes["presets-button"].disabled = true;
      nodes["history-button"].disabled = true;
      nodes["workbench-button"].disabled = true;
      nodes.status.textContent = error instanceof Error ? error.message : "Не удалось открыть каталог.";
      if (accessCodeRequired) nodes["access-code"].focus();
    }
  };
  nodes["access-form"].addEventListener("submit", (event) => {
    event.preventDefault();
    accessCode = nodes["access-code"].value;
    nodes["access-code"].value = "";
    return openCatalog();
  });
  nodes["input-tab"].addEventListener("click", () => showInputTab(true));
  nodes["prompt-tab"].addEventListener("click", () => showInputTab(false));
  for (const id of ["input-tab", "prompt-tab"]) {
    nodes[id].addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const showInput = event.key === "Home" || (event.key !== "End" && id === "prompt-tab");
      showInputTab(showInput);
      nodes[showInput ? "input-tab" : "prompt-tab"].focus();
    });
  }
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
  nodes["retry-prompts"].addEventListener("click", loadPromptOptions);
  nodes["prompt-select"].addEventListener("change", () => {
    const ref = nodes["prompt-select"].value;
    const option = session.promptOptions?.find((item) => item.ref === ref);
    if (!option || (session.prompt !== session.baselinePrompt && !confirmImpl(DIRTY_WARNING))) {
      nodes["prompt-select"].value = promptRefFor(session);
      return;
    }
    applyPromptOption(option);
    nodes["save-prompt-status"].textContent = "";
  });
  nodes["save-prompt-form"].addEventListener("submit", async (event) => {
    event.preventDefault();
    const draft = session;
    if (!draft?.promptOptions || draft.savingPrompt) return;
    const name = nodes["save-prompt-name"].value.trim();
    if (!name || !draft.prompt.trim()) {
      nodes["save-prompt-status"].textContent = "Укажите название и текст промпта.";
      return;
    }
    const payload = {
      name, prompt: draft.prompt, source_ref: promptRefFor(draft),
      source_run_id: matchingPromptTrial(draft),
    };
    draft.savingPrompt = true;
    nodes["save-prompt"].disabled = true;
    nodes["save-prompt-status"].textContent = "Сохранение…";
    try {
      const saved = await protectedJson(promptUrl(draft), {method: "POST", body: JSON.stringify(payload)});
      if (!validPromptOption(saved) || saved.group !== "lab") throw unknownWriteOutcome();
      if (session !== draft) return;
      draft.promptOptions.push(saved);
      if (draft.prompt === payload.prompt && promptRefFor(draft) === payload.source_ref) {
        applyPromptOption(saved);
      }
      renderPromptOptions();
      nodes["save-prompt-panel"].open = false;
      nodes["save-prompt-name"].value = "";
      nodes["save-prompt-status"].textContent = `Сохранён промпт «${saved.name}».`;
      nodes["prompt-select"].focus();
    } catch (error) {
      if (session === draft) {
        nodes["save-prompt-status"].textContent = error.message;
        if (error.outcomeUnknown) {
          draft.promptOptions = null;
          void loadPromptOptions();
        }
      }
    } finally {
      draft.savingPrompt = false;
      if (session === draft) nodes["save-prompt"].disabled = !draft.promptOptions;
    }
  });
  nodes["model-select"].addEventListener("change", () => {
    renderModelCatalogWarning();
    renderReasoning();
    if (!nodes["presets-panel"].hidden) renderPresetState();
  });
  nodes["reasoning-effort"].addEventListener("change", () => {
    const option = selectedModelOption();
    nodes["reasoning-effort"].disabled = option?.reasoningMode !== "supported";
    nodes["reasoning-help"].textContent = option ? modelReasonText(option) : "Выберите модель.";
    updateRunButton();
    refreshAdmissionValidation();
    if (!nodes["presets-panel"].hidden) renderPresetState();
  });
  nodes["refresh-models"].addEventListener("click", async () => {
    nodes["refresh-models"].disabled = true;
    const controller = new AbortControllerImpl();
    let timedOut = false;
    activeModelRefreshAbortController = controller;
    const timeoutId = scheduleImpl(() => {
      timedOut = true;
      controller.abort();
    }, catalogRefreshTimeoutMs);
    activeModelRefreshTimeoutId = timeoutId;
    try {
      const response = await fetchImpl("/v1/atom-lab/models/refresh", {
        method: "POST",
        headers: {[ACCESS_HEADER]: accessCode},
        signal: controller.signal,
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(safeApiMessage(payload, "Не удалось запросить обновление."));
      const refresh = parseModelRefresh(payload);
      if (!refresh) throw new Error("Обновление каталога вернуло некорректный ответ.");
      cancelScheduleImpl(timeoutId);
      if (activeModelRefreshAbortController === controller) activeModelRefreshAbortController = null;
      if (activeModelRefreshTimeoutId === timeoutId) activeModelRefreshTimeoutId = null;
      modelCatalogReadGeneration += 1;
      modelCatalogRefreshStatus = refresh.refresh_status;
      modelCatalog = modelCatalog ? {...modelCatalog, ...refresh} : modelCatalog;
      stopModelCatalogPolling();
      if (["pending", "running"].includes(refresh.refresh_status)) {
        nodes["model-catalog-warning"].textContent = "Каталог устарел; обновление запрошено.";
        startModelCatalogPolling();
      } else {
        await reloadCurrentModelCatalog();
      }
    } catch (error) {
      if (error?.name === "AbortError" && (destroyed || paused)) return;
      const message = error instanceof Error
        ? timedOut
          ? "Время ожидания обновления каталога истекло."
          : error.message
        : "Не удалось запросить обновление.";
      showModelCatalogFailure(message);
    } finally {
      cancelScheduleImpl(timeoutId);
      if (activeModelRefreshAbortController === controller) activeModelRefreshAbortController = null;
      if (activeModelRefreshTimeoutId === timeoutId) activeModelRefreshTimeoutId = null;
      if (!destroyed) nodes["refresh-models"].disabled = false;
    }
  });
  nodes["run-button"].addEventListener("click", () => submitRun());
  nodes["retry-submit"].addEventListener("click", () => submitRun({retry: true}));
  nodes["retry-read"].addEventListener("click", () => {
    nodes["retry-read"].hidden = true;
    if (activeSubmission) {
      activeSubmission.pollStartedAt = nowImpl();
      activeSubmission.pollFailureCount = 0;
    }
    pollRun(activeSubmission);
  });
  nodes["fill-example"].addEventListener("click", () => {
    if (hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    replaceWithExample(session);
    renderEditor();
  });
  nodes["reset-prompt"].addEventListener("click", () => {
    if (session.prompt === session.basePrompt) return;
    if (hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    resetPrompt(session);
    nodes["prompt-editor"].value = session.prompt;
    updateDraftState();
  });
  nodes["presets-button"].addEventListener("click", async () => {
    if (!session || presetLibraryLoading || presetOpenInFlight || presetSaveInFlight) return;
    showLibrary("presets");
    setPresetLibraryLoading(true);
    try {
      await loadPresets({merge: presetItems.length > 0});
    } finally {
      setPresetLibraryLoading(false);
      if (presetEditorActive || selectedPresetVersion) {
        syncFixedFieldAvailability();
      }
      renderPresetState();
    }
  });
  nodes["history-button"].addEventListener("click", async () => {
    if (!session) return;
    showLibrary("history");
    nodes["history-context"].textContent = `Все атомы · местное время: ${Intl.DateTimeFormat().resolvedOptions().timeZone}`;
    await loadHistory();
  });
  for (const id of ["close-presets", "close-history", "workbench-button"]) {
    nodes[id].addEventListener("click", () => showLibrary());
  }
  nodes["load-more-presets"].addEventListener("click", () => loadPresets({append: true}));
  nodes["load-more-versions"].addEventListener("click", () => loadMorePresetVersions());
  nodes["load-more-history"].addEventListener("click", () => loadHistory({append: true}));
  nodes["new-preset"].addEventListener("click", () => {
    if (presetLibraryLoading || presetOpenInFlight || presetSaveInFlight || presetSaveOutcomeUnknown) return;
    if (presetHasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    startNewPreset();
    nodes["preset-name"].focus();
  });
  nodes["edit-preset"].addEventListener("click", () => editSelectedPreset());
  nodes["apply-preset"].addEventListener("click", () => editSelectedPreset({openWorkbench: true}));
  nodes["cancel-preset"].addEventListener("click", () => {
    if (presetSaveInFlight || presetSaveOutcomeUnknown) return;
    if (presetHasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    if (selectedPresetVersion) commitPresetVersion(selectedPresetVersion);
    else startNewPreset({activate: false, clearSessionPreset: false});
    renderPresetList();
  });
  nodes["preset-name"].addEventListener("input", renderPresetState);
  nodes["preset-description"].addEventListener("input", renderPresetState);
  nodes["preset-version-select"].addEventListener("change", () => {
    if (!selectedPresetSummary || presetOpenInFlight || presetSaveInFlight) return;
    const nextVersion = Number(nodes["preset-version-select"].value);
    if (presetHasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) {
      nodes["preset-version-select"].value = String(selectedPresetVersion.version);
      return;
    }
    openPreset(selectedPresetSummary, nextVersion, {force: true, refreshVersions: false});
  });
  nodes["save-preset"].addEventListener("click", () => savePreset());
  nodes["save-as-new-preset"].addEventListener("click", () => savePreset({forceNew: true}));
  nodes["adapt-preset"].addEventListener("click", () => {
    if (!presetReadOnly || !selectedPresetVersion || presetOpenInFlight || presetSaveInFlight) return;
    if (hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    const historical = cloneJson(selectedPresetVersion);
    const atom = catalog.find((item) => item.atom_id === historical.atom_id);
    if (!atom || !applyConfigurationToEditor(historical, {adapted: true})) {
      setPresetError("Историческую версию нельзя адаптировать автоматически.");
      return;
    }
    selectedPresetSummary = null;
    selectedPresetVersion = null;
    presetEditorActive = true;
    presetSourceOverride = null;
    setPresetReadOnly(false);
    nodes["preset-name"].value = historical.name;
    nodes["preset-description"].value = historical.description;
    const allowedFields = new Set(Object.keys(atom.input_schema.properties ?? {}));
    renderFixedFields(historical.fixed_fields.filter((field) => allowedFields.has(field)));
    nodes["preset-version-select"].replaceChildren();
    nodes["load-more-versions"].hidden = true;
    clearPresetExport();
    presetDraftBaseline = presetFingerprint({
      ...currentPresetPayload(),
      name: "",
      description: "",
      fixed_fields: [],
    });
    renderPresetList();
    renderPresetState();
  });
  nodes["open-latest-preset"].addEventListener("click", async () => {
    const recovery = conflictLatestPreset;
    if (!recovery || presetOpenInFlight || presetSaveInFlight) return;
    if (hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    presetOpenInFlight = true;
    updatePresetEditorDisabled();
    setPresetError();
    let latestPage;
    try {
      latestPage = await fetchPresetVersions(recovery.summary.preset_id);
    } catch (error) {
      conflictLatestPreset = null;
      setPresetError(error instanceof Error
        ? `Не удалось получить актуальную версию: ${error.message}`
        : "Не удалось получить актуальную версию.");
      return;
    } finally {
      presetOpenInFlight = false;
      updatePresetEditorDisabled();
    }
    const latest = latestPage?.items[0];
    if (!latest || !selectedPresetVersion || latest.version <= selectedPresetVersion.version) {
      conflictLatestPreset = null;
      setPresetError("Сервер не вернул более новую актуальную версию. Обновите библиотеку вручную.");
      updatePresetEditorDisabled();
      return;
    }
    const summary = {
      ...recovery.summary,
      latest_version: latest.version,
      name: latest.name,
      description: latest.description,
      atom_id: latest.atom_id,
      updated_at: latest.created_at,
    };
    presetItems = presetItems.map((item) => item.preset_id === summary.preset_id ? summary : item);
    await openPreset(summary, latest.version, {
      force: true,
      refreshVersions: false,
      versionsPageOverride: latestPage,
    });
  });
  nodes["export-preset"].addEventListener("click", async () => {
    if (!selectedPresetVersion || presetOpenInFlight || presetSaveInFlight) return;
    setPresetError();
    clearPresetExport();
    const generation = presetExportGeneration;
    try {
      const {preset_id: presetId, version} = selectedPresetVersion;
      const parsed = parsePresetExport(
        await protectedJson(`/v1/atom-lab/presets/${encodeURIComponent(presetId)}/versions/${version}/export`),
        presetId,
        version,
      );
      if (!parsed) throw new Error("Экспорт вернул некорректный ответ.");
      if (generation !== presetExportGeneration) return;
      const text = JSON.stringify(parsed, null, 2);
      nodes["preset-export"].textContent = text;
      nodes["preset-export"].hidden = false;
      nodes["preset-export-download"].href = `data:application/json;charset=utf-8,${encodeURIComponent(text)}`;
      nodes["preset-export-download"].download = `atom-lab-${presetId}-v${version}.json`;
      nodes["preset-export-download"].hidden = false;
    } catch (error) {
      if (generation !== presetExportGeneration) return;
      setPresetError(error instanceof Error ? error.message : "Не удалось экспортировать версию.");
    }
  });
  nodes["restore-history"].addEventListener("click", () => {
    if (!selectedHistoryDetail || historyOpenInFlight) return;
    if (hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    const configuration = historyConfiguration(selectedHistoryDetail);
    if (!isRecord(configuration.input) || !isNonEmptyString(configuration.prompt) || !isNonEmptyString(configuration.model_id)) {
      nodes["history-error"].textContent = "Исторический снимок нельзя восстановить автоматически.";
      return;
    }
    const compatible = currentContractMatchesHistory(selectedHistoryDetail);
    const preset = selectedHistoryDetail.snapshot.preset;
    const restoredPresetRef = compatible
      && isRecord(preset) && isNonEmptyString(preset.id) && isPositiveInteger(preset.version)
        ? {preset_id: preset.id, version: preset.version}
        : null;
    if (!applyConfigurationToEditor(configuration, {
      presetRef: restoredPresetRef,
      sourceRunId: compatible ? selectedHistoryDetail.run_id : null,
      restored: true,
      adapted: !compatible,
    })) {
      nodes["history-error"].textContent = "Исторический снимок нельзя восстановить автоматически.";
      return;
    }
    startNewPreset({activate: false});
    session.presetRef = restoredPresetRef;
    showLibrary();
    nodes.status.textContent = compatible
      ? "Снимок восстановлен как черновик. Для запуска нажмите «Запустить атом»."
      : "Снимок явно адаптирован к текущему контракту без ссылки на устаревший пресет.";
  });
  nodes["save-history-preset"].addEventListener("click", () => {
    if (!selectedHistoryDetail || historyOpenInFlight) return;
    if (hasUnsavedDraft() && !confirmImpl(DIRTY_WARNING)) return;
    const configuration = historyConfiguration(selectedHistoryDetail);
    const atom = catalog.find((item) => item.atom_id === configuration.atom_id);
    if (!atom || !isRecord(configuration.input) || !isNonEmptyString(configuration.prompt) || !isNonEmptyString(configuration.model_id)) {
      nodes["history-error"].textContent = "Исторический снимок нельзя сохранить как пресет автоматически.";
      return;
    }
    startNewPreset({fromHistory: {
      atom,
      base_action_config_id: configuration.base_action_config_id,
      schema_refs: cloneJson(configuration.schema_refs),
      input: cloneJson(configuration.input),
      prompt: configuration.prompt,
      prompt_ref: configuration.prompt_ref,
      promptSourceRef: configuration.prompt_source_ref ?? null,
      modelId: configuration.model_id,
      reasoningEffort: configuration.reasoning_effort,
      sourceRunId: selectedHistoryDetail.run_id,
    }, clearSessionPreset: false});
    showLibrary("presets");
    nodes.status.textContent = "Подготовлен пресет из выбранного снимка истории.";
  });

  nodes["collapse-history"].addEventListener("click", () => {
    historyOpenGeneration += 1;
    historyOpenInFlight = false;
    const previousId = selectedHistoryDetail?.run_id;
    selectedHistoryDetail = null;
    renderHistoryList();
    for (const item of nodes["history-list"].querySelectorAll("button")) {
      if (item.dataset.runId === previousId) item.focus();
    }
  });
  const historyTabs = ["result", "request", "diagnostics"];
  for (const [index, tab] of historyTabs.entries()) {
    const control = nodes[`history-${tab}-tab`];
    control.addEventListener("click", () => showHistoryTab(tab));
    control.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? historyTabs.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + historyTabs.length) % historyTabs.length;
      showHistoryTab(historyTabs[next]);
      nodes[`history-${historyTabs[next]}-tab`].focus();
    });
  }

  showInputTab(true);
  const pause = () => {
    paused = true;
    stopModelCatalogPolling({preserveDeadline: !destroyed});
    if (activeModelRefreshTimeoutId !== null) cancelScheduleImpl(activeModelRefreshTimeoutId);
    activeModelRefreshTimeoutId = null;
    activeModelRefreshAbortController?.abort();
    activeModelRefreshAbortController = null;
    if (runPollTimer !== null) cancelScheduleImpl(runPollTimer);
    runPollTimer = null;
    activeRunAbortController?.abort();
    activeRunAbortController = null;
    activeSubmissionAbortController?.abort();
    activeSubmissionAbortController = null;
  };
  const resume = () => {
    if (destroyed || !paused) return undefined;
    paused = false;
    const catalogReload = modelCatalogReloadPending ? reloadCurrentModelCatalog() : null;
    if (["pending", "running"].includes(modelCatalogRefreshStatus)) {
      startModelCatalogPolling();
    }
    let runReload = null;
    if (activeSubmission?.runId && !activeSubmission.terminal) {
      activeSubmission.pollFailureCount = 0;
      runReload = pollRun(activeSubmission);
    }
    if (catalogReload && runReload) return Promise.all([catalogReload, runReload]);
    return catalogReload ?? runReload ?? undefined;
  };
  const handlePageHide = (event) => {
    if (event?.persisted) {
      pause();
      return;
    }
    destroy();
  };
  const handlePageShow = (event) => event?.persisted ? resume() : undefined;
  const handleBeforeUnload = (event) => {
    if (!hasUnsavedDraft()) return undefined;
    event.preventDefault?.();
    event.returnValue = "";
    return "";
  };
  const destroy = () => {
    destroyed = true;
    pause();
    lifecycleTarget.removeEventListener?.("pagehide", handlePageHide);
    lifecycleTarget.removeEventListener?.("pageshow", handlePageShow);
    lifecycleTarget.removeEventListener?.("beforeunload", handleBeforeUnload);
  };
  lifecycleTarget.addEventListener?.("pagehide", handlePageHide);
  lifecycleTarget.addEventListener?.("pageshow", handlePageShow);
  lifecycleTarget.addEventListener?.("beforeunload", handleBeforeUnload);
  if (!accessCodeRequired) void openCatalog();
  return {getSession: () => session, getActiveSubmission: () => activeSubmission, destroy};
}

if (typeof document !== "undefined" && document.querySelector("#access-form")) {
  bootstrapAtomLab({
    document,
    fetchImpl: (...args) => fetch(...args),
    confirmImpl: (message) => globalThis.confirm(message),
  });
}
