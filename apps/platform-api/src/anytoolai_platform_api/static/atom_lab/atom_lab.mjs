const ACCESS_HEADER = "X-Atom-Lab-Access-Code";
const DIRTY_WARNING = "Несохранённые изменения будут потеряны. Продолжить?";
const RUN_POLL_INTERVAL_MS = 250;
const RUN_POLL_MAX_BACKOFF_MS = 4_000;
const RUN_POLL_TIMEOUT_MS = 90_000;
const RETRYABLE_SUBMISSION_STATUSES = new Set([408, 425, 500, 502, 503, 504]);
const TERMINAL_RUN_STATUSES = new Set(["succeeded", "failed", "expired", "cancelled"]);
const RUN_STATUSES = new Set(["queued", "running", ...TERMINAL_RUN_STATUSES]);
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
const PROMPT_REFERENCE_FIELD = ["prompt", "ref"].join("_");

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
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
    && isNonEmptyString(value.atom_id)
    && isNonEmptyString(value.created_at)
    && isNonEmptyString(value.updated_at);
}

function isPresetVersionSummary(value) {
  return isRecord(value)
    && isNonEmptyString(value.preset_id)
    && isPositiveInteger(value.version)
    && isNonEmptyString(value.name)
    && typeof value.description === "string"
    && isNonEmptyString(value.atom_id)
    && isNonEmptyString(value.created_at);
}

function isSchemaReference(value) {
  return isRecord(value)
    && isNonEmptyString(value.schema_ref)
    && isPositiveInteger(value.version);
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
    || !isNonEmptyString(value.atom_id)
    || !isNonEmptyString(value.base_action_config_id)
    || !isRecord(value.schema_refs)
    || !isSchemaReference(value.schema_refs.input)
    || !isSchemaReference(value.schema_refs.output)
    || !isNonEmptyString(value.prompt)
    || !isNonEmptyString(value[PROMPT_REFERENCE_FIELD])
    || !isNonEmptyString(value.model_id)
    || !isNullableReasoningEffort(value.reasoning_effort)
    || !Array.isArray(value.fixed_fields)
    || !value.fixed_fields.every(isNonEmptyString)
    || new Set(value.fixed_fields).size !== value.fixed_fields.length
    || !isRecord(value.example_input)
    || !isNullableString(value.source_run_id)
    || !isNonEmptyString(value.created_at)
  ) return null;
  return value;
}

function parsePage(value, itemParser) {
  if (
    !isRecord(value)
    || !Array.isArray(value.items)
    || !value.items.every(itemParser)
    || !isNullableString(value.next_cursor)
  ) return null;
  return value;
}

export function parsePresetList(value) {
  return parsePage(value, isPresetSummary);
}

export function parsePresetVersionList(value) {
  return parsePage(value, isPresetVersionSummary);
}

function isRunSummary(value) {
  return isRecord(value)
    && isNonEmptyString(value.run_id)
    && RUN_STATUSES.has(value.status)
    && isNonEmptyString(value.atom_id)
    && isNonEmptyString(value.model_id)
    && isNullableString(value.preset_id)
    && (value.preset_version === null || isPositiveInteger(value.preset_version))
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

function renderValidation(document, container, session, admissionErrors = []) {
  clearValidationPresentation(document, container, session);
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
      ? document.getElementById(error.controlId ?? controlIdForKey(error.key ?? error.path))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "type"))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "add"))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "add-item"))
        ?? document.getElementById(controlIdForKey(error.key ?? error.path, "add-key"))
      : null;
    if (control) {
      if (!session.validationAttributes.has(control.id)) {
        session.validationAttributes.set(control.id, {
          ariaInvalid: control.getAttribute?.("aria-invalid") ?? null,
          ariaDescribedBy: control.getAttribute?.("aria-describedby") ?? null,
        });
      }
      control.setAttribute("aria-invalid", "true");
      const descriptions = [control.getAttribute?.("aria-describedby"), errorId].filter(Boolean);
      control.setAttribute("aria-describedby", [...new Set(descriptions)].join(" "));
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
      const valueToAdd = initialValue(schema);
      setDraftPath(session, path, valueToAdd);
      rerender(true, firstControlId(schema, path, valueToAdd));
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
  value.forEach((_item, index) => {
    const row = document.createElement("div");
    row.className = "array-item";
    renderField(context, row, schema.items ?? {}, [...path, index], `Элемент ${index + 1}`, true);
    const removeButton = button(document, `Удалить элемент ${index + 1}`, () => {
      omitDraftPath(session, [...path, index]);
      const nextIndex = Math.min(index, value.length - 1);
      const focusId = value.length > 0
        ? firstControlId(schema.items ?? {}, [...path, nextIndex], value[nextIndex])
        : fieldControlId(path, "add-item");
      rerender(true, focusId);
    });
    row.append(removeButton);
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

function runStatusLabel(status) {
  return {
    queued: "Ожидает запуска",
    running: "Выполняется",
    succeeded: "Завершён",
    failed: "Ошибка",
    expired: "Истёк",
    cancelled: "Отменён",
  }[status] ?? "Неизвестное состояние";
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
    term.textContent = key;
    const description = document.createElement("dd");
    description.textContent = typeof item === "string" ? item : JSON.stringify(item, null, 2);
    list.append(term, description);
  }
  container.append(list);
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
  idempotencyKeyFactory = () => globalThis.crypto?.randomUUID?.()
    ?? `run-${Date.now()}-${Math.random().toString(16).slice(2)}`,
}) {
  const nodes = Object.fromEntries([
    "access-form", "access-code", "access-panel", "workspace", "status", "atom-navigation",
    "atom-title", "atom-action-type", "atom-description", "atom-transformation", "input-schema",
    "output-schema", "input-tab", "prompt-tab", "input-panel", "prompt-panel", "form-mode",
    "json-mode", "input-editor", "json-panel", "json-editor", "json-error", "prompt-editor",
    "fill-example", "reset-prompt", "draft-state", "validation-errors", "presets-button",
    "history-button", "model-select", "reasoning-effort", "reasoning-help",
    "model-catalog-warning", "refresh-models", "run-button", "retry-submit", "retry-read", "run-state",
    "submitted-snapshot", "result-section", "result-readable", "result-json",
    "invalid-response", "invalid-response-code", "invalid-response-raw", "run-metadata",
    "run-diagnostics", "presets-panel", "close-presets", "preset-list", "load-more-presets",
    "preset-name", "preset-description", "fixed-fields", "preset-version-select", "new-preset",
    "load-more-versions",
    "save-preset", "export-preset", "preset-state", "preset-error", "preset-export",
    "preset-export-download",
    "preset-conflict", "open-latest-preset", "save-as-new-preset", "history-panel",
    "close-history", "history-list", "load-more-history", "history-warning", "history-detail",
    "restore-history", "save-history-preset", "history-error",
  ].map((id) => [id, requiredNode(document, `#${id}`)]));
  let accessCode = "";
  let catalog = [];
  let session = null;
  let selectedAtomId = null;
  let modelCatalog = null;
  let modelCatalogRefreshStatus = null;
  let modelCatalogReadGeneration = 0;
  let modelOptions = [];
  let activeSubmission = null;
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
  let historyItems = [];
  let historyCursor = null;
  let selectedHistoryDetail = null;
  let restoredHistoryDraft = false;
  let presetSourceOverride = null;
  let paused = false;
  let destroyed = false;

  const hasUnsavedDraft = () => Boolean(
    session?.dirty
    || restoredHistoryDraft
    || (presetDraftBaseline !== null
      && presetFingerprint(currentPresetPayload()) !== presetDraftBaseline),
  );

  const updateRunButton = () => {
    const option = selectedModelOption();
    const effort = nodes["reasoning-effort"].value;
    const hasValidSelection = Boolean(option?.selectable)
      && (effort === "" || option.allowedEfforts.includes(effort));
    const submissionBlocksNewRun = Boolean(activeSubmission && (
      !activeSubmission.runId || !activeSubmission.terminal
    ));
    nodes["run-button"].disabled = submitInFlight || !hasValidSelection || submissionBlocksNewRun;
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

  const renderReasoning = (preferredEffort = "") => {
    const option = selectedModelOption();
    nodes["reasoning-effort"].replaceChildren();
    const none = document.createElement("option");
    none.value = "";
    none.textContent = "Без запрошенного effort";
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
      nodes["model-select"].append(invalidated);
    }
    const selected = previousRemainsSelectable ? previous : selectionInvalidated ? null : first;
    const selectedModelId = selected?.modelId ?? (selectionInvalidated ? previousModelId : "");
    nodes["model-select"].value = selectedModelId;
    nodes["model-select"].disabled = !first;
    renderModelCatalogWarning(selectionInvalidated);
    renderReasoning(previousModelId && selectedModelId === previousModelId ? previousReasoningEffort : "");
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

  const protectedJson = async (url, options = {}) => {
    const response = await fetchImpl(url, {
      ...options,
      headers: {
        [ACCESS_HEADER]: accessCode,
        ...(options.body === undefined ? {} : {"Content-Type": "application/json"}),
        ...(options.headers ?? {}),
      },
    });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const error = parseAtomLabError(payload);
      const failure = new Error(error?.message ?? safeApiMessage(payload, "Операция не выполнена."));
      failure.code = error?.code ?? "request_failed";
      failure.status = response.status;
      failure.fieldErrors = error?.fieldErrors ?? [];
      throw failure;
    }
    return payload;
  };

  const topLevelFields = () => Object.keys(
    (presetSourceOverride?.atom ?? session?.atom)?.input_schema.properties ?? {},
  );

  const selectedFixedFields = () => [...nodes["fixed-fields"].querySelectorAll("input")]
    .filter((input) => input.checked)
    .map((input) => input.value);

  const renderFixedFields = (fixedFields = []) => {
    nodes["fixed-fields"].replaceChildren();
    const selected = new Set(fixedFields);
    for (const field of topLevelFields()) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = field;
      input.checked = selected.has(field);
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
      base_action_config_id: atom.base_action_config_id,
      schema_refs: cloneJson(atom.schema_refs),
      prompt: source?.prompt ?? session.prompt,
      [PROMPT_REFERENCE_FIELD]: atom[PROMPT_REFERENCE_FIELD],
      model_id: source?.modelId ?? addressedModelId(nodes["model-select"].value),
      reasoning_effort: source?.reasoningEffort ?? (nodes["reasoning-effort"].value || null),
      fixed_fields: selectedFixedFields(),
      example_input: cloneJson(source?.input ?? getDraftPayload(session)),
      source_run_id: source?.sourceRunId ?? session.sourceRunId,
    };
  };

  const presetFingerprint = (payload) => JSON.stringify(payload);

  const renderPresetState = () => {
    if (!session) return;
    const changed = presetDraftBaseline === null
      || presetFingerprint(currentPresetPayload()) !== presetDraftBaseline;
    const source = presetSourceOverride ? "Снимок истории" : selectedPresetVersion
      ? `Пресет ${selectedPresetVersion.preset_id}, версия ${selectedPresetVersion.version}`
      : "Новый пресет";
    nodes["preset-state"].textContent = `${source}. ${changed ? "Есть несохранённый черновик." : "Открыта сохранённая версия."}`;
    nodes["save-preset"].textContent = selectedPresetVersion ? "Сохранить новую версию" : "Сохранить новый";
  };

  const applyModelSelection = (modelId, reasoningEffort) => {
    const raw = modelId.startsWith("openai/") ? modelId.slice("openai/".length) : modelId;
    const option = modelOptions.find((item) => item.modelId === raw || addressedModelId(item.modelId) === modelId);
    const value = option?.modelId ?? raw;
    if (!option) {
      const unavailable = document.createElement("option");
      unavailable.value = value;
      unavailable.textContent = `${modelId} — недоступна`;
      unavailable.disabled = true;
      nodes["model-select"].append(unavailable);
    }
    nodes["model-select"].value = value;
    renderReasoning(reasoningEffort ?? "");
    if (!option) nodes["model-catalog-warning"].textContent = "Сохранённая модель недоступна. Выберите доступную модель перед запуском.";
  };

  const applyConfigurationToEditor = (configuration, {presetRef = null, sourceRunId = null, restored = false} = {}) => {
    const atom = catalog.find((item) => item.atom_id === configuration.atom_id);
    if (!atom) return false;
    selectAtom(atom, {force: true});
    session.payload = cloneJson(configuration.example_input ?? configuration.input);
    session.baselinePayload = restored ? {} : cloneJson(session.payload);
    session.prompt = configuration.prompt;
    session.baselinePrompt = restored ? session.basePrompt : configuration.prompt;
    session.presetRef = presetRef;
    session.sourceRunId = sourceRunId;
    restoredHistoryDraft = restored;
    nodes["prompt-editor"].value = session.prompt;
    applyModelSelection(configuration.model_id, configuration.reasoning_effort);
    renderEditor();
    return true;
  };

  const renderPresetList = () => {
    nodes["preset-list"].replaceChildren();
    for (const preset of presetItems) {
      const item = button(document, preset.name, () => openPreset(preset));
      const metadata = document.createElement("small");
      metadata.textContent = `${preset.atom_id} · v${preset.latest_version} · ${preset.description}`;
      item.append(metadata);
      item.setAttribute("aria-current", String(preset.preset_id === selectedPresetSummary?.preset_id));
      nodes["preset-list"].append(item);
    }
    nodes["load-more-presets"].hidden = presetCursor === null;
  };

  const loadPresets = async ({append = false} = {}) => {
    nodes["preset-error"].textContent = "";
    try {
      const query = append && presetCursor ? `?cursor=${encodeURIComponent(presetCursor)}` : "";
      const parsed = parsePresetList(await protectedJson(`/v1/atom-lab/presets${query}`));
      if (!parsed) throw new Error("Список пресетов вернул некорректный ответ.");
      presetItems = append ? [...presetItems, ...parsed.items] : parsed.items;
      presetCursor = parsed.next_cursor;
      renderPresetList();
    } catch (error) {
      nodes["preset-error"].textContent = error instanceof Error ? error.message : "Не удалось загрузить пресеты.";
    }
  };

  const loadPresetVersion = async (presetId, version) => {
    const parsed = parsePresetVersion(
      await protectedJson(`/v1/atom-lab/presets/${encodeURIComponent(presetId)}/versions/${version}`),
      presetId,
      version,
    );
    if (!parsed) throw new Error("Версия пресета вернула некорректный ответ.");
    selectedPresetVersion = cloneJson(parsed);
    presetSourceOverride = null;
    nodes["preset-name"].value = parsed.name;
    nodes["preset-description"].value = parsed.description;
    applyConfigurationToEditor(parsed, {
      presetRef: {preset_id: presetId, version},
      sourceRunId: parsed.source_run_id,
    });
    renderFixedFields(parsed.fixed_fields);
    presetDraftBaseline = presetFingerprint(currentPresetPayload());
    nodes["preset-version-select"].value = String(version);
    nodes["export-preset"].disabled = false;
    nodes["preset-conflict"].hidden = true;
    nodes["preset-export"].hidden = true;
    renderPresetState();
  };

  const loadPresetVersions = async (presetId, {append = false} = {}) => {
    const query = append && presetVersionsCursor
      ? `?cursor=${encodeURIComponent(presetVersionsCursor)}`
      : "";
    const parsed = parsePresetVersionList(await protectedJson(
      `/v1/atom-lab/presets/${encodeURIComponent(presetId)}/versions${query}`,
    ));
    if (!parsed) throw new Error("Список версий вернул некорректный ответ.");
    presetVersions = append ? [...presetVersions, ...parsed.items] : parsed.items;
    presetVersionsCursor = parsed.next_cursor;
    const selectedValue = nodes["preset-version-select"].value;
    nodes["preset-version-select"].replaceChildren();
    for (const version of presetVersions) {
      const option = document.createElement("option");
      option.value = String(version.version);
      option.textContent = `v${version.version} · ${version.created_at}`;
      nodes["preset-version-select"].append(option);
    }
    if (selectedValue) nodes["preset-version-select"].value = selectedValue;
    nodes["load-more-versions"].hidden = presetVersionsCursor === null;
  };

  const openPreset = async (preset, preferredVersion = preset.latest_version, {force = false} = {}) => {
    if (!force && (session?.dirty || presetDraftBaseline !== null && presetFingerprint(currentPresetPayload()) !== presetDraftBaseline)
      && !confirmImpl(DIRTY_WARNING)) return;
    nodes["preset-error"].textContent = "";
    selectedPresetSummary = preset;
    renderPresetList();
    try {
      await loadPresetVersions(preset.preset_id);
      await loadPresetVersion(preset.preset_id, preferredVersion);
    } catch (error) {
      nodes["preset-error"].textContent = error instanceof Error ? error.message : "Не удалось открыть пресет.";
    }
  };

  const startNewPreset = ({fromHistory = null} = {}) => {
    selectedPresetSummary = null;
    selectedPresetVersion = null;
    presetDraftBaseline = null;
    presetSourceOverride = fromHistory;
    nodes["preset-name"].value = fromHistory ? `Запуск ${fromHistory.sourceRunId}` : "";
    nodes["preset-description"].value = "";
    nodes["preset-version-select"].replaceChildren();
    nodes["load-more-versions"].hidden = true;
    nodes["export-preset"].disabled = true;
    nodes["preset-export"].hidden = true;
    nodes["preset-conflict"].hidden = true;
    renderFixedFields([]);
    renderPresetState();
  };

  const savePreset = async ({forceNew = false} = {}) => {
    nodes["preset-error"].textContent = "";
    const payload = currentPresetPayload();
    const updating = Boolean(selectedPresetVersion) && !forceNew;
    const url = updating
      ? `/v1/atom-lab/presets/${encodeURIComponent(selectedPresetVersion.preset_id)}/versions`
      : "/v1/atom-lab/presets";
    const body = updating ? {...payload, base_version: selectedPresetVersion.version} : payload;
    try {
      const created = await protectedJson(url, {method: "POST", body: JSON.stringify(body)});
      if (!isRecord(created) || !isNonEmptyString(created.preset_id) || !isPositiveInteger(created.version)) {
        throw new Error("Сохранение пресета вернуло некорректный ответ.");
      }
      await loadPresets();
      const summary = presetItems.find((item) => item.preset_id === created.preset_id) ?? {
        preset_id: created.preset_id,
        latest_version: created.version,
        name: payload.name,
        description: payload.description,
        atom_id: payload.atom_id,
      };
      await openPreset(summary, created.version, {force: true});
      nodes["preset-state"].textContent = `Сохранена неизменяемая версия ${created.version}.`;
    } catch (error) {
      if (error?.code === "preset_version_conflict") {
        nodes["preset-conflict"].hidden = false;
        await loadPresets();
      }
      nodes["preset-error"].textContent = `${error instanceof Error ? error.message : "Не удалось сохранить пресет."} Значения черновика сохранены.`;
      renderPresetState();
    }
  };

  const renderHistoryList = () => {
    nodes["history-list"].replaceChildren();
    for (const run of historyItems) {
      const item = button(document, `${run.atom_id} · ${run.status}`, () => openHistoryRun(run.run_id));
      const metadata = document.createElement("small");
      metadata.textContent = `${run.created_at} · ${run.model_id}${run.preset_id ? ` · preset v${run.preset_version}` : ""}`;
      item.append(metadata);
      item.setAttribute("aria-current", String(run.run_id === selectedHistoryDetail?.run_id));
      nodes["history-list"].append(item);
    }
    nodes["load-more-history"].hidden = historyCursor === null;
  };

  const loadHistory = async ({append = false} = {}) => {
    nodes["history-error"].textContent = "";
    try {
      const query = append && historyCursor ? `?cursor=${encodeURIComponent(historyCursor)}` : "";
      const parsed = parseRunList(await protectedJson(`/v1/atom-lab/runs${query}`));
      if (!parsed) throw new Error("История вернула некорректный ответ.");
      historyItems = append ? [...historyItems, ...parsed.items] : parsed.items;
      historyCursor = parsed.next_cursor;
      renderHistoryList();
    } catch (error) {
      nodes["history-error"].textContent = error instanceof Error ? error.message : "Не удалось загрузить историю.";
    }
  };

  const historyConfiguration = (detail) => ({
    atom_id: detail.snapshot.atom_id,
    input: detail.snapshot.input,
    prompt: detail.snapshot.prompt?.content,
    model_id: detail.snapshot.provider?.model_id,
    reasoning_effort: detail.snapshot.provider?.reasoning_effort ?? null,
  });

  const currentContractMatchesHistory = (detail) => {
    const atom = catalog.find((item) => item.atom_id === detail.snapshot.atom_id);
    return Boolean(atom
      && detail.snapshot.schemas?.input?.ref === atom.schema_refs.input.schema_ref
      && detail.snapshot.schemas?.input?.version === atom.schema_refs.input.version
      && detail.snapshot.schemas?.output?.ref === atom.schema_refs.output.schema_ref
      && detail.snapshot.schemas?.output?.version === atom.schema_refs.output.version);
  };

  const openHistoryRun = async (runId) => {
    nodes["history-error"].textContent = "";
    try {
      const parsed = parseRunDetail(await protectedJson(`/v1/atom-lab/runs/${encodeURIComponent(runId)}`), runId);
      if (!parsed) throw new Error("Снимок запуска вернул некорректный ответ.");
      selectedHistoryDetail = cloneJson(parsed);
      renderHistoryList();
      nodes["history-detail"].textContent = JSON.stringify(parsed, null, 2);
      const compatible = currentContractMatchesHistory(parsed);
      const modelId = parsed.snapshot.provider?.model_id;
      const rawModelId = modelId?.startsWith("openai/") ? modelId.slice("openai/".length) : modelId;
      const modelAvailable = modelOptions.some((item) => item.modelId === rawModelId && item.selectable);
      nodes["history-warning"].textContent = !compatible
        ? "Исторический контракт недоступен. Снимок доступен только для чтения; восстановление требует явной адаптации к текущему контракту."
        : !modelAvailable
          ? "Историческая модель недоступна. Снимок можно восстановить, но перед запуском нужно явно выбрать модель."
          : "";
      nodes["restore-history"].textContent = compatible ? "Восстановить настройки" : "Адаптировать к текущему контракту";
      nodes["restore-history"].disabled = false;
      nodes["save-history-preset"].disabled = !compatible;
    } catch (error) {
      nodes["history-error"].textContent = error instanceof Error ? error.message : "Не удалось открыть запуск.";
    }
  };

  const displayAcceptedSubmission = (submission) => {
    nodes["submitted-snapshot"].textContent = JSON.stringify(submission.snapshot, null, 2);
    nodes["run-metadata"].textContent = "";
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
    nodes["run-state"].textContent = runStatusLabel(detail.status);
    const diagnostics = detail.diagnostics ?? {};
    const requestedEffort = diagnostics.requested_reasoning_effort ?? "не запрошен";
    const responseModel = diagnostics.response_model_id ?? "неизвестна";
    const duration = diagnostics.duration_ms === null || diagnostics.duration_ms === undefined
      ? "—"
      : `${diagnostics.duration_ms} мс`;
    nodes["run-metadata"].textContent = [
      `Длительность: ${duration}`,
      `Запрошенная модель: ${diagnostics.requested_model_id ?? activeSubmission.snapshot.model_id}`,
      `Модель в ответе: ${responseModel}`,
      `Запрошенный reasoning: ${requestedEffort}`,
      `Validation attempts: ${diagnostics.validation_attempts ?? 0}`,
      `Transport attempts: ${diagnostics.transport_attempts ?? 0}`,
      `Physical calls: ${diagnostics.physical_calls ?? 0}`,
    ].join("\n");
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
      renderReadableResult(document, nodes["result-readable"], detail.result);
      nodes["result-json"].textContent = JSON.stringify(detail.result, null, 2);
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
      nodes["run-state"].textContent = "Время ожидания в браузере истекло. Backend job не отменён.";
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
        nodes["run-state"].textContent = "Время ожидания в браузере истекло. Backend job не отменён.";
        nodes["retry-read"].hidden = false;
        return;
      }
      if (!response.ok) {
        const retryable = [408, 425, 429, 500, 502, 503, 504].includes(response.status);
        if (retryable) {
          const retryAfterMs = response.status === 429
            ? retryAfterDelayMs(response.headers?.get?.("Retry-After"), nowImpl())
            : null;
          nodes["run-state"].textContent = "Переподключение… Запуск принят; текущее состояние временно неизвестно.";
          scheduleNextPoll(submission, {retryable: true, retryAfterMs});
          return;
        }
        const code = typeof payload?.error?.code === "string" ? payload.error.code : "request_failed";
        nodes["run-state"].textContent = `${code}: ${safeApiMessage(payload, "Не удалось прочитать запуск.")}`;
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
        nodes["run-state"].textContent = "Некорректный ответ API. Запуск сохранён для повторного чтения.";
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
      nodes["run-state"].textContent = "Переподключение… Запуск принят; текущее состояние временно неизвестно.";
      scheduleNextPoll(submission, {retryable: true});
    }
  };

  const submitRun = async ({retry = false} = {}) => {
    if (destroyed || paused || submitInFlight || !session) return;
    const pendingReplay = retry && activeSubmission && !activeSubmission.runId;
    if (!pendingReplay) {
      admissionErrors = [];
      renderValidation(document, nodes["validation-errors"], session, admissionErrors);
      const errors = validateDraft(session);
      if (errors.length > 0) {
        renderValidation(document, nodes["validation-errors"], session, admissionErrors);
        nodes["run-state"].textContent = "Исправьте входные данные перед запуском.";
        return;
      }
      const option = selectedModelOption();
      if (!option?.selectable) {
        nodes["run-state"].textContent = "Выберите доступную модель.";
        return;
      }
      activeSubmission = createRunSubmission(session, {
        modelId: option.modelId,
        reasoningEffort: nodes["reasoning-effort"].value || null,
        idempotencyKey: idempotencyKeyFactory(),
      });
    }
    const submission = activeSubmission;
    submitInFlight = true;
    nodes["run-button"].disabled = true;
    nodes["retry-submit"].hidden = true;
    nodes["retry-read"].hidden = true;
    nodes["run-state"].textContent = "Отправка запуска…";
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
        nodes["run-state"].textContent = "Результат отправки неизвестен. Повторите тот же submission безопасно.";
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
        nodes["run-state"].textContent = `${code}: ${error?.message ?? safeApiMessage(payload, "Запуск не принят.")} Черновик сохранён.`;
        activeSubmission = null;
        return;
      }
      const accepted = parseAcceptedRun(payload);
      if (!accepted) {
        nodes["run-state"].textContent = "Некорректный ответ API после отправки. Повторите тот же submission безопасно.";
        nodes["retry-submit"].hidden = false;
        return;
      }
      admissionErrors = [];
      renderValidation(document, nodes["validation-errors"], session, admissionErrors);
      submission.runId = accepted.run_id;
      session.sourceRunId = accepted.run_id;
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
      nodes["run-state"].textContent = runStatusLabel(accepted.status);
      if (runPollTimer !== null) cancelScheduleImpl(runPollTimer);
      runPollTimer = scheduleImpl(() => {
        runPollTimer = null;
        return pollRun(submission);
      }, 0);
    } catch (error) {
      if (destroyed) return;
      nodes["run-state"].textContent = error?.name === "AbortError"
        ? "Результат отправки неизвестен. Повторите тот же submission безопасно."
        : error instanceof Error
          ? `${error.message} Черновик сохранён.`
          : "Сетевая ошибка. Черновик сохранён.";
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
      ? "Есть несохранённые правки."
      : session.presetRef
        ? `Открыта сохранённая версия ${session.presetRef.version}.`
        : "Черновик без изменений.";
    refreshAdmissionValidation();
    if (!nodes["presets-panel"].hidden) renderPresetState();
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

  const selectAtom = (atom, {force = false} = {}) => {
    if (!force && (session?.dirty || restoredHistoryDraft) && !confirmImpl(DIRTY_WARNING)) return;
    if (session) clearValidationPresentation(document, nodes["validation-errors"], session);
    selectedAtomId = atom.atom_id;
    session = createDraftSession(atom);
    restoredHistoryDraft = false;
    admissionErrors = [];
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
      await reloadCurrentModelCatalog();
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
  nodes["presets-button"].addEventListener("click", async () => {
    if ((session?.dirty || restoredHistoryDraft) && !confirmImpl(DIRTY_WARNING)) return;
    nodes["history-panel"].hidden = true;
    nodes["presets-panel"].hidden = false;
    if (presetItems.length === 0) await loadPresets();
    if (!selectedPresetVersion && !presetSourceOverride) startNewPreset();
  });
  nodes["history-button"].addEventListener("click", async () => {
    if ((session?.dirty || restoredHistoryDraft) && !confirmImpl(DIRTY_WARNING)) return;
    nodes["presets-panel"].hidden = true;
    nodes["history-panel"].hidden = false;
    await loadHistory();
  });
  nodes["close-presets"].addEventListener("click", () => { nodes["presets-panel"].hidden = true; });
  nodes["close-history"].addEventListener("click", () => { nodes["history-panel"].hidden = true; });
  nodes["load-more-presets"].addEventListener("click", () => loadPresets({append: true}));
  nodes["load-more-versions"].addEventListener("click", () => {
    if (!selectedPresetSummary) return;
    loadPresetVersions(selectedPresetSummary.preset_id, {append: true})
      .catch((error) => { nodes["preset-error"].textContent = error.message; });
  });
  nodes["load-more-history"].addEventListener("click", () => loadHistory({append: true}));
  nodes["new-preset"].addEventListener("click", () => {
    if (presetDraftBaseline !== null && presetFingerprint(currentPresetPayload()) !== presetDraftBaseline
      && !confirmImpl(DIRTY_WARNING)) return;
    startNewPreset();
  });
  nodes["preset-name"].addEventListener("input", renderPresetState);
  nodes["preset-description"].addEventListener("input", renderPresetState);
  nodes["preset-version-select"].addEventListener("change", () => {
    if (!selectedPresetSummary) return;
    const nextVersion = Number(nodes["preset-version-select"].value);
    if (selectedPresetVersion
      && presetFingerprint(currentPresetPayload()) !== presetDraftBaseline
      && !confirmImpl(DIRTY_WARNING)) {
      nodes["preset-version-select"].value = String(selectedPresetVersion.version);
      return;
    }
    loadPresetVersion(selectedPresetSummary.preset_id, nextVersion)
      .catch((error) => { nodes["preset-error"].textContent = error.message; });
  });
  nodes["save-preset"].addEventListener("click", () => savePreset());
  nodes["save-as-new-preset"].addEventListener("click", () => savePreset({forceNew: true}));
  nodes["open-latest-preset"].addEventListener("click", async () => {
    const latest = presetItems.find((item) => item.preset_id === selectedPresetVersion?.preset_id);
    if (!latest || !confirmImpl(DIRTY_WARNING)) return;
    await openPreset(latest, latest.latest_version);
  });
  nodes["export-preset"].addEventListener("click", async () => {
    if (!selectedPresetVersion) return;
    nodes["preset-error"].textContent = "";
    try {
      const {preset_id: presetId, version} = selectedPresetVersion;
      const parsed = parsePresetExport(
        await protectedJson(`/v1/atom-lab/presets/${encodeURIComponent(presetId)}/versions/${version}/export`),
        presetId,
        version,
      );
      if (!parsed) throw new Error("Экспорт вернул некорректный ответ.");
      const text = JSON.stringify(parsed, null, 2);
      nodes["preset-export"].textContent = text;
      nodes["preset-export"].hidden = false;
      nodes["preset-export-download"].href = `data:application/json;charset=utf-8,${encodeURIComponent(text)}`;
      nodes["preset-export-download"].download = `atom-lab-${presetId}-v${version}.json`;
      nodes["preset-export-download"].hidden = false;
    } catch (error) {
      nodes["preset-error"].textContent = error instanceof Error ? error.message : "Не удалось экспортировать версию.";
    }
  });
  nodes["restore-history"].addEventListener("click", () => {
    if (!selectedHistoryDetail) return;
    if ((session?.dirty || restoredHistoryDraft) && !confirmImpl(DIRTY_WARNING)) return;
    const configuration = historyConfiguration(selectedHistoryDetail);
    if (!isRecord(configuration.input) || !isNonEmptyString(configuration.prompt) || !isNonEmptyString(configuration.model_id)) {
      nodes["history-error"].textContent = "Исторический снимок нельзя восстановить автоматически.";
      return;
    }
    const preset = selectedHistoryDetail.snapshot.preset;
    applyConfigurationToEditor(configuration, {
      presetRef: isRecord(preset) && isNonEmptyString(preset.id) && isPositiveInteger(preset.version)
        ? {preset_id: preset.id, version: preset.version}
        : null,
      sourceRunId: selectedHistoryDetail.run_id,
      restored: true,
    });
    nodes["history-panel"].hidden = true;
    nodes.status.textContent = "Снимок восстановлен как черновик. Для запуска нажмите «Запустить атом».";
  });
  nodes["save-history-preset"].addEventListener("click", () => {
    if (!selectedHistoryDetail) return;
    const configuration = historyConfiguration(selectedHistoryDetail);
    const atom = catalog.find((item) => item.atom_id === configuration.atom_id);
    if (!atom || !isRecord(configuration.input) || !isNonEmptyString(configuration.prompt) || !isNonEmptyString(configuration.model_id)) {
      nodes["history-error"].textContent = "Исторический снимок нельзя сохранить как пресет автоматически.";
      return;
    }
    startNewPreset({fromHistory: {
      atom,
      input: cloneJson(configuration.input),
      prompt: configuration.prompt,
      modelId: configuration.model_id,
      reasoningEffort: configuration.reasoning_effort,
      sourceRunId: selectedHistoryDetail.run_id,
    }});
    nodes["history-panel"].hidden = true;
    nodes["presets-panel"].hidden = false;
    nodes.status.textContent = "Подготовлен пресет из выбранного снимка истории.";
  });

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
  return {getSession: () => session, getActiveSubmission: () => activeSubmission, destroy};
}

if (typeof document !== "undefined" && document.querySelector("#access-form")) {
  bootstrapAtomLab({
    document,
    fetchImpl: (...args) => fetch(...args),
    confirmImpl: (message) => globalThis.confirm(message),
  });
}
