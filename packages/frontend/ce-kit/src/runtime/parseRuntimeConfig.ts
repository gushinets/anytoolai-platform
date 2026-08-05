import type { AssertExactSchemaShape } from "../api/driftAssertions";
import type { components } from "../api/generated/platformApi";
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
  if (!_isRecord(payload)) {
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
  } = payload;

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
  if (!_sameIds(frontendIds, parsedFrontends.map((frontend) => frontend.frontendId))) {
    return null;
  }

  const parsedScenarios: RuntimeScenario[] = [];
  for (const scenario of scenarios) {
    const parsed = _parseScenario(scenario);
    if (!parsed) {
      return null;
    }
    parsedScenarios.push(parsed);
  }
  if (!_sameIds(scenarioIds, parsedScenarios.map((scenario) => scenario.scenarioId))) {
    return null;
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

function _isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function _isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/** Guards against the id list and the entry list (e.g. frontend_ids vs. frontends) desyncing. */
function _sameIds(ids: string[], entryIds: string[]): boolean {
  if (ids.length !== entryIds.length) {
    return false;
  }
  const idSet = new Set(ids);
  const entrySet = new Set(entryIds);
  return (
    idSet.size === ids.length &&
    entrySet.size === entryIds.length &&
    entryIds.every((entryId) => idSet.has(entryId))
  );
}

function _parseRendererHint(value: unknown): RuntimeRendererHint | null {
  if (!_isRecord(value)) {
    return null;
  }
  const { renderer, schema_ref: schemaRef, schema_version: schemaVersion } = value;
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
  if (!_isRecord(value)) {
    return null;
  }
  const { frontend_id: frontendId, type, enabled } = value;
  if (typeof frontendId !== "string" || typeof type !== "string" || typeof enabled !== "boolean") {
    return null;
  }
  return { frontendId, type, enabled };
}

function _parseScenario(value: unknown): RuntimeScenario | null {
  if (!_isRecord(value)) {
    return null;
  }
  const {
    scenario_id: scenarioId,
    version,
    allowed_next_actions: allowedNextActions,
    input_renderer_hint: inputRendererHint,
    output_renderer_hint: outputRendererHint,
  } = value;
  // `allowed_next_actions` is optional on the wire (RuntimeScenarioResponse) -- both an absent key
  // and an explicit `null` mean "no next actions", not "malformed payload".
  const allowedNextActionsMissing = allowedNextActions === undefined || allowedNextActions === null;
  if (
    typeof scenarioId !== "string" ||
    typeof version !== "number" ||
    (!allowedNextActionsMissing && !_isStringArray(allowedNextActions))
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
    allowedNextActions: allowedNextActionsMissing ? [] : allowedNextActions,
    inputRendererHint: parsedInputHint,
    outputRendererHint: parsedOutputHint,
  };
}

function _parseQuotaSummary(value: unknown): RuntimeQuotaSummary | null {
  if (!_isRecord(value)) {
    return null;
  }
  const {
    quota_policy_id: quotaPolicyId,
    unit,
    limit_count: limitCount,
    period,
    dimension,
  } = value;
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

// Compile-time drift check: fails typecheck if any of these backend response schemas grows,
// loses, retypes, or changes the nullability of a field the parsers above don't know about.
type _RuntimeConfigShapeCheck = AssertExactSchemaShape<
  components["schemas"]["RuntimeConfigResponse"],
  {
    product_id: string;
    frontend_ids: string[];
    frontends: components["schemas"]["RuntimeFrontendResponse"][];
    scenario_ids: string[];
    scenarios: components["schemas"]["RuntimeScenarioResponse"][];
    quota_summary: components["schemas"]["RuntimeQuotaSummaryResponse"] | null;
    allowed_ui_capabilities: string[];
  }
>;
const _assertRuntimeConfigShapeMatchesGenerated: _RuntimeConfigShapeCheck = true;
void _assertRuntimeConfigShapeMatchesGenerated;

type _RuntimeFrontendShapeCheck = AssertExactSchemaShape<
  components["schemas"]["RuntimeFrontendResponse"],
  { frontend_id: string; type: string; enabled: boolean }
>;
const _assertRuntimeFrontendShapeMatchesGenerated: _RuntimeFrontendShapeCheck = true;
void _assertRuntimeFrontendShapeMatchesGenerated;

type _RuntimeScenarioShapeCheck = AssertExactSchemaShape<
  components["schemas"]["RuntimeScenarioResponse"],
  {
    scenario_id: string;
    version: number;
    allowed_next_actions?: string[];
    input_renderer_hint: components["schemas"]["RuntimeRendererHintResponse"];
    output_renderer_hint: components["schemas"]["RuntimeRendererHintResponse"];
  }
>;
const _assertRuntimeScenarioShapeMatchesGenerated: _RuntimeScenarioShapeCheck = true;
void _assertRuntimeScenarioShapeMatchesGenerated;

type _RuntimeRendererHintShapeCheck = AssertExactSchemaShape<
  components["schemas"]["RuntimeRendererHintResponse"],
  { renderer: "json_schema"; schema_ref: string; schema_version?: number | null }
>;
const _assertRuntimeRendererHintShapeMatchesGenerated: _RuntimeRendererHintShapeCheck = true;
void _assertRuntimeRendererHintShapeMatchesGenerated;

type _RuntimeQuotaSummaryShapeCheck = AssertExactSchemaShape<
  components["schemas"]["RuntimeQuotaSummaryResponse"],
  { quota_policy_id: string; unit: string; limit_count: number; period: string; dimension: string }
>;
const _assertRuntimeQuotaSummaryShapeMatchesGenerated: _RuntimeQuotaSummaryShapeCheck = true;
void _assertRuntimeQuotaSummaryShapeMatchesGenerated;
