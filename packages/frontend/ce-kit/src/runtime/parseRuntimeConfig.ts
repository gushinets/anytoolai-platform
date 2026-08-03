import type {
  RuntimeConfig,
  RuntimeFrontend,
  RuntimeQuotaSummary,
  RuntimeRendererHint,
  RuntimeScenario,
} from "./types";

/**
 * Validates and maps the backend's `RuntimeConfigResponse` payload (snake_case) into the
 * client's `RuntimeConfig` shape (camelCase). Returns null for anything that doesn't match,
 * so callers fall back to `invalid_response` instead of trusting arbitrary payload content.
 */
export function parseRuntimeConfig(payload: unknown): RuntimeConfig | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }

  const {
    product_id: productId,
    frontend_ids: frontendIds,
    frontends,
    scenario_ids: scenarioIds,
    scenarios,
    quota_summary: quotaSummary,
    allowed_ui_capabilities: allowedUiCapabilities,
  } = payload as Record<string, unknown>;

  if (
    typeof productId !== "string" ||
    !_isStringArray(frontendIds) ||
    !Array.isArray(frontends) ||
    !_isStringArray(scenarioIds) ||
    !Array.isArray(scenarios) ||
    !_isStringArray(allowedUiCapabilities)
  ) {
    return null;
  }

  const parsedFrontends: RuntimeFrontend[] = [];
  for (const frontend of frontends) {
    const parsed = _parseFrontend(frontend);
    if (!parsed) {
      return null;
    }
    parsedFrontends.push(parsed);
  }

  const parsedScenarios: RuntimeScenario[] = [];
  for (const scenario of scenarios) {
    const parsed = _parseScenario(scenario);
    if (!parsed) {
      return null;
    }
    parsedScenarios.push(parsed);
  }

  let parsedQuotaSummary: RuntimeQuotaSummary | null = null;
  if (quotaSummary !== null && quotaSummary !== undefined) {
    parsedQuotaSummary = _parseQuotaSummary(quotaSummary);
    if (!parsedQuotaSummary) {
      return null;
    }
  }

  return {
    productId,
    frontendIds,
    frontends: parsedFrontends,
    scenarioIds,
    scenarios: parsedScenarios,
    quotaSummary: parsedQuotaSummary,
    allowedUiCapabilities,
  };
}

function _isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function _parseRendererHint(value: unknown): RuntimeRendererHint | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const { renderer, schema_ref: schemaRef, schema_version: schemaVersion } =
    value as Record<string, unknown>;
  if (renderer !== "json_schema" || typeof schemaRef !== "string") {
    return null;
  }
  if (schemaVersion !== null && schemaVersion !== undefined && typeof schemaVersion !== "number") {
    return null;
  }
  return {
    renderer,
    schemaRef,
    schemaVersion: typeof schemaVersion === "number" ? schemaVersion : null,
  };
}

function _parseFrontend(value: unknown): RuntimeFrontend | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const { frontend_id: frontendId, type, enabled } = value as Record<string, unknown>;
  if (typeof frontendId !== "string" || typeof type !== "string" || typeof enabled !== "boolean") {
    return null;
  }
  return { frontendId, type, enabled };
}

function _parseScenario(value: unknown): RuntimeScenario | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const {
    scenario_id: scenarioId,
    version,
    allowed_next_actions: allowedNextActions,
    input_renderer_hint: inputRendererHint,
    output_renderer_hint: outputRendererHint,
  } = value as Record<string, unknown>;
  if (
    typeof scenarioId !== "string" ||
    typeof version !== "number" ||
    !_isStringArray(allowedNextActions)
  ) {
    return null;
  }

  const parsedInputHint = _parseRendererHint(inputRendererHint);
  const parsedOutputHint = _parseRendererHint(outputRendererHint);
  if (!parsedInputHint || !parsedOutputHint) {
    return null;
  }

  return {
    scenarioId,
    version,
    allowedNextActions,
    inputRendererHint: parsedInputHint,
    outputRendererHint: parsedOutputHint,
  };
}

function _parseQuotaSummary(value: unknown): RuntimeQuotaSummary | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const {
    quota_policy_id: quotaPolicyId,
    unit,
    limit_count: limitCount,
    period,
    dimension,
  } = value as Record<string, unknown>;
  if (
    typeof quotaPolicyId !== "string" ||
    typeof unit !== "string" ||
    typeof limitCount !== "number" ||
    typeof period !== "string" ||
    typeof dimension !== "string"
  ) {
    return null;
  }
  return { quotaPolicyId, unit, limitCount, period, dimension };
}
